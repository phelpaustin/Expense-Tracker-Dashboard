# data_sync.py
"""
Keep the small JSON files under ``data/`` in sync with the SAME shared
Google Drive folder that holds the expense spreadsheet ("Expense Manager"
location).

Design
------
* The spreadsheet's parent folder is the source of truth for sync.
* At app startup, ``pull_all()`` downloads any remote copies into ``data/``
  so a fresh machine / new session converges to the shared state.
* On every save, the owning module calls ``push(path)`` to upload the
  updated file back to the shared folder.
* Everything is best-effort: when Drive is unavailable (no creds, libs
  missing, offline) all calls become silent no-ops and the app keeps
  working purely on local files — exactly as before.

``trips.json`` is intentionally NOT managed here: trips already sync to
dedicated Google Sheets worksheets via ``trips_manager``, so adding a second
mechanism would create two competing sources of truth.
"""
from __future__ import annotations

import logging
import os
from datetime import date

import streamlit as st

from config import (
    SessionKeys,
    PENDING_BILLS_FILE,
)
from settings_manager import (
    ALERT_SETTINGS_FILE,
    NOTIFICATION_SETTINGS_FILE,
)
import drive_storage as ds

log = logging.getLogger("data_sync")


# Files synced to the shared spreadsheet folder.
MANAGED_FILES: list[str] = [
    "data/dropdown_options.json",
    "data/budgets.json",
    "data/income.json",
    "data/accounts.json",
    "data/networth_snapshots.json",
    ALERT_SETTINGS_FILE,
    NOTIFICATION_SETTINGS_FILE,
    PENDING_BILLS_FILE,
]


def register_sheet(sheet) -> None:
    """Record the spreadsheet id so push/pull can locate the shared folder."""
    spreadsheet_id = ds.get_spreadsheet_id(sheet)
    if spreadsheet_id:
        st.session_state[SessionKeys.DRIVE_SPREADSHEET_ID] = spreadsheet_id
        log.info("Data sync: registered spreadsheet id %s", spreadsheet_id)
    else:
        log.info("Data sync: no spreadsheet id available (Drive sync disabled)")


def push(local_path: str) -> bool:
    """Upload one data file to the shared Drive folder (best-effort)."""
    if not st.session_state.get(SessionKeys.DRIVE_SPREADSHEET_ID):
        log.info("Data sync: skip push of %s (no spreadsheet id yet)", local_path)
        return False
    log.info("Data sync: pushing %s to Drive", local_path)
    ok = ds.push_data_file(local_path)
    if ok:
        log.info("Data sync: push OK → %s", local_path)
    else:
        log.warning("Data sync: push FAILED → %s", local_path)
    return ok


def push_backup(local_path: str, force: bool = False) -> bool:
    """
    Mirror one point-in-time snapshot to the Drive 'backups' sub-folder,
    honouring the user's auto-sync mode.

    Modes (from settings): ``every_save`` pushes on every call; ``daily``
    pushes only the first time each day; ``manual`` never auto-pushes. Pass
    ``force=True`` (the "Sync now" button) to bypass the mode gate.
    """
    if not st.session_state.get(SessionKeys.DRIVE_SPREADSHEET_ID):
        return False
    if not force:
        mode = get_backup_sync_mode()
        if mode == "manual":
            return False
        if mode == "daily" and _synced_today():
            return False
    ok = ds.push_backup_file(local_path)
    if ok:
        _mark_synced_now()
        log.info("Data sync: backup pushed → %s", os.path.basename(local_path))
    else:
        log.info("Data sync: backup push skipped/failed → %s",
                 os.path.basename(local_path))
    return ok


def pull_backups() -> int:
    """Download any remote snapshots missing locally. Returns count pulled."""
    if not st.session_state.get(SessionKeys.DRIVE_SPREADSHEET_ID):
        return 0
    n = ds.pull_backups()
    if n:
        log.info("Data sync: pulled %d backup snapshot(s) from Drive", n)
    return n


# ── Auto-sync mode helpers ──────────────────────────────────────────────
def get_backup_sync_mode() -> str:
    try:
        from settings_manager import load_sync_settings
        return load_sync_settings().get("backup_sync_mode", "daily")
    except Exception:  # noqa: BLE001
        return "daily"


def _synced_today() -> bool:
    try:
        from settings_manager import load_sync_settings
        last = load_sync_settings().get("last_backup_sync")
        return bool(last) and str(last).startswith(date.today().isoformat())
    except Exception:  # noqa: BLE001
        return False


def _mark_synced_now() -> None:
    try:
        from settings_manager import load_sync_settings, save_sync_settings
        s = load_sync_settings()
        s["last_backup_sync"] = date.today().isoformat()
        save_sync_settings(s)
    except Exception:  # noqa: BLE001
        pass


def sync_now(df=None, sheet=None) -> dict:
    """
    Force a full sync on demand (the "Sync now" button):
      * push a fresh snapshot of *df* to Drive,
      * upload the managed settings files,
      * pull any remote snapshots missing locally.

    Returns a small status dict. Best-effort — safe no-op when Drive is off.
    """
    result = {"snapshot": False, "managed_pushed": 0, "backups_pulled": 0}
    if sheet is not None:
        register_sheet(sheet)
    if not st.session_state.get(SessionKeys.DRIVE_SPREADSHEET_ID):
        return result

    if df is not None and not getattr(df, "empty", True):
        try:
            from backup_manager import create_backup
            path = create_backup(df, label="manualsync")
            result["snapshot"] = push_backup(path, force=True)
        except Exception as exc:  # noqa: BLE001
            log.warning("sync_now snapshot failed: %s", exc)

    for path in MANAGED_FILES:
        if os.path.exists(path) and ds.push_data_file(path):
            result["managed_pushed"] += 1

    try:
        result["backups_pulled"] = ds.pull_backups()
    except Exception as exc:  # noqa: BLE001
        log.warning("sync_now backup pull failed: %s", exc)

    log.info("Data sync: manual sync complete (%s)", result)
    return result


def pull_all(sheet=None) -> None:
    """
    One-time-per-session pull of all managed files from the shared folder.
    Safe to call on every startup; it no-ops after the first successful run
    and whenever Drive is unavailable.
    """
    if st.session_state.get(SessionKeys.DATA_SYNC_PULLED):
        return

    if sheet is not None and not st.session_state.get(
        SessionKeys.DRIVE_SPREADSHEET_ID
    ):
        register_sheet(sheet)

    if not st.session_state.get(SessionKeys.DRIVE_SPREADSHEET_ID):
        log.info("Data sync: pull skipped (Drive unavailable / no spreadsheet id)")
        return

    log.info("Data sync: pulling %d managed file(s) from Drive", len(MANAGED_FILES))
    pulled = 0
    seeded = 0
    for path in MANAGED_FILES:
        if ds.pull_data_file(path):
            pulled += 1
            log.info("Data sync: pulled %s from Drive", path)
        elif os.path.exists(path):
            # No remote copy yet, but we have it locally → seed Drive with it.
            if ds.push_data_file(path):
                seeded += 1
                log.info("Data sync: seeded %s to Drive (no remote copy existed)",
                         path)
            else:
                log.info("Data sync: could not seed %s to Drive", path)
        else:
            log.info("Data sync: %s has no remote or local copy (skipped)", path)

    log.info("Data sync: pull complete (%d pulled, %d seeded of %d managed file(s))",
             pulled, seeded, len(MANAGED_FILES))

    # Converge the point-in-time backup history too, so the rolling snapshot
    # set survives losing the local machine.
    try:
        pull_backups()
    except Exception as exc:  # noqa: BLE001 - backup pull is best-effort
        log.warning("Data sync: backup pull failed: %s", exc)

    st.session_state[SessionKeys.DATA_SYNC_PULLED] = True
