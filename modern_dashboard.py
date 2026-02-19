# modern_dashboard.py
"""
Redesigned expense tracker dashboard — refined dark-luxury aesthetic,
fluid layout, rich typography, and smooth interactions.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, datetime
from config import Columns


# ============================================================
# THEME & GLOBAL CSS
# ============================================================
def inject_global_styles():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

    /* ── Base ── */
    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }

    .stApp {
        background: linear-gradient(135deg, #060b14 0%, #0d1524 50%, #060b14 100%);
        background-attachment: fixed;
    }

    /* ── Remove Streamlit chrome ── */
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1400px; }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: #0a1628 !important;
        border-right: 1px solid #1e3a5f;
    }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label {
        color: #94a3b8 !important;
    }

    /* ── Inputs ── */
    .stTextInput > div > input,
    .stNumberInput > div > input,
    .stSelectbox > div > div,
    .stDateInput > div > input {
        background: #0f1f35 !important;
        border: 1px solid #1e3a5f !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
        font-family: 'DM Sans', sans-serif !important;
    }
    .stTextInput > div > input:focus,
    .stNumberInput > div > input:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        background: #6366f1;
        color: white;
        border: none;
        border-radius: 8px;
        font-family: 'DM Sans', sans-serif;
        font-weight: 600;
        letter-spacing: 0.02em;
        transition: all 0.2s;
        padding: 0.5rem 1.2rem;
    }
    .stButton > button:hover {
        background: #818cf8;
        transform: translateY(-1px);
        box-shadow: 0 4px 15px rgba(99,102,241,0.35);
    }
    .stButton > button[kind="secondary"] {
        background: transparent;
        border: 1px solid #334155;
        color: #94a3b8;
    }
    .stButton > button[kind="secondary"]:hover {
        border-color: #6366f1;
        color: #a5b4fc;
        background: rgba(99,102,241,0.08);
    }

    /* ── Expander ── */
    details {
        background: #0d1e35;
        border: 1px solid #1e3a5f;
        border-radius: 10px;
        padding: 0.25rem;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        background: #0a1628;
        border-radius: 10px;
        border: 1px solid #1e3a5f;
        gap: 4px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 8px;
        color: #64748b;
        font-weight: 500;
        transition: all 0.2s;
    }
    .stTabs [aria-selected="true"] {
        background: #1e293b !important;
        color: #a5b4fc !important;
    }

    /* ── Dataframe ── */
    [data-testid="stDataFrame"] {
        border: 1px solid #1e3a5f;
        border-radius: 10px;
        overflow: hidden;
    }

    /* ── Metrics ── */
    [data-testid="stMetric"] {
        background: #0d1e35;
        border: 1px solid #1e3a5f;
        border-radius: 12px;
        padding: 1rem 1.25rem;
    }
    [data-testid="stMetricLabel"] { color: #64748b !important; font-size: 0.8rem; }
    [data-testid="stMetricValue"] { color: #e2e8f0 !important; font-size: 1.6rem; font-weight: 700; }

    /* ── Alerts ── */
    .stSuccess { background: rgba(34,197,94,0.1); border-color: #22c55e; border-radius: 8px; }
    .stError   { background: rgba(239,68,68,0.1);  border-color: #ef4444; border-radius: 8px; }
    .stWarning { background: rgba(245,158,11,0.1); border-color: #f59e0b; border-radius: 8px; }
    .stInfo    { background: rgba(99,102,241,0.1); border-color: #6366f1; border-radius: 8px; }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0a1628; }
    ::-webkit-scrollbar-thumb { background: #1e3a5f; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #6366f1; }

    /* ── Divider ── */
    hr { border-color: #1e3a5f !important; }
    </style>
    """, unsafe_allow_html=True)


# ============================================================
# HEADER
# ============================================================
def render_header(title: str = "💳 Expense Tracker", subtitle: str = ""):
    st.markdown(f"""
    <div style="padding: 1.25rem 0 1rem 0; border-bottom: 1px solid #1e3a5f; margin-bottom: 1.5rem;">
        <div style="font-size: 0.75rem; font-weight: 600; letter-spacing: 0.15em; color: #6366f1; text-transform: uppercase; margin-bottom: 0.25rem;">
            Personal Finance
        </div>
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div>
                <h1 style="margin: 0; font-size: 1.9rem; font-weight: 700; color: #f1f5f9; letter-spacing: -0.03em;">{title}</h1>
                {f'<p style="margin: 0.25rem 0 0; color: #64748b; font-size: 0.9rem;">{subtitle}</p>' if subtitle else ''}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# KPI CARDS
# ============================================================
def render_kpi_cards(df: pd.DataFrame):
    """Render KPI summary cards with sparklines."""
    if df.empty:
        return

    df2 = df.copy()
    df2[Columns.DATE] = pd.to_datetime(df2[Columns.DATE], errors="coerce")
    today = datetime.now()

    # Current month
    cm = df2[(df2[Columns.DATE].dt.year == today.year) & (df2[Columns.DATE].dt.month == today.month)]
    # Previous month
    prev_month = (today.month - 2) % 12 + 1
    prev_year = today.year if today.month > 1 else today.year - 1
    pm = df2[(df2[Columns.DATE].dt.year == prev_year) & (df2[Columns.DATE].dt.month == prev_month)]

    total_all_time = df2[Columns.PRICE_PAID].sum()
    this_month_total = cm[Columns.PRICE_PAID].sum()
    prev_month_total = pm[Columns.PRICE_PAID].sum()
    mom_delta_pct = ((this_month_total - prev_month_total) / prev_month_total * 100) if prev_month_total > 0 else 0
    avg_transaction = df2[Columns.PRICE_PAID].mean()
    num_categories = df2[Columns.CATEGORY].nunique()
    num_transactions = len(df2)

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "This Month",
        f"{this_month_total:,.0f} SEK",
        delta=f"{mom_delta_pct:+.1f}% vs last month",
        delta_color="inverse"
    )
    col2.metric("Total All-Time", f"{total_all_time:,.0f} SEK")
    col3.metric("Avg Transaction", f"{avg_transaction:,.0f} SEK", f"{num_transactions} transactions")
    col4.metric("Active Categories", str(num_categories))


# ============================================================
# CATEGORY DONUT
# ============================================================
def render_category_donut(df: pd.DataFrame, title: str = "Spending by Category"):
    if df.empty:
        return
    agg = df.groupby(Columns.CATEGORY)[Columns.PRICE_PAID].sum().reset_index().sort_values(Columns.PRICE_PAID, ascending=False)
    agg = pd.concat([agg.head(7), pd.DataFrame([{Columns.CATEGORY: "Other", Columns.PRICE_PAID: agg.iloc[7:][Columns.PRICE_PAID].sum()}])]) if len(agg) > 7 else agg

    colors = ["#6366f1","#22d3ee","#f59e0b","#22c55e","#f97316","#ec4899","#a855f7","#64748b"]

    fig = go.Figure(go.Pie(
        labels=agg[Columns.CATEGORY],
        values=agg[Columns.PRICE_PAID],
        hole=0.62,
        marker=dict(colors=colors[:len(agg)], line=dict(color="#0f172a", width=2)),
        textfont=dict(family="DM Sans", color="#94a3b8"),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} SEK<br>%{percent}<extra></extra>",
    ))

    total = agg[Columns.PRICE_PAID].sum()
    fig.add_annotation(
        text=f"<b>{total:,.0f}</b><br><span style='font-size:12px'>SEK total</span>",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=18, color="#e2e8f0", family="DM Sans")
    )

    fig.update_layout(
        title=dict(text=title, font=dict(color="#94a3b8", size=14, family="DM Sans"), x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(font=dict(color="#64748b", family="DM Sans"), bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=40, b=10, l=0, r=0),
        height=320,
        showlegend=True,
    )
    st.plotly_chart(fig, config={"displayModeBar": False})


# ============================================================
# MONTHLY TREND LINE
# ============================================================
def render_monthly_trend(df: pd.DataFrame):
    if df.empty:
        return
    df2 = df.copy()
    df2[Columns.DATE] = pd.to_datetime(df2[Columns.DATE], errors="coerce")
    df2["YM"] = df2[Columns.DATE].dt.to_period("M").astype(str)
    monthly = df2.groupby("YM")[Columns.PRICE_PAID].sum().reset_index().sort_values("YM")

    fig = go.Figure()

    # Fill area
    fig.add_trace(go.Scatter(
        x=monthly["YM"], y=monthly[Columns.PRICE_PAID],
        fill="tozeroy",
        fillcolor="rgba(99,102,241,0.08)",
        line=dict(color="#6366f1", width=2.5),
        mode="lines+markers",
        marker=dict(size=5, color="#6366f1"),
        hovertemplate="<b>%{x}</b><br>%{y:,.0f} SEK<extra></extra>",
        name="Monthly total"
    ))

    # Rolling average
    if len(monthly) >= 3:
        monthly["Rolling3"] = monthly[Columns.PRICE_PAID].rolling(3).mean()
        fig.add_trace(go.Scatter(
            x=monthly["YM"], y=monthly["Rolling3"],
            line=dict(color="#22d3ee", width=1.5, dash="dot"),
            mode="lines",
            name="3-month avg",
            hovertemplate="<b>%{x}</b><br>Avg: %{y:,.0f} SEK<extra></extra>",
        ))

    fig.update_layout(
        title=dict(text="Monthly Spending Trend", font=dict(color="#94a3b8", size=14), x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#64748b", family="DM Sans"),
        xaxis=dict(showgrid=False, tickcolor="#1e3a5f", linecolor="#1e3a5f"),
        yaxis=dict(showgrid=True, gridcolor="#1e3a5f", zeroline=False),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#64748b")),
        margin=dict(t=40, b=20, l=0, r=0),
        height=300,
    )
    st.plotly_chart(fig, config={"displayModeBar": False})


# ============================================================
# TOP ITEMS TABLE
# ============================================================
def render_top_items(df: pd.DataFrame, n: int = 10):
    if df.empty:
        return
    st.markdown("""
    <div style="font-size:0.85rem; font-weight:600; color:#64748b; letter-spacing:0.08em; 
                text-transform:uppercase; margin-bottom:0.75rem;">
        Top Expenses
    </div>
    """, unsafe_allow_html=True)

    top = (
        df.sort_values(Columns.PRICE_PAID, ascending=False)
        .head(n)[[Columns.DATE, Columns.ITEM, Columns.CATEGORY, Columns.SHOP, Columns.PRICE_PAID]]
        .copy()
    )
    top[Columns.DATE] = pd.to_datetime(top[Columns.DATE], errors="coerce").dt.strftime("%b %d, %Y")
    top[Columns.PRICE_PAID] = top[Columns.PRICE_PAID].apply(lambda x: f"{x:,.2f} SEK")
    st.dataframe(
        top.rename(columns={
            Columns.DATE: "Date", Columns.ITEM: "Item",
            Columns.CATEGORY: "Category", Columns.SHOP: "Shop",
            Columns.PRICE_PAID: "Amount"
        }),
        width="stretch",
        hide_index=True
    )


# ============================================================
# QUICK-ADD SIDEBAR
# ============================================================
def render_quick_add_sidebar():
    """Minimal, polished quick-add form for the sidebar."""
    st.sidebar.markdown("""
    <div style="font-size:0.7rem; font-weight:700; letter-spacing:0.12em; color:#6366f1;
                text-transform:uppercase; padding:0.5rem 0 0.25rem;">
        Quick Add
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# PAGE LAYOUT HELPERS
# ============================================================
def two_col_layout(left_fn, right_fn, ratio=(1, 1)):
    col1, col2 = st.columns(ratio)
    with col1:
        left_fn()
    with col2:
        right_fn()


def card(content_fn, title: str = "", bg: str = "#0d1e35", border: str = "#1e3a5f"):
    """Wrap content in a styled card."""
    st.markdown(f"""
    <div style="background:{bg}; border:1px solid {border}; border-radius:12px; 
                padding:1.25rem 1.25rem 0.5rem; margin-bottom:1rem;">
        {f'<div style="font-size:0.75rem; font-weight:600; color:#64748b; letter-spacing:0.1em; text-transform:uppercase; margin-bottom:0.75rem;">{title}</div>' if title else ''}
    """, unsafe_allow_html=True)
    content_fn()
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# MAIN DASHBOARD PAGE
# ============================================================
def render_main_dashboard(df: pd.DataFrame, save_fn=None, sheet=None):
    inject_global_styles()
    render_header("Expense Tracker", f"Welcome back · {datetime.now().strftime('%B %d, %Y')}")

    if df.empty:
        st.markdown("""
        <div style="text-align:center; padding:4rem 2rem; color:#64748b;">
            <div style="font-size:3rem; margin-bottom:1rem;">📊</div>
            <div style="font-size:1.25rem; color:#94a3b8; font-weight:600;">No expenses yet</div>
            <div style="font-size:0.9rem; margin-top:0.5rem;">Add your first expense using the sidebar →</div>
        </div>
        """, unsafe_allow_html=True)
        return

    # KPI row
    render_kpi_cards(df)
    st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)

    # Main charts row
    col1, col2 = st.columns([1.4, 1])
    with col1:
        render_monthly_trend(df)
    with col2:
        render_category_donut(df)

    st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)

    # Bottom section
    col3, col4 = st.columns([1.4, 1])
    with col3:
        render_top_items(df)
    with col4:
        _render_recent_activity(df)


def _render_recent_activity(df: pd.DataFrame, n: int = 8):
    """Compact recent activity feed."""
    st.markdown("""
    <div style="font-size:0.85rem; font-weight:600; color:#64748b; letter-spacing:0.08em; 
                text-transform:uppercase; margin-bottom:0.75rem;">
        Recent Activity
    </div>
    """, unsafe_allow_html=True)

    recent = df.copy()
    recent[Columns.DATE] = pd.to_datetime(recent[Columns.DATE], errors="coerce")
    recent = recent.sort_values(Columns.DATE, ascending=False).head(n)

    cat_colors = {}
    color_palette = ["#6366f1","#22d3ee","#f59e0b","#22c55e","#f97316","#ec4899","#a855f7"]
    for i, cat in enumerate(df[Columns.CATEGORY].unique()):
        cat_colors[cat] = color_palette[i % len(color_palette)]

    for _, row in recent.iterrows():
        color = cat_colors.get(row.get(Columns.CATEGORY, ""), "#64748b")
        date_str = row[Columns.DATE].strftime("%b %d") if pd.notna(row[Columns.DATE]) else ""
        st.markdown(f"""
        <div style="display:flex; justify-content:space-between; align-items:center;
                    padding:0.5rem 0.75rem; border-radius:8px; margin-bottom:0.35rem;
                    background:#0d1e35; border-left:3px solid {color};">
            <div>
                <div style="color:#e2e8f0; font-size:0.85rem; font-weight:500;">{row.get(Columns.ITEM, '—')}</div>
                <div style="color:#475569; font-size:0.75rem;">{row.get(Columns.CATEGORY, '')} · {date_str}</div>
            </div>
            <div style="color:#f1f5f9; font-weight:600; font-size:0.9rem; font-family:'DM Mono', monospace;">
                {row.get(Columns.PRICE_PAID, 0):,.0f} SEK
            </div>
        </div>
        """, unsafe_allow_html=True)