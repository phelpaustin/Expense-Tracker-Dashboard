# main_dashboard.py
import streamlit as st
import pandas as pd

from config import USE_GOOGLE_SHEETS
from data_manager import init_storage, load_data, save_data
from ui_components import sidebar_add_expense, filter_section, inline_edit_table, theme_css
from charts import (
    kpi_row, category_pie, monthly_spending,
    calendar_heatmap, stacked_area_chart, multi_year_comparison
)
from analytics import monthly_trends, category_insights, what_if_simulation
from import_export import import_button, export_buttons

st.set_page_config(page_title="Expense Dashboard", layout="wide", initial_sidebar_state="expanded")

# Theme toggle (checkbox)
dark_mode = st.sidebar.checkbox("🌗 Dark mode", value=False)
theme_css(dark_mode)

st.title("💰 Expense Dashboard")

# --- Data load ---
sheet = init_storage()
version = st.session_state.get("data_version", 0)
df = load_data(_sheet=sheet, version=version)

# Sidebar: Add / Filters
sidebar_add_expense(df, lambda d: save_data(d, sheet))
df_filtered = filter_section(df)

# Import / Export
imported_df = import_button()
if imported_df is not None:
    # User imported: replace dataset (you can change this behavior)
    df = imported_df
    save_data(df, sheet)
    st.experimental_rerun()

export_buttons(df_filtered)

# Top KPIs
kpi_row(df_filtered)

st.markdown("---")
st.subheader("📊 Insights & Visualizations")

# Layout: 2 columns for main charts
col1, col2 = st.columns(2)
with col1:
    category_pie(df_filtered)
    calendar_heatmap(df_filtered)
with col2:
    monthly_spending(df_filtered)
    stacked_area_chart(df_filtered)

st.markdown("---")
multi_year_comparison(df_filtered)

# Analytics
st.divider()
st.header("🧠 Analytical Insights")
monthly_trends(df_filtered)
category_insights(df_filtered)
what_if_simulation(df_filtered)

# Inline editing (bottom)
st.markdown("---")
inline_edit_table(df_filtered, save_data, sheet)
