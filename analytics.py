# analytics.py
import streamlit as st
import pandas as pd
from datetime import datetime
from config import Columns

# statsmodels optional import handled safely
try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    HAS_STATS = True
except Exception:
    HAS_STATS = False


@st.cache_data(ttl=300)
def monthly_agg_for_forecast(df):
    df2 = df.copy()
    df2[Columns.DATE] = pd.to_datetime(df2[Columns.DATE], errors="coerce")
    df2 = df2.dropna(subset=[Columns.DATE])
    df2[Columns.YEAR_MONTH] = df2[Columns.DATE].dt.to_period("M").astype(str)
    monthly = (
        df2.groupby(Columns.YEAR_MONTH)[Columns.PRICE_PAID]
        .sum().reset_index().sort_values(Columns.YEAR_MONTH)
    )
    return monthly


def monthly_trends(df):
    st.subheader("📈 Expense Trends & Forecasts")
    if df.empty:
        st.info("No data to display.")
        return

    monthly = monthly_agg_for_forecast(df)
    if monthly.empty:
        st.info("No monthly data available.")
        return

    st.write("Monthly spending:")
    st.line_chart(monthly.set_index(Columns.YEAR_MONTH)[Columns.PRICE_PAID])

    if len(monthly) >= 2:
        last = monthly[Columns.PRICE_PAID].iloc[-1]
        prev = monthly[Columns.PRICE_PAID].iloc[-2]
        pct_change = ((last - prev) / prev * 100) if prev != 0 else 0
        arrow = "⬆️" if pct_change > 0 else "⬇️"
        st.markdown(f"**Change vs previous month:** {arrow} {abs(pct_change):.1f}%")
    else:
        st.markdown("Not enough months to compute % change.")

    if not HAS_STATS:
        st.info("📦 Install `statsmodels` for forecasting: `pip install statsmodels`")
        return

    if len(monthly) < 2:
        st.warning("Need at least 2 months of data to forecast.")
        return

    try:
        model = ExponentialSmoothing(monthly[Columns.PRICE_PAID], trend="add", seasonal=None)
        fit = model.fit()
        forecast = fit.forecast(1)
        next_month_forecast = float(forecast.iloc[0])
        st.markdown(f"**Forecast (next month):** {next_month_forecast:,.0f} SEK")
    except Exception as e:
        st.error(f"Forecast failed: {e}")


def category_insights(df):
    st.subheader("🏆 Category Insights")
    if df.empty:
        st.info("No data yet.")
        return

    df2 = df.copy()
    df2[Columns.PRICE_PAID] = pd.to_numeric(df2[Columns.PRICE_PAID], errors="coerce").fillna(0)
    df2[Columns.DATE] = pd.to_datetime(df2[Columns.DATE], errors="coerce")
    current_month = pd.Timestamp.now().to_period("M").strftime("%Y-%m")
    df2[Columns.YEAR_MONTH] = df2[Columns.DATE].dt.to_period("M").astype(str)
    this_month = df2[df2[Columns.YEAR_MONTH] == current_month]

    if this_month.empty:
        st.info("No expenses recorded this month.")
    else:
        total_this_month = this_month[Columns.PRICE_PAID].sum()
        cat_sum = (
            this_month.groupby(Columns.CATEGORY)[Columns.PRICE_PAID]
            .sum().reset_index().sort_values(Columns.PRICE_PAID, ascending=False)
        )
        st.write("**Top Categories (This Month):**")
        for rank, (_, row) in enumerate(cat_sum.head(5).iterrows(), 1):
            pct = row[Columns.PRICE_PAID] / total_this_month * 100 if total_this_month else 0
            st.write(f"{rank}. **{row[Columns.CATEGORY]}** — {row[Columns.PRICE_PAID]:,.0f} SEK ({pct:.1f}%)")

    # Avg cost per purchase by category
    efficiency = df2.groupby(Columns.CATEGORY).agg(
        TotalSpend=(Columns.PRICE_PAID, "sum"),
        Purchases=(Columns.CATEGORY, "count")
    ).reset_index()
    efficiency["Avg SEK / Purchase"] = (
        efficiency["TotalSpend"] / efficiency["Purchases"]
    ).round(0)
    st.write("**Avg cost per purchase by category:**")
    st.dataframe(
        efficiency[[Columns.CATEGORY, "Avg SEK / Purchase"]]
        .sort_values("Avg SEK / Purchase", ascending=False)
        .rename(columns={Columns.CATEGORY: "Category"}),
        width="stretch", hide_index=True
    )


def what_if_simulation(df):
    """Dynamic what-if simulator — lets user pick any category, not just 'dining'."""
    st.sidebar.markdown("### 💭 What-if Simulation")
    if df.empty:
        st.sidebar.info("No data to simulate.")
        return

    df2 = df.copy()
    df2[Columns.PRICE_PAID] = pd.to_numeric(df2[Columns.PRICE_PAID], errors="coerce").fillna(0)
    total_spend = df2[Columns.PRICE_PAID].sum()

    # Dynamic category list from actual data
    categories = sorted(df2[Columns.CATEGORY].dropna().unique().tolist())
    if not categories:
        st.sidebar.caption("No categories found.")
        return

    selected_cat = st.sidebar.selectbox(
        "Category to cut", categories, key="whatif_cat"
    )
    reduction = st.sidebar.slider(
        f"Reduce {selected_cat} by (%)", 0, 100, 10, key="whatif_pct"
    )

    cat_spend = df2[df2[Columns.CATEGORY] == selected_cat][Columns.PRICE_PAID].sum()
    savings   = cat_spend * (reduction / 100)
    new_total = total_spend - savings

    if savings > 0:
        st.sidebar.info(f"💡 Potential savings: **{savings:,.0f} SEK**")
        st.sidebar.caption(f"New estimated total: {new_total:,.0f} SEK")
    else:
        st.sidebar.caption(f"No '{selected_cat}' spending in current data.")