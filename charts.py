# charts.py
import pandas as pd
import plotly.express as px
import streamlit as st
from config import (
    Columns, 
    ChartConfig, 
    UIConstants
)


@st.cache_data(ttl=300)
def grouped_monthly(df):
    df2 = df.copy()
    # Use Columns constants instead of magic strings
    df2[Columns.DATE] = pd.to_datetime(df2[Columns.DATE], errors="coerce")
    df2 = df2.dropna(subset=[Columns.DATE])
    df2[Columns.YEAR_MONTH] = df2[Columns.DATE].dt.to_period("M").astype(str)
    agg = (
        df2.groupby(Columns.YEAR_MONTH)[Columns.PRICE_PAID]
        .sum()
        .reset_index()
        .sort_values(Columns.YEAR_MONTH)
    )
    return agg


def kpi_row(df):
    # Use Columns and UIConstants instead of magic strings
    if df.empty or Columns.PRICE_PAID not in df.columns:
        st.info(UIConstants.MSG_NO_DATA)
        return

    total_spent = df[Columns.PRICE_PAID].sum()
    avg_tx = df[Columns.PRICE_PAID].mean() if len(df) > 0 else 0
    categories = df[Columns.CATEGORY].nunique()
    
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
        st.info(UIConstants.MSG_NO_DATA)
        return
    
    # Use Columns constants
    agg = (
        df.groupby(Columns.CATEGORY)[Columns.PRICE_PAID]
        .sum()
        .reset_index()
        .sort_values(Columns.PRICE_PAID, ascending=False)
    )
    
    fig = px.pie(
        agg,
        names=Columns.CATEGORY,
        values=Columns.PRICE_PAID,
        title=ChartConfig.TITLE_SPENDING_BY_CATEGORY,  # Use constant
        hole=ChartConfig.PIE_HOLE_SIZE,  # Use constant
    )
    
    # Use ChartConfig constants
    fig.update_layout(
        showlegend=True,
        margin=ChartConfig.CHART_MARGIN
    )
    st.plotly_chart(fig, config=ChartConfig.PLOTLY_CONFIG)


def monthly_spending(df):
    if df.empty:
        st.info(UIConstants.MSG_NO_DATA)
        return
    
    agg = grouped_monthly(df)
    fig = px.line(
        agg,
        x=Columns.YEAR_MONTH,
        y=Columns.PRICE_PAID,
        markers=True,
        title=ChartConfig.TITLE_MONTHLY_TREND,  # Use constant
        labels={Columns.PRICE_PAID: "SEK"},
    )
    fig.update_layout(margin=ChartConfig.CHART_MARGIN)
    st.plotly_chart(fig, config=ChartConfig.PLOTLY_CONFIG)


def calendar_heatmap(df):
    if df.empty:
        st.info(UIConstants.MSG_NO_DATA)
        return
    
    df2 = df.copy()
    df2[Columns.DATE] = pd.to_datetime(df2[Columns.DATE], errors="coerce")
    df2 = df2.dropna(subset=[Columns.DATE])
    
    # Group by date
    daily = df2.groupby(df2[Columns.DATE].dt.date)[Columns.PRICE_PAID].sum().reset_index()
    daily.columns = [Columns.DATE, Columns.PRICE_PAID]
    daily[Columns.DATE] = pd.to_datetime(daily[Columns.DATE])
    
    # Use Columns constants for computed columns
    daily[Columns.DAY_OF_WEEK] = daily[Columns.DATE].dt.day_name()
    daily[Columns.WEEK] = daily[Columns.DATE].dt.isocalendar().week
    
    fig = px.density_heatmap(
        daily,
        x=Columns.WEEK,
        y=Columns.DAY_OF_WEEK,
        z=Columns.PRICE_PAID,
        title=ChartConfig.TITLE_CALENDAR_HEATMAP,  # Use constant
        color_continuous_scale=ChartConfig.COLOR_SCALE_HEATMAP,  # Use constant
    )
    fig.update_layout(margin=ChartConfig.CHART_MARGIN)
    st.plotly_chart(fig, config=ChartConfig.PLOTLY_CONFIG)


def stacked_area_chart(df):
    if df.empty:
        st.info(UIConstants.MSG_NO_DATA)
        return
    
    df2 = df.copy()
    df2[Columns.DATE] = pd.to_datetime(df2[Columns.DATE], errors="coerce")
    df2 = df2.dropna(subset=[Columns.DATE])
    df2[Columns.YEAR_MONTH] = df2[Columns.DATE].dt.to_period("M").astype(str)
    
    monthly_cat = (
        df2.groupby([Columns.YEAR_MONTH, Columns.CATEGORY])[Columns.PRICE_PAID]
        .sum()
        .reset_index()
        .sort_values(Columns.YEAR_MONTH)
    )
    
    fig = px.area(
        monthly_cat,
        x=Columns.YEAR_MONTH,
        y=Columns.PRICE_PAID,
        color=Columns.CATEGORY,
        title=ChartConfig.TITLE_STACKED_AREA,  # Use constant
    )
    fig.update_layout(margin=ChartConfig.CHART_MARGIN)
    st.plotly_chart(fig, config=ChartConfig.PLOTLY_CONFIG)


def multi_year_comparison(df):
    if df.empty:
        st.info(UIConstants.MSG_NO_DATA)
        return
    
    df2 = df.copy()
    df2[Columns.DATE] = pd.to_datetime(df2[Columns.DATE], errors="coerce")
    df2 = df2.dropna(subset=[Columns.DATE])
    df2[Columns.YEAR] = df2[Columns.DATE].dt.year
    
    agg = df2.groupby([Columns.YEAR, Columns.CATEGORY])[Columns.PRICE_PAID].sum().reset_index()
    
    fig = px.bar(
        agg,
        x=Columns.CATEGORY,
        y=Columns.PRICE_PAID,
        color=Columns.YEAR,
        barmode="group",
        title=ChartConfig.TITLE_YEARLY_COMPARISON,  # Use constant
    )
    fig.update_layout(margin=ChartConfig.CHART_MARGIN)
    st.plotly_chart(fig, config=ChartConfig.PLOTLY_CONFIG)