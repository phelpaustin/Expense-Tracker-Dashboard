# pages/page_edit.py
# ──────────────────────────────────────────────────────────────
#  Edit & Delete Entries page
# ──────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd

from ui_components import inline_edit_table
from page_helpers import hero


def render(df: pd.DataFrame, save_data, sheet, **_) -> None:
    hero("Edit & Delete Entries", "Manage your expense records", "✏️")
    if df.empty:
        st.info("No data available to edit.")
        return
    inline_edit_table(df, save_data, sheet)
