# pages/page_dashboard.py
# ──────────────────────────────────────────────────────────────
#  Dashboard page — overview KPIs, period selector, quick charts
# ──────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd

from date_utils import normalize_dataframe_dates, format_date
from data_manager import bump_data_version, clean_data
from ui_components import sidebar_add_expense, filter_section
from charts import kpi_row
from analytics import monthly_trends
from alerts_engine import get_all_alerts, get_enabled_alerts
from page_helpers import hero, donut_chart, monthly_bar_chart, period_selector, incomplete_entries_expander
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

def _handle_import_merge(df: pd.DataFrame, save_data, sheet) -> None:
    show_import = (
        not st.session_state.get("merge_complete", False)
        and not st.session_state.get("merge_complete_flagged", False)
    )
    if show_import:
        existing_cols = df.columns.tolist() if not df.empty else None
        if ff.HAS_IMPORT_WORKFLOW:
            ff.import_workflow(existing_columns=existing_cols)
        elif ff.import_button is not None:
            imported = ff.import_button(existing_columns=existing_cols)
            if imported is not None and not imported.empty:
                if "Date" in imported.columns:
                    imported["Date"] = normalize_dataframe_dates(imported, "Date")["Date"]
                st.session_state["pending_import_df"] = imported
                st.session_state["merge_ready"] = True
                st.subheader("📄 Preview")
                st.dataframe(imported, width="stretch", hide_index=True)
    else:
        if st.session_state.get("merge_complete"):
            st.sidebar.success("✅ Last import merged.")

    if st.session_state.get("merge_ready", False):
        if ff.HAS_MERGE:
            ff.perform_merge_if_ready(df, save_data, sheet)
        else:
            pending = st.session_state.get("pending_import_df", pd.DataFrame())
            if not pending.empty:
                try:
                    combined = pd.concat([df, pending], ignore_index=True)
                    from data_manager import clean_data
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


# ── Quick-Intelligence strip ───────────────────────────────────

def _quick_intelligence(df: pd.DataFrame, df_period: pd.DataFrame) -> None:
    st.markdown("---")
    st.markdown("### ⚡ Quick Intelligence")

    df_prep = df.copy()
    df_prep["Date"] = pd.to_datetime(
        normalize_dataframe_dates(df_prep, "Date")["Date"], errors="coerce"
    )
    df_prep["PricePaid"] = pd.to_numeric(df_prep["PricePaid"], errors="coerce").fillna(0)
    df_prep["YM"] = df_prep["Date"].dt.to_period("M").astype(str)

    now = pd.Timestamp.now()
    curr_ym = now.to_period("M").strftime("%Y-%m")
    prev_ym = (now - pd.DateOffset(months=1)).to_period("M").strftime("%Y-%m")
    this_mo = df_prep[df_prep["YM"] == curr_ym]["PricePaid"].sum()
    prev_mo = df_prep[df_prep["YM"] == prev_ym]["PricePaid"].sum()
    avg_3mo = df_prep.groupby("YM")["PricePaid"].sum().sort_index().tail(4).head(3).mean()
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


# ── Public page entry-point ────────────────────────────────────

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

    sidebar_add_expense(df, lambda d: save_data(d, sheet))
    df_filtered = filter_section(df)
    _handle_import_merge(df, save_data, sheet)

    if ff.export_buttons is not None:
        ff.export_buttons(df)

    incomplete_entries_expander(df, save_data, sheet)

    if not df.empty:
        _alerts_banner(df)

    st.markdown("---")
    st.markdown("### 📅 Select Period")
    df_period = period_selector(df_filtered)

    st.markdown("### 📈 Overview")
    if not df_period.empty:
        if ff.HAS_INTELLIGENCE and ff.smart_kpi_row is not None:
            ff.smart_kpi_row(df)
        else:
            kpi_row(df_period)
    else:
        st.info("No data for selected period.")

    if not df_period.empty:
        st.markdown("")
        col1, col2 = st.columns([1.4, 1])
        with col1:
            monthly_bar_chart(df_filtered, t)     # t passed explicitly ✓
        with col2:
            donut_chart(df_period, t)             # t passed explicitly ✓

    if ff.HAS_INTELLIGENCE and not df_period.empty:
        _quick_intelligence(df, df_period)

    if not df_period.empty:
        st.markdown("---")
        st.markdown("### 🔍 Period Summary")
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

    st.markdown("### 🧾 Expense Records")
    if not df_period.empty:
        disp = df_period.copy()
        disp["Date"] = disp["Date"].apply(format_date)
        st.dataframe(disp, width="stretch", hide_index=True)
    else:
        st.info("No expenses for selected period.")
