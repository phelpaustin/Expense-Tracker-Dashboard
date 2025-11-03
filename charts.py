# charts.py
import pandas as pd
import plotly.express as px
import streamlit as st


@st.cache_data(ttl=300)
def grouped_monthly(df):
    df2 = df.copy()
    df2["Date"] = pd.to_datetime(df2["Date"], errors="coerce")
    df2 = df2.dropna(subset=["Date"])
    df2["YearMonth"] = df2["Date"].dt.to_period("M").astype(str)
    agg = (
        df2.groupby("YearMonth")["PricePaid"]
        .sum()
        .reset_index()
        .sort_values("YearMonth")
    )
    return agg


def kpi_row(df):
    if df.empty or "PricePaid" not in df.columns:
        st.info("No data to show KPIs.")
        return

    total_spent = df["PricePaid"].sum()
    avg_tx = df["PricePaid"].mean() if len(df) > 0 else 0
    categories = df["Category"].nunique()
    col1, col2, col3 = st.columns(3)
    col1.markdown(
        f"<div class='kpi-card'><div class='kpi-label'>💰 Total Spent</div><div class='kpi-value'>{total_spent:,.0f} SEK</div></div>",
        unsafe_allow_html=True,
    )
    col2.markdown(
        f"<div class='kpi-card'><div class='kpi-label'>🧾 Avg Transaction</div><div class='kpi-value'>{avg_tx:,.0f} SEK</div></div>",
        unsafe_allow_html=True,
    )
    col3.markdown(
        f"<div class='kpi-card'><div class='kpi-label'>📂 Categories</div><div class='kpi-value'>{categories}</div></div>",
        unsafe_allow_html=True,
    )


def category_pie(df):
    if df.empty:
        st.info("No data available to display.")
        return
    agg = (
        df.groupby("Category")["PricePaid"]
        .sum()
        .reset_index()
        .sort_values("PricePaid", ascending=False)
    )
    fig = px.pie(
        agg,
        names="Category",
        values="PricePaid",
        title="💸 Spending by Category",
        hole=0.3,
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def monthly_spending(df):
    if df.empty:
        st.info("No data available to display.")
        return
    agg = grouped_monthly(df)
    fig = px.line(
        agg,
        x="YearMonth",
        y="PricePaid",
        markers=True,
        title="📈 Monthly Spending Trend",
        labels={"PricePaid": "SEK"},
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def calendar_heatmap(df):
    if df.empty:
        st.info("No data available to display.")
        return
    df2 = df.copy()
    df2["Date"] = pd.to_datetime(df2["Date"], errors="coerce")
    df2 = df2.dropna(subset=["Date"])
    daily = df2.groupby(df2["Date"].dt.date)["PricePaid"].sum().reset_index()
    daily.columns = ["Date", "PricePaid"]
    daily["Date"] = pd.to_datetime(daily["Date"])
    daily["dow"] = daily["Date"].dt.day_name()
    daily["week"] = daily["Date"].dt.isocalendar().week
    fig = px.density_heatmap(
        daily,
        x="week",
        y="dow",
        z="PricePaid",
        title="📆 Spending Heatmap (week vs weekday)",
        color_continuous_scale="Blues",
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def stacked_area_chart(df):
    if df.empty:
        st.info("No data available to display.")
        return
    df2 = df.copy()
    df2["Date"] = pd.to_datetime(df2["Date"], errors="coerce")
    df2 = df2.dropna(subset=["Date"])
    df2["YearMonth"] = df2["Date"].dt.to_period("M").astype(str)
    monthly_cat = (
        df2.groupby(["YearMonth", "Category"])["PricePaid"]
        .sum()
        .reset_index()
        .sort_values("YearMonth")
    )
    fig = px.area(
        monthly_cat,
        x="YearMonth",
        y="PricePaid",
        color="Category",
        title="📊 Monthly Spending by Category (Stacked)",
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def multi_year_comparison(df):
    if df.empty:
        st.info("No data available to display.")
        return
    df2 = df.copy()
    df2["Date"] = pd.to_datetime(df2["Date"], errors="coerce")
    df2 = df2.dropna(subset=["Date"])
    df2["Year"] = df2["Date"].dt.year
    agg = df2.groupby(["Year", "Category"])["PricePaid"].sum().reset_index()
    fig = px.bar(
        agg,
        x="Category",
        y="PricePaid",
        color="Year",
        barmode="group",
        title="📅 Yearly Comparison by Category",
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
