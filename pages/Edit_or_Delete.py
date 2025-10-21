# pages/Edit_or_Delete.py
import streamlit as st
import pandas as pd
from data_manager import init_storage, load_data, save_data
from ui_components import inline_edit_table, theme_css

st.set_page_config(page_title="✏️ Edit or Delete Entries", layout="wide")

# Theme
dark_mode = st.sidebar.checkbox("🌗 Dark mode", value=False)
theme_css(dark_mode)

st.title("✏️ Edit or Delete Entries")

# Load data
sheet = init_storage()
version = st.session_state.get("data_version", 0)
df = load_data(_sheet=sheet, version=version)

if df.empty:
    st.info("No data available to edit.")
else:
    inline_edit_table(df, save_data, sheet)

# Back button
st.sidebar.markdown("---")
if st.sidebar.button("⬅️ Back to Expense Dashboard"):
    st.switch_page("main_dashboard_app.py")

