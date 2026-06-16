# alerts_engine.py
"""
Smart budget alert system with threshold and predictive notifications.
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from config import Columns
from budget_manager import load_budgets, calculate_budget_status
from ai_insights import _get_keys, _call_ai


class BudgetAlert:
    """Represents a single budget alert."""
    
    SEVERITY_LEVELS = {
        "info": "💡",
        "caution": "🟡",
        "warning": "🟠",
        "critical": "🔴"
    }
    
    def __init__(
        self,
        category: str,
        severity: str,
        message: str,
        data: Dict = None
    ):
        self.category = category
        self.severity = severity
        self.message = message
        self.data = data or {}
        self.timestamp = datetime.now()
    
    def __repr__(self):
        icon = self.SEVERITY_LEVELS.get(self.severity, "ℹ️")
        return f"{icon} {self.message}"


def check_threshold_alerts(df: pd.DataFrame, budgets: Dict) -> List[BudgetAlert]:
    """
    Check if any budgets have crossed threshold levels (80%, 90%, 100%).
    
    Args:
        df: Expenses dataframe
        budgets: Dict of {category: budget_amount}
    
    Returns:
        List of BudgetAlert objects
    """
    alerts = []
    statuses = calculate_budget_status(df, budgets, period="monthly")
    
    for status in statuses:
        if status["category"] == "Total":
            continue
        
        pct = status["pct"]
        cat = status["category"]
        spent = status["spent"]
        budget = status["budget"]
        
        # Critical: Budget exceeded
        if pct >= 100:
            alerts.append(BudgetAlert(
                category=cat,
                severity="critical",
                message=f"Budget exceeded: {cat} is at {pct:.0f}% ({spent:,.0f} / {budget:,.0f} SEK)",
                data=status
            ))
        
        # Warning: 90-99%
        elif pct >= 90:
            remaining = budget - spent
            alerts.append(BudgetAlert(
                category=cat,
                severity="warning",
                message=f"Warning: {cat} is at {pct:.0f}% (only {remaining:,.0f} SEK left)",
                data=status
            ))
        
        # Caution: 80-89%
        elif pct >= 80:
            alerts.append(BudgetAlert(
                category=cat,
                severity="caution",
                message=f"Caution: {cat} is at {pct:.0f}% of budget",
                data=status
            ))
    
    return alerts


def check_predictive_alerts(df: pd.DataFrame, budgets: Dict) -> List[BudgetAlert]:
    """
    Predict if user will exceed budget based on current spending velocity.
    
    Args:
        df: Expenses dataframe
        budgets: Dict of {category: budget_amount}
    
    Returns:
        List of BudgetAlert objects
    """
    alerts = []
    
    if df.empty or not budgets:
        return alerts
    
    # Prepare data
    df = df.copy()
    df[Columns.DATE] = pd.to_datetime(df[Columns.DATE], errors="coerce")
    df[Columns.PRICE_PAID] = pd.to_numeric(df[Columns.PRICE_PAID], errors="coerce").fillna(0)
    
    # Filter to current month
    now = datetime.now()
    current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    df = df[df[Columns.DATE] >= current_month]
    
    # Calculate days elapsed and remaining in month
    days_elapsed = (now - current_month).days + 1
    days_in_month = (current_month.replace(month=current_month.month % 12 + 1, day=1) - timedelta(days=1)).day
    days_remaining = days_in_month - days_elapsed
    
    if days_remaining <= 0:
        return alerts
    
    # Check each budget category
    for category, budget in budgets.items():
        cat_spending = df[df[Columns.CATEGORY] == category][Columns.PRICE_PAID].sum()
        
        if cat_spending == 0:
            continue
        
        # Calculate daily velocity
        daily_avg = cat_spending / days_elapsed
        
        # Project end-of-month spending
        projected_total = daily_avg * days_in_month
        
        # Alert if projected to exceed
        if projected_total > budget:
            overage = projected_total - budget
            days_until_exceed = int((budget - cat_spending) / daily_avg) if daily_avg > 0 else 999
            
            if days_until_exceed <= 5:
                alerts.append(BudgetAlert(
                    category=category,
                    severity="warning",
                    message=(
                        f"📈 Prediction: {category} will exceed budget in ~{days_until_exceed} days "
                        f"(projected: {projected_total:,.0f} SEK)"
                    ),
                    data={
                        "current": cat_spending,
                        "budget": budget,
                        "projected": projected_total,
                        "overage": overage,
                        "days_until_exceed": days_until_exceed
                    }
                ))
            elif projected_total > budget * 1.1:  # More than 10% over
                alerts.append(BudgetAlert(
                    category=category,
                    severity="caution",
                    message=(
                        f"📊 Watch out: {category} is trending {(projected_total/budget-1)*100:.0f}% "
                        f"over budget (projected: {projected_total:,.0f} SEK)"
                    ),
                    data={
                        "current": cat_spending,
                        "budget": budget,
                        "projected": projected_total
                    }
                ))
    
    return alerts


def check_velocity_alerts(df: pd.DataFrame) -> List[BudgetAlert]:
    """
    Detect unusual spending velocity (spending much faster than usual).
    
    Args:
        df: Expenses dataframe
    
    Returns:
        List of BudgetAlert objects
    """
    alerts = []
    
    if df.empty:
        return alerts
    
    # Prepare data
    df = df.copy()
    df[Columns.DATE] = pd.to_datetime(df[Columns.DATE], errors="coerce")
    df[Columns.PRICE_PAID] = pd.to_numeric(df[Columns.PRICE_PAID], errors="coerce").fillna(0)
    df[Columns.YEAR_MONTH] = df[Columns.DATE].dt.to_period("M")
    
    # Get last 3 months for comparison
    recent_months = df[Columns.YEAR_MONTH].unique()
    if len(recent_months) < 2:
        return alerts  # Need at least 2 months for comparison
    
    current_month = recent_months[-1]
    prev_months = recent_months[-4:-1]  # Last 3 months before current
    
    # Calculate spending by category for current vs previous months
    current_spending = (
        df[df[Columns.YEAR_MONTH] == current_month]
        .groupby(Columns.CATEGORY)[Columns.PRICE_PAID]
        .sum()
    )
    
    prev_spending = (
        df[df[Columns.YEAR_MONTH].isin(prev_months)]
        .groupby(Columns.CATEGORY)[Columns.PRICE_PAID]
        .mean()  # Average of previous months
    )
    
    # Compare and alert on significant increases
    for category in current_spending.index:
        current = current_spending[category]
        baseline = prev_spending.get(category, 0)
        
        if baseline == 0:
            continue
        
        # Alert if 2x or more
        ratio = current / baseline
        if ratio >= 2.0:
            alerts.append(BudgetAlert(
                category=category,
                severity="caution",
                message=(
                    f"⚡ {category} spending is {ratio:.1f}x your usual rate "
                    f"({current:,.0f} SEK vs avg {baseline:,.0f} SEK)"
                ),
                data={
                    "current": current,
                    "baseline": baseline,
                    "ratio": ratio
                }
            ))
    
    return alerts


def get_all_alerts(df: pd.DataFrame, budgets: Dict) -> List[BudgetAlert]:
    """
    Get all active alerts (threshold + predictive + velocity).
    
    Args:
        df: Expenses dataframe
        budgets: Dict of {category: budget_amount}
    
    Returns:
        List of all active BudgetAlert objects, sorted by severity
    """
    alerts = []
    
    # Collect all alert types — use AI-personalised thresholds when available
    alerts.extend(check_threshold_alerts_ai(df, budgets))
    alerts.extend(check_predictive_alerts(df, budgets))
    alerts.extend(check_velocity_alerts(df))
    
    # Sort by severity (critical first)
    severity_order = {"critical": 0, "warning": 1, "caution": 2, "info": 3}
    alerts.sort(key=lambda a: severity_order.get(a.severity, 4))
    
    return alerts


def generate_daily_summary(df: pd.DataFrame, budgets: Dict) -> str:
    """
    Generate a daily spending summary for notifications.
    
    Args:
        df: Expenses dataframe
        budgets: Dict of {category: budget_amount}
    
    Returns:
        Formatted summary string
    """
    # Filter to today
    today = datetime.now().date()
    df = df.copy()
    df[Columns.DATE] = pd.to_datetime(df[Columns.DATE], errors="coerce")
    today_spending = df[df[Columns.DATE].dt.date == today][Columns.PRICE_PAID].sum()
    
    # This week
    week_start = today - timedelta(days=today.weekday())
    week_spending = df[df[Columns.DATE].dt.date >= week_start][Columns.PRICE_PAID].sum()
    
    # This month
    month_start = today.replace(day=1)
    month_spending = df[df[Columns.DATE].dt.date >= month_start][Columns.PRICE_PAID].sum()
    
    # Total budget for month
    total_budget = sum(budgets.values()) if budgets else 0
    budget_pct = (month_spending / total_budget * 100) if total_budget > 0 else 0
    
    summary = f"""
📊 Daily Summary for {today.strftime('%B %d, %Y')}

💰 Today: {today_spending:,.0f} SEK
📅 This week: {week_spending:,.0f} SEK  
📆 This month: {month_spending:,.0f} SEK ({budget_pct:.0f}% of budget)
"""
    
    return summary.strip()


def get_enabled_alerts(df: pd.DataFrame, budgets: Dict) -> List[BudgetAlert]:
    """
    Get only alerts that are enabled in settings.
    """
    from settings_page import load_alert_settings
    
    settings = load_alert_settings()
    
    if not settings.get("alerts_enabled", True):
        return []
    
    alerts = []
    
    # Threshold alerts
    threshold_alerts = check_threshold_alerts(df, budgets)
    for alert in threshold_alerts:
        pct = alert.data.get("pct", 0)
        if pct >= 100 and settings.get("threshold_100", True):
            alerts.append(alert)
        elif pct >= 90 and settings.get("threshold_90", True):
            alerts.append(alert)
        elif pct >= 80 and settings.get("threshold_80", True):
            alerts.append(alert)
    
    # Predictive alerts
    if settings.get("predictive_alerts", True):
        alerts.extend(check_predictive_alerts(df, budgets))
    
    # Velocity alerts
    if settings.get("velocity_alerts", True):
        alerts.extend(check_velocity_alerts(df))
    
    return alerts

# ══════════════════════════════════════════════════════════════════════════
# AI-POWERED ALERT FEATURES
# ══════════════════════════════════════════════════════════════════════════

def get_ai_alert_thresholds(df: pd.DataFrame, budgets: dict) -> dict:
    """
    Ask AI to recommend personalised alert thresholds per category
    based on historical spending variance.

    Instead of fixed 80/90/100% for everything, returns per-category
    thresholds like:
        {"Groceries": {"caution": 70, "warning": 85, "critical": 100},
         "Dining Out": {"caution": 60, "warning": 80, "critical": 95}}

    Result is cached in session_state for the month.
    """
    import json, re
    import streamlit as st

    cache_key = "ai_alert_thresholds"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    keys = _get_keys()
    if not any(keys.values()) or df.empty or not budgets:
        return {}

    # Build variance summary per category
    df2 = df.copy()
    df2[Columns.DATE] = pd.to_datetime(df2[Columns.DATE], errors="coerce")
    df2[Columns.PRICE_PAID] = pd.to_numeric(df2[Columns.PRICE_PAID], errors="coerce").fillna(0)
    df2["YM"] = df2[Columns.DATE].dt.to_period("M").astype(str)

    cat_budgets = {k: v for k, v in budgets.items() if k != "__total_monthly__"}
    if not cat_budgets:
        return {}

    variance_summary = {}
    for cat, budget in cat_budgets.items():
        monthly = df2[df2[Columns.CATEGORY] == cat].groupby("YM")[Columns.PRICE_PAID].sum()
        if monthly.empty:
            continue
        avg = float(monthly.mean())
        std = float(monthly.std()) if len(monthly) > 1 else 0.0
        cv  = (std / avg * 100) if avg > 0 else 0   # coefficient of variation
        variance_summary[cat] = {
            "budget":     budget,
            "avg_spend":  round(avg, 2),
            "std_dev":    round(std, 2),
            "variability_pct": round(cv, 1),
            "months_data": int(len(monthly)),
        }

    if not variance_summary:
        return {}

    system = (
        "You are a personal finance alert system configurator. "
        "The user will provide spending history per category with variability metrics. "
        "For each category, recommend three alert threshold percentages: caution, warning, critical. "
        "High-variability categories (cv > 30%) should have looser thresholds. "
        "Low-variability categories should have tighter thresholds. "
        "critical must always be 95-105, warning between 75-95, caution between 55-80. "
        "Return ONLY valid JSON: "
        '{"CategoryName": {"caution": 70, "warning": 85, "critical": 100}, ...} '
        "No markdown, no explanation."
    )
    user = (
        f"Here is my spending variance by category:\n"
        f"{json.dumps(variance_summary, indent=2)}\n\n"
        "Recommend personalised alert thresholds for each category."
    )

    try:
        raw, _ = _call_ai(system, user, keys)
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        thresholds = json.loads(cleaned)
        if isinstance(thresholds, dict):
            st.session_state[cache_key] = thresholds
            return thresholds
    except Exception:
        pass

    return {}


def check_threshold_alerts_ai(df: pd.DataFrame, budgets: dict) -> list:
    """
    Like check_threshold_alerts() but uses AI-personalised thresholds
    when available, falling back to fixed 80/90/100 otherwise.
    """
    ai_thresholds = get_ai_alert_thresholds(df, budgets)

    alerts = []
    from budget_manager import calculate_budget_status
    statuses = calculate_budget_status(df, budgets, period="monthly")

    for status in statuses:
        if status["category"] == "Total":
            continue
        cat   = status["category"]
        pct   = status["pct"]
        spent = status["spent"]
        budget = status["budget"]

        # Use AI thresholds if available, else fall back to fixed values
        t = ai_thresholds.get(cat, {"caution": 80, "warning": 90, "critical": 100})
        t_critical = t.get("critical", 100)
        t_warning  = t.get("warning",  90)
        t_caution  = t.get("caution",  80)

        source = "AI-personalised" if cat in ai_thresholds else "default"

        if pct >= t_critical:
            alerts.append(BudgetAlert(
                category=cat, severity="critical",
                message=(f"Budget exceeded: {cat} at {pct:.0f}% "
                         f"({spent:,.0f} / {budget:,.0f} SEK) [{source} threshold: {t_critical}%]"),
                data=status,
            ))
        elif pct >= t_warning:
            remaining = budget - spent
            alerts.append(BudgetAlert(
                category=cat, severity="warning",
                message=(f"Warning: {cat} at {pct:.0f}% "
                         f"(only {remaining:,.0f} SEK left) [{source} threshold: {t_warning}%]"),
                data=status,
            ))
        elif pct >= t_caution:
            alerts.append(BudgetAlert(
                category=cat, severity="caution",
                message=(f"Caution: {cat} at {pct:.0f}% of budget "
                         f"[{source} threshold: {t_caution}%]"),
                data=status,
            ))

    return alerts


def ai_alert_summary(df: pd.DataFrame, budgets: dict) -> None:
    """
    Render a concise AI-written summary of all active alerts.
    Call this at the bottom of your alerts / notification UI.
    """
    import json
    import streamlit as st

    keys = _get_keys()
    if not any(keys.values()):
        return

    all_alerts = get_all_alerts(df, budgets)
    if not all_alerts:
        return

    cache_key = f"ai_alert_summary_{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    if cache_key not in st.session_state:
        if not st.button("🤖 Get AI Alert Analysis", key="ai_alert_btn"):
            return

        alert_list = [
            {"category": a.category, "severity": a.severity, "message": a.message}
            for a in all_alerts
        ]
        system = (
            "You are a concise personal finance assistant. "
            "The user has several budget alerts. Summarise them in 3-4 plain-English bullet points. "
            "Identify the most urgent issue, explain what it means in practical terms, "
            "and give one concrete action for each. Be direct, no fluff. "
            "Use bullet points starting with •."
        )
        user = (
            f"Here are my current budget alerts:\n"
            f"{json.dumps(alert_list, indent=2)}\n\n"
            "Give me a plain-English summary with priority actions."
        )
        with st.spinner("AI is summarising your alerts…"):
            text, provider = _call_ai(system, user, keys)

        if text:
            st.session_state[cache_key] = (text, provider)
        else:
            st.error("No AI response. Check your API key in secrets.toml.")
            return

    if cache_key not in st.session_state:
        return

    text, provider = st.session_state[cache_key]
    t_bg, t_border, t_fg, t_muted = "#fff", "#e2e8f0", "#0f172a", "#64748b"
    try:
        from budget_manager import _t
        tc = _t()
        t_bg, t_border, t_fg, t_muted = tc["card"], tc["border"], tc["fg"], tc["muted"]
    except Exception:
        pass

    bullets = [b.strip().lstrip("•").strip() for b in text.split("\n") if b.strip()]
    bullets = [b for b in bullets if len(b) > 10]
    items_html = "".join(
        f"<li style='margin-bottom:0.4rem;color:{t_fg};'>{b}</li>"
        for b in bullets
    ) or f"<li style='color:{t_fg};'>{text}</li>"

    st.markdown(
        f"<div style='background:{t_bg};border:1px solid {t_border};"
        f"border-left:4px solid #ef4444;border-radius:12px;"
        f"padding:1rem 1.3rem;margin-top:0.75rem;'>"
        f"<div style='font-weight:700;color:{t_fg};margin-bottom:0.5rem;'>🤖 AI Alert Analysis</div>"
        f"<ul style='margin:0;padding-left:1.2rem;font-size:0.9rem;line-height:1.7;'>{items_html}</ul>"
        f"<div style='margin-top:0.5rem;font-size:0.7rem;color:{t_muted};'>Generated by {provider}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if st.button("🔄 Refresh analysis", key="refresh_alert_ai"):
        st.session_state.pop(cache_key, None)
        st.rerun()
