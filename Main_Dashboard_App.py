# Main_Dashboard_App.py  ── REFACTORED
# ─────────────────────────────────────────────────────────────
#  Responsibilities (only):
#    1. Streamlit page config
#    2. Theme application
#    3. Data loading + multi-user session isolation
#    4. Sidebar construction
#    5. Page routing
#
#  All page logic lives in views/page_*.py
#  All optional-module flags live in feature_flags.py  (HAS_ prefix throughout)
#  Theme dict `t` is always passed explicitly — never read as a global
# ─────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd
from datetime import date

from config import Columns
from date_utils import normalize_dataframe_dates
from data_manager import init_storage, load_data, save_data
from analytics import what_if_simulation
from settings_page import render_settings_page
from theme import THEMES, DEFAULT_THEME, get_theme, apply_theme
import feature_flags as ff

# ── Page modules ──────────────────────────────────────────────
from views import page_dashboard, page_intelligence, page_analytics, page_edit, page_import_export, page_trips


# ═══════════════════════════════════════════════════════════════
#  PAGE CONFIG  (must be the very first Streamlit call)
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
df_raw  = load_data(_sheet=sheet, version=version)

if df_raw is None or not isinstance(df_raw, pd.DataFrame):
    df_raw = pd.DataFrame()

if not df_raw.empty and "Date" in df_raw.columns:
    df_raw["Date"] = normalize_dataframe_dates(df_raw, "Date")["Date"]

for col in [
    "Date", "ExpenseType", "PricePaid", "Quantity", "PricePerUnit",
    "Category", "Shop", "Item", "Brand", "Subcategory", "Currency", "QuantityUnit",
]:
    if col not in df_raw.columns:
        df_raw[col] = None


# ── Multi-user session isolation ───────────────────────────────
#  filter_by_user existed in multi_user_manager but was never
#  called — every page previously received the full unfiltered
#  dataset.  Applied once here so every page module sees only
#  the active user's rows automatically.
if ff.HAS_USERS:
    active_user: str | None = st.session_state.get("active_user")
    df = ff.filter_by_user(df_raw, user_id=active_user)
else:
    df = df_raw


# ═══════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════
def build_sidebar(t: dict) -> None:
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
        f"<div style='font-size:0.62rem;font-weight:700;letter-spacing:0.11em;"
        f"color:{t['text_muted']};text-transform:uppercase;margin-top:0.3rem;"
        f"margin-bottom:0.25rem;'>🎨 Theme</div>",
        unsafe_allow_html=True,
    )
    chosen = st.sidebar.selectbox(
        "Theme",
        list(THEMES.keys()),
        index=list(THEMES.keys()).index(st.session_state.get("theme_name", DEFAULT_THEME)),
        key="theme_selector",
        label_visibility="collapsed",
    )
    if chosen != st.session_state.get("theme_name", DEFAULT_THEME):
        st.session_state["theme_name"] = chosen
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"<div style='font-size:0.62rem;font-weight:700;letter-spacing:0.11em;"
        f"color:{t['text_muted']};text-transform:uppercase;margin-bottom:0.35rem;'>"
        f"Navigation</div>",
        unsafe_allow_html=True,
    )

    pages: dict[str, str] = {
        "🏠 Dashboard":       "dashboard",
        "🧠 Intelligence":    "intelligence",
        "📊 Analytics":       "analytics",
        "✏️ Edit & Delete":   "edit",
        "📤 Import / Export": "import_export",
        "✈️ Trips":           "trips",
        "⚙️ Settings":        "settings",
    }
    if ff.HAS_BUDGET:            pages["🎯 Budgets"]            = "budgets"
    if ff.HAS_RECURRING:         pages["🔁 Recurring"]           = "recurring"
    if ff.HAS_PRICE_TRACKER:     pages["💰 Price Tracker"]       = "price_tracker"
    if ff.HAS_FINANCIAL_METRICS: pages["📈 Financial Metrics"]   = "financial_metrics"
    if ff.HAS_OCR:               pages["📷 Receipt Scanner"]     = "receipt"
    if ff.HAS_TAX:               pages["🧾 Tax Reports"]         = "tax"
    if ff.HAS_ML:                pages["🤖 Smart Categorize"]    = "ml"
    if ff.HAS_USERS:             pages["👥 Team & Splits"]       = "users"
    if ff.HAS_NOTIFY:            pages["🔔 Notifications"]       = "notifications"
    if ff.HAS_BACKUP:            pages["💾 Backups"]              = "backup"

    if "page" not in st.session_state:
        st.session_state["page"] = "dashboard"

    for label, key in pages.items():
        if st.session_state["page"] == key:
            st.sidebar.markdown(f"<div class='nav-active'>{label}</div>", unsafe_allow_html=True)
        else:
            if st.sidebar.button(label, key=f"nav_{key}", width="stretch"):
                st.session_state["page"] = key
                st.rerun()

    st.sidebar.markdown("---")

    if ff.HAS_USERS:
        ff.user_switcher_widget()

    what_if_simulation(df)


build_sidebar(t)

if ff.HAS_NOTIFY and st.session_state.get("page") != "notifications":
    ff.render_notification_banner(df)


# ═══════════════════════════════════════════════════════════════
#  ROUTER
#  ctx bundles all page dependencies; page modules use **ctx
#  so they accept only what they need without reaching into globals.
# ═══════════════════════════════════════════════════════════════
page = st.session_state.get("page", "dashboard")
ctx  = dict(df=df, save_data=save_data, sheet=sheet, t=t)

if page == "dashboard":
    page_dashboard.render(**ctx)

elif page == "intelligence":
    page_intelligence.render(**ctx)

elif page == "analytics":
    page_analytics.render(**ctx)

elif page == "edit":
    page_edit.render(**ctx)

elif page == "import_export":
    page_import_export.render(**ctx)

elif page == "trips":
    page_trips.render(**ctx)

elif page == "budgets" and ff.HAS_BUDGET:
    from page_helpers import hero
    hero("Budget Tracker", "Set and track your monthly budgets", "🎯")
    t1, t2 = st.tabs(["📊 Overview", "⚙️ Setup Budgets"])
    with t1: ff.budget_dashboard_ui(df)
    with t2: ff.budget_setup_ui(df)

elif page == "recurring" and ff.HAS_RECURRING:
    ff.recurring_manager_ui(df, save_data, sheet)

elif page == "price_tracker" and ff.HAS_PRICE_TRACKER:
    ff.price_tracker_ui(df)

elif page == "financial_metrics" and ff.HAS_FINANCIAL_METRICS:
    ff.financial_metrics_ui(df)

elif page == "receipt" and ff.HAS_OCR:
    ff.receipt_upload_ui_with_translation(df, save_data, sheet)

elif page == "tax" and ff.HAS_TAX:
    ff.tax_export_ui(df)

elif page == "ml" and ff.HAS_ML:
    ff.smart_categorize_ui(df, save_data, sheet)

elif page == "users" and ff.HAS_USERS:
    from page_helpers import hero
    hero("Team & Splits", "Manage users and split expenses", "👥")
    t1, t2 = st.tabs(["👥 Members", "💸 Expense Splits"])
    with t1: ff.user_management_ui()
    with t2: ff.user_splits_ui(df)

elif page == "notifications" and ff.HAS_NOTIFY:
    ff.notification_settings_ui(df)

elif page == "backup" and ff.HAS_BACKUP:
    ff.backup_settings_ui(df, save_data, sheet)

elif page == "settings":
    render_settings_page(df)

else:
    page_dashboard.render(**ctx)