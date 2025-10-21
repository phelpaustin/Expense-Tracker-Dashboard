# pages/Analytics_and_Trends.py
import streamlit as st
import pandas as pd
from data_manager import init_storage, load_data
from analytics import monthly_trends, category_insights, what_if_simulation
from charts import monthly_spending, stacked_area_chart, multi_year_comparison, calendar_heatmap
from ui_components import theme_css

st.set_page_config(page_title="📊 Analytics Dashboard", layout="wide")

# Theme
dark_mode = st.sidebar.checkbox("🌗 Dark mode", value=False)
theme_css(dark_mode)

st.title("📊 Analytics & Trends")

# Load data
sheet = init_storage()
version = st.session_state.get("data_version", 0)
df = load_data(_sheet=sheet, version=version)

if df.empty:
    st.info("No data available for analytics.")
    st.stop()

st.markdown("### 🔥 Monthly & Yearly Visualizations")

col1, col2 = st.columns(2)
with col1:
    monthly_spending(df)
    calendar_heatmap(df)
with col2:
    stacked_area_chart(df)
    multi_year_comparison(df)

st.markdown("---")
st.header("🧠 Analytical Insights")
monthly_trends(df)
category_insights(df)
what_if_simulation(df)

# Navigation
st.sidebar.markdown("---")
if st.sidebar.button("⬅️ Back to Expense Dashboard"):
    st.switch_page("Main_Dashboard_App.py")
