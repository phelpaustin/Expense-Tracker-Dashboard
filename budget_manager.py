# budget_manager.py
"""
Budget tracking module with total monthly budget + optional category budgets.
Theme-aware: respects the active app theme for all charts and cards.
"""
import json
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from config import Columns
from theme import get_chart_theme
from ai_insights import _get_keys, _call_ai


# ══════════════════════════════════════════════════════════════════════════
# THEME SUPPORT — single source of truth lives in theme.py
# ══════════════════════════════════════════════════════════════════════════

# Special key used to store the total monthly budget inside budgets.json
TOTAL_BUDGET_KEY = "__total_monthly__"
# Sentinel key holding the flexible-budget config (period + rollover).
BUDGET_CONFIG_KEY = "__config__"
# Aliases so the flexible-period helpers read clearly.
_date = date
_timedelta = timedelta


def _t() -> dict:
    return get_chart_theme()


# ══════════════════════════════════════════════════════════════════════════
# BUDGET STORAGE
# ══════════════════════════════════════════════════════════════════════════
BUDGET_FILE = "data/budgets.json"
from json_store import JsonStore
_STORE = JsonStore(BUDGET_FILE, default={}, sync=True)


def load_budgets() -> dict:
    return _STORE.load()


def save_budgets(budgets: dict) -> None:
    _STORE.save(budgets)


def get_total_monthly_budget() -> Optional[float]:
    """Return the total monthly budget, or None if not set."""
    budgets = load_budgets()
    val = budgets.get(TOTAL_BUDGET_KEY)
    return float(val) if val else None


def set_total_monthly_budget(amount: float) -> None:
    """Save (or clear) the total monthly budget."""
    budgets = load_budgets()
    if amount and amount > 0:
        budgets[TOTAL_BUDGET_KEY] = amount
    else:
        budgets.pop(TOTAL_BUDGET_KEY, None)
    save_budgets(budgets)


def _category_budgets_only(budgets: dict) -> dict:
    """Return budgets dict without the total-monthly / config sentinel keys."""
    return {k: v for k, v in budgets.items() if k not in (TOTAL_BUDGET_KEY, BUDGET_CONFIG_KEY)}


# ══════════════════════════════════════════════════════════════════════════
# FLEXIBLE BUDGET PERIODS  (weekly / monthly / annual + rollover)
# ══════════════════════════════════════════════════════════════════════════
# Config lives under a sentinel key in budgets.json. Default = Monthly, no
# rollover → identical to the previous monthly-only behaviour.
BUDGET_PERIODS = ["Weekly", "Monthly", "Annual"]


def get_budget_config() -> dict:
    cfg = load_budgets().get(BUDGET_CONFIG_KEY) or {}
    period = cfg.get("period")
    return {
        "period": period if period in BUDGET_PERIODS else "Monthly",
        "rollover": bool(cfg.get("rollover", False)),
    }


def set_budget_config(period: str, rollover: bool) -> None:
    budgets = load_budgets()
    budgets[BUDGET_CONFIG_KEY] = {
        "period": period if period in BUDGET_PERIODS else "Monthly",
        "rollover": bool(rollover),
    }
    save_budgets(budgets)


def current_period_range(period_type: str, when: _date = None):
    """Return ``(start, end, label, total_days)`` for the period containing *when*."""
    when = when or _date.today()
    if period_type == "Weekly":
        start = when - _timedelta(days=when.weekday())      # Monday
        end = start + _timedelta(days=6)
        label = f"Week of {start:%b %d}"
    elif period_type == "Annual":
        start = _date(when.year, 1, 1)
        end = _date(when.year, 12, 31)
        label = str(when.year)
    else:  # Monthly
        start = when.replace(day=1)
        if when.month == 12:
            end = _date(when.year, 12, 31)
        else:
            end = _date(when.year, when.month + 1, 1) - _timedelta(days=1)
        label = f"{when:%B %Y}"
    return start, end, label, (end - start).days + 1


def spending_in_range(df: pd.DataFrame, start: _date, end: _date) -> float:
    """Total spending with a date in [start, end]."""
    if df is None or df.empty:
        return 0.0
    d = df.copy()
    d[Columns.PRICE_PAID] = pd.to_numeric(d[Columns.PRICE_PAID], errors="coerce").fillna(0)
    d[Columns.DATE] = pd.to_datetime(d[Columns.DATE], errors="coerce")
    d = d.dropna(subset=[Columns.DATE])
    mask = (d[Columns.DATE].dt.date >= start) & (d[Columns.DATE].dt.date <= end)
    return float(d.loc[mask, Columns.PRICE_PAID].sum())


def rollover_available(df: pd.DataFrame, budget: float, period_type: str,
                       current_start: _date, lookback: int = 24) -> float:
    """
    Net unspent budget carried from prior periods (only over periods within the
    recorded data range, so a fresh dataset doesn't fabricate huge surpluses).
    Can be negative when past periods overspent.
    """
    if not budget or budget <= 0 or df is None or df.empty:
        return 0.0
    dates = pd.to_datetime(df[Columns.DATE], errors="coerce").dropna()
    if dates.empty:
        return 0.0
    earliest = dates.min().date()
    carry = 0.0
    cursor_start = current_start
    for _ in range(lookback):
        prev_end = cursor_start - _timedelta(days=1)
        if prev_end < earliest:
            break
        p_start, p_end, _lbl, _tot = current_period_range(period_type, prev_end)
        carry += budget - spending_in_range(df, p_start, p_end)
        cursor_start = p_start
    return round(carry, 2)


def period_budget_status(df: pd.DataFrame) -> Optional[dict]:
    """
    Current-period budget status honouring the configured period + rollover.
    Returns None when no total budget is set.
    """
    budget = get_total_monthly_budget()   # amount is per the configured period
    if not budget:
        return None
    cfg = get_budget_config()
    start, end, label, total_days = current_period_range(cfg["period"])
    spent = spending_in_range(df, start, end)
    roll = rollover_available(df, budget, cfg["period"], start) if cfg["rollover"] else 0.0
    effective = budget + roll
    remaining = effective - spent
    pct = (spent / effective * 100) if effective > 0 else 0
    today = _date.today()
    days_elapsed = max((min(today, end) - start).days + 1, 1)
    projected = (spent / days_elapsed) * total_days
    return {
        "period": cfg["period"], "label": label, "budget": budget,
        "rollover": roll, "effective": effective, "spent": spent,
        "remaining": remaining, "pct": pct, "projected": projected,
        "days_total": total_days, "days_elapsed": days_elapsed,
        "days_remaining": max(total_days - days_elapsed, 0),
    }


# ══════════════════════════════════════════════════════════════════════════
# SPENDING CALCULATIONS
# ══════════════════════════════════════════════════════════════════════════
def get_available_months(df: pd.DataFrame) -> list:
    """Return sorted list of year-month periods present in df, newest first."""
    if df.empty:
        return []
    df2 = df.copy()
    df2[Columns.DATE] = pd.to_datetime(df2[Columns.DATE], errors="coerce")
    periods = df2[Columns.DATE].dt.to_period("M").dropna().unique()
    return sorted(periods, reverse=True)


def get_total_monthly_spending(df: pd.DataFrame, period=None) -> float:
    """Sum all spending in the given period (pd.Period or 'YYYY-MM' str). Defaults to current month."""
    if df.empty:
        return 0.0
    df2 = df.copy()
    df2[Columns.PRICE_PAID] = pd.to_numeric(df2[Columns.PRICE_PAID], errors="coerce").fillna(0)
    df2[Columns.DATE] = pd.to_datetime(df2[Columns.DATE], errors="coerce")
    target = pd.Period(period, "M") if period is not None else pd.Timestamp.now().to_period("M")
    df2["_ym"] = df2[Columns.DATE].dt.to_period("M")
    return df2[df2["_ym"] == target][Columns.PRICE_PAID].sum()


def calculate_budget_status(df: pd.DataFrame, budgets: dict, period=None) -> List[Dict]:
    """
    Calculate spending vs budget for each category budget.
    period: pd.Period or 'YYYY-MM' string. Defaults to current month.
    Also prepends a 'Total' row using the total monthly budget if set.
    """
    if df.empty and not budgets:
        return []

    # Accept None, "monthly" (legacy alias), a pd.Period, or a "YYYY-MM" string
    if period is None or period == "monthly":
        target = pd.Timestamp.now().to_period("M")
    elif isinstance(period, pd.Period):
        target = period
    else:
        target = pd.Period(period, "M")

    df2 = df.copy()
    df2[Columns.PRICE_PAID] = pd.to_numeric(df2[Columns.PRICE_PAID], errors="coerce").fillna(0)
    df2[Columns.DATE] = pd.to_datetime(df2[Columns.DATE], errors="coerce")
    df2["_ym"] = df2[Columns.DATE].dt.to_period("M")
    df2 = df2[df2["_ym"] == target]

    category_spending = df2.groupby(Columns.CATEGORY)[Columns.PRICE_PAID].sum().to_dict()
    cat_budgets = _category_budgets_only(budgets)

    statuses = []
    for category, budget in cat_budgets.items():
        spent = category_spending.get(category, 0)
        remaining = budget - spent
        pct = (spent / budget * 100) if budget > 0 else 0
        status = "exceeded" if pct >= 100 else "warning" if pct >= 85 else "caution" if pct >= 60 else "ok"
        statuses.append({"category": category, "budget": budget, "spent": spent,
                         "remaining": remaining, "pct": pct, "status": status})

    # Build Total row
    total_budget = budgets.get(TOTAL_BUDGET_KEY)
    total_spent = get_total_monthly_spending(df, period=target)

    if total_budget:
        total_remaining = total_budget - total_spent
        total_pct = (total_spent / total_budget * 100) if total_budget > 0 else 0
        total_status = "exceeded" if total_pct >= 100 else "warning" if total_pct >= 85 else "caution" if total_pct >= 60 else "ok"
        statuses.insert(0, {"category": "Total", "budget": total_budget, "spent": total_spent,
                             "remaining": total_remaining, "pct": total_pct, "status": total_status})
    elif statuses:
        # Derive totals from category budgets when no global budget is set
        tb = sum(s["budget"] for s in statuses)
        ts = sum(s["spent"] for s in statuses)
        tr = tb - ts
        tp = (ts / tb * 100) if tb > 0 else 0
        t_status = "exceeded" if tp >= 100 else "warning" if tp >= 85 else "caution" if tp >= 60 else "ok"
        statuses.insert(0, {"category": "Total", "budget": tb, "spent": ts,
                             "remaining": tr, "pct": tp, "status": t_status})

    return statuses


# ══════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ══════════════════════════════════════════════════════════════════════════
def _status_color(status: str) -> str:
    return {"ok": "#22c55e", "caution": "#f59e0b", "warning": "#f97316", "exceeded": "#ef4444"}.get(status, "#64748b")


def _metric_box(label: str, value: str, sub: str, val_color: str, muted: str) -> str:
    """Return a single stat box as an HTML string (no f-string nesting needed at call site)."""
    return (
        '<div style="text-align:center;min-width:70px;">'
        f'<div style="font-size:0.68rem;color:{muted};font-weight:700;text-transform:uppercase;letter-spacing:0.08em;">{label}</div>'
        f'<div style="font-size:1.2rem;font-weight:700;color:{val_color};">{value}</div>'
        f'<div style="font-size:0.7rem;color:{muted};">{sub}</div>'
        '</div>'
    )


def _render_total_budget_card(df: pd.DataFrame, period=None):
    """Hero card for the total monthly budget."""
    t = _t()
    total_budget = get_total_monthly_budget()
    target = pd.Period(period, "M") if period is not None else pd.Timestamp.now().to_period("M")
    is_current = (target == pd.Timestamp.now().to_period("M"))
    total_spent = get_total_monthly_spending(df, period=target)

    if not total_budget:
        st.info("💡 No total monthly budget set yet. Go to **Setup** → Section 1 to set one.")
        return

    remaining = total_budget - total_spent
    pct = min((total_spent / total_budget * 100), 100) if total_budget else 0
    status = "exceeded" if pct >= 100 else "warning" if pct >= 85 else "caution" if pct >= 60 else "ok"
    color = _status_color(status)
    icon = {"ok": "✅", "caution": "🟡", "warning": "🟠", "exceeded": "🔴"}.get(status, "⚪")
    days_in_month = target.days_in_month
    period_label = "This Month" if is_current else str(target)
    remaining_label = "remaining" if is_current else ("under budget" if remaining >= 0 else "over budget")

    # ── Pre-compute all scalar values so no HTML is stored in a variable ──
    if is_current:
        now = datetime.now()
        days_elapsed = max(now.day, 1)
        days_remaining = days_in_month - now.day
        daily_avg = total_spent / days_elapsed
        projected = daily_avg * days_in_month
        proj_color = "#ef4444" if projected > total_budget else "#22c55e"

        m1 = _metric_box("Daily Avg", f"{daily_avg:,.0f}", "SEK/day", t["fg"], t["muted"])
        m2 = _metric_box("Projected", f"{projected:,.0f}", "SEK", proj_color, t["muted"])
        m3 = _metric_box("Days Left", str(days_remaining), f"of {days_in_month}", t["fg"], t["muted"])
    else:
        saved = total_budget - total_spent
        saved_color = "#22c55e" if saved >= 0 else "#ef4444"
        saved_label = "Saved" if saved >= 0 else "Over"
        daily_avg = total_spent / days_in_month

        m1 = _metric_box("Daily Avg", f"{daily_avg:,.0f}", "SEK/day", t["fg"], t["muted"])
        m2 = _metric_box(saved_label, f"{abs(saved):,.0f}", "SEK", saved_color, t["muted"])
        m3 = _metric_box("Days", str(days_in_month), "in month", t["fg"], t["muted"])

    st.markdown(
        f'<div style="background:{t["card"]};border:2px solid {color};border-radius:16px;'
        f'padding:1.6rem 2rem;margin-bottom:1.25rem;box-shadow:0 4px 20px rgba(0,0,0,0.07);">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:1rem;">'
        f'<div style="flex:1;min-width:220px;">'
        f'<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:{t["muted"]};margin-bottom:0.3rem;">'
        f'{icon} {period_label} Budget</div>'
        f'<div style="font-size:2.4rem;font-weight:800;color:{t["fg"]};line-height:1.1;">'
        f'{total_spent:,.0f} <span style="font-size:1.1rem;font-weight:500;color:{t["muted"]}">/ {total_budget:,.0f} SEK</span></div>'
        f'<div style="margin-top:0.8rem;background:{t["bar_bg"]};border-radius:999px;height:12px;overflow:hidden;">'
        f'<div style="background:{color};width:{pct:.1f}%;height:100%;border-radius:999px;"></div></div>'
        f'<div style="margin-top:0.5rem;font-size:0.85rem;color:{color};font-weight:600;">'
        f'{pct:.1f}% used · <span style="color:{t["muted"]};font-weight:400;">{remaining:,.0f} SEK {remaining_label}</span></div>'
        f'</div>'
        f'<div style="display:flex;gap:1.5rem;flex-wrap:wrap;align-items:center;">'
        f'{m1}{m2}{m3}'
        f'</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def _render_budget_card(status: dict, large: bool = False):
    t = _t()
    cat = status["category"]
    budget = status.get("budget", 0) or 0
    spent = status.get("spent", 0) or 0
    remaining = status.get("remaining", 0) or 0
    pct = status.get("pct", 0) or 0
    s = status["status"]
    color = _status_color(s)
    icon = {"ok": "✅", "caution": "🟡", "warning": "🟠", "exceeded": "🔴"}.get(s, "⚪")

    st.markdown(f"""
    <div style="background:{t['card']};border-left:4px solid {color};border-radius:10px;
                padding:{'1.5rem' if large else '1rem'};margin-bottom:0.75rem;border:1px solid {t['border']};">
        <div style="font-size:{'1.1rem' if large else '0.9rem'};color:{t['muted']};margin-bottom:0.25rem;">{icon} {cat}</div>
        <div style="font-size:{'2rem' if large else '1.4rem'};font-weight:700;color:{t['fg']};">{spent:,.0f} SEK</div>
        <div style="font-size:0.85rem;color:{t['muted']};">of {budget:,.0f} SEK budget</div>
        <div style="background:{t['bar_bg']};border-radius:999px;height:8px;margin:0.75rem 0 0.25rem 0;overflow:hidden;">
            <div style="background:{color};height:100%;width:{min(pct,100):.1f}%;border-radius:999px;"></div>
        </div>
        <div style="font-size:0.8rem;color:{color};font-weight:600;">{pct:.1f}% used · {remaining:,.0f} SEK remaining</div>
    </div>
    """, unsafe_allow_html=True)


def _render_budget_alerts(statuses: list):
    exceeded = [s for s in statuses if s["status"] == "exceeded"]
    warning  = [s for s in statuses if s["status"] == "warning"]
    if exceeded:
        st.markdown("### 🚨 Budget Exceeded")
        for s in exceeded:
            st.error(f"**{s['category']}**: Spent {s['spent']:,.0f} SEK — "
                     f"{s['pct']:.1f}% of {s['budget']:,.0f} SEK budget "
                     f"(over by {abs(s['remaining']):,.0f} SEK)")
    if warning:
        st.markdown("### ⚠️ Budget Warning")
        for s in warning:
            st.warning(f"**{s['category']}**: {s['pct']:.1f}% used "
                       f"({s['spent']:,.0f} / {s['budget']:,.0f} SEK)")


# ══════════════════════════════════════════════════════════════════════════
# MAIN UI FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════
def _render_period_budget_card(df: pd.DataFrame):
    """Current-period budget hero honouring the configured period + rollover."""
    stt = period_budget_status(df)
    if not stt:
        return
    t = _t()
    pct = min(stt["pct"], 100)
    status = ("exceeded" if stt["pct"] >= 100 else "warning" if stt["pct"] >= 85
              else "caution" if stt["pct"] >= 60 else "ok")
    color = _status_color(status)
    icon = {"ok": "✅", "caution": "🟡", "warning": "🟠", "exceeded": "🔴"}.get(status, "⚪")
    proj_color = "#ef4444" if stt["projected"] > stt["effective"] else "#22c55e"

    roll_line = ""
    if stt["rollover"]:
        rc = "#22c55e" if stt["rollover"] >= 0 else "#ef4444"
        roll_line = (
            f'<div style="font-size:0.8rem;color:{t["muted"]};margin-top:0.4rem;">'
            f'Rollover carried: <span style="color:{rc};font-weight:600;">{stt["rollover"]:+,.0f} SEK</span> '
            f'→ effective budget {stt["effective"]:,.0f} SEK</div>'
        )

    m1 = _metric_box("Projected", f'{stt["projected"]:,.0f}', "SEK", proj_color, t["muted"])
    m2 = _metric_box("Remaining", f'{stt["remaining"]:,.0f}', "SEK", color, t["muted"])
    m3 = _metric_box("Days Left", str(stt["days_remaining"]), f'of {stt["days_total"]}', t["fg"], t["muted"])

    st.markdown(
        f'<div style="background:{t["card"]};border:2px solid {color};border-radius:16px;'
        f'padding:1.6rem 2rem;margin-bottom:1.25rem;box-shadow:0 4px 20px rgba(0,0,0,0.07);">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:1rem;">'
        f'<div style="flex:1;min-width:220px;">'
        f'<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:{t["muted"]};margin-bottom:0.3rem;">'
        f'{icon} {stt["period"]} Budget · {stt["label"]}</div>'
        f'<div style="font-size:2.4rem;font-weight:800;color:{t["fg"]};line-height:1.1;">'
        f'{stt["spent"]:,.0f} <span style="font-size:1.1rem;font-weight:500;color:{t["muted"]}">/ {stt["effective"]:,.0f} SEK</span></div>'
        f'<div style="margin-top:0.8rem;background:{t["bar_bg"]};border-radius:999px;height:12px;overflow:hidden;">'
        f'<div style="background:{color};width:{pct:.1f}%;height:100%;border-radius:999px;"></div></div>'
        f'<div style="margin-top:0.5rem;font-size:0.85rem;color:{color};font-weight:600;">'
        f'{stt["pct"]:.1f}% used · <span style="color:{t["muted"]};font-weight:400;">{stt["remaining"]:,.0f} SEK remaining</span></div>'
        f'{roll_line}'
        f'</div>'
        f'<div style="display:flex;gap:1.5rem;flex-wrap:wrap;align-items:center;">'
        f'{m1}{m2}{m3}'
        f'</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def budget_dashboard_ui(df: pd.DataFrame):
    """Main budget dashboard — month selector, total budget hero card, then category cards."""
    st.markdown("### 📊 Budget Dashboard")

    budgets = load_budgets()
    total_budget = get_total_monthly_budget()
    cat_budgets  = _category_budgets_only(budgets)

    if not total_budget and not cat_budgets:
        st.info("💡 No budgets set yet. Switch to the **Setup** tab to create your first budget!")
        return

    # ── Flexible-period hero (only when not the default monthly / rollover on) ──
    _cfg = get_budget_config()
    if total_budget and (_cfg["period"] != "Monthly" or _cfg["rollover"]):
        _render_period_budget_card(df)
        st.caption("Showing your configured budget period. The monthly view below is unchanged.")
        st.markdown("---")

    # ── Month selector ─────────────────────────────────────────────────────
    available_months = get_available_months(df)
    current_period = pd.Timestamp.now().to_period("M")

    if available_months:
        month_options = [str(m) for m in available_months]
        default_idx = month_options.index(str(current_period)) if str(current_period) in month_options else 0

        # Use a separate idx key — never write to the widget's own key after it's rendered
        if "budget_month_idx" not in st.session_state:
            st.session_state["budget_month_idx"] = default_idx
        st.session_state["budget_month_idx"] = max(0, min(st.session_state["budget_month_idx"], len(month_options) - 1))

        col_prev, col_drop, col_next = st.columns([1, 8, 1])
        with col_prev:
            if st.button("◀", key="budget_prev_month", width='stretch',
                         disabled=(st.session_state["budget_month_idx"] >= len(month_options) - 1),
                         help="Previous month"):
                st.session_state["budget_month_idx"] += 1
                st.rerun()
        with col_drop:
            selected_month_str = st.selectbox(
                "Viewing month",
                month_options,
                index=st.session_state["budget_month_idx"],
                key="budget_month_selector",
                label_visibility="collapsed",
            )
            # Keep idx in sync when user picks from the dropdown directly
            new_idx = month_options.index(selected_month_str)
            if new_idx != st.session_state["budget_month_idx"]:
                st.session_state["budget_month_idx"] = new_idx
        with col_next:
            if st.button("▶", key="budget_next_month", width='stretch',
                         disabled=(st.session_state["budget_month_idx"] <= 0),
                         help="Next month"):
                st.session_state["budget_month_idx"] -= 1
                st.rerun()
        selected_period = pd.Period(selected_month_str, "M")
    else:
        selected_period = current_period

    # ── Total monthly budget hero ──────────────────────────────────────────
    _render_total_budget_card(df, period=selected_period)

    # ── Alerts ────────────────────────────────────────────────────────────
    if cat_budgets:
        statuses = calculate_budget_status(df, budgets, period=selected_period)
        _render_budget_alerts([s for s in statuses if s["category"] != "Total"])

        st.markdown("### 📋 Category Budgets")
        category_statuses = [s for s in statuses if s["category"] != "Total"]

        if category_statuses:
            view_mode = st.radio("Display Mode", ["Cards", "Table"], horizontal=True, key="budget_view_mode")

            if view_mode == "Cards":
                cols = st.columns(2)
                for idx, status in enumerate(category_statuses):
                    with cols[idx % 2]:
                        _render_budget_card(status)
            else:
                table_data = []
                for s in category_statuses:
                    table_data.append({
                        "Category":  s["category"],
                        "Budget":    f"{s['budget']:,.0f} SEK",
                        "Spent":     f"{s['spent']:,.0f} SEK",
                        "Remaining": f"{s['remaining']:,.0f} SEK",
                        "% Used":    f"{s['pct']:.1f}%",
                        "Status":    {"ok": "✅ On Track", "caution": "🟡 Caution",
                                      "warning": "🟠 Warning", "exceeded": "🔴 Exceeded"}.get(s["status"], "—")
                    })
                st.dataframe(pd.DataFrame(table_data), width="stretch", hide_index=True)
    else:
        st.markdown("---")
        st.markdown("#### 💡 Tip")
        st.info("You can also add **per-category** budgets in the Setup tab "
                "to break down where your money is going.")


def budget_setup_ui(df: pd.DataFrame):
    """Budget setup — Section 1: total monthly budget, Section 2: optional category budgets."""
    st.markdown("### ⚙️ Budget Setup")

    # ── SECTION 1: Total Monthly Budget ───────────────────────────────────
    st.markdown("#### 💰 Section 1 — Total Monthly Budget")
    st.caption("Set a single spending cap for the entire month across all categories.")

    current_total = get_total_monthly_budget()

    col1, col2 = st.columns([2, 1])
    with col1:
        new_total = st.number_input(
            "Monthly Budget (SEK)",
            min_value=0.0,
            value=float(current_total) if current_total else 0.0,
            step=500.0,
            format="%.0f",
            help="Set 0 to remove the total budget",
            key="total_budget_input"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Save Total Budget", width="stretch", type="primary"):
            set_total_monthly_budget(new_total)
            if new_total > 0:
                st.success(f"✅ Total monthly budget set to **{new_total:,.0f} SEK**")
            else:
                st.info("Total monthly budget cleared.")
            st.rerun()

    # ── Budget period & rollover ──────────────────────────────────────────
    st.markdown("#### 🗓️ Budget Period & Rollover")
    st.caption("Track your total budget weekly, monthly, or annually — and optionally carry unspent budget forward.")
    _cfg = get_budget_config()
    pc1, pc2 = st.columns([2, 1])
    with pc1:
        sel_period = st.selectbox(
            "Budget period",
            BUDGET_PERIODS,
            index=BUDGET_PERIODS.index(_cfg["period"]),
            help="Your total budget amount is interpreted per this period.",
            key="budget_period_sel",
        )
    with pc2:
        st.markdown("<br>", unsafe_allow_html=True)
        sel_rollover = st.checkbox(
            "🔁 Rollover unspent",
            value=_cfg["rollover"],
            help="Carry each period's leftover (or overspend) into the next.",
            key="budget_rollover_chk",
        )
    if sel_period != _cfg["period"] or sel_rollover != _cfg["rollover"]:
        if st.button("💾 Save Period Settings", key="save_budget_period"):
            set_budget_config(sel_period, sel_rollover)
            st.success(
                f"✅ Budget period set to **{sel_period}**"
                + (" with rollover" if sel_rollover else "")
            )
            st.rerun()

    if current_total:
        t = _t()
        total_spent = get_total_monthly_spending(df)
        pct = (total_spent / current_total * 100) if current_total else 0
        color = _status_color("exceeded" if pct >= 100 else "warning" if pct >= 85 else "caution" if pct >= 60 else "ok")
        st.markdown(
            f"<div style='margin-top:0.5rem;padding:0.65rem 1rem;"
            f"background:{t['bar_bg']};border-radius:8px;border-left:3px solid {color};'>"
            f"<b style='color:{t['fg']};'>Current:</b> "
            f"<span style='color:{color};font-weight:700;'>{total_spent:,.0f} / {current_total:,.0f} SEK used ({pct:.1f}%)</span>"
            f"</div>",
            unsafe_allow_html=True
        )

    st.markdown("---")

    # ── AI Budget Suggestions ────────────────────────────────────────────
    _ai_budget_suggestions(df)

    # ── SECTION 2: Category Budgets (optional) ────────────────────────────
    st.markdown("#### 📂 Section 2 — Category Budgets *(Optional)*")
    st.caption("Optionally set per-category limits on top of your total budget for more detailed tracking.")

    categories = sorted(df[Columns.CATEGORY].dropna().unique().tolist()) if not df.empty else []
    if not categories:
        st.warning("No categories found. Add some expenses first to enable category budgets.")
    else:
        budgets = load_budgets()
        cat_budgets = _category_budgets_only(budgets)

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            selected_category = st.selectbox("Category", categories, key="budget_category")
        with c2:
            current_cat_budget = cat_budgets.get(selected_category, 0)
            budget_amount = st.number_input(
                "Category Budget (SEK)",
                min_value=0.0,
                value=float(current_cat_budget),
                step=100.0,
                key="budget_amount"
            )
        with c3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 Save Category", width="stretch"):
                budgets = load_budgets()
                if budget_amount > 0:
                    budgets[selected_category] = budget_amount
                    save_budgets(budgets)
                    st.success(f"✅ {selected_category}: {budget_amount:,.0f} SEK/month")
                else:
                    budgets.pop(selected_category, None)
                    save_budgets(budgets)
                    st.info(f"Category budget cleared for {selected_category}.")
                st.rerun()

        # Show existing category budgets
        if cat_budgets:
            st.markdown("##### Current Category Budgets")
            table = [{"Category": k, "Monthly Budget": f"{v:,.0f} SEK"} for k, v in sorted(cat_budgets.items())]
            st.dataframe(pd.DataFrame(table), width="stretch", hide_index=True)

            col_del1, col_del2 = st.columns([2, 1])
            with col_del1:
                cat_to_delete = st.selectbox("Select to delete", list(cat_budgets.keys()), key="delete_category")
            with col_del2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️ Delete", width="stretch", type="secondary"):
                    budgets = load_budgets()
                    budgets.pop(cat_to_delete, None)
                    save_budgets(budgets)
                    st.success(f"✅ Deleted budget for {cat_to_delete}")
                    st.rerun()

    st.markdown("---")

    # ── SECTION 3: Tips ───────────────────────────────────────────────────
    st.markdown("#### 💡 Section 3 — Tips")
    st.info("""
- **Total Budget** is your main guardrail — a single number for the whole month.
- **Category Budgets** are optional add-ons for finer control (e.g. keep Dining under 2,000 SEK).
- Both types show progress bars on the Dashboard tab in real time.
- Aim to keep the progress bar green (< 60% used) mid-month.
    """)

    st.markdown("---")

    # ── SECTION 4: Export / Import ────────────────────────────────────────
    st.markdown("#### 📤 Section 4 — Export / Import")
    col_io1, col_io2 = st.columns(2)

    budgets = load_budgets()
    with col_io1:
        if budgets:
            st.download_button(
                "📥 Export Budgets (JSON)",
                json.dumps(budgets, indent=2),
                "budgets.json",
                "application/json",
                width="stretch"
            )

    with col_io2:
        uploaded = st.file_uploader("📤 Import Budgets (JSON)", type=["json"], key="budget_import")
        if uploaded:
            try:
                imported = json.loads(uploaded.read())
                if isinstance(imported, dict):
                    save_budgets(imported)
                    st.success("✅ Budgets imported successfully!")
                    st.rerun()
                else:
                    st.error("Invalid JSON format")
            except Exception as e:
                st.error(f"Import failed: {e}")

# ══════════════════════════════════════════════════════════════════════════
# AI BUDGET SUGGESTIONS
# ══════════════════════════════════════════════════════════════════════════

def _ai_budget_suggestions(df: pd.DataFrame) -> None:
    """
    Analyse the last 3 months of spending per category and ask AI
    to recommend realistic monthly budget amounts.
    Shown inside budget_setup_ui() between the total budget and category sections.
    """
    import json
    t = _t()

    keys = _get_keys()
    if not any(keys.values()):
        return   # silently skip if no AI key — setup page still works fine

    st.markdown("---")
    st.markdown("#### 🤖 AI Budget Suggestions")
    st.caption("Based on your last 3 months of actual spending, the AI recommends per-category budgets.")

    cache_key = "ai_budget_suggestions"

    if cache_key not in st.session_state:
        if not st.button("✨ Generate AI Budget Suggestions", key="ai_budget_btn"):
            return

        if df.empty:
            st.info("No expense data found. Add some expenses first.")
            return

        # Build a 3-month category summary
        df2 = df.copy()
        df2[Columns.DATE] = pd.to_datetime(df2[Columns.DATE], errors="coerce")
        df2[Columns.PRICE_PAID] = pd.to_numeric(df2[Columns.PRICE_PAID], errors="coerce").fillna(0)
        df2[Columns.YEAR_MONTH] = df2[Columns.DATE].dt.to_period("M").astype(str)

        recent_3 = sorted(df2[Columns.YEAR_MONTH].unique())[-3:]
        df3 = df2[df2[Columns.YEAR_MONTH].isin(recent_3)]

        monthly_by_cat = (
            df3.groupby([Columns.YEAR_MONTH, Columns.CATEGORY])[Columns.PRICE_PAID]
            .sum().unstack(fill_value=0)
        )

        summary = {}
        for cat in monthly_by_cat.columns:
            vals = monthly_by_cat[cat].tolist()
            summary[cat] = {
                "monthly_values":  [round(v, 2) for v in vals],
                "average":         round(sum(vals) / len(vals), 2),
                "max":             round(max(vals), 2),
                "min":             round(min(vals), 2),
            }

        current_budgets = _category_budgets_only(load_budgets())

        system = (
            "You are a personal finance advisor. "
            "The user will give you their last 3 months of spending per category. "
            "Suggest a realistic monthly budget for each category. "
            "Budgets should be slightly above the average to be achievable, "
            "but tight enough to encourage discipline. "
            "Round to the nearest 50 SEK. "
            "Return ONLY a JSON object mapping category name to budget amount (integer). "
            "No markdown, no explanation, just the JSON."
        )
        user = (
            f"Here is my last 3 months of spending by category (SEK):\n"
            f"{json.dumps(summary, indent=2)}\n\n"
            f"Currently set budgets: {json.dumps(current_budgets)}\n\n"
            "Suggest a monthly budget for each category as a JSON object."
        )

        with st.spinner("AI is analysing your spending patterns…"):
            raw, provider = _call_ai(system, user, keys)

        # Parse the JSON response
        import re
        try:
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
            suggestions = json.loads(cleaned)
            if not isinstance(suggestions, dict):
                raise ValueError("not a dict")
            st.session_state[cache_key] = (suggestions, provider, summary)
        except Exception as e:
            st.error(f"AI returned unexpected format: {e}\n\nRaw: {raw[:300]}")
            return

    if cache_key not in st.session_state:
        return

    suggestions, provider, summary = st.session_state[cache_key]

    # Render suggestion cards
    muted_c = t["muted"]
    st.markdown(
        f"<div style='font-size:0.75rem;color:{muted_c};margin-bottom:0.75rem;'>"
        f"Suggestions from {provider} · based on your last 3 months</div>",
        unsafe_allow_html=True,
    )

    current_budgets = _category_budgets_only(load_budgets())
    cats = sorted(suggestions.keys())
    cols = st.columns(3)

    for i, cat in enumerate(cats):
        suggested = suggestions[cat]
        hist = summary.get(cat, {})
        avg  = hist.get("average", 0)
        with cols[i % 3]:
            diff     = suggested - current_budgets.get(cat, 0)
            diff_str = (f"+{diff:,.0f}" if diff > 0 else f"{diff:,.0f}") if cat in current_budgets else "new"
            diff_col = "#22c55e" if diff >= 0 else "#ef4444"
            card_bg = t["card"]
            card_border = t["border"]
            card_fg = t["fg"]
            card_muted = t["muted"]
            st.markdown(
                f"<div style='background:{card_bg};border:1px solid {card_border};"
                f"border-radius:10px;padding:0.8rem 1rem;margin-bottom:0.5rem;'>"
                f"<div style='font-size:0.78rem;color:{card_muted};'>{cat}</div>"
                f"<div style='font-size:1.3rem;font-weight:700;color:{card_fg};'>" 
                f"{suggested:,.0f} SEK</div>"
                f"<div style='font-size:0.72rem;color:{card_muted};'>" 
                f"avg {avg:,.0f} · "
                f"<span style='color:{diff_col};'>{diff_str} vs current</span></div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button(f"Apply {cat}", key=f"apply_ai_{cat}", use_container_width=True):
                budgets = load_budgets()
                budgets[cat] = suggested
                save_budgets(budgets)
                st.success(f"✅ {cat} budget set to {suggested:,.0f} SEK")
                st.rerun()

    # Apply all button
    st.markdown("<br>", unsafe_allow_html=True)
    col_all, col_clear = st.columns([2, 1])
    with col_all:
        if st.button("⚡ Apply ALL suggestions", type="primary", use_container_width=True, key="apply_all_ai"):
            budgets = load_budgets()
            for cat, amt in suggestions.items():
                budgets[cat] = amt
            save_budgets(budgets)
            st.session_state.pop(cache_key, None)
            st.success(f"✅ Applied {len(suggestions)} AI budget suggestions!")
            st.rerun()
    with col_clear:
        if st.button("🔄 Regenerate", use_container_width=True, key="regen_ai_budget"):
            st.session_state.pop(cache_key, None)
            st.rerun()

    st.markdown("---")
