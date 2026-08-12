# settings_manager.py
"""
Single source of truth for user-preference persistence.

Historically two modules each owned their own JSON file and load/save helpers:
    * settings_page.py        → data/alert_settings.json
    * notification_manager.py → data/notification_settings.json

This module consolidates that persistence logic in one place. The two JSON
files are kept (same paths) so existing user data is read without any
migration — that is the backward-compatibility guarantee. The original
public functions are re-exported from their old modules, so callers such as
``from settings_page import load_alert_settings`` keep working unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path

# ── On-disk locations (unchanged for backward compatibility) ────────────
ALERT_SETTINGS_FILE = "data/alert_settings.json"
NOTIFICATION_SETTINGS_FILE = "data/notification_settings.json"

# ── Defaults ────────────────────────────────────────────────────────────
ALERT_DEFAULTS: dict = {
    "alerts_enabled": True,
    "threshold_80": True,
    "threshold_90": True,
    "threshold_100": True,
    "predictive_alerts": True,
    "velocity_alerts": True,
    "daily_summary_enabled": False,
    "daily_summary_time": "18:00",
    "weekly_summary_enabled": False,
    "desktop_notifications": False,
}

NOTIFICATION_DEFAULTS: dict = {
    "enable_alerts": True,
    "alert_at_80": True,
    "alert_at_90": True,
    "alert_at_100": True,
    "enable_daily_summary": False,
    "summary_time": "18:00",
}


# ── Generic helpers ─────────────────────────────────────────────────────
def _load(path_str: str, defaults: dict) -> dict:
    """Load a settings file, merging over defaults so new keys are present."""
    path = Path(path_str)
    if path.exists():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            return {**defaults, **stored}
        except Exception:
            pass
    return dict(defaults)


def _save(path_str: str, settings: dict) -> bool:
    """Persist a settings dict to disk. Returns True on success."""
    try:
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        try:
            import data_sync
            data_sync.push(path_str)
        except Exception:  # noqa: BLE001 – sync is best-effort
            pass
        return True
    except Exception:
        return False


# ── Alert settings (formerly settings_page.py) ──────────────────────────
def get_default_alert_settings() -> dict:
    return dict(ALERT_DEFAULTS)


def load_alert_settings() -> dict:
    return _load(ALERT_SETTINGS_FILE, ALERT_DEFAULTS)


def save_alert_settings(settings: dict) -> bool:
    return _save(ALERT_SETTINGS_FILE, settings)


# ── Notification settings (formerly notification_manager.py) ────────────
def get_default_notification_settings() -> dict:
    return dict(NOTIFICATION_DEFAULTS)


def load_notification_settings() -> dict:
    return _load(NOTIFICATION_SETTINGS_FILE, NOTIFICATION_DEFAULTS)


def save_notification_settings(settings: dict) -> bool:
    return _save(NOTIFICATION_SETTINGS_FILE, settings)


# ── Cloud-sync settings (backup snapshot → Drive) ───────────────────────
SYNC_SETTINGS_FILE = "data/sync_settings.json"
SYNC_DEFAULTS: dict = {
    # How often local snapshots are mirrored to Drive on save:
    #   "every_save" | "daily" | "manual"
    "backup_sync_mode": "daily",
    # ISO date of the last successful Drive backup sync (per-machine state).
    "last_backup_sync": None,
}


def load_sync_settings() -> dict:
    return _load(SYNC_SETTINGS_FILE, SYNC_DEFAULTS)


def save_sync_settings(settings: dict) -> bool:
    """
    Persist cloud-sync settings LOCALLY only.

    Unlike the other settings, this is intentionally not pushed to Drive:
    ``last_backup_sync`` is per-machine state, and pushing it on every save
    would create needless Drive writes.
    """
    try:
        path = Path(SYNC_SETTINGS_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False
