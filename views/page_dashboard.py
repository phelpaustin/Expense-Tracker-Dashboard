# pages/page_dashboard.py
# ──────────────────────────────────────────────────────────────
#  Dashboard page — overview KPIs, period selector, quick charts
# ──────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd

from config import Columns
from date_utils import normalize_dataframe_dates, format_date
from ui_components import sidebar_add_expense, filter_section
from charts import kpi_row
from analytics import monthly_trends
from alerts_engine import get_all_alerts, get_enabled_alerts
from page_helpers import hero, donut_chart, monthly_bar_chart, period_selector, incomplete_entries_expander, handle_import_merge, section_header
import feature_flags as ff


# ── Alerts banner ─────────────────────────────────────────────

def _alerts_banner(df: pd.DataFrame) -> None:
    try:
        from budget_manager import load_budgets
        budgets = load_budgets()
    except Exception:
        return
    try:
        alerts = get_enabled_alerts(df, budgets)
    except Exception:
        alerts = get_all_alerts(df, budgets)
    if not alerts:
        return
    with st.expander(f"🔔 {len(alerts)} Active Alert{'s' if len(alerts) != 1 else ''}", expanded=True):
        for alert in alerts[:5]:
            if alert.severity == "critical":
                st.error(str(alert))
            elif alert.severity == "warning":
                st.warning(str(alert))
            elif alert.severity == "caution":
                st.info(str(alert))
            else:
                st.success(str(alert))


# ── Import / merge helper ──────────────────────────────────────
# Shared workflow lives in page_helpers.handle_import_merge (also used by
# the Import / Export page) so the logic exists in exactly one place.


# ── Quick-Intelligence strip ───────────────────────────────────

def _quick_intelligence(df: pd.DataFrame, df_period: pd.DataFrame) -> None:
    st.markdown("---")
    st.markdown("### ⚡ Quick Intelligence")

    df_prep = df.copy()
    df_prep["Date"] = pd.to_datetime(
        normalize_dataframe_dates(df_prep, "Date")["Date"], errors="coerce"
    )
    df_prep["PricePaid"] = pd.to_numeric(df_prep["PricePaid"], errors="coerce").fillna(0)
    df_prep[Columns.YEAR_MONTH] = df_prep["Date"].dt.to_period("M").astype(str)

    now = pd.Timestamp.now()
    curr_ym = now.to_period("M").strftime("%Y-%m")
    prev_ym = (now - pd.DateOffset(months=1)).to_period("M").strftime("%Y-%m")
    this_mo = df_prep[df_prep[Columns.YEAR_MONTH] == curr_ym]["PricePaid"].sum()
    prev_mo = df_prep[df_prep[Columns.YEAR_MONTH] == prev_ym]["PricePaid"].sum()
    avg_3mo = df_prep.groupby(Columns.YEAR_MONTH)["PricePaid"].sum().sort_index().tail(4).head(3).mean()
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
                top_cat = f"{cat_sums.idxmax()} ({cat_sums.max():,.0f} SEK)"
        st.metric("🏆 Top Category", top_cat)


# ── Grouped transaction view ───────────────────────────────────

def _render_transaction_groups(df: pd.DataFrame, t: dict) -> None:
    """
    Club individual expense rows into transactions.
    A transaction = unique (Date, Shop) pair.
    Each transaction renders as an expander; the items inside are a
    clean dataframe showing Category, Item, Brand, Qty, Unit and Price.
    """
    df2 = df.copy()

    # Normalise date to a plain Python date for reliable grouping
    df2["Date"] = pd.to_datetime(
        normalize_dataframe_dates(df2, "Date")["Date"], errors="coerce"
    ).dt.date

    # Coerce price
    df2["PricePaid"] = pd.to_numeric(df2["PricePaid"], errors="coerce").fillna(0)

    # Fill missing shop so grouping never breaks
    df2["Shop"] = df2["Shop"].fillna("Unknown Shop").replace("", "Unknown Shop")

    # Sort most-recent first
    df2 = df2.sort_values("Date", ascending=False)

    # Build (Date, Shop) groups maintaining sort order
    groups = df2.groupby(["Date", "Shop"], sort=False)

    # Columns to show inside each transaction's item table
    item_cols_wanted = ["Category", "Subcategory", "Item", "Brand", "Quantity", "QuantityUnit", "PricePaid", "Currency"]
    item_cols = [c for c in item_cols_wanted if c in df2.columns]

    for (txn_date, shop), grp in groups:
        total = grp["PricePaid"].sum()
        n_items = len(grp)
        date_str = format_date(txn_date) if txn_date else "—"

        # Build a compact category summary for the expander label
        if "Category" in grp.columns:
            cats = grp["Category"].dropna().unique().tolist()
            cat_summary = ", ".join(cats[:3])
            if len(cats) > 3:
                cat_summary += f" +{len(cats) - 3}"
        else:
            cat_summary = ""

        label = (
            f"📅 {date_str}  ·  🏪 {shop}  ·  "
            f"{n_items} item{'s' if n_items != 1 else ''}  ·  "
            f"**{total:,.2f} SEK**"
            + (f"  ·  _{cat_summary}_" if cat_summary else "")
        )

        with st.expander(label, expanded=False):
            # Item table (clean, hide index)
            display = grp[item_cols].copy().reset_index(drop=True)
            if "PricePaid" in display.columns:
                display = display.rename(columns={"PricePaid": "Price (SEK)"})
            st.dataframe(display, hide_index=True, width='stretch')

            # Transaction total row
            st.markdown(
                f"<div style='text-align:right; font-size:0.9rem; "
                f"color:{t.get('text_muted','#94a3b8')}; margin-top:4px;'>"
                f"Transaction total &nbsp; "
                f"<span style='font-weight:700; color:{t.get('text_primary','#0f172a')};'>"
                f"{total:,.2f} SEK</span></div>",
                unsafe_allow_html=True,
            )


# ── Public page entry-point ────────────────────────────────────

def _pending_bills_badge() -> None:
    """Show a banner with the count of pending (un-itemised) bills."""
    if not ff.HAS_PENDING_BILLS:
        return
    try:
        from pending_bills import pending_count
        n = pending_count()
    except Exception:
        return
    if n <= 0:
        return

    col_msg, col_btn = st.columns([4, 1])
    with col_msg:
        st.info(
            f"🧾 You have **{n}** pending bill{'s' if n != 1 else ''} waiting to be itemised."
        )
    with col_btn:
        if st.button("Review →", key="goto_pending_bills", width="stretch"):
            st.session_state["page"] = "pending_bills"
            st.rerun()


def render(df: pd.DataFrame, save_data, sheet, t: dict) -> None:
    """
    Render the main dashboard page.

    Parameters
    ----------
    df        : Full (user-filtered) expense DataFrame
    save_data : Callable(df, sheet) that persists data
    sheet     : Storage handle (Google Sheet or local)
    t         : Active theme dict — passed explicitly, never global
    """
    from datetime import date as _date

    hero(
        "Expense Dashboard",
        f"Tracking your spending — as of {_date.today().strftime('%B %d, %Y')}",
        "💳",
    )

    # Sidebar add-expense (renders into the sidebar, not the main canvas)
    sidebar_add_expense(df, lambda d: save_data(d, sheet))

    # Filters and export live in the sidebar by design (these functions render
    # into st.sidebar), keeping the main canvas clean.
    df_filtered = filter_section(df)
    if ff.export_buttons is not None:
        ff.export_buttons(df)

    # ── Main-area strip: notifications + data-fix widgets (only appear when
    #    they actually have something to show) ──
    _pending_bills_badge()
    if not df.empty:
        _alerts_banner(df)
    handle_import_merge(df, save_data, sheet)
    incomplete_entries_expander(df, save_data, sheet)

    # ── Period selector drives every tab below ──
    section_header("📅 Select Period", "Choose the time window to analyse")
    df_period = period_selector(df_filtered)

    if df_period.empty:
        st.info("No data for the selected period. Adjust the filters or period above.")
        return

    # ── Segmented dashboard: keeps each view focused instead of one long scroll ──
    tab_overview, tab_records, tab_insights = st.tabs(
        ["📊 Overview", "🧾 Records", "🧠 Insights"]
    )

    with tab_overview:
        section_header("📈 Overview", "Key spending metrics for the selected period")
        if ff.HAS_INTELLIGENCE and ff.smart_kpi_row is not None:
            ff.smart_kpi_row(df)
        else:
            kpi_row(df_period, df_full=df)

        st.markdown("")
        col1, col2 = st.columns([1.4, 1])
        with col1:
            monthly_bar_chart(df_filtered, t)
        with col2:
            donut_chart(df_period, t)

    with tab_records:
        section_header("🧾 Expense Records", "Transactions grouped by date and shop")
        _render_transaction_groups(df_period, t)

    with tab_insights:
        if ff.HAS_INTELLIGENCE:
            _quick_intelligence(df, df_period)

        section_header("🔍 Period Summary", "At-a-glance totals for the current view")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Transactions", len(df_period))
        c2.metric(
            "Highest Single",
            f"{df_period['PricePaid'].max():,.0f} SEK"
            if df_period["PricePaid"].notna().any() else "—",
        )
        c3.metric(
            "Avg Transaction",
            f"{df_period['PricePaid'].mean():,.0f} SEK"
            if df_period["PricePaid"].notna().any() else "—",
        )
        c4.metric(
            "Unique Categories",
            df_period["Category"].nunique() if "Category" in df_period.columns else "—",
        )
