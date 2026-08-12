# scanner_store.py
"""
3-stage receipt pipeline storage (crash-resumable).

A receipt physically MOVES between three folders as it progresses; its
current stage is implicit in *which* folder it lives in, so a restart just
re-lists the folders — no separate index, inherently crash-safe.

    Stage 1  uploads      → receipt uploaded, awaiting translation
    Stage 2  translated   → receipt + editable <id>.json, awaiting push
    Stage 3  final        → receipt archived after push to expense table

Storage model: the local ``scanner/`` folders are the working store (so the
pipeline works fully offline); every change is best-effort mirrored to a
``Scanner`` sub-folder inside the shared spreadsheet folder on Google Drive.
``sync_from_drive()`` pulls any Drive-only files into the local mirror so a
fresh machine recovers in-flight work.

Filename scheme:
    receipt file : ``{receipt_id}__{sanitized_original_name}``
    data file    : ``{receipt_id}.json``
"""
from __future__ import annotations

import io
import json
import os
import uuid
from datetime import datetime
from typing import Optional

import streamlit as st

import drive_storage as ds
from config import (
    SessionKeys,
    SCANNER_LOCAL_DIR,
    SCANNER_DRIVE_ROOT,
    SCANNER_STAGE_UPLOAD,
    SCANNER_STAGE_TRANSLATED,
    SCANNER_STAGE_FINAL,
    SCANNER_LOCAL_SUBDIRS,
    SCANNER_DRIVE_SUBFOLDERS,
)

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_SEP = "__"


# ═══════════════════════════════════════════════════════════════
# IDS / FILENAMES
# ═══════════════════════════════════════════════════════════════
def new_receipt_id() -> str:
    return uuid.uuid4().hex[:8]


def _sanitize(name: str) -> str:
    return ds.sanitize_for_filename(name)


def build_receipt_filename(receipt_id: str, original_name: str) -> str:
    ext = os.path.splitext(original_name or "")[1].lower() or ".bin"
    base = _sanitize(os.path.splitext(original_name or "receipt")[0])[:60] or "receipt"
    return f"{receipt_id}{_SEP}{base}{ext}"


def _receipt_id_from_filename(filename: str) -> str:
    return filename.split(_SEP, 1)[0]


def _original_from_filename(filename: str) -> str:
    parts = filename.split(_SEP, 1)
    return parts[1] if len(parts) > 1 else filename


def is_image(filename: str) -> bool:
    return os.path.splitext(filename or "")[1].lower() in _IMAGE_EXTS


def guess_mime(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    return {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".gif": "image/gif", ".pdf": "application/pdf",
    }.get(ext, "application/octet-stream")


# ═══════════════════════════════════════════════════════════════
# LOCAL PATHS
# ═══════════════════════════════════════════════════════════════
def _local_dir(stage: int) -> str:
    path = os.path.join(SCANNER_LOCAL_DIR, SCANNER_LOCAL_SUBDIRS[stage])
    os.makedirs(path, exist_ok=True)
    return path


def _find_receipt_local(stage: int, receipt_id: str) -> Optional[str]:
    """Return the local path of the receipt file for *receipt_id* in *stage*."""
    folder = _local_dir(stage)
    prefix = f"{receipt_id}{_SEP}"
    for name in os.listdir(folder):
        if name.startswith(prefix) and not name.endswith(".json"):
            return os.path.join(folder, name)
    return None


def _json_path(stage: int, receipt_id: str) -> str:
    return os.path.join(_local_dir(stage), f"{receipt_id}.json")


# ═══════════════════════════════════════════════════════════════
# DRIVE FOLDER RESOLUTION (cached in session)
# ═══════════════════════════════════════════════════════════════
def _stage_folder_id(stage: int) -> Optional[str]:
    """Resolve (and cache) the Drive folder id for a pipeline stage."""
    service = ds.get_drive_service()
    if service is None:
        return None

    cache = st.session_state.get(SessionKeys.SCANNER_STAGE_FOLDER_IDS) or {}
    if stage in cache:
        return cache[stage]

    shared = ds.get_shared_folder_id()
    if not shared:
        return None

    root_id = st.session_state.get(SessionKeys.SCANNER_ROOT_FOLDER_ID)
    if not root_id:
        root_id = ds.get_or_create_folder(service, shared, SCANNER_DRIVE_ROOT)
        if not root_id:
            return None
        st.session_state[SessionKeys.SCANNER_ROOT_FOLDER_ID] = root_id

    folder_id = ds.get_or_create_folder(
        service, root_id, SCANNER_DRIVE_SUBFOLDERS[stage]
    )
    if folder_id:
        cache[stage] = folder_id
        st.session_state[SessionKeys.SCANNER_STAGE_FOLDER_IDS] = cache
    return folder_id


# ═══════════════════════════════════════════════════════════════
# DRIVE MIRRORS (best-effort)
# ═══════════════════════════════════════════════════════════════
def _drive_upload(stage: int, filename: str, data: bytes, mime: str) -> None:
    try:
        service = ds.get_drive_service()
        folder_id = _stage_folder_id(stage)
        if service and folder_id:
            ds.upload_bytes(service, folder_id, filename, data, mime)
    except Exception as exc:  # noqa: BLE001
        print(f"[scanner_store] drive upload failed: {exc}")


def _drive_move(filename: str, from_stage: int, to_stage: int) -> None:
    try:
        service = ds.get_drive_service()
        if not service:
            return
        src = _stage_folder_id(from_stage)
        dst = _stage_folder_id(to_stage)
        if not src or not dst:
            return
        found = ds.find_in_folder(service, src, filename)
        if found:
            ds.move_file(service, found["id"], dst, src)
    except Exception as exc:  # noqa: BLE001
        print(f"[scanner_store] drive move failed: {exc}")


def _drive_delete(stage: int, filename: str) -> None:
    try:
        service = ds.get_drive_service()
        folder_id = _stage_folder_id(stage)
        if service and folder_id:
            found = ds.find_in_folder(service, folder_id, filename)
            if found:
                ds.delete_file(service, found["id"])
    except Exception as exc:  # noqa: BLE001
        print(f"[scanner_store] drive delete failed: {exc}")


# ═══════════════════════════════════════════════════════════════
# STAGE 1 — UPLOAD
# ═══════════════════════════════════════════════════════════════
def save_upload(file_bytes: bytes, original_name: str,
                mime_type: Optional[str] = None) -> dict:
    """Store a freshly uploaded receipt in stage 1 (local + Drive)."""
    receipt_id = new_receipt_id()
    filename = build_receipt_filename(receipt_id, original_name)
    mime = mime_type or guess_mime(original_name)

    local_path = os.path.join(_local_dir(SCANNER_STAGE_UPLOAD), filename)
    with open(local_path, "wb") as fh:
        fh.write(file_bytes)

    _drive_upload(SCANNER_STAGE_UPLOAD, filename, file_bytes, mime)

    return {
        "receipt_id": receipt_id,
        "filename": filename,
        "original_name": original_name,
        "local_path": local_path,
        "mime_type": mime,
    }


def list_uploads() -> list:
    """Receipts awaiting translation (stage 1)."""
    folder = _local_dir(SCANNER_STAGE_UPLOAD)
    out = []
    for name in sorted(os.listdir(folder)):
        if name.endswith(".json"):
            continue
        out.append({
            "receipt_id": _receipt_id_from_filename(name),
            "filename": name,
            "original_name": _original_from_filename(name),
            "local_path": os.path.join(folder, name),
        })
    return out


# ═══════════════════════════════════════════════════════════════
# STAGE 2 — TRANSLATE / EDIT
# ═══════════════════════════════════════════════════════════════
def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def translate_promote(receipt_id: str, parsed: dict, provider: str = "") -> bool:
    """
    Move a receipt from stage 1 → stage 2 and write its editable data file.
    """
    src = _find_receipt_local(SCANNER_STAGE_UPLOAD, receipt_id)
    if not src:
        return False
    filename = os.path.basename(src)
    dst = os.path.join(_local_dir(SCANNER_STAGE_TRANSLATED), filename)
    os.replace(src, dst)
    _drive_move(filename, SCANNER_STAGE_UPLOAD, SCANNER_STAGE_TRANSLATED)

    record = {
        "receipt_id": receipt_id,
        "receipt_filename": filename,
        "original_name": _original_from_filename(filename),
        "provider": provider,
        "created_at": _now(),
        "updated_at": _now(),
        "data": parsed or {},
    }
    _write_translation(receipt_id, record)
    return True


def save_translation(receipt_id: str, parsed: dict,
                     provider: Optional[str] = None) -> bool:
    """Overwrite the editable data file for a stage-2 receipt (re-save edits)."""
    record = read_translation(receipt_id) or {
        "receipt_id": receipt_id,
        "receipt_filename": "",
        "original_name": "",
        "created_at": _now(),
    }
    record["data"] = parsed or {}
    record["updated_at"] = _now()
    if provider is not None:
        record["provider"] = provider
    if not record.get("receipt_filename"):
        found = _find_receipt_local(SCANNER_STAGE_TRANSLATED, receipt_id)
        if found:
            record["receipt_filename"] = os.path.basename(found)
            record["original_name"] = _original_from_filename(
                os.path.basename(found)
            )
    _write_translation(receipt_id, record)
    return True


def _write_translation(receipt_id: str, record: dict) -> None:
    path = _json_path(SCANNER_STAGE_TRANSLATED, receipt_id)
    data = json.dumps(record, indent=2, default=str).encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(data)
    _drive_upload(
        SCANNER_STAGE_TRANSLATED, f"{receipt_id}.json", data, "application/json"
    )


def read_translation(receipt_id: str) -> Optional[dict]:
    path = _json_path(SCANNER_STAGE_TRANSLATED, receipt_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return None


def list_translated() -> list:
    """Receipts translated and awaiting edit/push (stage 2)."""
    folder = _local_dir(SCANNER_STAGE_TRANSLATED)
    out = []
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json"):
            continue
        receipt_id = name[:-len(".json")]
        record = read_translation(receipt_id)
        if not record:
            continue
        receipt_path = _find_receipt_local(SCANNER_STAGE_TRANSLATED, receipt_id)
        record["local_path"] = receipt_path
        out.append(record)
    return out


# ═══════════════════════════════════════════════════════════════
# STAGE 3 — ARCHIVE (after push)
# ═══════════════════════════════════════════════════════════════
def push_promote(receipt_id: str) -> bool:
    """
    Move a receipt from stage 2 → stage 3 (final archive) and delete its
    temporary data file. Call this only after the expense rows were saved.
    """
    src = _find_receipt_local(SCANNER_STAGE_TRANSLATED, receipt_id)
    if src:
        filename = os.path.basename(src)
        dst = os.path.join(_local_dir(SCANNER_STAGE_FINAL), filename)
        os.replace(src, dst)
        _drive_move(filename, SCANNER_STAGE_TRANSLATED, SCANNER_STAGE_FINAL)

    json_path = _json_path(SCANNER_STAGE_TRANSLATED, receipt_id)
    if os.path.exists(json_path):
        os.remove(json_path)
    _drive_delete(SCANNER_STAGE_TRANSLATED, f"{receipt_id}.json")
    return True


def list_archive() -> list:
    """Receipts that became expense entries (stage 3)."""
    folder = _local_dir(SCANNER_STAGE_FINAL)
    out = []
    for name in sorted(os.listdir(folder)):
        if name.endswith(".json"):
            continue
        out.append({
            "receipt_id": _receipt_id_from_filename(name),
            "filename": name,
            "original_name": _original_from_filename(name),
            "local_path": os.path.join(folder, name),
        })
    return out


# ═══════════════════════════════════════════════════════════════
# DISCARD / READ BYTES
# ═══════════════════════════════════════════════════════════════
def discard(receipt_id: str, stage: int) -> bool:
    """Remove a receipt (and any data file) from a stage entirely."""
    src = _find_receipt_local(stage, receipt_id)
    if src:
        filename = os.path.basename(src)
        try:
            os.remove(src)
        except OSError:
            pass
        _drive_delete(stage, filename)
    json_path = _json_path(stage, receipt_id)
    if os.path.exists(json_path):
        os.remove(json_path)
        _drive_delete(stage, f"{receipt_id}.json")
    return True


def read_receipt_bytes(stage: int, receipt_id: str) -> Optional[bytes]:
    """Receipt bytes: local first, then Drive fallback."""
    path = _find_receipt_local(stage, receipt_id)
    if path and os.path.exists(path):
        try:
            with open(path, "rb") as fh:
                return fh.read()
        except OSError:
            pass
    # Drive fallback
    try:
        service = ds.get_drive_service()
        folder_id = _stage_folder_id(stage)
        if service and folder_id:
            for f in ds.list_folder(service, folder_id):
                if f["name"].startswith(f"{receipt_id}{_SEP}"):
                    return ds.download_bytes(service, f["id"])
    except Exception:  # noqa: BLE001
        pass
    return None


# ═══════════════════════════════════════════════════════════════
# CROSS-MACHINE RECOVERY
# ═══════════════════════════════════════════════════════════════
def sync_from_drive(force: bool = False) -> None:
    """
    Pull any Drive-only files into the local mirror so in-flight work is
    recovered on a fresh machine. Runs once per session (best-effort).
    """
    if not force and st.session_state.get(SessionKeys.SCANNER_SYNCED):
        return

    service = ds.get_drive_service()
    if service is None or not ds.get_shared_folder_id():
        return

    try:
        for stage in (SCANNER_STAGE_UPLOAD, SCANNER_STAGE_TRANSLATED,
                      SCANNER_STAGE_FINAL):
            folder_id = _stage_folder_id(stage)
            if not folder_id:
                continue
            local_folder = _local_dir(stage)
            existing = set(os.listdir(local_folder))
            for f in ds.list_folder(service, folder_id):
                if f["name"] in existing:
                    continue
                data = ds.download_bytes(service, f["id"])
                if data is not None:
                    with open(os.path.join(local_folder, f["name"]), "wb") as fh:
                        fh.write(data)
        st.session_state[SessionKeys.SCANNER_SYNCED] = True
    except Exception as exc:  # noqa: BLE001
        print(f"[scanner_store] sync_from_drive failed: {exc}")
