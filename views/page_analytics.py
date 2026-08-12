# pages/page_analytics.py
# ──────────────────────────────────────────────────────────────
#  Analytics & Trends page — date-range filters, category
#  breakdown, time comparisons, forecasts, export
# ──────────────────────────────────────────────────────────────
from datetime import date, timedelta
from io import BytesIO

import pandas as pd
import streamlit as st

from config import Columns
from date_utils import normalize_dataframe_dates
from charts import category_pie, monthly_spending, stacked_area_chart, multi_year_comparison, calendar_heatmap
from analytics import monthly_trends, category_insights
from page_helpers import hero, monthly_bar_chart, empty_state
import feature_flags as ff


def render(df: pd.DataFrame, t: dict, **_) -> None:
    """
    Parameters
    ----------
    df : Full (user-filtered) expense DataFrame
    t  : Active theme dict — passed explicitly, never global
    """
    hero("Analytics & Trends", "Historical spending breakdown and forecasts", "📊")

    if df.empty:
        empty_state("No data available yet. Add expenses to see analytics and trends.")
        return

    # ── Date preparation ───────────────────────────────────────
    df_dates = df.copy()
    df_dates[Columns.DATE] = pd.to_datetime(
        normalize_dataframe_dates(df_dates, Columns.DATE)[Columns.DATE], errors="coerce"
    )
    df_dates = df_dates.dropna(subset=[Columns.DATE])

    if df_dates.empty:
        st.warning("No valid dates found in data.")
        return

    min_date = df_dates[Columns.DATE].min().date()
    max_date = df_dates[Columns.DATE].max().date()
    today = date.today()

    # ── Sidebar filters ────────────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🎯 Analytics Filters")

    presets = {
        "Custom (use sliders below)": None,
        "Last 30 Days": (today - timedelta(days=30), today),
        "Last 3 Months": (today - timedelta(days=90), today),
        "Last 6 Months": (today - timedelta(days=180), today),
        "Last Year": (today - timedelta(days=365), today),
        "Year to Date": (date(today.year, 1, 1), today),
        "All Time": (min_date, max_date),
    }
    preset = st.sidebar.selectbox("📅 Quick Date Range", list(presets.keys()), index=0)

    if preset != "Custom (use sliders below)" and presets[preset] is not None:
        default_start = max(presets[preset][0], min_date)
        default_end = min(presets[preset][1], max_date)
    else:
        default_start, default_end = min_date, max_date

    granularity = st.sidebar.radio("📊 View By", ["Daily", "Weekly", "Monthly", "Yearly"], index=2)
    all_categories = sorted(df_dates[Columns.CATEGORY].dropna().unique().tolist())
    selected_categories = st.sidebar.multiselect("🏷️ Filter Categories", all_categories, default=[])
    st.sidebar.markdown("---")

    # ── Date range inputs ──────────────────────────────────────
    st.markdown("### 📅 Date Range")
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        start_date = st.date_input("From", default_start, min_value=min_date, max_value=max_date, key="analytics_start")
    with col2:
        end_date = st.date_input("To", default_end, min_value=min_date, max_value=max_date, key="analytics_end")
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Reset All", width="stretch"):
            st.session_state["analytics_start"] = min_date
            st.session_state["analytics_end"] = max_date
            st.rerun()

    # ── Filter data ────────────────────────────────────────────
    df_filtered = df_dates[
        (df_dates[Columns.DATE].dt.date >= start_date)
        & (df_dates[Columns.DATE].dt.date <= end_date)
    ].copy()
    if selected_categories:
        df_filtered = df_filtered[df_filtered[Columns.CATEGORY].isin(selected_categories)]
    if df_filtered.empty:
        st.info("No data in selected filters.")
        return

    # ── Granularity label ──────────────────────────────────────
    if granularity == "Daily":
        df_filtered["Period"] = df_filtered[Columns.DATE].dt.date.astype(str)
        period_label = "Day"
    elif granularity == "Weekly":
        df_filtered["Period"] = df_filtered[Columns.DATE].dt.to_period("W").astype(str)
        period_label = "Week"
    elif granularity == "Monthly":
        df_filtered["Period"] = df_filtered[Columns.DATE].dt.to_period("M").astype(str)
        period_label = "Month"
    else:
        df_filtered["Period"] = df_filtered[Columns.DATE].dt.year.astype(str)
        period_label = "Year"

    cat_text = f" | {len(selected_categories)} categories" if selected_categories else " | All categories"
    st.caption(
        f"📊 **{len(df_filtered):,} transactions** from {start_date} to {end_date}"
        f"{cat_text} | Viewing by: {granularity}"
    )

    # ── Summary KPIs ───────────────────────────────────────────
    total_spent = df_filtered[Columns.PRICE_PAID].sum()
    num_tx = len(df_filtered)
    avg_tx = total_spent / num_tx if num_tx > 0 else 0

    if Columns.CATEGORY in df_filtered.columns and not df_filtered[Columns.CATEGORY].isna().all():
        top_cat = df_filtered.groupby(Columns.CATEGORY)[Columns.PRICE_PAID].sum().idxmax()
        top_cat_pct = (
            df_filtered.groupby(Columns.CATEGORY)[Columns.PRICE_PAID].sum().max()
            / total_spent * 100
        ) if total_spent > 0 else 0
    else:
        top_cat, top_cat_pct = "—", 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Total Spent", f"{total_spent:,.0f} SEK")
    c2.metric("🧾 Transactions", f"{num_tx:,}")
    c3.metric("📊 Avg / Transaction", f"{avg_tx:,.0f} SEK")
    if top_cat != "—":
        c4.metric("🏆 Top Category", f"{top_cat} ({top_cat_pct:.0f}%)")
    else:
        c4.metric("🏆 Top Category", "—")

    st.markdown("---")

    # ── Expanders ──────────────────────────────────────────────
    with st.expander("📊 **OVERVIEW** — Quick Summary & Trends", expanded=True):
        col1, col2 = st.columns([1.3, 1])
        with col1:
            monthly_spending(df_filtered)
        with col2:
            monthly_bar_chart(df_filtered, t)      # t passed explicitly ✓
        st.markdown("---")
        monthly_trends(df_filtered)

    with st.expander("🏆 **CATEGORY ANALYSIS** — Where Your Money Goes", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            category_insights(df_filtered)
        with col2:
            category_pie(df_filtered)
        if ff.HAS_ADVANCED and ff.category_evolution_chart:
            st.markdown("---")
            ff.category_evolution_chart(df_filtered)

    if ff.HAS_ADVANCED:
        with st.expander("📈 **TIME ANALYSIS** — Comparisons & Forecasts", expanded=False):
            ff.mom_comparison_chart(df_filtered)
            st.markdown("---")
            ff.yoy_comparison_chart(df_filtered)
            st.markdown("---")
            months_ahead = st.slider("Forecast months ahead", 1, 12, 3, key="forecast_months")
            ff.spending_forecast_chart(df_filtered, months_ahead)

    with st.expander("📆 **CALENDAR VIEWS** — When You Spend", expanded=False):
        calendar_heatmap(df_filtered)
        st.markdown("---")
        stacked_area_chart(df_filtered)
        st.markdown("---")
        multi_year_comparison(df_filtered)
        if ff.HAS_ADVANCED and ff.daily_heatmap:
            st.markdown("---")
            ff.daily_heatmap(df_filtered)

    if ff.HAS_ADVANCED:
        with st.expander("🔍 **ADVANCED INSIGHTS** — Anomalies & AI Analysis", expanded=False):
            ff.anomaly_detection_chart(df_filtered)
            st.markdown("---")
            ff.spending_insights(df_filtered)

    # ── Export ─────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("💾 **EXPORT FILTERED DATA**", expanded=False):
        export_df = df_filtered[[
            Columns.DATE, Columns.CATEGORY, Columns.SUBCATEGORY,
            Columns.ITEM, Columns.SHOP, Columns.PRICE_PAID, Columns.CURRENCY,
        ]].copy()
        export_df[Columns.DATE] = export_df[Columns.DATE].dt.date
        export_df = export_df.sort_values(Columns.DATE, ascending=False)
        st.dataframe(export_df.head(10), width="stretch", hide_index=True)
        st.caption(f"Preview showing first 10 of {len(export_df):,} rows")

        suffix = f"_{selected_categories[0]}" if len(selected_categories) == 1 else "_filtered"
        fname = f"analytics_{start_date}_{end_date}{suffix}"
        col1, col2 = st.columns(2)
        with col1:
            csv = export_df.to_csv(index=False).encode("utf-8")
            st.download_button("📄 Download CSV", csv, f"{fname}.csv", "text/csv", width="stretch")
        with col2:
            try:
                buf = BytesIO()
                export_df.to_excel(buf, index=False, engine="openpyxl")
                st.download_button(
                    "📊 Download Excel", buf.getvalue(), f"{fname}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                )
            except ImportError:
                st.caption("Install `openpyxl` for Excel export.")
