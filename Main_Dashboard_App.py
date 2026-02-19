# Main_Dashboard_App.py  ── UPGRADED VERSION
# ─────────────────────────────────────────────────────────────
#  Expense Tracker — Full-stack Streamlit Dashboard
#  Upgrades:
#    ✦ Modern glassmorphism-style KPI cards
#    ✦ Spending Intelligence page (hotspots, velocity, savings)
#    ✦ Enhanced Analytics with shop/brand/item breakdown
#    ✦ Cleaner sidebar navigation with icons
#    ✦ Smart budget recommendations
# ─────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, date, timedelta

from config import USE_GOOGLE_SHEETS, DEFAULT_CURRENCY, SUPPORTED_CURRENCIES, Columns
from data_manager import init_storage, load_data, save_data, bump_data_version, clean_data
from ui_components import sidebar_add_expense, filter_section, inline_edit_table
from charts import kpi_row, category_pie, monthly_spending, stacked_area_chart, multi_year_comparison, calendar_heatmap
from analytics import monthly_trends, category_insights, what_if_simulation
from alerts_engine import get_all_alerts, generate_daily_summary
from settings_page import render_settings_page

def show_alerts_banner(df):
    """Display active alerts at top of dashboard."""
    budgets = load_budgets()
    alerts = get_all_alerts(df, budgets)
    
    if not alerts:
        return
    
    # Show alerts in expandable container
    with st.expander(f"🔔 {len(alerts)} Active Alerts", expanded=True):
        for alert in alerts[:5]:  # Show top 5
            if alert.severity == "critical":
                st.error(str(alert))
            elif alert.severity == "warning":
                st.warning(str(alert))
            elif alert.severity == "caution":
                st.info(str(alert))
            else:
                st.success(str(alert))

# Call at top of dashboard:
    
# New intelligence engine
try:
    from spending_intelligence import (
        hotspot_analysis, temporal_patterns, budget_intelligence,
        savings_opportunities, smart_kpi_row,
    )
    HAS_INTELLIGENCE = True
except ImportError:
    HAS_INTELLIGENCE = False

try:
    from import_export import import_workflow, export_buttons
    _USE_IMPORT_WORKFLOW = True
except ImportError:
    from import_export import import_button, export_buttons
    _USE_IMPORT_WORKFLOW = False

try:
    from import_export import perform_merge_if_ready
    HAS_MERGE_FN = True
except ImportError:
    HAS_MERGE_FN = False

try:
    from budget_manager import budget_dashboard_ui, budget_setup_ui
    HAS_BUDGET = True
except ImportError:
    HAS_BUDGET = False

try:
    from recurring_manager import recurring_manager_ui
    HAS_RECURRING = True
except ImportError:
    HAS_RECURRING = False

try:
    from analytics_advanced import (
        yoy_comparison_chart, mom_comparison_chart,
        spending_forecast_chart, anomaly_detection_chart, spending_insights,
        category_evolution_chart, daily_heatmap,
    )
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False

try:
    from ml_categorizer import smart_categorize_ui
    HAS_ML = True
except ImportError:
    HAS_ML = False

try:
    from receipt_ocr import receipt_upload_ui
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

try:
    from tax_export import tax_export_ui
    HAS_TAX = True
except ImportError:
    HAS_TAX = False

try:
    from backup_manager import backup_settings_ui
    HAS_BACKUP = True
except ImportError:
    HAS_BACKUP = False

try:
    from notification_manager import render_notification_banner, notification_settings_ui
    HAS_NOTIFY = True
except ImportError:
    HAS_NOTIFY = False

try:
    from multi_user_manager import user_switcher_widget, user_management_ui, user_splits_ui
    HAS_USERS = True
except ImportError:
    HAS_USERS = False


# ═══════════════════════════════════════════════════════════════
#  THEME SYSTEM — 8 carefully designed palettes
# ═══════════════════════════════════════════════════════════════
THEMES = {
    "☀️ Light": {
        "app_bg": "#f5f7fa", "sidebar_bg": "#ffffff", "card_bg": "#ffffff",
        "border": "#e8ecf0", "text_primary": "#0d1117", "text_secondary": "#4a5568",
        "text_muted": "#9aa5b4", "accent": "#5a67d8", "accent_soft": "rgba(90,103,216,0.10)",
        "accent2": "#38b2ac", "input_bg": "#f0f4f8", "chart_paper": "#ffffff", "chart_grid": "#edf2f7",
        "gradient": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        "success": "#38a169", "warning": "#d69e2e", "danger": "#e53e3e",
    },
    "🌑 Dark": {
        "app_bg": "#0d1117", "sidebar_bg": "#161b22", "card_bg": "#21262d",
        "border": "#30363d", "text_primary": "#e6edf3", "text_secondary": "#8b949e",
        "text_muted": "#484f58", "accent": "#79c0ff", "accent_soft": "rgba(121,192,255,0.12)",
        "accent2": "#56d364", "input_bg": "#0d1117", "chart_paper": "#21262d", "chart_grid": "#30363d",
        "gradient": "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)",
        "success": "#56d364", "warning": "#e3b341", "danger": "#f85149",
    },
    "🌊 Ocean": {
        "app_bg": "#f0f9ff", "sidebar_bg": "#e0f2fe", "card_bg": "#ffffff",
        "border": "#bae6fd", "text_primary": "#0c4a6e", "text_secondary": "#0369a1",
        "text_muted": "#38bdf8", "accent": "#0284c7", "accent_soft": "rgba(2,132,199,0.10)",
        "accent2": "#0d9488", "input_bg": "#e0f2fe", "chart_paper": "#f0f9ff", "chart_grid": "#bae6fd",
        "gradient": "linear-gradient(135deg, #0284c7 0%, #0d9488 100%)",
        "success": "#0d9488", "warning": "#d97706", "danger": "#dc2626",
    },
    "🌿 Forest": {
        "app_bg": "#f0fdf4", "sidebar_bg": "#dcfce7", "card_bg": "#ffffff",
        "border": "#bbf7d0", "text_primary": "#14532d", "text_secondary": "#15803d",
        "text_muted": "#4ade80", "accent": "#16a34a", "accent_soft": "rgba(22,163,74,0.10)",
        "accent2": "#0f766e", "input_bg": "#dcfce7", "chart_paper": "#f0fdf4", "chart_grid": "#bbf7d0",
        "gradient": "linear-gradient(135deg, #16a34a 0%, #0f766e 100%)",
        "success": "#16a34a", "warning": "#ca8a04", "danger": "#dc2626",
    },
    "🌅 Sunset": {
        "app_bg": "#fff7ed", "sidebar_bg": "#ffedd5", "card_bg": "#ffffff",
        "border": "#fed7aa", "text_primary": "#7c2d12", "text_secondary": "#c2410c",
        "text_muted": "#fb923c", "accent": "#ea580c", "accent_soft": "rgba(234,88,12,0.10)",
        "accent2": "#db2777", "input_bg": "#ffedd5", "chart_paper": "#fff7ed", "chart_grid": "#fed7aa",
        "gradient": "linear-gradient(135deg, #ea580c 0%, #db2777 100%)",
        "success": "#16a34a", "warning": "#ca8a04", "danger": "#dc2626",
    },
    "🌙 Midnight": {
        "app_bg": "#0d0d1a", "sidebar_bg": "#0a0a14", "card_bg": "#13131f",
        "border": "#1e1e3f", "text_primary": "#e2e2ff", "text_secondary": "#a5b4fc",
        "text_muted": "#4f4f7a", "accent": "#7c3aed", "accent_soft": "rgba(124,58,237,0.15)",
        "accent2": "#db2777", "input_bg": "#13131f", "chart_paper": "#13131f", "chart_grid": "#1e1e3f",
        "gradient": "linear-gradient(135deg, #7c3aed 0%, #db2777 100%)",
        "success": "#22c55e", "warning": "#f59e0b", "danger": "#ef4444",
    },
    "🌸 Rose": {
        "app_bg": "#fff1f2", "sidebar_bg": "#ffe4e6", "card_bg": "#ffffff",
        "border": "#fecdd3", "text_primary": "#881337", "text_secondary": "#be123c",
        "text_muted": "#fb7185", "accent": "#e11d48", "accent_soft": "rgba(225,29,72,0.10)",
        "accent2": "#9333ea", "input_bg": "#ffe4e6", "chart_paper": "#fff1f2", "chart_grid": "#fecdd3",
        "gradient": "linear-gradient(135deg, #e11d48 0%, #9333ea 100%)",
        "success": "#16a34a", "warning": "#ca8a04", "danger": "#e11d48",
    },
    "⬜ Slate": {
        "app_bg": "#f8fafc", "sidebar_bg": "#f1f5f9", "card_bg": "#ffffff",
        "border": "#cbd5e1", "text_primary": "#1e293b", "text_secondary": "#475569",
        "text_muted": "#94a3b8", "accent": "#475569", "accent_soft": "rgba(71,85,105,0.10)",
        "accent2": "#0f766e", "input_bg": "#f1f5f9", "chart_paper": "#ffffff", "chart_grid": "#e2e8f0",
        "gradient": "linear-gradient(135deg, #475569 0%, #0f766e 100%)",
        "success": "#16a34a", "warning": "#ca8a04", "danger": "#dc2626",
    },
}
DEFAULT_THEME = "☀️ Light"


def get_theme() -> dict:
    return THEMES.get(st.session_state.get("theme_name", DEFAULT_THEME), THEMES[DEFAULT_THEME])


def apply_theme(t: dict):
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {{ font-family: 'Plus Jakarta Sans', sans-serif !important; }}
    .stApp {{ background-color: {t["app_bg"]} !important; color: {t["text_primary"]} !important; }}
    [data-testid="stSidebar"] {{ background-color: {t["sidebar_bg"]} !important; border-right: 1px solid {t["border"]} !important; }}
    [data-testid="stSidebar"] *, [data-testid="stSidebar"] label {{ color: {t["text_secondary"]} !important; }}
    .block-container {{ padding-top: 1.5rem; max-width: 1400px; }}
    h1, h2, h3, h4 {{ color: {t["text_primary"]} !important; letter-spacing: -0.025em; font-family: 'Plus Jakarta Sans', sans-serif !important; font-weight: 700 !important; }}

    /* ── Inputs ────────────────────────────────────────────────────── */
    .stTextInput > div > input, .stNumberInput > div > input, .stDateInput > div > input {{
        background: {t["input_bg"]} !important; border: 1.5px solid {t["border"]} !important;
        border-radius: 10px !important; color: {t["text_primary"]} !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important; padding: 0.5rem 0.75rem !important;
    }}
    .stTextInput > div > input:focus, .stNumberInput > div > input:focus {{
        border-color: {t["accent"]} !important; box-shadow: 0 0 0 3px {t["accent_soft"]} !important;
    }}
    .stSelectbox > div > div {{
        background: {t["input_bg"]} !important; border: 1.5px solid {t["border"]} !important;
        border-radius: 10px !important; color: {t["text_primary"]} !important;
    }}
    .stMultiSelect > div > div {{
        background: {t["input_bg"]} !important; border: 1.5px solid {t["border"]} !important;
        border-radius: 10px !important;
    }}

    /* ── Buttons ───────────────────────────────────────────────────── */
    .stButton > button {{
        background: {t["gradient"]} !important; color: white !important;
        border: none !important; border-radius: 10px !important; font-weight: 600 !important;
        letter-spacing: 0.01em; transition: all 0.2s ease; font-family: 'Plus Jakarta Sans', sans-serif !important;
        padding: 0.45rem 1.1rem !important;
    }}
    .stButton > button:hover {{
        opacity: 0.90; transform: translateY(-2px);
        box-shadow: 0 8px 25px {t["accent_soft"]};
    }}
    .stButton > button[kind="secondary"] {{
        background: transparent !important; border: 1.5px solid {t["border"]} !important;
        color: {t["text_secondary"]} !important;
    }}
    .stButton > button[kind="secondary"]:hover {{
        border-color: {t["accent"]} !important; color: {t["accent"]} !important;
    }}

    /* ── Metrics ───────────────────────────────────────────────────── */
    [data-testid="stMetric"] {{
        background: {t["card_bg"]}; border: 1.5px solid {t["border"]};
        border-radius: 14px; padding: 1.1rem 1.3rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.04);
        transition: box-shadow 0.2s;
    }}
    [data-testid="stMetric"]:hover {{ box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
    [data-testid="stMetricLabel"] {{
        color: {t["text_muted"]} !important; font-size: 0.72rem !important;
        font-weight: 700 !important; text-transform: uppercase; letter-spacing: 0.08em;
    }}
    [data-testid="stMetricValue"] {{
        color: {t["text_primary"]} !important; font-size: 1.65rem !important;
        font-weight: 800 !important; letter-spacing: -0.02em;
    }}

    /* ── Legacy KPI card ─────────────────────────────────────────── */
    .kpi-card {{
        background: {t["card_bg"]}; border: 1.5px solid {t["border"]};
        padding: 1.1rem 1.3rem; border-radius: 14px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.04);
        transition: box-shadow 0.2s;
    }}
    .kpi-card:hover {{ box-shadow: 0 6px 24px rgba(0,0,0,0.09); }}
    .kpi-label {{
        font-size: 0.72rem; color: {t["text_muted"]}; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.08em;
    }}
    .kpi-value {{
        font-size: 1.65rem; font-weight: 800; color: {t["text_primary"]};
        margin-top: 0.2rem; letter-spacing: -0.02em;
    }}

    /* ── Tabs ──────────────────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {{
        background: {t["input_bg"]}; border-radius: 12px;
        border: 1.5px solid {t["border"]}; gap: 2px; padding: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background: transparent; border-radius: 9px;
        color: {t["text_muted"]}; font-weight: 500; font-size: 0.88rem;
        transition: all 0.15s;
    }}
    .stTabs [aria-selected="true"] {{
        background: {t["card_bg"]} !important; color: {t["accent"]} !important;
        font-weight: 700 !important; box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
    }}

    /* ── Expander ─────────────────────────────────────────────────── */
    details {{
        background: {t["card_bg"]}; border: 1.5px solid {t["border"]};
        border-radius: 12px;
    }}
    details > summary {{ color: {t["text_primary"]} !important; padding: 0.75rem; }}

    /* ── Dataframe ────────────────────────────────────────────────── */
    [data-testid="stDataFrame"] {{
        border: 1.5px solid {t["border"]}; border-radius: 12px; overflow: hidden;
    }}

    /* ── Alert badges ─────────────────────────────────────────────── */
    .stSuccess, .stInfo {{ border-radius: 10px; }}
    .stWarning, .stError {{ border-radius: 10px; }}

    /* ── Section header style ─────────────────────────────────────── */
    .section-header {{
        font-size: 1rem; font-weight: 700; color: {t["text_primary"]};
        letter-spacing: -0.01em; margin: 1.2rem 0 0.6rem;
        display: flex; align-items: center; gap: 0.4rem;
    }}

    /* ── Sidebar nav active ───────────────────────────────────────── */
    .nav-active {{
        background: {t["accent_soft"]}; border-left: 3px solid {t["accent"]};
        border-radius: 0 9px 9px 0; padding: 0.2rem 0.5rem 0.2rem 0.35rem;
        margin-bottom: 0.15rem; font-weight: 700; color: {t["accent"]};
        font-size: 0.88rem;
    }}

    /* ── Divider ──────────────────────────────────────────────────── */
    hr {{ border-color: {t["border"]} !important; opacity: 0.6; margin: 1.25rem 0; }}

    /* ── Scrollbar ────────────────────────────────────────────────── */
    ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
    ::-webkit-scrollbar-track {{ background: {t["app_bg"]}; }}
    ::-webkit-scrollbar-thumb {{ background: {t["border"]}; border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: {t["accent"]}; }}

    /* ── Hide Streamlit chrome ────────────────────────────────────── */
    #MainMenu, footer {{ visibility: hidden; }}

    /* ── Page hero banner ─────────────────────────────────────────── */
    .hero-banner {{
        background: {t["gradient"]};
        border-radius: 16px; padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
        display: flex; align-items: center; justify-content: space-between;
    }}
    .hero-title {{
        font-size: 1.6rem; font-weight: 800; color: white;
        letter-spacing: -0.03em;
    }}
    .hero-sub {{
        font-size: 0.88rem; color: rgba(255,255,255,0.78); margin-top: 0.2rem;
    }}
    </style>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="💳 Expense Tracker",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

t = get_theme()
apply_theme(t)


# ═══════════════════════════════════════════════════════════════
#  DATA LOADING
# ═══════════════════════════════════════════════════════════════
@st.cache_resource
def get_sheet():
    return init_storage()

sheet   = get_sheet()
version = st.session_state.get("data_version", 0)
df      = load_data(_sheet=sheet, version=version)
if df is None or not isinstance(df, pd.DataFrame):
    df = pd.DataFrame()

if not df.empty and "Date" in df.columns:
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date

for c in ["Date", "ExpenseType", "PricePaid", "Quantity", "PricePerUnit",
          "Category", "Shop", "Item", "Brand", "Subcategory", "Currency", "QuantityUnit"]:
    if c not in df.columns:
        df[c] = None


# ═══════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════
def build_sidebar(t: dict):
    st.sidebar.markdown(f"""
    <div style="padding:0.85rem 0 0.6rem;">
        <div style="background:{t['gradient']};border-radius:10px;padding:0.8rem 1rem;">
            <div style="font-size:1.15rem;font-weight:800;color:white;letter-spacing:-0.02em;">
                💳 Expense Tracker
            </div>
            <div style="font-size:0.7rem;color:rgba(255,255,255,0.75);margin-top:3px;">
                {date.today().strftime('%A, %B %d %Y')}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown(
        f"<div style='font-size:0.62rem;font-weight:700;letter-spacing:0.11em;color:{t['text_muted']};"
        f"text-transform:uppercase;margin-top:0.3rem;margin-bottom:0.25rem;'>🎨 Theme</div>",
        unsafe_allow_html=True
    )
    chosen = st.sidebar.selectbox(
        "Theme", list(THEMES.keys()),
        index=list(THEMES.keys()).index(st.session_state.get("theme_name", DEFAULT_THEME)),
        key="theme_selector", label_visibility="collapsed",
    )
    if chosen != st.session_state.get("theme_name", DEFAULT_THEME):
        st.session_state["theme_name"] = chosen
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"<div style='font-size:0.62rem;font-weight:700;letter-spacing:0.11em;color:{t['text_muted']};"
        f"text-transform:uppercase;margin-bottom:0.35rem;'>Navigation</div>",
        unsafe_allow_html=True
    )

    pages = {
        "🏠 Dashboard":       "dashboard",
        "🧠 Intelligence":    "intelligence",
        "📊 Analytics":       "analytics",
        "✏️ Edit & Delete":   "edit",
        "📤 Import / Export": "import_export",
        "⚙️ Settings":        "settings",
    }
    if HAS_BUDGET:     pages["🎯 Budgets"]         = "budgets"
    if HAS_RECURRING:  pages["🔁 Recurring"]        = "recurring"
    if HAS_OCR:        pages["📷 Receipt Scanner"]  = "receipt"
    if HAS_TAX:        pages["🧾 Tax Reports"]      = "tax"
    if HAS_ML:         pages["🤖 Smart Categorize"] = "ml"
    if HAS_USERS:      pages["👥 Team & Splits"]    = "users"
    if HAS_NOTIFY:     pages["🔔 Notifications"]    = "notifications"
    if HAS_BACKUP:     pages["💾 Backups"]           = "backup"

    if "page" not in st.session_state:
        st.session_state["page"] = "dashboard"

    for label, key in pages.items():
        is_active = st.session_state["page"] == key
        if is_active:
            st.sidebar.markdown(
                f"<div class='nav-active'>{label}</div>",
                unsafe_allow_html=True,
            )
        else:
            if st.sidebar.button(label, key=f"nav_{key}", width="stretch"):
                st.session_state["page"] = key
                st.rerun()

    st.sidebar.markdown("---")

    if HAS_USERS:
        user_switcher_widget()

    what_if_simulation(df)


build_sidebar(t)

if HAS_NOTIFY and st.session_state.get("page") != "notifications":
    render_notification_banner(df)


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════
def style_fig(fig, height=360):
    fig.update_layout(
        paper_bgcolor=t["chart_paper"], plot_bgcolor=t["chart_paper"],
        font=dict(color=t["text_secondary"], family="Plus Jakarta Sans"),
        xaxis=dict(showgrid=False, tickcolor=t["border"], linecolor=t["border"]),
        yaxis=dict(showgrid=True, gridcolor=t["chart_grid"], zeroline=False),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=t["text_secondary"])),
        margin=dict(t=48, b=16, l=0, r=0), height=height,
        title_font=dict(color=t["text_secondary"], size=13, family="Plus Jakarta Sans"),
    )
    return fig


def _hero(title: str, subtitle: str, emoji: str = ""):
    st.markdown(
        f"""<div class="hero-banner">
            <div>
                <div class="hero-title">{emoji} {title}</div>
                <div class="hero-sub">{subtitle}</div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )


def _handle_import_merge():
    show_import = not st.session_state.get("merge_complete", False) and \
                  not st.session_state.get("merge_complete_flagged", False)
    if show_import:
        if _USE_IMPORT_WORKFLOW:
            import_workflow(existing_columns=df.columns.tolist() if not df.empty else None)
        else:
            imported = import_button(existing_columns=df.columns.tolist() if not df.empty else None)
            if imported is not None and not imported.empty:
                if "Date" in imported.columns:
                    imported["Date"] = pd.to_datetime(imported["Date"], errors="coerce").dt.date
                st.session_state["pending_import_df"] = imported
                st.session_state["merge_ready"] = True
                st.subheader("📄 Preview")
                st.dataframe(imported, width="stretch", hide_index=True)
    else:
        if st.session_state.get("merge_complete"):
            st.sidebar.success("✅ Last import merged.")

    if st.session_state.get("merge_ready", False):
        if HAS_MERGE_FN:
            perform_merge_if_ready(df, save_data, sheet)
        else:
            pending = st.session_state.get("pending_import_df", pd.DataFrame())
            if not pending.empty:
                try:
                    combined = pd.concat([df, pending], ignore_index=True)
                    combined = clean_data(combined)
                    save_data(combined, sheet)
                    st.cache_data.clear()
                    bump_data_version()
                    st.success("✅ Imported data merged successfully!")
                    for k in ["merge_ready", "pending_import_df"]:
                        st.session_state.pop(k, None)
                    st.session_state["merge_complete_flagged"] = True
                    st.session_state["merge_complete"] = True
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Merge failed: {e}")


def _incomplete_entries_expander():
    if df.empty or not all(c in df.columns for c in ["Date", "ExpenseType"]):
        return
    missing = df[df["Date"].isna() | (df["Date"] == "") |
                 df["ExpenseType"].isna() | (df["ExpenseType"] == "")].copy()
    if missing.empty:
        return
    with st.expander(f"⚠️ {len(missing)} Incomplete Entries", expanded=False):
        st.warning("Some entries are missing **Date** or **Expense Type**.")
        missing["Date"] = pd.to_datetime(missing["Date"], errors="coerce").dt.date
        edited = st.data_editor(missing, num_rows="dynamic", width="stretch", key="edit_missing", hide_index=True)
        if st.button("💾 Save Fixed Entries"):
            updated = pd.concat([df.drop(missing.index), edited], ignore_index=True)
            save_data(updated, sheet)
            bump_data_version()
            st.success("✅ Saved!")
            st.rerun()


def _period_selector(df_in) -> pd.DataFrame:
    if df_in.empty or "Date" not in df_in.columns:
        return pd.DataFrame()
    df2 = df_in.copy()
    df2["Date"] = pd.to_datetime(df2["Date"], errors="coerce")
    if df2["Date"].isna().all():
        return pd.DataFrame()
    years  = sorted(df2["Date"].dt.year.dropna().unique().tolist(), reverse=True)
    months = sorted(df2["Date"].dt.month.dropna().unique().tolist())
    col_y, col_m = st.columns(2)
    with col_y:
        sel_year = st.selectbox("Year", years, key="period_year")
    with col_m:
        month_names = ["All"] + [pd.Timestamp(2000, m, 1).strftime("%B") for m in months]
        sel_month   = st.selectbox("Month", month_names, key="period_month")
    result = df2[df2["Date"].dt.year == sel_year]
    if sel_month != "All":
        mn     = pd.to_datetime(sel_month, format="%B").month
        result = result[result["Date"].dt.month == mn]
    return result


def _donut_chart(df_in):
    if df_in.empty or "Category" not in df_in.columns:
        return
    agg = df_in.groupby("Category")["PricePaid"].sum().reset_index().sort_values("PricePaid", ascending=False)
    if len(agg) > 8:
        rest = agg.iloc[8:]["PricePaid"].sum()
        agg  = pd.concat([agg.head(8), pd.DataFrame([{"Category": "Other", "PricePaid": rest}])])
    palette = ["#5a67d8","#38b2ac","#f6ad55","#68d391","#fc8181","#76e4f7","#b794f4","#fc8181","#a0aec0"]
    total   = agg["PricePaid"].sum()
    fig = go.Figure(go.Pie(
        labels=agg["Category"], values=agg["PricePaid"], hole=0.62,
        marker=dict(colors=palette[:len(agg)], line=dict(color=t["app_bg"], width=3)),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} SEK — %{percent}<extra></extra>",
        textfont=dict(color=t["text_secondary"]),
    ))
    fig.add_annotation(
        text=f"<b>{total:,.0f}</b><br><span style='font-size:11px'>SEK total</span>",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=16, color=t["text_primary"], family="Plus Jakarta Sans"),
    )
    fig.update_layout(
        title="Spending by Category",
        paper_bgcolor=t["chart_paper"], plot_bgcolor=t["chart_paper"],
        font=dict(color=t["text_secondary"], family="Plus Jakarta Sans"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=t["text_secondary"])),
        margin=dict(t=48, b=8, l=0, r=0), height=360,
        title_font=dict(color=t["text_secondary"], size=13),
    )
    st.plotly_chart(fig, config={"displayModeBar": False})


def _monthly_bar_chart(df_in):
    df2 = df_in.copy()
    df2["Date"] = pd.to_datetime(df2["Date"], errors="coerce")
    df2 = df2.dropna(subset=["Date"])
    if df2.empty:
        return
    df2["YM"]  = df2["Date"].dt.to_period("M").astype(str)
    monthly    = df2.groupby("YM")["PricePaid"].sum().reset_index().sort_values("YM")
    avg_val    = monthly["PricePaid"].mean()
    colors     = [t["danger"] if v > avg_val * 1.2 else (t["warning"] if v > avg_val else t["accent"])
                  for v in monthly["PricePaid"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=monthly["YM"], y=monthly["PricePaid"],
        marker_color=colors, opacity=0.85,
        hovertemplate="<b>%{x}</b><br>%{y:,.0f} SEK<extra></extra>",
        name="Monthly total",
    ))
    fig.add_hline(y=avg_val, line_dash="dot", line_color=t["text_muted"], line_width=1.5,
                  annotation_text=f"Avg {avg_val:,.0f}", annotation_font_color=t["text_muted"])
    if len(monthly) >= 3:
        roll = monthly["PricePaid"].rolling(3).mean()
        fig.add_trace(go.Scatter(
            x=monthly["YM"], y=roll, mode="lines",
            line=dict(color=t["accent2"], dash="dot", width=2),
            name="3-mo avg",
        ))
    fig.update_layout(title="Monthly Spending", showlegend=len(monthly) >= 3)
    st.plotly_chart(style_fig(fig), config={"displayModeBar": False})


def _mom_delta_chart(df_in):
    df2 = df_in.copy()
    df2["Date"] = pd.to_datetime(df2["Date"], errors="coerce")
    df2["YM"]   = df2["Date"].dt.to_period("M").astype(str)
    monthly     = df2.groupby("YM")["PricePaid"].sum().reset_index().sort_values("YM")
    if len(monthly) < 2:
        return
    monthly["delta"] = monthly["PricePaid"].diff()
    monthly["color"] = monthly["delta"].apply(lambda x: t["danger"] if x > 0 else t["success"])
    fig = go.Figure(go.Bar(
        x=monthly["YM"].iloc[1:], y=monthly["delta"].iloc[1:],
        marker_color=monthly["color"].iloc[1:].tolist(),
        hovertemplate="<b>%{x}</b><br>%{y:+,.0f} SEK<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color=t["border"])
    fig.update_layout(title="Month-over-Month Change", showlegend=False)
    st.plotly_chart(style_fig(fig), config={"displayModeBar": False})


# ═══════════════════════════════════════════════════════════════
#  PAGE: DASHBOARD  ── Modern overview
# ═══════════════════════════════════════════════════════════════
def page_dashboard():
    _hero(
        "Expense Dashboard",
        f"Tracking your spending — as of {date.today().strftime('%B %d, %Y')}",
        "💳"
    )

    sidebar_add_expense(df, lambda d: save_data(d, sheet))
    df_filtered = filter_section(df)
    _handle_import_merge()
    export_buttons(df)
    _incomplete_entries_expander()

    st.markdown("---")
    st.markdown("### 📅 Select Period")
    df_period = _period_selector(df_filtered)

    # ── Smart KPIs ──
    st.markdown("### 📈 Overview")
    if not df_period.empty:
        if HAS_INTELLIGENCE:
            smart_kpi_row(df)       # full-dataset velocity context
        else:
            kpi_row(df_period)
    else:
        st.info("No data for selected period.")

    # ── Charts ──
    if not df_period.empty:
        st.markdown("")
        col1, col2 = st.columns([1.4, 1])
        with col1:
            _monthly_bar_chart(df_filtered)
        with col2:
            _donut_chart(df_period)

    # ── Quick intelligence snapshot ──
    if HAS_INTELLIGENCE and not df_period.empty:
        st.markdown("---")
        st.markdown("### ⚡ Quick Intelligence")
        df_prep = df.copy()
        df_prep["Date"] = pd.to_datetime(df_prep["Date"], errors="coerce")
        df_prep["PricePaid"] = pd.to_numeric(df_prep["PricePaid"], errors="coerce").fillna(0)
        df_prep["YM"] = df_prep["Date"].dt.to_period("M").astype(str)

        now      = pd.Timestamp.now()
        curr_ym  = now.to_period("M").strftime("%Y-%m")
        prev_ym  = (now - pd.DateOffset(months=1)).to_period("M").strftime("%Y-%m")
        this_mo  = df_prep[df_prep["YM"] == curr_ym]["PricePaid"].sum()
        prev_mo  = df_prep[df_prep["YM"] == prev_ym]["PricePaid"].sum()
        avg_3mo  = df_prep.groupby("YM")["PricePaid"].sum().sort_index().tail(4).head(3).mean()
        day_rate = this_mo / now.day if now.day > 0 else 0
        projected = day_rate * pd.Period(curr_ym, "M").days_in_month

        c1, c2, c3 = st.columns(3)
        with c1:
            mom_pct = ((this_mo - prev_mo) / prev_mo * 100) if prev_mo else None
            delta_str = f"{mom_pct:+.1f}% vs last month" if mom_pct is not None else None
            st.metric("🔥 This Month", f"{this_mo:,.0f} SEK", delta=delta_str, delta_color="inverse")
        with c2:
            proj_delta = f"{((projected - avg_3mo) / avg_3mo * 100):+.1f}% vs avg" if avg_3mo else None
            st.metric("🔮 Month Projection", f"{projected:,.0f} SEK", delta=proj_delta, delta_color="inverse")
        with c3:
            top_cat = "—"
            if not df_period.empty and "Category" in df_period.columns:
                cat_sums = df_period.groupby("Category")["PricePaid"].sum()
                if not cat_sums.empty:
                    top_cat = cat_sums.idxmax()
                    top_val = cat_sums.max()
                    top_cat = f"{top_cat} ({top_val:,.0f} SEK)"
            st.metric("🏆 Top Category", top_cat)

    # ── Quick stats ──
    if not df_period.empty:
        st.markdown("---")
        st.markdown("### 🔍 Period Summary")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Transactions", len(df_period))
        c2.metric("Highest Single", f"{df_period['PricePaid'].max():,.0f} SEK" if df_period["PricePaid"].notna().any() else "—")
        c3.metric("Avg Transaction", f"{df_period['PricePaid'].mean():,.0f} SEK" if df_period["PricePaid"].notna().any() else "—")
        c4.metric("Unique Categories", df_period["Category"].nunique() if "Category" in df_period.columns else "—")

    # ── Records ──
    st.markdown("### 🧾 Expense Records")
    if not df_period.empty:
        disp       = df_period.copy()
        disp["Date"] = pd.to_datetime(disp["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
        st.dataframe(disp, width="stretch", hide_index=True)
    else:
        st.info("No expenses for selected period.")


# ═══════════════════════════════════════════════════════════════
#  PAGE: INTELLIGENCE ── NEW
# ═══════════════════════════════════════════════════════════════
def page_intelligence():
    _hero(
        "Spending Intelligence",
        "Deep analysis of your purchase behaviour — hotspots, velocity & savings",
        "🧠"
    )

    if not HAS_INTELLIGENCE:
        st.error("❌ `spending_intelligence.py` not found. Add it to your project directory.")
        return

    if df.empty:
        st.info("No data available yet. Add some expenses to unlock intelligence.")
        return

    tab_labels = ["🔥 Hotspots", "⚡ Budget Intelligence", "💰 Savings", "📆 Patterns"]
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        hotspot_analysis(df)
    with tabs[1]:
        budget_intelligence(df)
    with tabs[2]:
        savings_opportunities(df)
    with tabs[3]:
        temporal_patterns(df)


# ═══════════════════════════════════════════════════════════════
#  PAGE: ANALYTICS
# ═══════════════════════════════════════════════════════════════
def page_analytics():
    """
    Analytics & Trends page with:
    - Sidebar filters (date presets, granularity, category)
    - Date range picker with reset
    - Quick insights banner
    - 5 collapsible sections with all charts
    - Export filtered data
    """
    _hero("Analytics & Trends", "Historical spending breakdown and forecasts", "📊")

    if df.empty:
        st.info("No data available yet.")
        return

    # ═══════════════════════════════════════════════════════════════
    # SIDEBAR FILTERS
    # ═══════════════════════════════════════════════════════════════
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🎯 Analytics Filters")
    
    # Prepare data
    df_dates = df.copy()
    df_dates[Columns.DATE] = pd.to_datetime(df_dates[Columns.DATE], errors="coerce")
    df_dates = df_dates.dropna(subset=[Columns.DATE])
    
    if df_dates.empty:
        st.warning("No valid dates found in data.")
        return
    
    min_date = df_dates[Columns.DATE].min().date()
    max_date = df_dates[Columns.DATE].max().date()
    
    # Date range presets
    today = date.today()
    presets = {
        "Custom (use sliders below)": None,
        "Last 30 Days": (today - timedelta(days=30), today),
        "Last 3 Months": (today - timedelta(days=90), today),
        "Last 6 Months": (today - timedelta(days=180), today),
        "Last Year": (today - timedelta(days=365), today),
        "Year to Date": (date(today.year, 1, 1), today),
        "All Time": (min_date, max_date),
    }
    
    preset = st.sidebar.selectbox(
        "📅 Quick Date Range",
        list(presets.keys()),
        index=0,
        help="Select a preset or use Custom to set your own range"
    )
    
    # Set dates based on preset
    if preset != "Custom (use sliders below)" and presets[preset] is not None:
        default_start, default_end = presets[preset]
        # Clamp to available data range
        default_start = max(default_start, min_date)
        default_end = min(default_end, max_date)
    else:
        default_start, default_end = min_date, max_date
    
    # Granularity selector
    granularity = st.sidebar.radio(
        "📊 View By",
        ["Daily", "Weekly", "Monthly", "Yearly"],
        index=2,
        help="Group data by time period"
    )
    
    # Category filter
    all_categories = sorted(df_dates[Columns.CATEGORY].dropna().unique().tolist())
    selected_categories = st.sidebar.multiselect(
        "🏷️ Filter Categories",
        all_categories,
        default=[],
        help="Leave empty to show all categories"
    )
    
    st.sidebar.markdown("---")

    # ═══════════════════════════════════════════════════════════════
    # DATE RANGE PICKER (main area)
    # ═══════════════════════════════════════════════════════════════
    st.markdown("### 📅 Date Range")
    col_filter1, col_filter2, col_filter3 = st.columns([2, 2, 1])
    
    with col_filter1:
        start_date = st.date_input(
            "From",
            default_start,
            min_value=min_date,
            max_value=max_date,
            key="analytics_start"
        )
    with col_filter2:
        end_date = st.date_input(
            "To",
            default_end,
            min_value=min_date,
            max_value=max_date,
            key="analytics_end"
        )
    with col_filter3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Reset All", width="stretch", help="Reset to all-time view"):
            st.session_state["analytics_start"] = min_date
            st.session_state["analytics_end"] = max_date
            st.rerun()
    
    # ═══════════════════════════════════════════════════════════════
    # APPLY FILTERS
    # ═══════════════════════════════════════════════════════════════
    # Date range filter
    df_filtered = df_dates[
        (df_dates[Columns.DATE].dt.date >= start_date) & 
        (df_dates[Columns.DATE].dt.date <= end_date)
    ].copy()
    
    # Category filter
    if selected_categories:
        df_filtered = df_filtered[df_filtered[Columns.CATEGORY].isin(selected_categories)]
    
    if df_filtered.empty:
        st.info("No data in selected filters.")
        return
    
    # Add period column based on granularity
    if granularity == "Daily":
        df_filtered["Period"] = df_filtered[Columns.DATE].dt.date.astype(str)
        period_label = "Day"
    elif granularity == "Weekly":
        df_filtered["Period"] = df_filtered[Columns.DATE].dt.to_period("W").astype(str)
        period_label = "Week"
    elif granularity == "Monthly":
        df_filtered["Period"] = df_filtered[Columns.DATE].dt.to_period("M").astype(str)
        period_label = "Month"
    else:  # Yearly
        df_filtered["Period"] = df_filtered[Columns.DATE].dt.year.astype(str)
        period_label = "Year"
    
    # Show filter summary
    category_text = f" | {len(selected_categories)} categories" if selected_categories else " | All categories"
    st.caption(
        f"📊 **{len(df_filtered):,} transactions** from {start_date} to {end_date}{category_text} | "
        f"Viewing by: {granularity}"
    )
    
    # ═══════════════════════════════════════════════════════════════
    # QUICK INSIGHTS BANNER
    # ═══════════════════════════════════════════════════════════════
    total_spent = df_filtered[Columns.PRICE_PAID].sum()
    num_transactions = len(df_filtered)
    avg_transaction = total_spent / num_transactions if num_transactions > 0 else 0
    
    if Columns.CATEGORY in df_filtered.columns and not df_filtered[Columns.CATEGORY].isna().all():
        top_category = df_filtered.groupby(Columns.CATEGORY)[Columns.PRICE_PAID].sum().idxmax()
        top_cat_amount = df_filtered.groupby(Columns.CATEGORY)[Columns.PRICE_PAID].sum().max()
        top_cat_pct = (top_cat_amount / total_spent * 100) if total_spent > 0 else 0
    else:
        top_category = "—"
        top_cat_pct = 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Total Spent", f"{total_spent:,.0f} SEK")
    col2.metric("🧾 Transactions", f"{num_transactions:,}")
    col3.metric("📊 Avg / Transaction", f"{avg_transaction:,.0f} SEK")
    if top_category != "—":
        col4.metric("🏆 Top Category", f"{top_category} ({top_cat_pct:.0f}%)")
    else:
        col4.metric("🏆 Top Category", "—")
    
    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════
    # SECTION 1: OVERVIEW
    # ═══════════════════════════════════════════════════════════════
    with st.expander("📊 **OVERVIEW** — Quick Summary & Trends", expanded=True):
        col1, col2 = st.columns([1.3, 1])
        with col1:
            monthly_spending(df_filtered)
        with col2:
            _monthly_bar_chart(df_filtered)
        
        st.markdown("---")
        monthly_trends(df_filtered)
        
        # Period-by-period breakdown (new - respects granularity)
        st.markdown(f"---")
        st.markdown(f"#### 📈 Spending by {period_label}")
        period_totals = (
            df_filtered.groupby("Period")[Columns.PRICE_PAID]
            .sum().reset_index().sort_values("Period")
        )
        
        if not period_totals.empty and len(period_totals) > 1:
            import plotly.express as px
            fig = px.bar(
                period_totals,
                x="Period",
                y=Columns.PRICE_PAID,
                title=f"Total Spending per {period_label}",
                labels={Columns.PRICE_PAID: "Amount (SEK)", "Period": period_label}
            )
            fig.update_layout(
                showlegend=False,
                xaxis_title=period_label,
                yaxis_title="SEK",
                hovermode="x unified"
            )
            st.plotly_chart(fig, config={"displayModeBar": False})
            
            # Show change vs previous period
            if len(period_totals) >= 2:
                latest = period_totals.iloc[-1][Columns.PRICE_PAID]
                previous = period_totals.iloc[-2][Columns.PRICE_PAID]
                pct_change = ((latest - previous) / previous * 100) if previous != 0 else 0
                arrow = "📈" if pct_change > 0 else "📉"
                change_text = "increase" if pct_change > 0 else "decrease"
                st.info(
                    f"{arrow} **{abs(pct_change):.1f}% {change_text}** "
                    f"vs previous {period_label.lower()} "
                    f"({previous:,.0f} → {latest:,.0f} SEK)"
                )

    # ═══════════════════════════════════════════════════════════════
    # SECTION 2: CATEGORY ANALYSIS
    # ═══════════════════════════════════════════════════════════════
    with st.expander("🏆 **CATEGORY ANALYSIS** — Where Your Money Goes", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            category_insights(df_filtered)
        with col2:
            category_pie(df_filtered)
        
        if HAS_ADVANCED:
            st.markdown("---")
            st.markdown("#### 📊 Category Evolution Over Time")
            category_evolution_chart(df_filtered)

    # ═══════════════════════════════════════════════════════════════
    # SECTION 3: TIME-BASED ANALYSIS
    # ═══════════════════════════════════════════════════════════════
    if HAS_ADVANCED:
        with st.expander("📈 **TIME ANALYSIS** — Comparisons & Forecasts", expanded=False):
            # Month-over-Month
            st.markdown("#### 📊 Month-over-Month Changes")
            _mom_delta_chart(df_filtered)
            
            st.markdown("---")
            
            # Year-over-Year
            st.markdown("#### 📅 Year-over-Year Comparison")
            yoy_comparison_chart(df_filtered)
            
            st.markdown("---")
            
            # Forecast
            st.markdown("#### 🔮 Spending Forecast")
            months_ahead = st.slider("Forecast months ahead", 1, 12, 3, key="forecast_months")
            spending_forecast_chart(df_filtered, months_ahead)

    # ═══════════════════════════════════════════════════════════════
    # SECTION 4: CALENDAR & PATTERNS
    # ═══════════════════════════════════════════════════════════════
    with st.expander("📆 **CALENDAR VIEWS** — When You Spend", expanded=False):
        st.markdown("#### 🗓️ Spending Heatmap")
        calendar_heatmap(df_filtered)
        
        st.markdown("---")
        
        st.markdown("#### 🔥 Stacked Area (Monthly Categories)")
        stacked_area_chart(df_filtered)
        
        st.markdown("---")
        
        st.markdown("#### 📅 Multi-Year Comparison")
        multi_year_comparison(df_filtered)
        
        if HAS_ADVANCED:
            st.markdown("---")
            st.markdown("#### 📅 Day of Week Analysis")
            daily_heatmap(df_filtered)

    # ═══════════════════════════════════════════════════════════════
    # SECTION 5: ADVANCED INSIGHTS
    # ═══════════════════════════════════════════════════════════════
    if HAS_ADVANCED:
        with st.expander("🔍 **ADVANCED INSIGHTS** — Anomalies & AI Analysis", expanded=False):
            st.markdown("#### 🔍 Anomaly Detection")
            st.caption("Identifies unusual spending months using statistical analysis (±2σ threshold)")
            anomaly_detection_chart(df_filtered)
            
            st.markdown("---")
            
            st.markdown("#### 💡 Smart Insights")
            st.caption("AI-generated observations about your spending patterns")
            spending_insights(df_filtered)
    
    # ═══════════════════════════════════════════════════════════════
    # EXPORT SECTION
    # ═══════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("💾 **EXPORT FILTERED DATA**", expanded=False):
        st.markdown("Download the currently filtered data for external analysis.")
        
        # Prepare export dataframe
        export_df = df_filtered[[
            Columns.DATE, Columns.CATEGORY, Columns.SUBCATEGORY,
            Columns.ITEM, Columns.SHOP, Columns.PRICE_PAID, Columns.CURRENCY
        ]].copy()
        export_df[Columns.DATE] = export_df[Columns.DATE].dt.date
        export_df = export_df.sort_values(Columns.DATE, ascending=False)
        
        # Show preview
        st.dataframe(
            export_df.head(10),
            width="stretch",
            hide_index=True
        )
        st.caption(f"Preview showing first 10 of {len(export_df):,} rows")
        
        # Export buttons
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            csv = export_df.to_csv(index=False).encode("utf-8")
            category_suffix = f"_{selected_categories[0]}" if len(selected_categories) == 1 else "_filtered"
            filename = f"analytics_{start_date}_{end_date}{category_suffix}.csv"
            st.download_button(
                "📄 Download CSV",
                csv,
                filename,
                "text/csv",
                width="stretch"
            )
        
        with col_exp2:
            try:
                from io import BytesIO
                buffer = BytesIO()
                export_df.to_excel(buffer, index=False, engine='openpyxl')
                excel_data = buffer.getvalue()
                filename_xlsx = filename.replace('.csv', '.xlsx')
                st.download_button(
                    "📊 Download Excel",
                    excel_data,
                    filename_xlsx,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch"
                )
            except ImportError:
                st.caption("Install `openpyxl` for Excel export: `pip install openpyxl`")


# ═══════════════════════════════════════════════════════════════
#  PAGE: EDIT
# ═══════════════════════════════════════════════════════════════
def page_edit():
    _hero("Edit & Delete Entries", "Manage your expense records", "✏️")
    if df.empty:
        st.info("No data available to edit.")
        return
    inline_edit_table(df, save_data, sheet)


# ═══════════════════════════════════════════════════════════════
#  PAGE: IMPORT / EXPORT
# ═══════════════════════════════════════════════════════════════
def page_import_export():
    _hero("Import / Export", "Bring in data or download your records", "📤")
    tab_in, tab_out = st.tabs(["📥 Import", "📤 Export"])
    with tab_in:
        _handle_import_merge()
    with tab_out:
        export_buttons(df)
        st.markdown("---")
        st.markdown("#### ⬇️ Download Current Data")
        try:
            from data_manager import export_data_bytes
            c1, c2 = st.columns(2)
            with c1:
                data, mime = export_data_bytes(df, "csv")
                if data:
                    st.download_button("📄 Download CSV", data, "expenses.csv", mime, width="stretch")
            with c2:
                data, mime = export_data_bytes(df, "xlsx")
                if data:
                    st.download_button("📘 Download Excel", data, "expenses.xlsx", mime, width="stretch")
        except (ImportError, AttributeError):
            import io
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button("📄 Download CSV", csv_bytes, "expenses.csv", "text/csv", width="stretch")
            try:
                buf = io.BytesIO(); df.to_excel(buf, index=False)
                st.download_button("📘 Download Excel", buf.getvalue(), "expenses.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   width="stretch")
            except Exception:
                st.info("Install openpyxl for Excel export: `pip install openpyxl`")


# ═══════════════════════════════════════════════════════════════
#  ROUTER
# ═══════════════════════════════════════════════════════════════
page = st.session_state.get("page", "dashboard")

if page == "dashboard":
    page_dashboard()
elif page == "intelligence":
    page_intelligence()
elif page == "analytics":
    page_analytics()
elif page == "edit":
    page_edit()
elif page == "import_export":
    page_import_export()
elif page == "budgets" and HAS_BUDGET:
    _hero("Budget Tracker", "Set and track your monthly budgets", "🎯")
    t1, t2 = st.tabs(["📊 Overview", "⚙️ Setup Budgets"])
    with t1: budget_dashboard_ui(df)
    with t2: budget_setup_ui(df)
elif page == "recurring" and HAS_RECURRING:
    recurring_manager_ui(df, save_data, sheet)
elif page == "receipt" and HAS_OCR:
    receipt_upload_ui(df, save_data, sheet)
elif page == "tax" and HAS_TAX:
    tax_export_ui(df)
elif page == "ml" and HAS_ML:
    smart_categorize_ui(df, save_data, sheet)
elif page == "users" and HAS_USERS:
    _hero("Team & Splits", "Manage users and split expenses", "👥")
    t1, t2 = st.tabs(["👥 Members", "💸 Expense Splits"])
    with t1: user_management_ui()
    with t2: user_splits_ui(df)
elif page == "notifications" and HAS_NOTIFY:
    notification_settings_ui(df)
elif page == "backup" and HAS_BACKUP:
    backup_settings_ui(df, save_data, sheet)
elif page == "settings":
    render_settings_page()
else:
    page_dashboard()