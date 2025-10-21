# main_dashboard_app.py  (Expense Dashboard - default launch page)
import streamlit as st
import pandas as pd

from config import USE_GOOGLE_SHEETS
from data_manager import init_storage, load_data, save_data
from ui_components import sidebar_add_expense, filter_section, theme_css
from charts import kpi_row, category_pie
from import_export import import_button, export_buttons

st.set_page_config(page_title="💰 Expense Dashboard", layout="wide")

# --- Theme ---
dark_mode = st.sidebar.checkbox("🌗 Dark mode", value=False)
theme_css(dark_mode)

st.title("💰 Expense Dashboard")

# --- Data load ---
sheet = init_storage()
version = st.session_state.get("data_version", 0)
df = load_data(_sheet=sheet, version=version)

# --- Sidebar: Add / Filter ---
sidebar_add_expense(df, lambda d: save_data(d, sheet))
df_filtered = filter_section(df)

# --- Import / Export ---
imported_df = import_button()
if imported_df is not None:
    df = imported_df
    save_data(df, sheet)
    st.rerun()

export_buttons(df_filtered)

# --- KPI Cards ---
st.markdown("## 📈 Overview")
kpi_row(df_filtered)

# --- Year & Month Filters for Viewing Entries ---
st.markdown("### 📅 Expenses by Month")
if not df_filtered.empty:
    df_filtered["Date"] = pd.to_datetime(df_filtered["Date"], errors="coerce")
    df_filtered["Year"] = df_filtered["Date"].dt.year
    years = sorted(df_filtered["Year"].dropna().unique().tolist(), reverse=True)
    selected_year = st.selectbox("Select Year", years)

    months = df_filtered[df_filtered["Year"] == selected_year]["Date"].dt.month.unique()
    months = sorted([m for m in months if pd.notna(m)])
    month_names = ["All"] + [pd.Timestamp(2000, m, 1).strftime("%B") for m in months]
    selected_month = st.selectbox("Select Month", month_names)

    if selected_month != "All":
        month_num = pd.to_datetime(selected_month, format="%B").month
        df_filtered = df_filtered[df_filtered["Date"].dt.month == month_num]

    st.dataframe(df_filtered, use_container_width=True)
else:
    st.info("No expense records available yet.")

# --- Pie Chart ---
st.markdown("## 🥧 Spending Breakdown")
category_pie(df_filtered)

# --- Navigation Buttons ---
st.sidebar.markdown("---")
if st.sidebar.button("➡️ Go to Analytics Page"):
    st.switch_page("pages/Analytics_and_Trends.py")

if st.sidebar.button("✏️ Edit / Delete Entries"):
    st.switch_page("pages/Edit_or_Delete.py")
