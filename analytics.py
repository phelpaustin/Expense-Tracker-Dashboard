# analytics.py
import streamlit as st
import pandas as pd
from datetime import datetime

# statsmodels optional import handled safely
try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    HAS_STATS = True
except Exception:
    HAS_STATS = False

@st.cache_data(ttl=300)
def monthly_agg_for_forecast(df):
    df2 = df.copy()
    df2["Date"] = pd.to_datetime(df2["Date"], errors="coerce")
    df2 = df2.dropna(subset=["Date"])
    df2["YearMonth"] = df2["Date"].dt.to_period("M").astype(str)
    monthly = df2.groupby("YearMonth")["PricePaid"].sum().reset_index().sort_values("YearMonth")
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

    # show last months
    st.write("Last months:")
    st.line_chart(monthly.set_index("YearMonth")["PricePaid"])

    # percent change vs previous month
    if len(monthly) >= 2:
        last = monthly["PricePaid"].iloc[-1]
        prev = monthly["PricePaid"].iloc[-2]
        pct_change = ((last - prev) / prev * 100) if prev != 0 else 0
        if pct_change > 0:
            st.markdown(f"**Change vs previous month:** ⬆️ {pct_change:.1f}%")
        else:
            st.markdown(f"**Change vs previous month:** ⬇️ {abs(pct_change):.1f}%")
    else:
        st.markdown("Not enough months to compute % change.")

    # forecast next month (only if statsmodels available and at least 2 months)
    if not HAS_STATS:
        st.info("Forecasting library not installed (statsmodels). Install `statsmodels` for forecasting.")
        return

    if len(monthly) < 2:
        st.warning("Need at least 2 months of data to forecast.")
        return

    try:
        model = ExponentialSmoothing(monthly["PricePaid"], trend="add", seasonal=None)
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
    df2["PricePaid"] = pd.to_numeric(df2["PricePaid"], errors="coerce").fillna(0)
    df2["Date"] = pd.to_datetime(df2["Date"], errors="coerce")
    current_month = pd.Timestamp.now().to_period("M").strftime("%Y-%m")
    df2["YearMonth"] = df2["Date"].dt.to_period("M").astype(str)
    this_month = df2[df2["YearMonth"] == current_month]

    if this_month.empty:
        st.info("No expenses recorded this month.")
    else:
        cat_sum = this_month.groupby("Category")["PricePaid"].sum().reset_index().sort_values("PricePaid", ascending=False)
        top3 = cat_sum.head(3)
        st.write("**Top 3 Categories (This Month):**")
        for i, row in top3.iterrows():
            st.write(f"{i+1}. {row['Category']} — {row['PricePaid']:.0f} SEK")

    # Efficiency score (overall dataset)
    efficiency = df2.groupby("Category").agg(TotalSpend=("PricePaid", "sum"),
                                            Purchases=("Category", "count")).reset_index()
    efficiency["EfficiencyScore"] = efficiency.apply(lambda r: (r["TotalSpend"] / r["Purchases"]) if r["Purchases"] else 0, axis=1)
    st.write("**Category Efficiency Score (SEK per purchase):**")
    st.dataframe(efficiency[["Category", "EfficiencyScore"]].sort_values("EfficiencyScore", ascending=False))


def what_if_simulation(df):
    st.sidebar.markdown("### 💭 What-if Simulation")
    if df.empty:
        st.sidebar.info("No data to simulate.")
        return
    reduction = st.sidebar.slider("Reduce Dining Expenses by (%)", 0, 100, 10)
    yearly_spend = df["PricePaid"].sum()
    dining_spend = df[df["Category"].str.contains("dining", case=False, na=False)]["PricePaid"].sum()
    savings = dining_spend * (reduction / 100)
    new_total = yearly_spend - savings
    st.sidebar.info(f"💡 Potential yearly savings: **{savings:,.0f} SEK**")
    st.sidebar.caption(f"New estimated yearly total: {new_total:,.0f} SEK")
