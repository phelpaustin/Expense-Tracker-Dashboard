# spending_intelligence.py
"""
🧠 Spending Intelligence Engine
────────────────────────────────────────────────────────────────
Advanced purchase analysis:
  • Hotspot Analysis      — WHERE are your expenses highest?
  • Budget Intelligence   — Smart budgeting recommendations
  • Velocity Tracker      — Are you on track this month?
  • Savings Opportunities — Where you can cut back
  • Shop & Brand Analysis — Which stores cost you the most
  • Temporal Patterns     — When do you spend most?
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import streamlit as st
from datetime import date, datetime
from typing import Optional
from ai_insights import ai_monthly_report
from config import Columns

# ── Shared colour palette ─────────────────────────────────────────────────────
PALETTE = ["#6366f1", "#22d3ee", "#f59e0b", "#22c55e",
           "#f97316", "#ec4899", "#a855f7", "#ef4444", "#64748b"]
DANGER  = "#ef4444"
WARNING = "#f59e0b"
OK      = "#22c55e"
INFO    = "#6366f1"

_THEME_PALETTES = {
    "☀️ Light":    {"paper":"#ffffff","grid":"#e2e8f0","text":"#475569","muted":"#94a3b8","fg":"#0f172a","border":"#e2e8f0","accent":"#6366f1","card":"#ffffff","bg":"#f8fafc"},
    "🌑 Dark":     {"paper":"#1e293b","grid":"#334155","text":"#94a3b8","muted":"#64748b","fg":"#f1f5f9","border":"#334155","accent":"#818cf8","card":"#1e293b","bg":"#0f172a"},
    "🌊 Ocean":    {"paper":"#f0f9ff","grid":"#bae6fd","text":"#0369a1","muted":"#38bdf8","fg":"#0c4a6e","border":"#bae6fd","accent":"#0284c7","card":"#ffffff","bg":"#f0f9ff"},
    "🌿 Forest":   {"paper":"#f0fdf4","grid":"#bbf7d0","text":"#15803d","muted":"#4ade80","fg":"#14532d","border":"#bbf7d0","accent":"#16a34a","card":"#ffffff","bg":"#f0fdf4"},
    "🌅 Sunset":   {"paper":"#fff7ed","grid":"#fed7aa","text":"#c2410c","muted":"#fb923c","fg":"#7c2d12","border":"#fed7aa","accent":"#ea580c","card":"#ffffff","bg":"#fff7ed"},
    "🌙 Midnight": {"paper":"#13131f","grid":"#1e1e3f","text":"#a5b4fc","muted":"#4f4f7a","fg":"#e2e2ff","border":"#1e1e3f","accent":"#7c3aed","card":"#13131f","bg":"#0d0d1a"},
    "🌸 Rose":     {"paper":"#fff1f2","grid":"#fecdd3","text":"#be123c","muted":"#fb7185","fg":"#881337","border":"#fecdd3","accent":"#e11d48","card":"#ffffff","bg":"#fff1f2"},
    "⬜ Slate":    {"paper":"#ffffff","grid":"#e2e8f0","text":"#475569","muted":"#94a3b8","fg":"#1e293b","border":"#cbd5e1","accent":"#64748b","card":"#ffffff","bg":"#f8fafc"},
}

def _t() -> dict:
    name = st.session_state.get("theme_name", "☀️ Light")
    return _THEME_PALETTES.get(name, _THEME_PALETTES["☀️ Light"])

def _fmt(fig: go.Figure, height: int = 360) -> go.Figure:
    t = _t()
    fig.update_layout(
        paper_bgcolor=t["paper"], plot_bgcolor=t["paper"],
        font=dict(color=t["text"], family="Plus Jakarta Sans, sans-serif"),
        xaxis=dict(showgrid=False, tickcolor=t["border"], linecolor=t["border"], tickfont=dict(color=t["muted"])),
        yaxis=dict(showgrid=True, gridcolor=t["grid"], zeroline=False, tickfont=dict(color=t["muted"])),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=t["text"]), bordercolor="rgba(0,0,0,0)"),
        margin=dict(t=52, b=16, l=0, r=0), height=height,
        title_font=dict(color=t["text"], size=13, family="Plus Jakarta Sans"),
    )
    return fig


def _card(html: str):
    t = _t()
    st.markdown(
        f"<div style='background:{t['card']};border:1px solid {t['border']};border-radius:14px;"
        f"padding:1.1rem 1.3rem;margin-bottom:0.75rem;box-shadow:0 2px 8px rgba(0,0,0,0.04);'>"
        f"{html}</div>",
        unsafe_allow_html=True
    )


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df2 = df.copy()
    df2[Columns.DATE] = pd.to_datetime(df2[Columns.DATE], errors="coerce")
    df2 = df2.dropna(subset=[Columns.DATE])
    df2[Columns.PRICE_PAID] = pd.to_numeric(df2[Columns.PRICE_PAID], errors="coerce").fillna(0)
    df2["YM"]      = df2[Columns.DATE].dt.to_period("M").astype(str)
    df2["Year"]    = df2[Columns.DATE].dt.year
    df2["Month"]   = df2[Columns.DATE].dt.month
    df2["DayName"] = df2[Columns.DATE].dt.day_name()
    df2["Week"]    = df2[Columns.DATE].dt.isocalendar().week.astype(int)
    df2["Quarter"] = df2[Columns.DATE].dt.quarter
    return df2


# ═══════════════════════════════════════════════════════════════════════════════
#  1. SPENDING HOTSPOTS  — WHERE are you spending the most?
# ═══════════════════════════════════════════════════════════════════════════════

def hotspot_analysis(df: pd.DataFrame):
    """Full 'Where am I spending most?' dashboard — category, shop, brand, item."""
    st.subheader("🔥 Spending Hotspots")
    st.caption("Pinpointing exactly where your money is going.")

    if df.empty:
        st.info("No data available.")
        return

    df2 = _prepare(df)
    t   = _t()

    tab1, tab2, tab3, tab4 = st.tabs(["📂 Category", "🏪 Shop", "🏷️ Brand", "🛒 Item"])

    # ── Category hotspot ──────────────────────────────────────────────────────
    with tab1:
        _category_hotspot(df2, t)

    # ── Shop hotspot ──────────────────────────────────────────────────────────
    with tab2:
        _shop_hotspot(df2, t)

    # ── Brand hotspot ─────────────────────────────────────────────────────────
    with tab3:
        _brand_hotspot(df2, t)

    # ── Item hotspot ──────────────────────────────────────────────────────────
    with tab4:
        _item_hotspot(df2, t)


def _category_hotspot(df2: pd.DataFrame, t: dict):
    if Columns.CATEGORY not in df2.columns:
        st.info("No category data.")
        return

    agg = (df2.groupby(Columns.CATEGORY)[Columns.PRICE_PAID]
           .agg(["sum", "count", "mean"]).reset_index()
           .rename(columns={"sum": "Total", "count": "Txns", "mean": "AvgTxn"})
           .sort_values("Total", ascending=False))

    total_all = agg["Total"].sum()
    agg["Share%"] = (agg["Total"] / total_all * 100).round(1)

    # Monthly trend per category
    monthly_cat = (df2.groupby(["YM", Columns.CATEGORY])[Columns.PRICE_PAID]
                   .sum().reset_index())

    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        # Treemap
        fig = px.treemap(
            agg, path=[Columns.CATEGORY], values="Total",
            color="Total", color_continuous_scale="Viridis",
            title="Category Spending Treemap",
            custom_data=["Share%", "AvgTxn", "Txns"],
        )
        fig.update_traces(
            hovertemplate="<b>%{label}</b><br>Total: %{value:,.0f} SEK<br>"
                          "Share: %{customdata[0]:.1f}%<br>"
                          "Avg txn: %{customdata[1]:,.0f} SEK<br>"
                          "Transactions: %{customdata[2]}<extra></extra>"
        )
        fig.update_layout(paper_bgcolor=t["paper"], height=340,
                          font=dict(color=t["text"], family="Plus Jakarta Sans"),
                          margin=dict(t=48, b=8, l=0, r=0))
        st.plotly_chart(fig, config={"displayModeBar": False})

    with col_right:
        st.markdown(f"<div style='font-weight:700;color:{t['fg']};margin-bottom:0.5rem;'>Top Categories</div>",
                    unsafe_allow_html=True)
        for _, row in agg.head(8).iterrows():
            pct = row["Share%"]
            bar_color = DANGER if pct > 30 else WARNING if pct > 15 else INFO
            st.markdown(
                f"""<div style='margin-bottom:0.5rem;'>
                    <div style='display:flex;justify-content:space-between;font-size:0.85rem;color:{t["fg"]};'>
                        <span><b>{row[Columns.CATEGORY]}</b></span>
                        <span>{row["Total"]:,.0f} SEK &nbsp;·&nbsp; <span style='color:{t["muted"]}'>{pct:.1f}%</span></span>
                    </div>
                    <div style='background:{t["border"]};border-radius:4px;height:6px;margin-top:4px;'>
                        <div style='background:{bar_color};width:{min(pct*3.2,100):.0f}%;height:6px;border-radius:4px;'></div>
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )

    # Category growth over time
    st.markdown("---")
    st.markdown(f"<b style='color:{t['fg']}'>Category spending over time</b>", unsafe_allow_html=True)
    top_cats = agg.head(6)[Columns.CATEGORY].tolist()
    pivot = (monthly_cat[monthly_cat[Columns.CATEGORY].isin(top_cats)]
             .pivot_table(index="YM", columns=Columns.CATEGORY, values=Columns.PRICE_PAID, aggfunc="sum")
             .fillna(0).reset_index().sort_values("YM"))

    fig2 = go.Figure()
    for i, cat in enumerate(top_cats):
        if cat in pivot.columns:
            fig2.add_trace(go.Scatter(
                x=pivot["YM"], y=pivot[cat], name=cat, mode="lines+markers",
                line=dict(color=PALETTE[i % len(PALETTE)], width=2),
                marker=dict(size=4),
                hovertemplate=f"<b>{cat}</b><br>%{{x}}<br>%{{y:,.0f}} SEK<extra></extra>",
            ))
    fig2.update_layout(title="Category Spending Trend")
    _fmt(fig2, 300)
    st.plotly_chart(fig2, config={"displayModeBar": False})


def _shop_hotspot(df2: pd.DataFrame, t: dict):
    shop_col = Columns.SHOP if hasattr(Columns, "SHOP") and Columns.SHOP in df2.columns else "Shop"
    if shop_col not in df2.columns or df2[shop_col].isna().all():
        st.info("No shop data found. Make sure the 'Shop' column is populated.")
        return

    agg = (df2.groupby(shop_col)[Columns.PRICE_PAID]
           .agg(["sum", "count", "mean"]).reset_index()
           .rename(columns={"sum": "Total", "count": "Visits", "mean": "AvgSpend"})
           .sort_values("Total", ascending=False))

    total_all = agg["Total"].sum()
    agg["Share%"] = (agg["Total"] / total_all * 100).round(1)

    col1, col2 = st.columns(2)

    with col1:
        fig = go.Figure(go.Bar(
            y=agg.head(12)[shop_col][::-1],
            x=agg.head(12)["Total"][::-1],
            orientation="h",
            marker_color=PALETTE[0],
            opacity=0.85,
            hovertemplate="<b>%{y}</b><br>Total: %{x:,.0f} SEK<extra></extra>",
        ))
        fig.update_layout(title="Top Shops by Total Spend")
        _fmt(fig, 380)
        st.plotly_chart(fig, config={"displayModeBar": False})

    with col2:
        fig2 = go.Figure(go.Bar(
            y=agg.head(12)[shop_col][::-1],
            x=agg.head(12)["AvgSpend"][::-1],
            orientation="h",
            marker_color=PALETTE[1],
            opacity=0.85,
            hovertemplate="<b>%{y}</b><br>Avg per visit: %{x:,.0f} SEK<extra></extra>",
        ))
        fig2.update_layout(title="Top Shops by Avg Spend per Visit")
        _fmt(fig2, 380)
        st.plotly_chart(fig2, config={"displayModeBar": False})

    # Table summary
    st.markdown("#### 🗂️ Shop Summary")
    display = agg.head(15).copy()
    display["Total"]    = display["Total"].map("{:,.0f} SEK".format)
    display["AvgSpend"] = display["AvgSpend"].map("{:,.0f} SEK".format)
    display["Share%"]   = display["Share%"].map("{:.1f}%".format)
    st.dataframe(display.rename(columns={shop_col: "Shop", "Visits": "Transactions", "AvgSpend": "Avg/Visit"}),
                 width="stretch", hide_index=True)


def _brand_hotspot(df2: pd.DataFrame, t: dict):
    brand_col = Columns.BRAND if hasattr(Columns, "BRAND") and Columns.BRAND in df2.columns else "Brand"
    if brand_col not in df2.columns or df2[brand_col].isna().all():
        st.info("No brand data found. Populate the 'Brand' column for brand analysis.")
        return

    agg = (df2.groupby(brand_col)[Columns.PRICE_PAID]
           .agg(["sum", "count"]).reset_index()
           .rename(columns={"sum": "Total", "count": "Txns"})
           .sort_values("Total", ascending=False).head(20))

    fig = px.bar(
        agg, x=brand_col, y="Total",
        color="Total", color_continuous_scale="Blues",
        title="Brand Spending — Top 20",
        labels={brand_col: "Brand", "Total": "SEK Spent"},
        custom_data=["Txns"],
    )
    fig.update_traces(hovertemplate="<b>%{x}</b><br>Total: %{y:,.0f} SEK<br>Purchases: %{customdata[0]}<extra></extra>")
    _fmt(fig, 360)
    st.plotly_chart(fig, config={"displayModeBar": False})


def _item_hotspot(df2: pd.DataFrame, t: dict):
    item_col = Columns.ITEM if hasattr(Columns, "ITEM") and Columns.ITEM in df2.columns else "Item"
    if item_col not in df2.columns or df2[item_col].isna().all():
        st.info("No item data found.")
        return

    agg = (df2.groupby(item_col)[Columns.PRICE_PAID]
           .agg(["sum", "count", "mean"]).reset_index()
           .rename(columns={"sum": "Total", "count": "Times", "mean": "AvgPrice"})
           .sort_values("Total", ascending=False).head(25))

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"<b style='color:{t['fg']}'>Most Expensive Items (by total spend)</b>", unsafe_allow_html=True)
        fig = go.Figure(go.Bar(
            y=agg.head(12)[item_col][::-1], x=agg.head(12)["Total"][::-1],
            orientation="h", marker_color=PALETTE[0], opacity=0.85,
        ))
        fig.update_layout(title=None); _fmt(fig, 320)
        st.plotly_chart(fig, config={"displayModeBar": False})
    with col2:
        st.markdown(f"<b style='color:{t['fg']}'>Most Frequently Bought</b>", unsafe_allow_html=True)
        freq = agg.sort_values("Times", ascending=False).head(12)
        fig2 = go.Figure(go.Bar(
            y=freq[item_col][::-1], x=freq["Times"][::-1],
            orientation="h", marker_color=PALETTE[2], opacity=0.85,
        ))
        fig2.update_layout(title=None); _fmt(fig2, 320)
        st.plotly_chart(fig2, config={"displayModeBar": False})


# ═══════════════════════════════════════════════════════════════════════════════
#  2. TEMPORAL PATTERNS  — WHEN do you spend most?
# ═══════════════════════════════════════════════════════════════════════════════

def temporal_patterns(df: pd.DataFrame):
    """Day-of-week, monthly timing, and quarter analysis."""
    st.subheader("📆 Spending Patterns — When Do You Spend?")
    if df.empty:
        st.info("No data.")
        return

    df2 = _prepare(df)
    t   = _t()

    col1, col2 = st.columns(2)

    # Day-of-week spending
    with col1:
        dow_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        dow = (df2.groupby("DayName")[Columns.PRICE_PAID].sum()
               .reindex(dow_order).fillna(0).reset_index())
        max_val = dow[Columns.PRICE_PAID].max()
        dow["color"] = dow[Columns.PRICE_PAID].apply(
            lambda x: DANGER if x == max_val else (WARNING if x >= max_val * 0.75 else PALETTE[0])
        )
        fig = go.Figure(go.Bar(
            x=dow["DayName"], y=dow[Columns.PRICE_PAID],
            marker_color=dow["color"], opacity=0.85,
            hovertemplate="<b>%{x}</b><br>%{y:,.0f} SEK<extra></extra>",
        ))
        fig.update_layout(title="Spending by Day of Week")
        _fmt(fig, 300)
        st.plotly_chart(fig, config={"displayModeBar": False})

    # Day-of-month heatmap
    with col2:
        dom = df2.copy()
        dom["Dom"] = dom[Columns.DATE].dt.day
        dom_agg = dom.groupby("Dom")[Columns.PRICE_PAID].sum().reset_index()
        fig2 = go.Figure(go.Bar(
            x=dom_agg["Dom"], y=dom_agg[Columns.PRICE_PAID],
            marker_color=PALETTE[1], opacity=0.85,
            hovertemplate="<b>Day %{x}</b><br>%{y:,.0f} SEK<extra></extra>",
        ))
        fig2.update_layout(title="Spending by Day of Month")
        _fmt(fig2, 300)
        st.plotly_chart(fig2, config={"displayModeBar": False})

    # Quarter breakdown
    st.markdown("---")
    st.markdown(f"<b style='color:{t['fg']}'>Quarterly Spending</b>", unsafe_allow_html=True)
    q_agg = df2.groupby(["Year","Quarter"])[Columns.PRICE_PAID].sum().reset_index()
    q_agg["Label"] = q_agg["Year"].astype(str) + " Q" + q_agg["Quarter"].astype(str)
    fig3 = go.Figure(go.Bar(
        x=q_agg["Label"], y=q_agg[Columns.PRICE_PAID],
        marker_color=PALETTE[3], opacity=0.85,
        hovertemplate="<b>%{x}</b><br>%{y:,.0f} SEK<extra></extra>",
    ))
    fig3.update_layout(title="Quarterly Spending")
    _fmt(fig3, 260)
    st.plotly_chart(fig3, config={"displayModeBar": False})

    # Insight callout
    if not dow.empty:
        peak_day = dow.loc[dow[Columns.PRICE_PAID].idxmax(), "DayName"]
        peak_amount = dow[Columns.PRICE_PAID].max()
        _card(f"""
            <div style='font-size:1rem;font-weight:700;color:{t['fg']};'>⚡ Pattern Insight</div>
            <div style='margin-top:0.4rem;color:{t['text']};font-size:0.92rem;'>
                Your heaviest spending day is <b>{peak_day}</b>
                ({peak_amount:,.0f} SEK total historically).
                Consider reviewing your {peak_day.lower()} expenses for quick savings.
            </div>
        """)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. BUDGET INTELLIGENCE  — Smart budgeting recommendations
# ═══════════════════════════════════════════════════════════════════════════════

def budget_intelligence(df: pd.DataFrame):
    """AI-powered budget recommendations and spending velocity."""
    st.subheader("🧠 Budget Intelligence")
    st.caption("Data-driven recommendations to help you spend smarter.")

    if df.empty:
        st.info("No data available.")
        return

    df2 = _prepare(df)
    t   = _t()

    now = pd.Timestamp.now()
    current_ym = now.to_period("M").strftime("%Y-%m")
    days_in_month = pd.Period(current_ym, "M").days_in_month
    day_of_month  = now.day
    days_left     = days_in_month - day_of_month

    this_month = df2[df2["YM"] == current_ym]
    last_month_ym = (now - pd.DateOffset(months=1)).to_period("M").strftime("%Y-%m")
    last_month = df2[df2["YM"] == last_month_ym]

    # ── Velocity cards ────────────────────────────────────────────────────────
    st.markdown("#### ⚡ Spending Velocity (This Month)")
    total_this_month = this_month[Columns.PRICE_PAID].sum() if not this_month.empty else 0
    total_last_month = last_month[Columns.PRICE_PAID].sum() if not last_month.empty else 0

    # Daily burn rate
    daily_rate = total_this_month / day_of_month if day_of_month > 0 else 0
    projected  = daily_rate * days_in_month
    last_daily = total_last_month / days_in_month if days_in_month > 0 else 0

    # 3-month average for comparison
    months_hist = (df2.groupby("YM")[Columns.PRICE_PAID].sum()
                   .sort_index().tail(4).head(3))
    avg_3mo = months_hist.mean() if not months_hist.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        delta = f"{((daily_rate - last_daily) / last_daily * 100):+.1f}% vs last month" if last_daily else None
        st.metric("Daily Burn Rate", f"{daily_rate:,.0f} SEK/day", delta=delta)
    with c2:
        proj_delta = f"{((projected - avg_3mo) / avg_3mo * 100):+.1f}% vs 3-mo avg" if avg_3mo else None
        st.metric("Month Projection", f"{projected:,.0f} SEK", delta=proj_delta, delta_color="inverse")
    with c3:
        st.metric("Spent So Far", f"{total_this_month:,.0f} SEK")
    with c4:
        st.metric("Days Left", str(days_left), delta=f"{days_left * daily_rate:,.0f} SEK projected")

    # ── Velocity gauge ────────────────────────────────────────────────────────
    if avg_3mo > 0:
        velocity_ratio = (projected / avg_3mo) * 100
        gauge_color = DANGER if velocity_ratio > 115 else (WARNING if velocity_ratio > 100 else OK)
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=velocity_ratio,
            delta={"reference": 100, "valueformat": ".1f", "suffix": "%"},
            title={"text": "Spend Velocity vs 3-Month Average", "font": {"size": 13, "color": t["text"]}},
            gauge={
                "axis": {"range": [0, 150], "tickcolor": t["muted"], "tickfont": {"color": t["muted"]}},
                "bar":  {"color": gauge_color},
                "bgcolor": t["grid"],
                "steps": [
                    {"range": [0,   85],  "color": "rgba(34,197,94,0.12)"},
                    {"range": [85,  100], "color": "rgba(245,158,11,0.12)"},
                    {"range": [100, 115], "color": "rgba(245,158,11,0.18)"},
                    {"range": [115, 150], "color": "rgba(239,68,68,0.15)"},
                ],
                "threshold": {"line": {"color": DANGER, "width": 2}, "thickness": 0.75, "value": 115},
            },
            number={"suffix": "%", "font": {"size": 28, "color": t["fg"]}},
        ))
        fig.update_layout(
            paper_bgcolor=t["paper"], font=dict(color=t["text"]),
            height=240, margin=dict(t=40, b=8, l=40, r=40),
        )
        st.plotly_chart(fig, config={"displayModeBar": False})

    # ── Recommendations ───────────────────────────────────────────────────────
    st.markdown("#### 💡 Smart Recommendations")
    recs = _generate_recommendations(df2, this_month, last_month, avg_3mo, projected, t)
    for rec in recs:
        _card(rec)

    # ── Category budget health ─────────────────────────────────────────────────
    st.markdown("#### 📊 Category Budget Health")
    _category_budget_health(df2, this_month, last_month, t)
    ai_monthly_report(df)


def _generate_recommendations(df2, this_month, last_month, avg_3mo, projected, t) -> list:
    recs = []
    fg, acc = t["fg"], t["accent"]

    if avg_3mo > 0 and projected > avg_3mo * 1.15:
        over_pct = ((projected - avg_3mo) / avg_3mo * 100)
        recs.append(f"""
            <span style='font-size:1.1rem;'>🚨</span>
            <b style='color:{DANGER}'>Overspending Alert</b><br>
            <span style='color:{t["text"]};font-size:0.9rem;'>
                You're on track to spend <b>{projected:,.0f} SEK</b> this month —
                <b>{over_pct:.1f}% above</b> your 3-month average of {avg_3mo:,.0f} SEK.
                Consider slowing down purchases in the next {(pd.Timestamp.now() - pd.Timestamp.now().to_period('M').to_timestamp()).days} days.
            </span>
        """)

    if not this_month.empty and Columns.CATEGORY in this_month.columns:
        cat_this  = this_month.groupby(Columns.CATEGORY)[Columns.PRICE_PAID].sum()
        cat_last  = last_month.groupby(Columns.CATEGORY)[Columns.PRICE_PAID].sum() if not last_month.empty else pd.Series(dtype=float)
        for cat in cat_this.index:
            if cat in cat_last.index and cat_last[cat] > 0:
                pct_change = (cat_this[cat] - cat_last[cat]) / cat_last[cat] * 100
                if pct_change > 50 and cat_this[cat] > 500:
                    recs.append(f"""
                        <span style='font-size:1.1rem;'>📈</span>
                        <b style='color:{WARNING}'>{cat} Spike Detected</b><br>
                        <span style='color:{t["text"]};font-size:0.9rem;'>
                            Your <b>{cat}</b> spending jumped <b>+{pct_change:.0f}%</b> vs last month
                            ({cat_this[cat]:,.0f} vs {cat_last[cat]:,.0f} SEK).
                            Review recent {cat.lower()} purchases.
                        </span>
                    """)

    if not df2.empty:
        monthly = df2.groupby("YM")[Columns.PRICE_PAID].sum().sort_index()
        if len(monthly) >= 3:
            trend = np.polyfit(range(len(monthly)), monthly.values, 1)[0]
            if trend > 200:
                recs.append(f"""
                    <span style='font-size:1.1rem;'>📉</span>
                    <b style='color:{PALETTE[0]}'>Rising Spending Trend</b><br>
                    <span style='color:{t["text"]};font-size:0.9rem;'>
                        Your monthly spending has been growing by ~{trend:,.0f} SEK/month on average.
                        If unchecked, annual extra spend = <b>{trend*12:,.0f} SEK</b>.
                    </span>
                """)

    if not this_month.empty:
        shop_col = "Shop" if "Shop" in this_month.columns else None
        if shop_col and not this_month[shop_col].isna().all():
            top_shop = this_month.groupby(shop_col)[Columns.PRICE_PAID].sum().idxmax()
            top_amt  = this_month.groupby(shop_col)[Columns.PRICE_PAID].sum().max()
            recs.append(f"""
                <span style='font-size:1.1rem;'>🏪</span>
                <b style='color:{acc}'>Top Shop This Month</b><br>
                <span style='color:{t["text"]};font-size:0.9rem;'>
                    <b>{top_shop}</b> is your biggest expense source this month at <b>{top_amt:,.0f} SEK</b>.
                    Consider whether all purchases there are necessary.
                </span>
            """)

    if not recs:
        recs.append(f"""
            <span style='font-size:1.1rem;'>✅</span>
            <b style='color:{OK}'>Spending Looks Healthy!</b><br>
            <span style='color:{t["text"]};font-size:0.9rem;'>
                No major alerts this month. Keep tracking to maintain this trajectory.
            </span>
        """)

    return recs


def _category_budget_health(df2, this_month, last_month, t):
    if this_month.empty or Columns.CATEGORY not in this_month.columns:
        st.info("No category data for the current month.")
        return

    cat_this = this_month.groupby(Columns.CATEGORY)[Columns.PRICE_PAID].sum().sort_values(ascending=False)
    cat_last = (last_month.groupby(Columns.CATEGORY)[Columns.PRICE_PAID].sum()
                if not last_month.empty else pd.Series(dtype=float))

    rows = []
    for cat, amt in cat_this.items():
        prev = cat_last.get(cat, 0)
        change = ((amt - prev) / prev * 100) if prev > 0 else None
        rows.append({"Category": cat, "This Month": amt, "Last Month": prev,
                     "Change%": change})

    df_tbl = pd.DataFrame(rows).sort_values("This Month", ascending=False)

    # Visual bars
    max_val = df_tbl["This Month"].max()
    for _, row in df_tbl.iterrows():
        pct  = (row["This Month"] / max_val * 100) if max_val > 0 else 0
        chg  = row["Change%"]
        chg_html = ""
        if chg is not None:
            arrow = "↑" if chg > 0 else "↓"
            color = DANGER if chg > 20 else (WARNING if chg > 0 else OK)
            chg_html = f"<span style='color:{color};font-size:0.8rem;margin-left:0.5rem;'>{arrow} {abs(chg):.1f}%</span>"
        bar_color = DANGER if pct > 80 else (WARNING if pct > 50 else PALETTE[0])

        st.markdown(
            f"""<div style='margin-bottom:0.6rem;'>
                <div style='display:flex;justify-content:space-between;font-size:0.87rem;color:{t["fg"]};'>
                    <span><b>{row["Category"]}</b>{chg_html}</span>
                    <span style='color:{t["muted"]};'>{row["This Month"]:,.0f} SEK</span>
                </div>
                <div style='background:{t["border"]};border-radius:4px;height:8px;margin-top:5px;'>
                    <div style='background:{bar_color};width:{pct:.0f}%;height:8px;border-radius:4px;
                                transition:width 0.3s ease;'></div>
                </div>
            </div>""",
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  4. SAVINGS OPPORTUNITIES  — Where can you cut back?
# ═══════════════════════════════════════════════════════════════════════════════

def savings_opportunities(df: pd.DataFrame):
    """Identifies realistic areas to save money."""
    st.subheader("💰 Savings Opportunities")
    st.caption("Data-driven areas where reducing spend has the biggest impact.")

    if df.empty:
        st.info("No data available.")
        return

    df2 = _prepare(df)
    t   = _t()

    # Find fastest growing categories vs 3-month baseline
    monthly_cat = (df2.groupby(["YM", Columns.CATEGORY])[Columns.PRICE_PAID]
                   .sum().reset_index().sort_values("YM"))
    recent_yms  = sorted(df2["YM"].unique())
    last3 = recent_yms[-4:-1] if len(recent_yms) >= 4 else recent_yms[:-1]
    curr  = recent_yms[-1]

    baseline = (monthly_cat[monthly_cat["YM"].isin(last3)]
                .groupby(Columns.CATEGORY)[Columns.PRICE_PAID].mean())
    current  = (monthly_cat[monthly_cat["YM"] == curr]
                .groupby(Columns.CATEGORY)[Columns.PRICE_PAID].sum())

    opp = []
    for cat in current.index:
        if cat in baseline.index and baseline[cat] > 100:
            excess   = current[cat] - baseline[cat]
            excess_p = (excess / baseline[cat]) * 100
            if excess > 200 and excess_p > 15:
                annual  = excess * 12
                opp.append({
                    "Category":    cat,
                    "Current":     current[cat],
                    "Baseline":    baseline[cat],
                    "Excess":      excess,
                    "Excess%":     excess_p,
                    "Annual Save": annual,
                })

    opp_df = pd.DataFrame(opp).sort_values("Excess", ascending=False) if opp else pd.DataFrame()

    if opp_df.empty:
        _card(f"""
            <span style='font-size:1.2rem;'>✅</span>
            <b style='color:{OK}'>No Major Excess Spending Found</b><br>
            <span style='color:{t["text"]};font-size:0.9rem;'>
                Your recent month spending is in line with your personal 3-month baseline. Keep it up!
            </span>
        """)
    else:
        total_annual_savings = opp_df["Annual Save"].sum()
        st.markdown(
            f"<div style='font-size:1.1rem;font-weight:700;color:{DANGER};margin-bottom:0.75rem;'>"
            f"🎯 Potential Annual Savings: {total_annual_savings:,.0f} SEK</div>",
            unsafe_allow_html=True,
        )

        for _, row in opp_df.iterrows():
            _card(f"""
                <div style='display:flex;justify-content:space-between;align-items:center;'>
                    <div>
                        <b style='color:{t["fg"]};font-size:0.95rem;'>{row["Category"]}</b>
                        <span style='color:{DANGER};font-size:0.82rem;margin-left:0.4rem;'>
                            ↑ {row["Excess%"]:.0f}% above average
                        </span><br>
                        <span style='color:{t["muted"]};font-size:0.82rem;'>
                            Avg: {row["Baseline"]:,.0f} SEK/mo · Current: {row["Current"]:,.0f} SEK/mo
                        </span>
                    </div>
                    <div style='text-align:right;'>
                        <div style='font-weight:700;color:{DANGER};font-size:1rem;'>
                            +{row["Excess"]:,.0f} SEK
                        </div>
                        <div style='color:{t["muted"]};font-size:0.78rem;'>
                            = {row["Annual Save"]:,.0f}/yr if corrected
                        </div>
                    </div>
                </div>
            """)

    # Price-per-unit efficiency (if Quantity and PricePerUnit exist)
    ppu_col = "PricePerUnit" if "PricePerUnit" in df2.columns else None
    qty_col = "Quantity"     if "Quantity"     in df2.columns else None
    if ppu_col and qty_col and Columns.CATEGORY in df2.columns:
        st.markdown("---")
        st.markdown("#### 🏷️ Price Efficiency by Category")
        efficiency = (df2.dropna(subset=[ppu_col])
                      .groupby(Columns.CATEGORY)[ppu_col]
                      .mean().reset_index()
                      .rename(columns={ppu_col: "Avg Price/Unit"})
                      .sort_values("Avg Price/Unit", ascending=False).head(12))
        if not efficiency.empty:
            fig = go.Figure(go.Bar(
                y=efficiency[Columns.CATEGORY][::-1],
                x=efficiency["Avg Price/Unit"][::-1],
                orientation="h", marker_color=PALETTE[2], opacity=0.85,
                hovertemplate="<b>%{y}</b><br>Avg price/unit: %{x:,.2f} SEK<extra></extra>",
            ))
            fig.update_layout(title="Average Price per Unit by Category")
            _fmt(fig, 320)
            st.plotly_chart(fig, config={"displayModeBar": False})

    # ── AI savings advice ─────────────────────────────────────────────────────
    if not opp_df.empty:
        st.markdown("---")
        st.markdown("#### 🤖 AI Savings Advice")
        st.caption("Specific, actionable tips based on your actual spending patterns.")
        _ai_savings_advice(opp_df, curr, t)


def _ai_savings_advice(opp_df: pd.DataFrame, curr_month: str, t: dict):
    """
    Call AI with excess-spend data and render actionable tips per category.
    Adds top items bought in each overspent category for richer advice.
    """
    import json
    from ai_insights import _get_keys, _call_ai

    keys = _get_keys()
    if not any(keys.values()):
        st.info("Add a GEMINI_API_KEY to secrets.toml to get AI-powered savings tips.")
        return

    cache_key = f"ai_savings_{curr_month}"
    if cache_key not in st.session_state:
        if not st.button("✨ Get AI Savings Tips", key="ai_savings_btn"):
            return

        payload = []
        for _, row in opp_df.iterrows():
            entry = {
                "category":    row["Category"],
                "current_mo":  round(row["Current"], 2),
                "avg_3mo":     round(row["Baseline"], 2),
                "excess":      round(row["Excess"], 2),
                "excess_pct":  round(row["Excess%"], 1),
                "annual_save": round(row["Annual Save"], 2),
            }
            if row.get("TopItems"):
                entry["top_items_this_month"] = row["TopItems"]
            payload.append(entry)

        system = (
            "You are a personal finance coach. "
            "The user will give you categories where they overspent vs their 3-month average. "
            "For each category, give 2-3 concrete, specific actions they can take to reduce spending. "
            "Be direct and practical. Reference the actual items where provided. "
            "Format your response as a simple list grouped by category. "
            "Currency is SEK. Keep the whole response under 300 words."
        )
        user = (
            f"Here are my overspent categories for {curr_month}:\n"
            f"{json.dumps(payload, indent=2)}\n\n"
            "Give me specific actions to cut back in each category."
        )
        with st.spinner("AI is analysing your spending patterns…"):
            text, provider = _call_ai(system, user, keys)

        if text:
            st.session_state[cache_key] = (text, provider)
        else:
            st.error("No AI provider responded. Check your API keys.")
            return

    if cache_key not in st.session_state:
        return

    text, provider = st.session_state[cache_key]
    st.markdown(
        f"<div style='background:{t["card"]};border:1px solid {t["border"]};"
        f"border-left:4px solid #6366f1;border-radius:12px;"
        f"padding:1rem 1.3rem;font-size:0.9rem;color:{t["fg"]};line-height:1.7;'>"
        + text.replace("\n", "<br>") +
        f"<div style='margin-top:0.6rem;font-size:0.72rem;color:{t["muted"]};'>"
        f"Generated by {provider}</div></div>",
        unsafe_allow_html=True,
    )
    col1, _ = st.columns([1, 5])
    with col1:
        if st.button("🔄 Refresh", key="refresh_savings_ai"):
            st.session_state.pop(cache_key, None)
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  5. SMART SUMMARY KPI ROW  — enhanced version
# ═══════════════════════════════════════════════════════════════════════════════

def smart_kpi_row(df: pd.DataFrame):
    """Enhanced KPI row with trend context and health indicators."""
    if df.empty:
        return

    df2 = _prepare(df)
    t   = _t()

    now      = pd.Timestamp.now()
    curr_ym  = now.to_period("M").strftime("%Y-%m")
    prev_ym  = (now - pd.DateOffset(months=1)).to_period("M").strftime("%Y-%m")

    this_mo  = df2[df2["YM"] == curr_ym][Columns.PRICE_PAID].sum()
    prev_mo  = df2[df2["YM"] == prev_ym][Columns.PRICE_PAID].sum()
    total    = df2[Columns.PRICE_PAID].sum()
    avg_mo   = df2.groupby("YM")[Columns.PRICE_PAID].sum().mean()
    n_cats   = df2[Columns.CATEGORY].nunique() if Columns.CATEGORY in df2.columns else 0
    n_txns   = len(df2[df2["YM"] == curr_ym])

    mom_pct  = ((this_mo - prev_mo) / prev_mo * 100) if prev_mo else None
    mom_clr  = DANGER if (mom_pct or 0) > 10 else (WARNING if (mom_pct or 0) > 0 else OK)

    cards = [
        {
            "icon": "💰", "label": "This Month",
            "value": f"{this_mo:,.0f} SEK",
            "sub": (f"<span style='color:{mom_clr}'>{mom_pct:+.1f}% vs last month</span>" if mom_pct is not None else ""),
        },
        {
            "icon": "📊", "label": "Monthly Average",
            "value": f"{avg_mo:,.0f} SEK",
            "sub": f"<span style='color:{t['muted']}'>All-time avg</span>",
        },
        {
            "icon": "🔢", "label": "Transactions (Month)",
            "value": str(n_txns),
            "sub": f"<span style='color:{t['muted']}'>{total:,.0f} SEK lifetime</span>",
        },
        {
            "icon": "📂", "label": "Active Categories",
            "value": str(n_cats),
            "sub": f"<span style='color:{t['muted']}'>Across all time</span>",
        },
    ]

    cols = st.columns(len(cards))
    for col, card in zip(cols, cards):
        col.markdown(
            f"""<div style='background:{t["card"]};border:1px solid {t["border"]};border-radius:14px;
                            padding:1.1rem 1.2rem;box-shadow:0 2px 12px rgba(0,0,0,0.05);'>
                    <div style='font-size:0.7rem;font-weight:700;text-transform:uppercase;
                                letter-spacing:0.08em;color:{t["muted"]};margin-bottom:0.3rem;'>
                        {card["icon"]} {card["label"]}
                    </div>
                    <div style='font-size:1.65rem;font-weight:800;color:{t["fg"]};line-height:1.15;
                                font-family:"Plus Jakarta Sans",sans-serif;'>
                        {card["value"]}
                    </div>
                    <div style='margin-top:0.25rem;font-size:0.78rem;'>{card["sub"]}</div>
                </div>""",
            unsafe_allow_html=True,
        )
