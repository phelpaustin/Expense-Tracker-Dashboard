# budget_manager.py
"""
Budget tracking module with monthly/category budgets, alerts, and visual progress.
Theme-aware: respects the active app theme for all charts and cards.
"""
import json
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Dict, List
from config import Columns


# ══════════════════════════════════════════════════════════════════════════
# THEME SUPPORT - Mirrors Main_Dashboard_App THEMES dict
# ══════════════════════════════════════════════════════════════════════════
_THEME_PALETTES = {
    "☀️ Light":    {"paper": "#ffffff", "card": "#ffffff", "text": "#475569", "muted": "#94a3b8", "fg": "#0f172a", "border": "#e2e8f0",  "accent": "#6366f1", "bar_bg": "#f1f5f9"},
    "🌑 Dark":     {"paper": "#1e293b", "card": "#1e293b", "text": "#94a3b8", "muted": "#64748b", "fg": "#f1f5f9", "border": "#334155",  "accent": "#818cf8", "bar_bg": "#334155"},
    "🌊 Ocean":    {"paper": "#f0f9ff", "card": "#e0f2fe", "text": "#0369a1", "muted": "#38bdf8", "fg": "#0c4a6e", "border": "#bae6fd",  "accent": "#0284c7", "bar_bg": "#bae6fd"},
    "🌿 Forest":   {"paper": "#f0fdf4", "card": "#dcfce7", "text": "#15803d", "muted": "#4ade80", "fg": "#14532d", "border": "#bbf7d0",  "accent": "#16a34a", "bar_bg": "#bbf7d0"},
    "🌅 Sunset":   {"paper": "#fff7ed", "card": "#ffedd5", "text": "#c2410c", "muted": "#fb923c", "fg": "#7c2d12", "border": "#fed7aa",  "accent": "#ea580c", "bar_bg": "#fed7aa"},
    "🌙 Midnight": {"paper": "#13131f", "card": "#13131f", "text": "#a5b4fc", "muted": "#4f4f7a", "fg": "#e2e2ff", "border": "#1e1e3f",  "accent": "#7c3aed", "bar_bg": "#1e1e3f"},
    "🌸 Rose":     {"paper": "#fff1f2", "card": "#ffe4e6", "text": "#be123c", "muted": "#fb7185", "fg": "#881337", "border": "#fecdd3",  "accent": "#e11d48", "bar_bg": "#fecdd3"},
    "⬜ Slate":    {"paper": "#ffffff", "card": "#f1f5f9", "text": "#475569", "muted": "#94a3b8", "fg": "#1e293b", "border": "#cbd5e1",  "accent": "#64748b", "bar_bg": "#e2e8f0"},
}


def _t() -> dict:
    """Return the active theme colours from session_state."""
    name = st.session_state.get("theme_name", "☀️ Light")
    return _THEME_PALETTES.get(name, _THEME_PALETTES["☀️ Light"])


# ══════════════════════════════════════════════════════════════════════════
# BUDGET STORAGE
# ══════════════════════════════════════════════════════════════════════════
BUDGET_FILE = "data/budgets.json"


def load_budgets() -> dict:
    """Load budgets from JSON file."""
    path = Path(BUDGET_FILE)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}


def save_budgets(budgets: dict) -> None:
    """Save budgets to JSON file."""
    path = Path(BUDGET_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(budgets, indent=2))


# ══════════════════════════════════════════════════════════════════════════
# BUDGET CALCULATION
# ══════════════════════════════════════════════════════════════════════════
def calculate_budget_status(df: pd.DataFrame, budgets: dict, period: str = "monthly") -> List[Dict]:
    """
    Calculate spending vs budget for each category.
    
    Args:
        df: Expenses dataframe
        budgets: Dict of {category: budget_amount}
        period: "monthly" or "total"
    
    Returns:
        List of dicts with category, budget, spent, remaining, pct, status
    """
    if df.empty or not budgets:
        return []
    
    df = df.copy()
    df[Columns.PRICE_PAID] = pd.to_numeric(df[Columns.PRICE_PAID], errors="coerce").fillna(0)
    df[Columns.DATE] = pd.to_datetime(df[Columns.DATE], errors="coerce")
    
    # Filter to current month for monthly budgets
    if period == "monthly":
        current_month = pd.Timestamp.now().to_period("M")
        df[Columns.YEAR_MONTH] = df[Columns.DATE].dt.to_period("M")
        df = df[df[Columns.YEAR_MONTH] == current_month]
    
    # Calculate spending by category
    category_spending = (
        df.groupby(Columns.CATEGORY)[Columns.PRICE_PAID]
        .sum()
        .to_dict()
    )
    
    # Build status for each budget
    statuses = []
    total_budget = 0
    total_spent = 0
    
    for category, budget in budgets.items():
        spent = category_spending.get(category, 0)
        remaining = budget - spent
        pct = (spent / budget * 100) if budget > 0 else 0
        
        # Determine status
        if pct >= 100:
            status = "exceeded"
        elif pct >= 85:
            status = "warning"
        elif pct >= 60:
            status = "caution"
        else:
            status = "ok"
        
        statuses.append({
            "category": category,
            "budget": budget,
            "spent": spent,
            "remaining": remaining,
            "pct": pct,
            "status": status
        })
        
        total_budget += budget
        total_spent += spent
    
    # Add total row
    if statuses:
        total_remaining = total_budget - total_spent
        total_pct = (total_spent / total_budget * 100) if total_budget > 0 else 0
        
        if total_pct >= 100:
            total_status = "exceeded"
        elif total_pct >= 85:
            total_status = "warning"
        elif total_pct >= 60:
            total_status = "caution"
        else:
            total_status = "ok"
        
        statuses.insert(0, {
            "category": "Total",
            "budget": total_budget,
            "spent": total_spent,
            "remaining": total_remaining,
            "pct": total_pct,
            "status": total_status
        })
    
    return statuses


# ══════════════════════════════════════════════════════════════════════════
# VISUALIZATION COMPONENTS (Theme-Aware)
# ══════════════════════════════════════════════════════════════════════════
def _render_budget_card(status: dict, large: bool = False):
    """Render a budget progress card with theme-aware colours."""
    t = _t()
    cat = status["category"]
    budget = status.get("budget", 0) or 0
    spent = status.get("spent", 0) or 0
    remaining = status.get("remaining", 0) or 0
    pct = status.get("pct", 0) or 0
    s = status["status"]

    # Status colors (universal)
    color = {
        "ok": "#22c55e",
        "caution": "#f59e0b",
        "warning": "#f97316",
        "exceeded": "#ef4444"
    }.get(s, "#64748b")
    
    icon = {
        "ok": "✅",
        "caution": "🟡",
        "warning": "🟠",
        "exceeded": "🔴",
        "unset": "⚪"
    }.get(s, "⚪")

    st.markdown(f"""
    <div style="background:{t['card']}; border-left:4px solid {color}; border-radius:10px;
                padding:{'1.5rem' if large else '1rem'}; margin-bottom:0.75rem; border:1px solid {t['border']};">
        <div style="font-size:{'1.1rem' if large else '0.9rem'}; color:{t['muted']}; margin-bottom:0.25rem;">{icon} {cat}</div>
        <div style="font-size:{'2rem' if large else '1.4rem'}; font-weight:700; color:{t['fg']};">{spent:,.0f} SEK</div>
        <div style="font-size:0.85rem; color:{t['muted']};">of {budget:,.0f} SEK budget</div>
        <div style="background:{t['bar_bg']}; border-radius:999px; height:8px; margin:0.75rem 0 0.25rem 0; overflow:hidden;">
            <div style="background:{color}; height:100%; width:{min(pct,100):.1f}%; border-radius:999px; transition:width 0.5s;"></div>
        </div>
        <div style="font-size:0.8rem; color:{color}; font-weight:600;">{pct:.1f}% used · {remaining:,.0f} SEK remaining</div>
    </div>
    """, unsafe_allow_html=True)


def _render_budget_gauge(status: dict, label: str):
    """Render a Plotly gauge chart with theme-aware colours."""
    t = _t()
    pct = status["pct"] or 0
    
    # Status color
    color = {
        "ok": "#22c55e",
        "caution": "#f59e0b",
        "warning": "#f97316",
        "exceeded": "#ef4444"
    }.get(status["status"], "#64748b")

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=status["spent"],
        delta={
            "reference": status["budget"],
            "decreasing": {"color": "#22c55e"},
            "increasing": {"color": "#ef4444"}
        },
        number={"suffix": " SEK", "font": {"color": t["fg"]}},
        gauge={
            "axis": {"range": [0, status["budget"] * 1.2], "tickcolor": t["muted"]},
            "bar": {"color": color},
            "bgcolor": t["card"],
            "bordercolor": t["border"],
            "steps": [
                {"range": [0, status["budget"] * 0.6], "color": t["paper"]},
                {"range": [status["budget"] * 0.6, status["budget"] * 0.85], "color": t["card"]},
                {"range": [status["budget"] * 0.85, status["budget"] * 1.2], "color": t["bar_bg"]},
            ],
            "threshold": {
                "line": {"color": "#ef4444", "width": 3},
                "value": status["budget"]
            },
        },
        title={"text": f"Spending vs Budget — {label}", "font": {"color": t["text"]}},
    ))
    
    fig.update_layout(
        paper_bgcolor=t["paper"],
        font_color=t["fg"],
        height=280,
        margin=dict(t=60, b=20)
    )
    
    st.plotly_chart(fig, config={"displayModeBar": False})


def _render_budget_alerts(statuses: list):
    """Show alerts for exceeded or warning budgets."""
    exceeded = [s for s in statuses if s["status"] == "exceeded" and s["category"] != "Total"]
    warning = [s for s in statuses if s["status"] == "warning" and s["category"] != "Total"]

    if exceeded:
        st.markdown("### 🚨 Budget Exceeded")
        for s in exceeded:
            st.error(
                f"**{s['category']}**: Spent {s['spent']:,.0f} SEK — "
                f"{s['pct']:.1f}% of {s['budget']:,.0f} SEK budget "
                f"(over by {abs(s['remaining']):,.0f} SEK)"
            )
    
    if warning:
        st.markdown("### ⚠️ Budget Warning")
        for s in warning:
            st.warning(
                f"**{s['category']}**: {s['pct']:.1f}% used "
                f"({s['spent']:,.0f} / {s['budget']:,.0f} SEK)"
            )


# ══════════════════════════════════════════════════════════════════════════
# MAIN UI FUNCTIONS (Required by Main_Dashboard_App)
# ══════════════════════════════════════════════════════════════════════════
def budget_dashboard_ui(df: pd.DataFrame):
    """
    Main budget dashboard showing current month's budget status.
    Called from Main_Dashboard_App.py in the Budgets page.
    """
    st.markdown("### 📊 Budget Dashboard")
    
    budgets = load_budgets()
    
    if not budgets:
        st.info("💡 No budgets set yet. Switch to **Setup** tab to create your first budget!")
        return
    
    # Calculate current status
    statuses = calculate_budget_status(df, budgets, period="monthly")
    
    if not statuses:
        st.info("No spending data for current month yet.")
        return
    
    # Show alerts first
    _render_budget_alerts(statuses)
    
    st.markdown("---")
    
    # Total budget card (large)
    if statuses:
        total_status = statuses[0]  # First item is always "Total"
        _render_budget_card(total_status, large=True)
    
    st.markdown("### 📋 Category Budgets")
    
    # Individual category cards
    category_statuses = [s for s in statuses if s["category"] != "Total"]
    
    if not category_statuses:
        st.info("No category budgets set.")
        return
    
    # Display mode selector
    view_mode = st.radio(
        "Display Mode",
        ["Cards", "Gauges", "Table"],
        horizontal=True,
        key="budget_view_mode"
    )
    
    if view_mode == "Cards":
        # Card view (2 columns)
        cols = st.columns(2)
        for idx, status in enumerate(category_statuses):
            with cols[idx % 2]:
                _render_budget_card(status)
    
    elif view_mode == "Gauges":
        # Gauge view (1 per row)
        for status in category_statuses:
            _render_budget_gauge(status, status["category"])
    
    else:
        # Table view
        table_data = []
        for s in category_statuses:
            table_data.append({
                "Category": s["category"],
                "Budget": f"{s['budget']:,.0f} SEK",
                "Spent": f"{s['spent']:,.0f} SEK",
                "Remaining": f"{s['remaining']:,.0f} SEK",
                "% Used": f"{s['pct']:.1f}%",
                "Status": {
                    "ok": "✅ On Track",
                    "caution": "🟡 Caution",
                    "warning": "🟠 Warning",
                    "exceeded": "🔴 Exceeded"
                }.get(s["status"], "—")
            })
        
        st.dataframe(
            pd.DataFrame(table_data),
            width="stretch",
            hide_index=True
        )


def budget_setup_ui(df: pd.DataFrame):
    """
    Budget setup interface for creating/editing budgets.
    Called from Main_Dashboard_App.py in the Budgets page.
    """
    st.markdown("### ⚙️ Budget Setup")
    
    budgets = load_budgets()
    
    # Get available categories from data
    if not df.empty:
        categories = sorted(df[Columns.CATEGORY].dropna().unique().tolist())
    else:
        categories = []
    
    if not categories:
        st.warning("No categories found in your expense data. Add some expenses first!")
        return
    
    st.markdown("#### ➕ Add/Edit Budget")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        selected_category = st.selectbox(
            "Category",
            categories,
            key="budget_category"
        )
    
    with col2:
        current_budget = budgets.get(selected_category, 0)
        budget_amount = st.number_input(
            "Monthly Budget (SEK)",
            min_value=0.0,
            value=float(current_budget),
            step=100.0,
            key="budget_amount"
        )
    
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Save Budget", width="stretch"):
            budgets[selected_category] = budget_amount
            save_budgets(budgets)
            st.success(f"✅ Budget set for {selected_category}: {budget_amount:,.0f} SEK/month")
            st.rerun()
    
    st.markdown("---")
    st.markdown("#### 📋 Current Budgets")
    
    if budgets:
        # Show current budgets with delete option
        budget_list = []
        for cat, amount in sorted(budgets.items()):
            budget_list.append({
                "Category": cat,
                "Monthly Budget": f"{amount:,.0f} SEK",
                "Delete": cat
            })
        
        budget_df = pd.DataFrame(budget_list)
        
        # Display as table
        st.dataframe(
            budget_df[["Category", "Monthly Budget"]],
            width="stretch",
            hide_index=True
        )
        
        # Delete budget
        st.markdown("#### 🗑️ Delete Budget")
        col_del1, col_del2 = st.columns([2, 1])
        
        with col_del1:
            cat_to_delete = st.selectbox(
                "Select category to delete",
                list(budgets.keys()),
                key="delete_category"
            )
        
        with col_del2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🗑️ Delete", width="stretch", type="secondary"):
                del budgets[cat_to_delete]
                save_budgets(budgets)
                st.success(f"✅ Budget deleted for {cat_to_delete}")
                st.rerun()
        
        st.markdown("---")
        st.markdown("#### 💡 Quick Tips")
        st.info("""
        - Set realistic budgets based on past spending
        - Review and adjust monthly
        - Use the Dashboard tab to track progress
        - Aim to stay in the 🟢 green zone (< 60% used)
        """)
    else:
        st.info("No budgets set yet. Use the form above to create your first budget!")
    
    # Export/Import budgets
    st.markdown("---")
    st.markdown("#### 📤 Export/Import")
    
    col_io1, col_io2 = st.columns(2)
    
    with col_io1:
        if budgets:
            budget_json = json.dumps(budgets, indent=2)
            st.download_button(
                "📥 Export Budgets (JSON)",
                budget_json,
                "budgets.json",
                "application/json",
                width="stretch"
            )
    
    with col_io2:
        uploaded_file = st.file_uploader(
            "📤 Import Budgets (JSON)",
            type=["json"],
            key="budget_import"
        )
        
        if uploaded_file:
            try:
                imported = json.loads(uploaded_file.read())
                if isinstance(imported, dict):
                    save_budgets(imported)
                    st.success("✅ Budgets imported successfully!")
                    st.rerun()
                else:
                    st.error("Invalid JSON format")
            except Exception as e:
                st.error(f"Import failed: {e}")