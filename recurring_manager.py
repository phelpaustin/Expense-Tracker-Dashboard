# recurring_manager.py
"""
Recurring expense templates — define once, apply every period.
"""
import json
import pandas as pd
import streamlit as st
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from config import Columns


RECURRING_FILE = "data/recurring.json"


FREQUENCIES = {
    "Daily": 1,
    "Weekly": 7,
    "Bi-weekly": 14,
    "Monthly": 30,
    "Quarterly": 90,
    "Yearly": 365,
}


# ============================================================
# STORAGE
# ============================================================
def load_recurring() -> list:
    path = Path(RECURRING_FILE)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return []
    return []


def save_recurring(templates: list):
    Path(RECURRING_FILE).parent.mkdir(parents=True, exist_ok=True)
    Path(RECURRING_FILE).write_text(json.dumps(templates, indent=2, default=str))


def add_template(template: dict):
    templates = load_recurring()
    template["id"] = f"rec_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    template["created"] = str(date.today())
    template["last_applied"] = None
    templates.append(template)
    save_recurring(templates)
    return template["id"]


def delete_template(template_id: str):
    templates = [t for t in load_recurring() if t.get("id") != template_id]
    save_recurring(templates)


def update_last_applied(template_id: str):
    templates = load_recurring()
    for t in templates:
        if t.get("id") == template_id:
            t["last_applied"] = str(date.today())
    save_recurring(templates)


# ============================================================
# LOGIC
# ============================================================
def is_due(template: dict) -> bool:
    """Check if a recurring expense is due today."""
    last = template.get("last_applied")
    freq_days = FREQUENCIES.get(template.get("frequency", "Monthly"), 30)
    if last is None:
        return True
    last_date = datetime.strptime(last, "%Y-%m-%d").date()
    return (date.today() - last_date).days >= freq_days


def get_due_templates() -> list:
    return [t for t in load_recurring() if is_due(t)]


def apply_template(template: dict, df: pd.DataFrame, save_fn) -> pd.DataFrame:
    """Apply a template and add to the expense DataFrame."""
    today = date.today()
    new_row = {
        Columns.DATE: today,
        Columns.EXPENSE_TYPE: template.get("expense_type", "Service"),
        Columns.CATEGORY: template.get("category", ""),
        Columns.SUBCATEGORY: template.get("subcategory", ""),
        Columns.ITEM: template.get("item", ""),
        Columns.BRAND: template.get("brand", ""),
        Columns.SHOP: template.get("shop", ""),
        Columns.PRICE_PAID: float(template.get("price", 0)),
        Columns.CURRENCY: template.get("currency", "SEK"),
        Columns.QUANTITY: float(template.get("quantity", 1)),
        Columns.QUANTITY_UNIT: template.get("unit", "Count"),
        Columns.PRICE_PER_UNIT: round(float(template.get("price", 0)) / max(float(template.get("quantity", 1)), 0.01), 2),
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    update_last_applied(template["id"])
    return df


# ============================================================
# UI
# ============================================================
def recurring_manager_ui(df: pd.DataFrame, save_fn, sheet=None):
    st.markdown("## 🔁 Recurring Expenses")

    # --- Due alerts ---
    due = get_due_templates()
    if due:
        st.warning(f"⏰ **{len(due)} recurring expense(s) due today!**")
        for t in due:
            cols = st.columns([3, 1, 1])
            cols[0].markdown(f"**{t['item']}** — {t['price']:,.2f} SEK ({t['frequency']})")
            if cols[1].button("➕ Apply", key=f"apply_{t['id']}"):
                df = apply_template(t, df, save_fn)
                save_fn(df, sheet)
                st.success(f"✅ Applied: {t['item']}")
                st.rerun()
            if cols[2].button("Skip", key=f"skip_{t['id']}"):
                update_last_applied(t["id"])
                st.rerun()
        st.markdown("---")

    # --- List existing templates ---
    templates = load_recurring()
    st.markdown(f"### 📋 Templates ({len(templates)})")
    if templates:
        for t in templates:
            with st.expander(f"{'⏰ DUE · ' if is_due(t) else ''}{t['item']} — {t['price']:,.2f} SEK · {t['frequency']}"):
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Category:** {t.get('category', '—')}")
                c2.markdown(f"**Shop:** {t.get('shop', '—')}")
                c3.markdown(f"**Last Applied:** {t.get('last_applied') or 'Never'}")
                if st.button("🗑️ Delete Template", key=f"del_{t['id']}"):
                    delete_template(t["id"])
                    st.rerun()
    else:
        st.info("No templates yet. Add one below!")

    # --- Add template form ---
    st.markdown("### ➕ Add Recurring Template")
    with st.form("add_recurring_form"):
        cats = sorted(df[Columns.CATEGORY].dropna().unique().tolist()) if not df.empty else []
        shops = sorted(df[Columns.SHOP].dropna().unique().tolist()) if not df.empty else []

        c1, c2 = st.columns(2)
        item = c1.text_input("Item Name *", placeholder="e.g., Netflix, Rent, Gym")
        expense_type = c2.selectbox("Expense Type", ["Service", "Goods"])
        price = c1.number_input("Amount (SEK) *", min_value=0.01, step=10.0)
        quantity = c2.number_input("Quantity", min_value=0.01, value=1.0)
        category = c1.selectbox("Category", [""] + cats)
        shop = c2.text_input("Shop/Provider", placeholder="e.g., Netflix, Landlord")
        frequency = st.selectbox("Frequency", list(FREQUENCIES.keys()), index=2)
        note = st.text_input("Note (optional)")

        if st.form_submit_button("💾 Save Template", type="primary"):
            if item.strip() and price > 0:
                add_template({
                    "item": item.strip(), "expense_type": expense_type,
                    "price": price, "quantity": quantity, "category": category,
                    "shop": shop.strip(), "frequency": frequency, "note": note,
                    "currency": "SEK", "unit": "Count"
                })
                st.success(f"✅ Template saved: {item}")
                st.rerun()
            else:
                st.error("Item name and price are required")