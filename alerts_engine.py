# alerts_engine.py
"""
Smart budget alert system with threshold and predictive notifications.
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from config import Columns
from budget_manager import load_budgets, calculate_budget_status


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
    
    # Collect all alert types
    alerts.extend(check_threshold_alerts(df, budgets))
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