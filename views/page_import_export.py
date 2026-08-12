# pages/page_import_export.py
# ──────────────────────────────────────────────────────────────
#  Import / Export page
# ──────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd

from page_helpers import hero, handle_import_merge
import feature_flags as ff


def render(df: pd.DataFrame, save_data, sheet, **_) -> None:
    hero("Import / Export", "Bring in data or download your records", "📤")

    tab_in, tab_out = st.tabs(["📥 Import", "📤 Export"])

    with tab_in:
        handle_import_merge(df, save_data, sheet)

    with tab_out:
        if ff.export_buttons is not None:
            ff.export_buttons(df)
        st.markdown("---")
        st.markdown("#### ⬇️ Download Current Data")
        _download_buttons(df)


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
