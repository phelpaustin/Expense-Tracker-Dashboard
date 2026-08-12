# charts.py
import pandas as pd
import plotly.express as px
import streamlit as st
from uuid import uuid4
from config import (
    Columns, 
    ChartConfig, 
    UIConstants
)


@st.cache_data(ttl=300, max_entries=16)
def grouped_monthly(df):
    from utils import prepare_expense_df
    df2 = prepare_expense_df(df, numeric_price=False)
    agg = (
        df2.groupby(Columns.YEAR_MONTH)[Columns.PRICE_PAID]
        .sum()
        .reset_index()
        .sort_values(Columns.YEAR_MONTH)
    )
    return agg


@st.cache_data(ttl=300, max_entries=16)
def _month_stats(df_full):
    """
    Cache the (expensive) date parsing + current/previous-month slicing once
    per frame, returning just the scalar totals kpi_row needs. Keyed on the
    frame so it is not recomputed on every rerun.
    """
    if df_full is None or df_full.empty or Columns.PRICE_PAID not in df_full.columns:
        return None
    d = df_full[[Columns.DATE, Columns.PRICE_PAID]].copy()
    d[Columns.DATE] = pd.to_datetime(d[Columns.DATE], errors="coerce")
    d = d.dropna(subset=[Columns.DATE])
    if d.empty:
        return None
    now = pd.Timestamp.now()
    prev_month = now - pd.DateOffset(months=1)
    curr = d[(d[Columns.DATE].dt.year == now.year) & (d[Columns.DATE].dt.month == now.month)][Columns.PRICE_PAID]
    prev = d[(d[Columns.DATE].dt.year == prev_month.year) & (d[Columns.DATE].dt.month == prev_month.month)][Columns.PRICE_PAID]
    return {
        "curr_sum": float(curr.sum()),
        "prev_sum": float(prev.sum()),
        "curr_mean": float(curr.mean()) if len(curr) else 0.0,
        "prev_mean": float(prev.mean()) if len(prev) else 0.0,
    }


def _delta_text(curr_val, prev_val):
    """Format a month-over-month delta. Lower spending is 'good' (green)."""
    if not prev_val:
        return None, None, None
    pct = (curr_val - prev_val) / prev_val * 100
    if abs(pct) < 0.05:
        return "0.0% vs last month", "", True
    direction = "up" if pct > 0 else "down"
    good = pct < 0  # spending less than last month is good
    return f"{abs(pct):.1f}% vs last month", direction, good


def kpi_row(df, df_full=None):
    # Use Columns and UIConstants instead of magic strings
    if df.empty or Columns.PRICE_PAID not in df.columns:
        from page_helpers import empty_state
        empty_state(UIConstants.MSG_NO_DATA)
        return

    total_spent = df[Columns.PRICE_PAID].sum()
    avg_tx = df[Columns.PRICE_PAID].mean() if len(df) > 0 else 0
    categories = df[Columns.CATEGORY].nunique()

    stats = _month_stats(df_full)
    if stats:
        total_delta, total_dir, total_good = _delta_text(stats["curr_sum"], stats["prev_sum"])
        avg_delta, avg_dir, avg_good = _delta_text(stats["curr_mean"], stats["prev_mean"])
    else:
        total_delta = total_dir = total_good = None
        avg_delta = avg_dir = avg_good = None

    from page_helpers import animated_metric_row
    animated_metric_row([
        {"label": "💰 Total Spent", "value": total_spent, "suffix": " SEK", "decimals": 0,
         "delta": total_delta, "delta_dir": total_dir, "delta_good": total_good},
        {"label": "🧾 Avg Transaction", "value": avg_tx, "suffix": " SEK", "decimals": 0,
         "delta": avg_delta, "delta_dir": avg_dir, "delta_good": avg_good},
        {"label": "📂 Categories", "value": categories, "decimals": 0},
    ])


def category_pie(df):
    if df.empty:
        from page_helpers import empty_state
        empty_state(UIConstants.MSG_NO_DATA)
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
    st.plotly_chart(fig, config=ChartConfig.PLOTLY_CONFIG, key=f"chart_category_pie_{uuid4().hex}")


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
    st.plotly_chart(fig, config=ChartConfig.PLOTLY_CONFIG, key=f"chart_monthly_spending_{uuid4().hex}")


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
    st.plotly_chart(fig, config=ChartConfig.PLOTLY_CONFIG, key=f"chart_calendar_heatmap_{uuid4().hex}")


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
    st.plotly_chart(fig, config=ChartConfig.PLOTLY_CONFIG, key=f"chart_stacked_area_{uuid4().hex}")


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
    st.plotly_chart(fig, config=ChartConfig.PLOTLY_CONFIG, key=f"chart_multi_year_{uuid4().hex}")