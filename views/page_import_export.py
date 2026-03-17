# pages/page_import_export.py
# ──────────────────────────────────────────────────────────────
#  Import / Export page
# ──────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd

from page_helpers import hero
import feature_flags as ff


def render(df: pd.DataFrame, save_data, sheet, **_) -> None:
    hero("Import / Export", "Bring in data or download your records", "📤")

    tab_in, tab_out = st.tabs(["📥 Import", "📤 Export"])

    with tab_in:
        _import_tab(df, save_data, sheet)

    with tab_out:
        if ff.export_buttons is not None:
            ff.export_buttons(df)
        st.markdown("---")
        st.markdown("#### ⬇️ Download Current Data")
        _download_buttons(df)


def _import_tab(df: pd.DataFrame, save_data, sheet) -> None:
    from date_utils import normalize_dataframe_dates
    from data_manager import bump_data_version, clean_data

    show_import = (
        not st.session_state.get("merge_complete", False)
        and not st.session_state.get("merge_complete_flagged", False)
    )
    if show_import:
        existing_cols = df.columns.tolist() if not df.empty else None
        if ff.HAS_IMPORT_WORKFLOW:
            ff.import_workflow(existing_columns=existing_cols)
        elif ff.import_button is not None:
            imported = ff.import_button(existing_columns=existing_cols)
            if imported is not None and not imported.empty:
                if "Date" in imported.columns:
                    imported["Date"] = normalize_dataframe_dates(imported, "Date")["Date"]
                st.session_state["pending_import_df"] = imported
                st.session_state["merge_ready"] = True
                st.subheader("📄 Preview")
                st.dataframe(imported, width="stretch", hide_index=True)
    else:
        if st.session_state.get("merge_complete"):
            st.sidebar.success("✅ Last import merged.")

    if st.session_state.get("merge_ready", False):
        if ff.HAS_MERGE:
            ff.perform_merge_if_ready(df, save_data, sheet)
        else:
            pending = st.session_state.get("pending_import_df", pd.DataFrame())
            if not pending.empty:
                try:
                    combined = pd.concat([df, pending], ignore_index=True)
                    combined = clean_data(combined)
                    save_data(combined, sheet)
                    st.cache_data.clear()
                    bump_data_version()
                    st.success("✅ Imported data merged successfully!")
                    for k in ["merge_ready", "pending_import_df"]:
                        st.session_state.pop(k, None)
                    st.session_state["merge_complete_flagged"] = True
                    st.session_state["merge_complete"] = True
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Merge failed: {e}")


def _download_buttons(df: pd.DataFrame) -> None:
    try:
        from data_manager import export_data_bytes
        c1, c2 = st.columns(2)
        with c1:
            data, mime = export_data_bytes(df, "csv")
            if data:
                st.download_button("📄 Download CSV", data, "expenses.csv", mime, width="stretch")
        with c2:
            data, mime = export_data_bytes(df, "xlsx")
            if data:
                st.download_button("📘 Download Excel", data, "expenses.xlsx", mime, width="stretch")
    except (ImportError, AttributeError):
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button("📄 Download CSV", csv_bytes, "expenses.csv", "text/csv", width="stretch")
