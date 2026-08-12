# backup_manager.py
"""
Automatic backup to local/cloud storage with rotation.
"""
import io
import os
import json
import shutil
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from pathlib import Path

from security_utils import sanitize_df_for_export


BACKUP_DIR = Path("data/backups")
MAX_BACKUPS = 10  # Keep last N backups


def create_backup(df: pd.DataFrame, label: str = "auto") -> str:
    """Create a timestamped CSV backup. Returns backup file path."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"expenses_{label}_{timestamp}.csv"
    path = BACKUP_DIR / filename
    df.to_csv(path, index=False)
    _rotate_backups()
    return str(path)


def _rotate_backups():
    """Delete oldest backups if over MAX_BACKUPS."""
    backups = sorted(BACKUP_DIR.glob("*.csv"), key=os.path.getmtime)
    while len(backups) > MAX_BACKUPS:
        backups.pop(0).unlink()
        backups = sorted(BACKUP_DIR.glob("*.csv"), key=os.path.getmtime)


def list_backups() -> list:
    """Return list of backup files with metadata."""
    if not BACKUP_DIR.exists():
        return []
    backups = []
    for f in sorted(BACKUP_DIR.glob("*.csv"), key=os.path.getmtime, reverse=True):
        stat = f.stat()
        backups.append({
            "filename": f.name,
            "path": str(f),
            "size_kb": round(stat.st_size / 1024, 1),
            "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
        })
    return backups


def restore_backup(backup_path: str) -> pd.DataFrame:
    """Restore DataFrame from a backup file."""
    return pd.read_csv(backup_path)


def export_backup_bytes(df: pd.DataFrame) -> bytes:
    """Return CSV as bytes for download button."""
    return sanitize_df_for_export(df).to_csv(index=False).encode("utf-8")


def export_backup_excel(df: pd.DataFrame) -> bytes:
    """Return Excel bytes for download."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sanitize_df_for_export(df).to_excel(writer, index=False, sheet_name="Expenses")
    return output.getvalue()


def backup_settings_ui(df: pd.DataFrame, save_fn, sheet=None):
    """Backup management UI."""
    st.markdown("## 💾 Data Backup")

    # Backup stats
    backups = list_backups()
    col1, col2, col3 = st.columns(3)
    col1.metric("Saved Backups", len(backups))
    col2.metric("Total Rows", len(df))
    col3.metric("Max Retained", MAX_BACKUPS)

    # ── Cloud Sync ─────────────────────────────────────────────────────
    st.markdown("### ☁️ Cloud Sync")
    try:
        from settings_manager import load_sync_settings, save_sync_settings
        import data_sync

        sync_cfg = load_sync_settings()
        mode_labels = {
            "every_save": "Every save",
            "daily": "Once a day",
            "manual": "Manual only",
        }
        modes = list(mode_labels.keys())
        current_mode = sync_cfg.get("backup_sync_mode", "daily")
        sc1, sc2 = st.columns([2, 1])
        with sc1:
            selected = st.selectbox(
                "Auto-sync snapshots to Google Drive",
                modes,
                index=modes.index(current_mode) if current_mode in modes else 1,
                format_func=lambda m: mode_labels[m],
                help="How often local snapshots are mirrored to your shared "
                     "Drive folder. 'Manual only' disables automatic pushes.",
            )
            if selected != current_mode:
                sync_cfg["backup_sync_mode"] = selected
                save_sync_settings(sync_cfg)
                st.toast("Cloud sync mode updated", icon="✅")
        with sc2:
            st.caption(
                f"Last Drive sync:\n\n**{sync_cfg.get('last_backup_sync') or 'never'}**"
            )

        if st.button("☁️ Sync to Drive now", type="primary", width="stretch"):
            with st.spinner("Syncing to Google Drive…"):
                res = data_sync.sync_now(df, sheet)
            if res.get("snapshot") or res.get("managed_pushed") or res.get("backups_pulled"):
                st.success(
                    f"✅ Synced — snapshot pushed: {res['snapshot']}, "
                    f"settings files: {res['managed_pushed']}, "
                    f"backups pulled: {res['backups_pulled']}."
                )
                st.rerun()
            else:
                st.warning("Drive sync unavailable or nothing to sync yet.")
    except Exception as e:  # noqa: BLE001 – cloud sync is optional
        st.caption(f"Cloud sync unavailable: {e}")

    # Manual backup trigger
    st.markdown("### 📤 Create Backup")
    label = st.text_input("Backup label", value="manual", placeholder="e.g., pre-import, monthly")
    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("💾 Save Local Backup", width="stretch", type="primary"):
            path = create_backup(df, label)
            st.success(f"✅ Backup saved: {Path(path).name}")

    with c2:
        csv_data = export_backup_bytes(df)
        st.download_button(
            "📄 Download CSV",
            data=csv_data,
            file_name=f"expenses_backup_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            width="stretch"
        )

    with c3:
        excel_data = export_backup_excel(df)
        st.download_button(
            "📘 Download Excel",
            data=excel_data,
            file_name=f"expenses_backup_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch"
        )

    # Backup list
    if backups:
        st.markdown("### 📂 Available Backups")
        for b in backups:
            with st.expander(f"📁 {b['filename']} — {b['size_kb']} KB · {b['created']}"):
                c1, c2 = st.columns(2)
                if c1.button("🔄 Restore This Backup", key=f"restore_{b['filename']}"):
                    restored_df = restore_backup(b["path"])
                    save_fn(restored_df, sheet)
                    st.success("✅ Backup restored! Refresh to see changes.")
                    st.rerun()
                if c2.button("🗑️ Delete", key=f"del_backup_{b['filename']}"):
                    Path(b["path"]).unlink(missing_ok=True)
                    st.rerun()
    else:
        st.info("No backups yet. Create your first backup above.")
