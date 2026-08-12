# pages/page_edit.py
# ──────────────────────────────────────────────────────────────
#  Edit & Delete Entries page
# ──────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd

from ui_components import inline_edit_table
from page_helpers import hero, empty_state


def render(df: pd.DataFrame, save_data, sheet, **_) -> None:
    hero("Edit & Delete Entries", "Manage your expense records", "✏️")
    if df.empty:
        empty_state("No data available to edit. Add some expenses first.")
        return
    inline_edit_table(df, save_data, sheet)
