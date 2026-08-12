# Main_Dashboard_App.py
# ─────────────────────────────────────────────────────────────
# Responsibilities (only):
# 1. Streamlit page config
# 2. Theme application
# 3. Data loading + one-time dedup write-back + multi-user session isolation
# 4. Sidebar construction
# 5. Page routing
#
# All page logic lives in views/page_*.py
# All optional-module flags live in feature_flags.py (HAS_ prefix throughout)
# Theme dict `t` is always passed explicitly — never read as a global
# ─────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
from datetime import date
from config import Columns
from date_utils import normalize_dataframe_dates
from data_manager import init_storage, load_data, ensure_no_duplicates, save_data, restore_sheet_if_empty
from analytics import what_if_simulation
from settings_page import render_settings_page
from theme import THEMES, DEFAULT_THEME, get_theme, apply_theme
import feature_flags as ff

# ── Page modules ──────────────────────────────────────────────
from views import page_dashboard, page_intelligence, page_analytics, page_edit, page_import_export, page_trips, page_pending_bills, page_bills_ledger

# ═══════════════════════════════════════════════════════════════
# PAGE CONFIG (must be the very first Streamlit call)
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
# DATA LOADING
# ═══════════════════════════════════════════════════════════════

@st.cache_resource
def get_sheet():
    return init_storage()

# Show shimmer skeletons during the first (slow) storage init + Drive sync.
_booting = "boot_done" not in st.session_state
_boot_placeholder = st.empty()
if _booting:
    from page_helpers import skeleton_dashboard
    with _boot_placeholder.container():
        skeleton_dashboard()

sheet = get_sheet()

# ── Sync data/ JSON files from the shared Drive folder (best-effort) ──
# Pulls the latest dropdown options, budgets, settings and pending bills
# from the same Drive folder that holds the spreadsheet, so app state
# follows the spreadsheet across machines. No-op when Drive is unavailable.
try:
    import data_sync
    data_sync.pull_all(sheet)
except Exception:  # noqa: BLE001 – sync is best-effort
    pass

if _booting:
    _boot_placeholder.empty()
    st.session_state["boot_done"] = True

version = st.session_state.get("data_version", 0)
df_raw = load_data(_sheet=sheet, version=version)

if df_raw is None or not isinstance(df_raw, pd.DataFrame):
    df_raw = pd.DataFrame()

# ── One-time dedup write-back ──────────────────────────────────
# On the very first load after the app starts (version == 0), check
# whether the stored data contains duplicates. If it does, remove them
# and write the cleaned DataFrame back to the source immediately so
# subsequent restarts load clean data and never show the "Removed N
# duplicates" log message again.
if version == 0 and not df_raw.empty:
    df_raw = ensure_no_duplicates(df_raw, sheet=sheet)
    # If the Sheet was emptied (e.g. by an interrupted write) but we recovered
    # rows from the local CSV, push them back so Google Sheets is repopulated.
    restore_sheet_if_empty(df_raw, sheet=sheet)

if not df_raw.empty and "Date" in df_raw.columns:
    df_raw["Date"] = normalize_dataframe_dates(df_raw, "Date")["Date"]

for col in [
    "Date", "ExpenseType", "PricePaid", "Quantity", "PricePerUnit",
    "Category", "Shop", "Item", "Brand", "Subcategory", "Currency", "QuantityUnit",
]:
    if col not in df_raw.columns:
        df_raw[col] = None

# ── Auto-post due recurring templates (once per session) ───────
# Templates that opted into auto-post are applied automatically on the first
# load of the session, so recurring expenses appear without a manual "Apply".
if ff.HAS_RECURRING and not st.session_state.get("_recurring_autoposted"):
    st.session_state["_recurring_autoposted"] = True
    try:
        df_raw, _applied = ff.auto_apply_due_templates(df_raw, save_data, sheet)
        if _applied:
            _names = list(dict.fromkeys(_applied))  # unique, order-preserving
            st.toast(
                f"🔁 Auto-posted {len(_applied)} recurring expense(s): "
                + ", ".join(_names[:3]) + ("…" if len(_names) > 3 else ""),
                icon="🔁",
            )
    except Exception:
        pass

# ── Multi-user session isolation ───────────────────────────────
if ff.HAS_USERS:
    active_user: str | None = st.session_state.get("active_user")
    df = ff.filter_by_user(df_raw, user_id=active_user)
else:
    df = df_raw

# ═══════════════════════════════════════════════════════════════
# PAGE REGISTRY  (single source of truth for nav order + routing)
# ═══════════════════════════════════════════════════════════════
# Each page is declared once here as (key, label, enabled, render). The sidebar
# navigation and the router both iterate this list, so adding a page means
# editing exactly one place. ``render`` takes the shared context dict
# ``{df, save_data, sheet, t}``.
from collections import namedtuple

PageSpec = namedtuple("PageSpec", "key label enabled render")


def _render_budgets(c: dict) -> None:
    from page_helpers import hero
    hero("Budget Tracker", "Set and track your monthly budgets", "🎯")
    tab1, tab2 = st.tabs(["📊 Overview", "⚙️ Setup Budgets"])
    with tab1: ff.budget_dashboard_ui(c["df"])
    with tab2: ff.budget_setup_ui(c["df"])


def _render_users(c: dict) -> None:
    from page_helpers import hero
    hero("Team & Splits", "Manage users and split expenses", "👥")
    tab1, tab2 = st.tabs(["👥 Members", "💸 Expense Splits"])
    with tab1: ff.user_management_ui()
    with tab2: ff.user_splits_ui(c["df"])


def get_page_registry() -> "list[PageSpec]":
    """Return the ordered list of enabled pages (order == sidebar order)."""
    specs = [
        PageSpec("dashboard",     "🏠 Dashboard",        True,                    lambda c: page_dashboard.render(**c)),
        PageSpec("intelligence",  "🧠 Intelligence",     True,                    lambda c: page_intelligence.render(**c)),
        PageSpec("analytics",     "📊 Analytics",        True,                    lambda c: page_analytics.render(**c)),
        PageSpec("edit",          "✏️ Edit & Delete",    True,                    lambda c: page_edit.render(**c)),
        PageSpec("import_export", "📤 Import / Export",  True,                    lambda c: page_import_export.render(**c)),
        PageSpec("pending_bills", "🧾 Pending Bills",    ff.HAS_PENDING_BILLS,    lambda c: page_pending_bills.render(**c)),
        PageSpec("bills_ledger",  "📒 Bills Ledger",     ff.HAS_BILLS_LEDGER,     lambda c: page_bills_ledger.render(**c)),
        PageSpec("trips",         "✈️ Trips",            ff.HAS_TRIPS,            lambda c: page_trips.render(**c)),
        PageSpec("settings",      "⚙️ Settings",         True,                    lambda c: render_settings_page(c["df"])),
        PageSpec("budgets",       "🎯 Budgets",          ff.HAS_BUDGET,           _render_budgets),
        PageSpec("recurring",     "🔁 Recurring",        ff.HAS_RECURRING,        lambda c: ff.recurring_manager_ui(c["df"], c["save_data"], c["sheet"])),        PageSpec("income",        "💵 Income",            ff.HAS_INCOME,           lambda c: ff.income_manager_ui(c["df"], c["save_data"], c["sheet"])),
        PageSpec("accounts",      "🏦 Net Worth",         ff.HAS_ACCOUNTS,         lambda c: ff.accounts_manager_ui(c["df"], c["save_data"], c["sheet"])),        PageSpec("price_tracker", "💰 Price Tracker",    ff.HAS_PRICE_TRACKER,    lambda c: ff.price_tracker_ui(c["df"])),
        PageSpec("financial_metrics", "📈 Financial Metrics", ff.HAS_FINANCIAL_METRICS, lambda c: ff.financial_metrics_ui(c["df"])),
        PageSpec("receipt",       "📷 Receipt Scanner",  ff.HAS_OCR,              lambda c: ff.receipt_upload_ui_with_translation(c["df"], c["save_data"], c["sheet"])),
        PageSpec("tax",           "🧾 Tax Reports",      ff.HAS_TAX,              lambda c: ff.tax_export_ui(c["df"])),
        PageSpec("ml",            "🤖 Smart Categorize", ff.HAS_ML,               lambda c: ff.smart_categorize_ui(c["df"], c["save_data"], c["sheet"])),
        PageSpec("users",         "👥 Team & Splits",    ff.HAS_USERS,            _render_users),
        PageSpec("notifications", "🔔 Notifications",    ff.HAS_NOTIFY,           lambda c: ff.notification_settings_ui(c["df"])),
        PageSpec("backup",        "💾 Backups",          ff.HAS_BACKUP,           lambda c: ff.backup_settings_ui(c["df"], c["save_data"], c["sheet"])),
        PageSpec("ai_insights",   "🤖 AI Insights",      ff.HAS_AI,               lambda c: ff.ai_chat_ui(c["df"])),
    ]
    return [s for s in specs if s.enabled]


PAGE_REGISTRY = get_page_registry()


# ═══════════════════════════════════════════════════════════════
# SIDEBAR
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

    if "page" not in st.session_state:
        st.session_state["page"] = "dashboard"

    for spec in PAGE_REGISTRY:
        if st.session_state["page"] == spec.key:
            st.sidebar.markdown(f"<div class='nav-active'>{spec.label}</div>", unsafe_allow_html=True)
        else:
            if st.sidebar.button(spec.label, key=f"nav_{spec.key}", width="stretch"):
                st.session_state["page"] = spec.key
                st.rerun()

    st.sidebar.markdown("---")

    if ff.HAS_USERS:
        ff.user_switcher_widget()

    what_if_simulation(df)


build_sidebar(t)

if ff.HAS_NOTIFY and st.session_state.get("page") != "notifications":
    ff.render_notification_banner(df)

# ═══════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════

page = st.session_state.get("page", "dashboard")
ctx = dict(df=df, save_data=save_data, sheet=sheet, t=t)

_spec = next((s for s in PAGE_REGISTRY if s.key == page), None)
if _spec is not None:
    _spec.render(ctx)
else:
    page_dashboard.render(**ctx)