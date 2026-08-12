# drive_storage.py
"""
Receipt file storage for pending bills.

Primary path  : Google Drive — uploads the bill copy into a sub-folder
                (``DRIVE_RECEIPTS_FOLDER_NAME``) created inside the *same*
                Drive folder that already holds the expense spreadsheet
                (the "Expense Manager" location shared with the service
                account).
Fallback path : a local ``receipts/`` folder, used whenever the Drive
                API libraries or credentials are unavailable — mirrors the
                local-CSV fallback used for the expense data itself.

Only a reference to the uploaded file (id + web link) is ever stored in
``data/pending_bills.json`` — never the file bytes.
"""
from __future__ import annotations

import io
import os
import re
import logging
from datetime import date as _date
from typing import Optional

import streamlit as st

from config import (
    CREDENTIALS_FILE,
    RECEIPTS_LOCAL_DIR,
    DRIVE_RECEIPTS_FOLDER_NAME,
    GOOGLE_DRIVE_SCOPE,
)

# Drive API scope (read/write files created by this app).
_DRIVE_SCOPES = [GOOGLE_DRIVE_SCOPE]

log = logging.getLogger("drive_storage")


# ═══════════════════════════════════════════════════════════════
# FILENAME HELPERS
# ═══════════════════════════════════════════════════════════════
def sanitize_for_filename(value: str) -> str:
    """Make an arbitrary string safe to use inside a filename."""
    value = (value or "").strip()
    # Replace path separators and unsafe characters with underscores.
    value = re.sub(r"[^\w\-. ]+", "_", value)
    value = re.sub(r"\s+", "_", value).strip("._")
    return value or "unknown"


def build_receipt_filename(shop: str, bill_date, bill_id: str, original_name: str) -> str:
    """
    Compose a stable receipt filename: ``{shop}_{YYYY-MM-DD}_{bill_id}.{ext}``.

    The original file's extension is preserved (defaults to ``.bin``).
    """
    ext = os.path.splitext(original_name or "")[1].lower() or ".bin"
    if isinstance(bill_date, (_date,)):
        date_str = bill_date.isoformat()
    else:
        date_str = sanitize_for_filename(str(bill_date))[:10] or "nodate"
    return f"{sanitize_for_filename(shop)}_{date_str}_{bill_id}{ext}"


# ═══════════════════════════════════════════════════════════════
# GOOGLE DRIVE
# ═══════════════════════════════════════════════════════════════
def _load_user_credentials():
    """
    Load OAuth *user* credentials from the saved token (refreshing if
    needed). These are owned by a real Google account that HAS storage
    quota, unlike a service account. Returns creds or None.
    """
    from config import OAUTH_TOKEN_FILE

    if not os.path.exists(OAUTH_TOKEN_FILE):
        return None
    try:
        from google.oauth2.credentials import Credentials as UserCredentials
        from google.auth.transport.requests import Request

        creds = UserCredentials.from_authorized_user_file(
            OAUTH_TOKEN_FILE, _DRIVE_SCOPES
        )
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(OAUTH_TOKEN_FILE, "w") as fh:
                fh.write(creds.to_json())
            log.info("Drive: refreshed OAuth user token")
        if creds and creds.valid:
            log.info("Drive: using OAuth user credentials (token.json)")
            return creds
        return None
    except Exception as exc:  # noqa: BLE001
        log.warning("Drive: could not load OAuth user token: %s", exc)
        return None


def _load_service_account_credentials():
    """Load service-account credentials (read/edit only; cannot own files)."""
    if not os.path.exists(CREDENTIALS_FILE):
        return None
    try:
        from google.oauth2.service_account import Credentials

        log.info("Drive: using service-account credentials (no storage quota)")
        return Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=_DRIVE_SCOPES
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Drive: service-account credentials failed: %s", exc)
        return None


@st.cache_resource(show_spinner=False)
def _get_drive_service():
    """
    Build (and cache) a Google Drive v3 service.

    Prefers OAuth *user* credentials (``token.json``) because a service
    account has no Drive storage quota and cannot create files in a
    personal My Drive folder. Falls back to the service account (fine for
    reading/editing existing files). Returns None if nothing is available.
    """
    try:
        from googleapiclient.discovery import build
    except ImportError:
        return None

    creds = _load_user_credentials() or _load_service_account_credentials()
    if creds is None:
        return None

    try:
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception as exc:  # noqa: BLE001
        log.warning("Drive service init failed: %s", exc)
        return None


# ── Session write-guard (stops retrying after a fatal quota error) ──
def drive_writes_disabled() -> bool:
    """True if Drive writes were disabled this session (e.g. quota error)."""
    from config import SessionKeys
    try:
        return bool(st.session_state.get(SessionKeys.DRIVE_WRITE_DISABLED))
    except Exception:  # noqa: BLE001
        return False


def _note_write_error(exc: Exception) -> None:
    """
    If *exc* is a non-recoverable write error (service-account quota),
    disable Drive writes for the rest of the session so we stop retrying.
    """
    from config import SessionKeys

    msg = str(exc)
    if "storageQuotaExceeded" in msg or "do not have storage quota" in msg:
        try:
            already = st.session_state.get(SessionKeys.DRIVE_WRITE_DISABLED)
            st.session_state[SessionKeys.DRIVE_WRITE_DISABLED] = True
        except Exception:  # noqa: BLE001
            already = False
        if not already:
            log.error(
                "Drive: writes disabled for this session — the service "
                "account has no storage quota. Run 'python3 authorize_drive.py' "
                "to log in with a Google account that has Drive space."
            )


def _get_spreadsheet_parent(service, spreadsheet_id: str) -> Optional[str]:
    """Return the id of the Drive folder that contains the spreadsheet."""
    try:
        meta = service.files().get(
            fileId=spreadsheet_id,
            fields="parents",
            supportsAllDrives=True,
        ).execute()
        parents = meta.get("parents") or []
        return parents[0] if parents else None
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not read spreadsheet parent: %s", exc)
        return None


def _get_or_create_receipts_folder(service, parent_id: str) -> Optional[str]:
    """
    Find (or create) the receipts sub-folder inside *parent_id*.
    The resolved id is cached in session_state for the rest of the session.
    """
    from config import SessionKeys

    cached = st.session_state.get(SessionKeys.DRIVE_RECEIPTS_FOLDER_ID)
    if cached:
        return cached

    safe_name = DRIVE_RECEIPTS_FOLDER_NAME.replace("'", "\\'")
    try:
        query = (
            f"name = '{safe_name}' and "
            "mimeType = 'application/vnd.google-apps.folder' and "
            f"'{parent_id}' in parents and trashed = false"
        )
        res = service.files().list(
            q=query,
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files = res.get("files", [])
        if files:
            folder_id = files[0]["id"]
        else:
            folder = service.files().create(
                body={
                    "name": DRIVE_RECEIPTS_FOLDER_NAME,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id],
                },
                fields="id",
                supportsAllDrives=True,
            ).execute()
            folder_id = folder["id"]

        st.session_state[SessionKeys.DRIVE_RECEIPTS_FOLDER_ID] = folder_id
        return folder_id
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not get/create receipts folder: %s", exc)
        return None


def _upload_to_drive(
    spreadsheet_id: str,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
) -> Optional[dict]:
    """Upload to Drive; return {'file_id', 'web_link'} or None on failure."""
    service = _get_drive_service()
    if service is None or not spreadsheet_id:
        return None

    if drive_writes_disabled():
        return None

    parent_id = _get_spreadsheet_parent(service, spreadsheet_id)
    if not parent_id:
        return None

    folder_id = _get_or_create_receipts_folder(service, parent_id)
    if not folder_id:
        return None

    try:
        from googleapiclient.http import MediaIoBaseUpload

        media = MediaIoBaseUpload(
            io.BytesIO(file_bytes),
            mimetype=mime_type or "application/octet-stream",
            resumable=False,
        )
        created = service.files().create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media,
            fields="id, webViewLink",
            supportsAllDrives=True,
        ).execute()
        return {
            "file_id": created.get("id"),
            "web_link": created.get("webViewLink"),
        }
    except Exception as exc:  # noqa: BLE001
        _note_write_error(exc)
        log.warning("Drive upload failed: %s", exc)
        return None


# ═══════════════════════════════════════════════════════════════
# LOCAL FALLBACK
# ═══════════════════════════════════════════════════════════════
def _save_locally(file_bytes: bytes, filename: str) -> Optional[dict]:
    """Save the receipt to the local receipts/ folder. Returns a reference."""
    try:
        os.makedirs(RECEIPTS_LOCAL_DIR, exist_ok=True)
        path = os.path.join(RECEIPTS_LOCAL_DIR, filename)
        with open(path, "wb") as fh:
            fh.write(file_bytes)
        return {"file_id": None, "web_link": None, "local_path": path}
    except Exception as exc:  # noqa: BLE001
        log.warning("Local receipt save failed: %s", exc)
        return None


# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════
def store_receipt(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    spreadsheet_id: Optional[str] = None,
) -> dict:
    """
    Store a receipt, preferring Google Drive and falling back to local disk.

    Returns a reference dict with keys:
        ``file_id``, ``web_link``, ``local_path``, ``filename``, ``storage``
    ``storage`` is one of ``"drive"``, ``"local"`` or ``"none"``.
    """
    result = {
        "file_id": None,
        "web_link": None,
        "local_path": None,
        "filename": filename,
        "storage": "none",
    }
    if not file_bytes:
        return result

    drive_ref = _upload_to_drive(spreadsheet_id, file_bytes, filename, mime_type)
    if drive_ref:
        result.update(drive_ref)
        result["storage"] = "drive"
        # Keep a local copy too as a safety net.
        local_ref = _save_locally(file_bytes, filename)
        if local_ref:
            result["local_path"] = local_ref["local_path"]
        return result

    local_ref = _save_locally(file_bytes, filename)
    if local_ref:
        result.update(local_ref)
        result["storage"] = "local"
    return result


def get_spreadsheet_id(sheet) -> Optional[str]:
    """Best-effort extraction of the spreadsheet file id from a worksheet."""
    if sheet is None:
        return None
    try:
        return sheet.spreadsheet.id
    except Exception:  # noqa: BLE001
        return None


# Image extensions we can render as inline thumbnails.
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def is_image_receipt(receipt: dict) -> bool:
    """True if the receipt's filename looks like a renderable image."""
    if not receipt:
        return False
    name = receipt.get("filename") or receipt.get("local_path") or ""
    return os.path.splitext(name)[1].lower() in _IMAGE_EXTS


def get_receipt_bytes(receipt: dict) -> Optional[bytes]:
    """
    Return the receipt's raw bytes for inline preview.

    Tries the local copy first (fast, no network), then downloads from
    Google Drive via the stored file id. Returns None if unavailable.
    """
    if not receipt:
        return None

    local_path = receipt.get("local_path")
    if local_path and os.path.exists(local_path):
        try:
            with open(local_path, "rb") as fh:
                return fh.read()
        except Exception:  # noqa: BLE001
            pass

    file_id = receipt.get("file_id")
    if file_id:
        service = _get_drive_service()
        if service is not None:
            try:
                from googleapiclient.http import MediaIoBaseDownload

                request = service.files().get_media(
                    fileId=file_id, supportsAllDrives=True
                )
                buffer = io.BytesIO()
                downloader = MediaIoBaseDownload(buffer, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                return buffer.getvalue()
            except Exception as exc:  # noqa: BLE001
                log.warning("Drive download failed: %s", exc)

    return None


# ═══════════════════════════════════════════════════════════════
# DATA-FILE SYNC (JSON files → shared spreadsheet folder)
# ═══════════════════════════════════════════════════════════════
# These helpers keep the small JSON files under data/ in sync with the
# SAME shared Drive folder that holds the expense spreadsheet, so the app
# state follows the spreadsheet across machines. Files are stored directly
# in that folder (not the receipts sub-folder).

def _get_shared_folder_id(spreadsheet_id: Optional[str]) -> Optional[str]:
    """
    Return (and cache) the id of the Drive folder that holds the
    spreadsheet — the shared "Expense Manager" location.
    """
    from config import SessionKeys

    cached = st.session_state.get(SessionKeys.DRIVE_DATA_FOLDER_ID)
    if cached:
        return cached

    spreadsheet_id = spreadsheet_id or st.session_state.get(
        SessionKeys.DRIVE_SPREADSHEET_ID
    )
    service = _get_drive_service()
    if service is None:
        log.warning("Drive: service unavailable (libs/credentials missing) — "
                    "cannot resolve shared folder")
        return None
    if not spreadsheet_id:
        log.warning("Drive: no spreadsheet id — cannot resolve shared folder")
        return None

    parent = _get_spreadsheet_parent(service, spreadsheet_id)
    if parent:
        st.session_state[SessionKeys.DRIVE_DATA_FOLDER_ID] = parent
        log.info("Drive: shared folder resolved (id=%s) for spreadsheet %s",
                 parent, spreadsheet_id)
    else:
        log.warning("Drive: spreadsheet %s has no parent folder — the service "
                    "account may not have access to the shared folder",
                    spreadsheet_id)
    return parent


def _find_file_in_folder(service, folder_id: str, filename: str) -> Optional[dict]:
    """Return {'id', ...} for a file named *filename* in *folder_id*, else None."""
    safe_name = filename.replace("'", "\\'")
    try:
        res = service.files().list(
            q=(
                f"name = '{safe_name}' and '{folder_id}' in parents "
                "and trashed = false"
            ),
            fields="files(id, name, modifiedTime)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files = res.get("files", [])
        return files[0] if files else None
    except Exception as exc:  # noqa: BLE001
        log.warning("Lookup failed for %s: %s", filename, exc)
        return None


def push_data_file(local_path: str, spreadsheet_id: Optional[str] = None) -> bool:
    """
    Upload (create or update) a local data file into the shared Drive folder.
    Best-effort: returns False silently if Drive is unavailable.
    """
    if not os.path.exists(local_path):
        return False

    if drive_writes_disabled():
        return False

    service = _get_drive_service()
    if service is None:
        log.warning("Drive: push of %s skipped — Drive service unavailable",
                    local_path)
        return False

    folder_id = _get_shared_folder_id(spreadsheet_id)
    if not folder_id:
        log.warning("Drive: push of %s skipped — shared folder not resolved",
                    local_path)
        return False

    filename = os.path.basename(local_path)
    try:
        from googleapiclient.http import MediaIoBaseUpload

        with open(local_path, "rb") as fh:
            data = fh.read()
        media = MediaIoBaseUpload(
            io.BytesIO(data),
            mimetype="application/json",
            resumable=False,
        )
        existing = _find_file_in_folder(service, folder_id, filename)
        if existing:
            service.files().update(
                fileId=existing["id"],
                media_body=media,
                supportsAllDrives=True,
            ).execute()
            log.info("Drive: updated %s in shared folder %s (id=%s)",
                     filename, folder_id, existing["id"])
        else:
            created = service.files().create(
                body={"name": filename, "parents": [folder_id]},
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            ).execute()
            log.info("Drive: created %s in shared folder %s (id=%s)",
                     filename, folder_id, created.get("id"))
        return True
    except Exception as exc:  # noqa: BLE001
        _note_write_error(exc)
        log.error("Drive: data push failed for %s: %s", filename, exc)
        log.warning("Data push failed for %s: %s", filename, exc)
        return False


def pull_data_file(local_path: str, spreadsheet_id: Optional[str] = None) -> bool:
    """
    Download a data file from the shared Drive folder to *local_path*,
    overwriting the local copy. Returns True only if a remote copy existed
    and was written. Best-effort: returns False silently otherwise.
    """
    service = _get_drive_service()
    if service is None:
        return False

    folder_id = _get_shared_folder_id(spreadsheet_id)
    if not folder_id:
        return False

    filename = os.path.basename(local_path)
    existing = _find_file_in_folder(service, folder_id, filename)
    if not existing:
        return False

    try:
        from googleapiclient.http import MediaIoBaseDownload

        request = service.files().get_media(
            fileId=existing["id"], supportsAllDrives=True
        )
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        with open(local_path, "wb") as fh:
            fh.write(buffer.getvalue())
        log.info("Drive: downloaded %s from shared folder %s (id=%s)",
                 filename, folder_id, existing["id"])
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Drive: data pull failed for %s: %s", filename, exc)
        log.warning("Data pull failed for %s: %s", filename, exc)
        return False


# ═══════════════════════════════════════════════════════════════
# GENERIC DRIVE HELPERS (public — used by the scanner pipeline)
# ═══════════════════════════════════════════════════════════════
def get_drive_service():
    """Public accessor for the cached Drive v3 service (or None)."""
    return _get_drive_service()


def get_shared_folder_id(spreadsheet_id: Optional[str] = None) -> Optional[str]:
    """Public accessor for the shared spreadsheet folder id (or None)."""
    return _get_shared_folder_id(spreadsheet_id)


def find_in_folder(service, folder_id: str, filename: str) -> Optional[dict]:
    """Public wrapper around the folder file lookup."""
    return _find_file_in_folder(service, folder_id, filename)


def get_or_create_folder(service, parent_id: str, name: str) -> Optional[str]:
    """Find (or create) a sub-folder *name* under *parent_id*. Returns its id."""
    if service is None or not parent_id:
        return None
    safe_name = name.replace("'", "\\'")
    try:
        res = service.files().list(
            q=(
                f"name = '{safe_name}' and "
                "mimeType = 'application/vnd.google-apps.folder' and "
                f"'{parent_id}' in parents and trashed = false"
            ),
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files = res.get("files", [])
        if files:
            return files[0]["id"]
        folder = service.files().create(
            body={
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            },
            fields="id",
            supportsAllDrives=True,
        ).execute()
        return folder.get("id")
    except Exception as exc:  # noqa: BLE001
        log.warning("get/create folder '%s' failed: %s", name, exc)
        return None


def upload_bytes(service, folder_id: str, filename: str, data: bytes,
                 mime_type: str = "application/octet-stream") -> Optional[str]:
    """Upload (create or update) *data* as *filename* into *folder_id*. Returns file id."""
    if service is None or not folder_id:
        return None
    if drive_writes_disabled():
        return None
    try:
        from googleapiclient.http import MediaIoBaseUpload

        media = MediaIoBaseUpload(
            io.BytesIO(data), mimetype=mime_type or "application/octet-stream",
            resumable=False,
        )
        existing = _find_file_in_folder(service, folder_id, filename)
        if existing:
            updated = service.files().update(
                fileId=existing["id"], media_body=media, supportsAllDrives=True,
            ).execute()
            return existing["id"]
        created = service.files().create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media, fields="id", supportsAllDrives=True,
        ).execute()
        return created.get("id")
    except Exception as exc:  # noqa: BLE001
        _note_write_error(exc)
        log.warning("upload '%s' failed: %s", filename, exc)
        return None


def move_file(service, file_id: str, new_parent_id: str,
              old_parent_id: Optional[str] = None) -> bool:
    """Move a Drive file into *new_parent_id* (removing *old_parent_id*)."""
    if service is None or not file_id or not new_parent_id:
        return False
    try:
        kwargs = dict(
            fileId=file_id,
            addParents=new_parent_id,
            fields="id, parents",
            supportsAllDrives=True,
        )
        if old_parent_id:
            kwargs["removeParents"] = old_parent_id
        service.files().update(**kwargs).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("move file failed: %s", exc)
        return False


def delete_file(service, file_id: str) -> bool:
    """Permanently delete (trash) a Drive file."""
    if service is None or not file_id:
        return False
    try:
        service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("delete file failed: %s", exc)
        return False


def list_folder(service, folder_id: str) -> list:
    """Return [{'id', 'name'}] for non-trashed files directly in *folder_id*."""
    if service is None or not folder_id:
        return []
    try:
        res = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageSize=1000,
        ).execute()
        return res.get("files", [])
    except Exception as exc:  # noqa: BLE001
        log.warning("list folder failed: %s", exc)
        return []


def download_bytes(service, file_id: str) -> Optional[bytes]:
    """Download a Drive file's raw bytes by id."""
    if service is None or not file_id:
        return None
    try:
        from googleapiclient.http import MediaIoBaseDownload

        request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()
    except Exception as exc:  # noqa: BLE001
        log.warning("download failed: %s", exc)
        return None


# ============================================================
# BACKUP HISTORY SYNC (data/backups/ ⇄ Drive "backups" subfolder)
# ============================================================
# Point-in-time snapshots are mirrored into a dedicated sub-folder of the
# shared spreadsheet folder so the rolling history survives losing the local
# machine. Kept separate from MANAGED_FILES because the filenames are dynamic
# (timestamped) rather than a fixed known set.
BACKUPS_SUBFOLDER = "backups"
REMOTE_BACKUPS_MAX = 30  # how many snapshots to retain on Drive


def _get_backups_folder_id(spreadsheet_id: Optional[str] = None) -> Optional[str]:
    """Return (creating if needed) the id of the Drive 'backups' sub-folder."""
    service = _get_drive_service()
    if service is None:
        return None
    shared = _get_shared_folder_id(spreadsheet_id)
    if not shared:
        return None
    return get_or_create_folder(service, shared, BACKUPS_SUBFOLDER)


def _rotate_remote_backups(service, folder_id: str, max_keep: int) -> None:
    """Delete the oldest remote snapshots beyond *max_keep* (timestamp order)."""
    backups = sorted(
        (f for f in list_folder(service, folder_id) if f["name"].endswith(".csv")),
        key=lambda f: f["name"],  # names are timestamped → lexicographic == chrono
    )
    excess = len(backups) - max_keep
    for f in backups[: max(0, excess)]:
        delete_file(service, f["id"])


def push_backup_file(local_path: str, max_keep: int = REMOTE_BACKUPS_MAX,
                     spreadsheet_id: Optional[str] = None) -> bool:
    """
    Upload one backup CSV into the Drive 'backups' sub-folder and rotate old
    remote copies. Best-effort: returns False silently if Drive is unavailable.
    """
    if not local_path or not os.path.exists(local_path):
        return False
    if drive_writes_disabled():
        return False
    service = _get_drive_service()
    folder_id = _get_backups_folder_id(spreadsheet_id)
    if service is None or not folder_id:
        return False
    try:
        with open(local_path, "rb") as fh:
            data = fh.read()
        fid = upload_bytes(
            service, folder_id, os.path.basename(local_path), data,
            mime_type="text/csv",
        )
        if fid is None:
            return False
        _rotate_remote_backups(service, folder_id, max_keep)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("push backup '%s' failed: %s", local_path, exc)
        return False


def pull_backups(local_dir: str = "data/backups",
                 spreadsheet_id: Optional[str] = None) -> int:
    """
    Download any remote snapshots that are missing locally into *local_dir*.
    Returns the number of files downloaded. Best-effort (0 when unavailable).
    """
    service = _get_drive_service()
    folder_id = _get_backups_folder_id(spreadsheet_id)
    if service is None or not folder_id:
        return 0
    try:
        os.makedirs(local_dir, exist_ok=True)
        local_names = set(os.listdir(local_dir))
    except Exception:  # noqa: BLE001
        local_names = set()
    downloaded = 0
    for f in list_folder(service, folder_id):
        name = f["name"]
        if not name.endswith(".csv") or name in local_names:
            continue
        data = download_bytes(service, f["id"])
        if data is None:
            continue
        try:
            with open(os.path.join(local_dir, name), "wb") as fh:
                fh.write(data)
            downloaded += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("write pulled backup '%s' failed: %s", name, exc)
    return downloaded


