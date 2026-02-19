# analytics_advanced.py
"""
Advanced analytics — YoY/MoM comparisons, forecasting, anomaly detection,
category evolution, day-of-week heatmap, and smart insights.

All charts respect the active app theme (no hardcoded dark colours).
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from config import Columns

PALETTE = ["#6366f1", "#22d3ee", "#f59e0b", "#22c55e",
           "#f97316", "#ec4899", "#a855f7", "#ef4444"]

# ─── Theme lookup (mirrors Main_Dashboard_App THEMES dict) ────────────────────
_THEME_PALETTES = {
    "☀️ Light":    {"paper": "#ffffff", "grid": "#e2e8f0",  "text": "#475569", "muted": "#94a3b8", "fg": "#0f172a", "border": "#e2e8f0",  "accent": "#6366f1"},
    "🌑 Dark":     {"paper": "#1e293b", "grid": "#334155",  "text": "#94a3b8", "muted": "#64748b", "fg": "#f1f5f9", "border": "#334155",  "accent": "#818cf8"},
    "🌊 Ocean":    {"paper": "#f0f9ff", "grid": "#bae6fd",  "text": "#0369a1", "muted": "#38bdf8", "fg": "#0c4a6e", "border": "#bae6fd",  "accent": "#0284c7"},
    "🌿 Forest":   {"paper": "#f0fdf4", "grid": "#bbf7d0",  "text": "#15803d", "muted": "#4ade80", "fg": "#14532d", "border": "#bbf7d0",  "accent": "#16a34a"},
    "🌅 Sunset":   {"paper": "#fff7ed", "grid": "#fed7aa",  "text": "#c2410c", "muted": "#fb923c", "fg": "#7c2d12", "border": "#fed7aa",  "accent": "#ea580c"},
    "🌙 Midnight": {"paper": "#13131f", "grid": "#1e1e3f",  "text": "#a5b4fc", "muted": "#4f4f7a", "fg": "#e2e2ff", "border": "#1e1e3f",  "accent": "#7c3aed"},
    "🌸 Rose":     {"paper": "#fff1f2", "grid": "#fecdd3",  "text": "#be123c", "muted": "#fb7185", "fg": "#881337", "border": "#fecdd3",  "accent": "#e11d48"},
    "⬜ Slate":    {"paper": "#ffffff", "grid": "#e2e8f0",  "text": "#475569", "muted": "#94a3b8", "fg": "#1e293b", "border": "#cbd5e1",  "accent": "#64748b"},
}


def _t() -> dict:
    name = st.session_state.get("theme_name", "☀️ Light")
    return _THEME_PALETTES.get(name, _THEME_PALETTES["☀️ Light"])


def _fmt(fig: go.Figure, height: int = 380) -> go.Figure:
    t = _t()
    fig.update_layout(
        paper_bgcolor=t["paper"], plot_bgcolor=t["paper"],
        font=dict(color=t["text"], family="Plus Jakarta Sans, sans-serif"),
        xaxis=dict(showgrid=False, tickcolor=t["border"], linecolor=t["border"],
                   tickfont=dict(color=t["muted"])),
        yaxis=dict(showgrid=True, gridcolor=t["grid"], zeroline=False,
                   tickfont=dict(color=t["muted"])),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=t["text"]),
                    bordercolor="rgba(0,0,0,0)"),
        margin=dict(t=52, b=16, l=0, r=0),
        height=height,
        title_font=dict(color=t["text"], size=13),
    )
    return fig


# ─── Data preparation ─────────────────────────────────────────────────────────
def prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df2 = df.copy()
    df2[Columns.DATE]      = pd.to_datetime(df2[Columns.DATE], errors="coerce")
    df2 = df2.dropna(subset=[Columns.DATE])
    df2["Year"]             = df2[Columns.DATE].dt.year
    df2["Month"]            = df2[Columns.DATE].dt.month
    df2["MonthName"]        = df2[Columns.DATE].dt.strftime("%b")
    df2[Columns.YEAR_MONTH] = df2[Columns.DATE].dt.to_period("M").astype(str)
    df2["Week"]             = df2[Columns.DATE].dt.isocalendar().week
    df2["DayOfWeek"]        = df2[Columns.DATE].dt.day_name()
    df2["Quarter"]          = df2[Columns.DATE].dt.quarter
    return df2


# ─── YoY comparison ───────────────────────────────────────────────────────────
def yoy_comparison_chart(df: pd.DataFrame):
    df2 = prepare_df(df)
    if df2.empty:
        return
    t = _t()
    years = sorted(df2["Year"].unique())
    if len(years) < 2:
        st.info("Need at least 2 years of data for YoY comparison.")
        return

    monthly     = df2.groupby(["Year", "Month", "MonthName"])[Columns.PRICE_PAID].sum().reset_index()
    month_order = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

    fig = go.Figure()
    for i, yr in enumerate(years):
        yr_data = monthly[monthly["Year"] == yr].sort_values("Month")
        fig.add_trace(go.Bar(
            name=str(yr), x=yr_data["MonthName"], y=yr_data[Columns.PRICE_PAID],
            marker_color=PALETTE[i % len(PALETTE)], opacity=0.85,
            hovertemplate=f"<b>{yr} — %{{x}}</b><br>%{{y:,.0f}} SEK<extra></extra>",
        ))
    fig.update_layout(title="📅 Year-over-Year Monthly Comparison", barmode="group",
                      xaxis=dict(categoryorder="array", categoryarray=month_order))
    _fmt(fig)
    st.plotly_chart(fig, config={"displayModeBar": False})

    if len(years) >= 2:
        st.markdown("#### 📊 YoY % Change by Month")
        pivot = monthly.pivot_table(index="Month", columns="Year",
                                    values=Columns.PRICE_PAID, aggfunc="sum").fillna(0)
        pivot.index = [month_order[m - 1] for m in pivot.index]
        for i in range(len(years) - 1, 0, -1):
            y1, y2 = years[i - 1], years[i]
            if y1 in pivot.columns and y2 in pivot.columns:
                pct = ((pivot[y2] - pivot[y1]) / pivot[y1].replace(0, np.nan) * 100).round(1)
                pivot[f"Δ {y1}→{y2} (%)"] = pct.apply(
                    lambda x: f"{'↑' if x > 0 else '↓'} {abs(x):.1f}%" if pd.notna(x) else "—"
                )
        st.dataframe(pivot.rename(columns={y: f"{y} (SEK)" for y in years}),
                     width="stretch")


# ─── MoM comparison ───────────────────────────────────────────────────────────
def mom_comparison_chart(df: pd.DataFrame):
    df2 = prepare_df(df)
    if df2.empty:
        return
    t = _t()

    monthly = (df2.groupby(Columns.YEAR_MONTH)[Columns.PRICE_PAID]
               .sum().reset_index().sort_values(Columns.YEAR_MONTH))
    monthly["Prev"]     = monthly[Columns.PRICE_PAID].shift(1)
    monthly["MoMDelta"] = monthly[Columns.PRICE_PAID] - monthly["Prev"]
    monthly["MoMPct"]   = (monthly["MoMDelta"] / monthly["Prev"] * 100).round(1)
    monthly["Color"]    = monthly["MoMDelta"].apply(lambda x: "#ef4444" if x > 0 else "#22c55e")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.65, 0.35],
                        subplot_titles=["Monthly Total (SEK)", "Month-over-Month Change (%)"])
    fig.add_trace(go.Bar(x=monthly[Columns.YEAR_MONTH], y=monthly[Columns.PRICE_PAID],
                         name="Spending", marker_color=t["accent"], opacity=0.85,
                         hovertemplate="<b>%{x}</b><br>%{y:,.0f} SEK<extra></extra>"),
                  row=1, col=1)
    fig.add_trace(go.Bar(x=monthly[Columns.YEAR_MONTH], y=monthly["MoMPct"],
                         name="MoM %", marker_color=monthly["Color"].tolist(), opacity=0.85,
                         hovertemplate="<b>%{x}</b><br>%{y:+.1f}%<extra></extra>"),
                  row=2, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color=t["border"], row=2, col=1)
    fig.update_layout(title="📈 Month-over-Month Analysis", showlegend=False)
    _fmt(fig, height=480)
    st.plotly_chart(fig, config={"displayModeBar": False})

    if len(monthly) >= 2:
        last, prev = monthly.iloc[-1], monthly.iloc[-2]
        c1, c2, c3 = st.columns(3)
        c1.metric("This Month", f"{last[Columns.PRICE_PAID]:,.0f} SEK",
                  delta=f"{last['MoMPct']:+.1f}% vs last month" if pd.notna(last["MoMPct"]) else None)
        c2.metric("Last Month", f"{prev[Columns.PRICE_PAID]:,.0f} SEK")
        c3.metric("6-Month Avg", f"{monthly[Columns.PRICE_PAID].tail(6).mean():,.0f} SEK")


# ─── Spending forecast ────────────────────────────────────────────────────────
def spending_forecast_chart(df: pd.DataFrame, months_ahead: int = 3):
    df2 = prepare_df(df)
    if df2.empty:
        return
    t = _t()

    monthly = (df2.groupby(Columns.YEAR_MONTH)[Columns.PRICE_PAID]
               .sum().reset_index().sort_values(Columns.YEAR_MONTH))
    if len(monthly) < 4:
        st.info("Need at least 4 months of data for forecasting.")
        return

    x = np.arange(len(monthly))
    y = monthly[Columns.PRICE_PAID].values
    slope, intercept = np.polyfit(x, y, 1)

    future_x      = np.arange(len(monthly), len(monthly) + months_ahead)
    future_y      = slope * future_x + intercept
    last_period   = pd.Period(monthly[Columns.YEAR_MONTH].iloc[-1], "M")
    future_labels = [(last_period + i + 1).strftime("%Y-%m") for i in range(months_ahead)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=monthly[Columns.YEAR_MONTH], y=monthly[Columns.PRICE_PAID],
                             name="Actual", mode="lines+markers",
                             line=dict(color=t["accent"], width=2.5), marker=dict(size=5)))
    fig.add_trace(go.Scatter(x=monthly[Columns.YEAR_MONTH], y=slope * x + intercept,
                             name="Trend", mode="lines",
                             line=dict(color=t["muted"], dash="dot", width=1.5)))
    fig.add_trace(go.Scatter(
        x=[monthly[Columns.YEAR_MONTH].iloc[-1]] + future_labels,
        y=[monthly[Columns.PRICE_PAID].iloc[-1]] + future_y.tolist(),
        name="Forecast", mode="lines+markers",
        line=dict(color="#f59e0b", dash="dash", width=2.5),
        marker=dict(size=9, symbol="diamond"),
    ))
    fig.update_layout(title=f"🔮 Spending Forecast (+{months_ahead} months)")
    _fmt(fig)
    st.plotly_chart(fig, config={"displayModeBar": False})

    cols = st.columns(months_ahead)
    for i, (label, val) in enumerate(zip(future_labels, future_y)):
        cols[i].metric(label, f"{max(val, 0):,.0f} SEK")


# ─── Anomaly detection ────────────────────────────────────────────────────────
def anomaly_detection_chart(df: pd.DataFrame):
    df2 = prepare_df(df)
    if df2.empty:
        return
    t = _t()

    monthly = (df2.groupby(Columns.YEAR_MONTH)[Columns.PRICE_PAID]
               .sum().reset_index().sort_values(Columns.YEAR_MONTH))
    if len(monthly) < 4:
        st.info("Need more data for anomaly detection.")
        return

    mean = monthly[Columns.PRICE_PAID].mean()
    std  = monthly[Columns.PRICE_PAID].std()
    monthly["ZScore"]    = (monthly[Columns.PRICE_PAID] - mean) / std if std > 0 else 0
    monthly["IsAnomaly"] = monthly["ZScore"].abs() > 2.0
    monthly["Color"]     = monthly["IsAnomaly"].map({True: "#ef4444", False: t["accent"]})

    fig = go.Figure()
    fig.add_hline(y=mean + 2 * std, line_dash="dash", line_color="#ef4444",
                  annotation_text="Anomaly threshold (+2σ)", annotation_font_color=t["muted"])
    fig.add_hline(y=mean, line_dash="dot", line_color=t["muted"],
                  annotation_text="Average", annotation_font_color=t["muted"])
    fig.add_trace(go.Bar(x=monthly[Columns.YEAR_MONTH], y=monthly[Columns.PRICE_PAID],
                         marker_color=monthly["Color"].tolist(),
                         hovertemplate="<b>%{x}</b><br>%{y:,.0f} SEK<extra></extra>"))
    fig.update_layout(title="🔍 Anomaly Detection — Unusual Spending Periods", showlegend=False)
    _fmt(fig, height=350)
    st.plotly_chart(fig, config={"displayModeBar": False})

    anomalies = monthly[monthly["IsAnomaly"]]
    if not anomalies.empty:
        st.warning(f"⚠️ **{len(anomalies)} anomalous month(s) detected:**")
        for _, row in anomalies.iterrows():
            direction = "above" if row["ZScore"] > 0 else "below"
            st.markdown(f"  • **{row[Columns.YEAR_MONTH]}**: {row[Columns.PRICE_PAID]:,.0f} SEK "
                        f"({abs(row['ZScore']):.1f}σ {direction} average)")
    else:
        st.success("✅ No unusual spending anomalies detected.")


# ─── Category evolution ───────────────────────────────────────────────────────
def category_evolution_chart(df: pd.DataFrame):
    """Stacked area — top-8 category spending evolution over time."""
    df2 = prepare_df(df)
    if df2.empty:
        return
    t = _t()

    top_cats = (df2.groupby(Columns.CATEGORY)[Columns.PRICE_PAID]
                .sum().nlargest(8).index.tolist())
    monthly_cat = (
        df2[df2[Columns.CATEGORY].isin(top_cats)]
        .groupby([Columns.YEAR_MONTH, Columns.CATEGORY])[Columns.PRICE_PAID]
        .sum().reset_index().sort_values(Columns.YEAR_MONTH)
    )

    fig = px.area(monthly_cat, x=Columns.YEAR_MONTH, y=Columns.PRICE_PAID,
                  color=Columns.CATEGORY,
                  title="📊 Category Spending Evolution (Top 8)",
                  color_discrete_sequence=PALETTE)
    fig.update_layout(legend_title=None)
    _fmt(fig, height=400)
    st.plotly_chart(fig, config={"displayModeBar": False})


# ─── Day-of-week heatmap ──────────────────────────────────────────────────────
def daily_heatmap(df: pd.DataFrame):
    """Bar chart: total spending per day of week, colour-scaled by amount."""
    df2 = prepare_df(df)
    if df2.empty:
        return
    t = _t()

    day_order  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    dow_totals = (df2.groupby("DayOfWeek")[Columns.PRICE_PAID]
                  .sum().reindex(day_order, fill_value=0).reset_index())
    dow_totals.columns = ["Day", "Total"]

    fig = go.Figure(go.Bar(
        x=dow_totals["Day"], y=dow_totals["Total"],
        marker=dict(color=dow_totals["Total"],
                    colorscale=[[0, t["grid"]], [1, t["accent"]]],
                    showscale=True, colorbar=dict(tickfont=dict(color=t["muted"]))),
        hovertemplate="<b>%{x}</b><br>%{y:,.0f} SEK<extra></extra>",
    ))
    fig.update_layout(title="📆 Spending by Day of Week", showlegend=False)
    _fmt(fig, height=320)
    st.plotly_chart(fig, config={"displayModeBar": False})


# ─── Spending insights ────────────────────────────────────────────────────────
def spending_insights(df: pd.DataFrame):
    """Auto-generated bullet-point insights from spending patterns."""
    df2 = prepare_df(df)
    if df2.empty:
        st.info("No data for insights.")
        return

    st.markdown("### 💡 Spending Insights")
    insights: list = []
    monthly    = df2.groupby(Columns.YEAR_MONTH)[Columns.PRICE_PAID].sum().sort_index()
    last_month = monthly.iloc[-1] if len(monthly) >= 1 else 0

    if len(monthly) >= 2:
        prev_month = monthly.iloc[-2]
        pct  = (last_month - prev_month) / prev_month * 100 if prev_month > 0 else 0
        word = "📈 increased" if pct > 0 else "📉 decreased"
        insights.append(f"Spending **{word} {abs(pct):.1f}%** vs last month.")

    if len(monthly) >= 6:
        avg6 = monthly.tail(6).mean()
        if last_month > avg6 * 1.2:
            insights.append(f"⚠️ This month is **{((last_month / avg6) - 1) * 100:.0f}% above** "
                            f"your 6-month average ({avg6:,.0f} SEK).")
        elif last_month < avg6 * 0.8:
            insights.append(f"✅ This month is **{((avg6 / last_month) - 1) * 100:.0f}% below** "
                            f"your 6-month average — great savings!")

    if Columns.CATEGORY in df2.columns:
        cat_totals  = df2.groupby(Columns.CATEGORY)[Columns.PRICE_PAID].sum()
        top_cat     = cat_totals.idxmax()
        top_cat_pct = cat_totals.max() / df2[Columns.PRICE_PAID].sum() * 100
        insights.append(f"🏆 **{top_cat}** is your top category at **{top_cat_pct:.1f}%** of total.")

    if not df2.empty:
        max_row   = df2.loc[df2[Columns.PRICE_PAID].idxmax()]
        item_name = max_row.get(Columns.ITEM, "—") or "—"
        insights.append(f"💸 Biggest transaction: **{item_name}** — "
                        f"{max_row[Columns.PRICE_PAID]:,.0f} SEK on "
                        f"{max_row[Columns.DATE].strftime('%b %d, %Y')}")
        best_day = df2.groupby("DayOfWeek")[Columns.PRICE_PAID].sum().idxmax()
        insights.append(f"📅 You spend the most on **{best_day}s**.")

    for ins in insights:
        st.markdown(f"- {ins}")


# ─── Standalone page ──────────────────────────────────────────────────────────
def advanced_analytics_page(df: pd.DataFrame):
    st.markdown("# 🔬 Advanced Analytics")
    if df.empty:
        st.info("No expense data available.")
        return
    tabs = st.tabs(["📅 YoY / MoM", "🔮 Forecast", "🔍 Anomalies",
                    "📊 Category Evolution", "📅 Day of Week", "💡 Insights"])
    with tabs[0]:
        col1, col2 = st.columns(2)
        with col1:
            yoy_comparison_chart(df)
        with col2:
            mom_comparison_chart(df)
    with tabs[1]:
        months = st.slider("Forecast months ahead", 1, 12, 3, key="adv_fc")
        spending_forecast_chart(df, months)
    with tabs[2]:
        anomaly_detection_chart(df)
    with tabs[3]:
        category_evolution_chart(df)
    with tabs[4]:
        daily_heatmap(df)
    with tabs[5]:
        spending_insights(df)