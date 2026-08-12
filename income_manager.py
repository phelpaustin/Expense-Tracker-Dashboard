# income_manager.py
"""
First-class income ledger.

Previously "income" was a single manual number in the Financial Metrics page,
so savings-rate and cash-flow were rough approximations. This module stores
real, dated income entries (salary, refunds, side income, …) so those metrics
can use actual per-month income.

Entries are persisted to ``data/income.json`` via the shared JsonStore and
mirror to Drive like the other managed files.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

import pandas as pd
import streamlit as st

from json_store import JsonStore

INCOME_FILE = "data/income.json"
_STORE = JsonStore(INCOME_FILE, default=[], sync=True)


# ============================================================
# STORAGE
# ============================================================
def load_income() -> list:
    data = _STORE.load()
    return data if isinstance(data, list) else []


def save_income(entries: list) -> bool:
    return _STORE.save(entries)


def add_income(when: date, amount: float, source: str, note: str = "") -> str:
    entries = load_income()
    entry_id = uuid.uuid4().hex[:12]
    entries.append({
        "id": entry_id,
        "date": str(when),
        "amount": round(float(amount), 2),
        "source": (source or "").strip() or "Income",
        "note": (note or "").strip(),
    })
    save_income(entries)
    return entry_id


def delete_income(entry_id: str) -> None:
    save_income([e for e in load_income() if e.get("id") != entry_id])


def update_income(entry_id: str, when: date, amount: float, source: str, note: str = "") -> bool:
    """Update an existing income entry in place. Returns True if found."""
    entries = load_income()
    found = False
    for e in entries:
        if e.get("id") == entry_id:
            e["date"] = str(when)
            e["amount"] = round(float(amount), 2)
            e["source"] = (source or "").strip() or "Income"
            e["note"] = (note or "").strip()
            found = True
            break
    if found:
        save_income(entries)
    return found


# ============================================================
# DERIVED VIEWS
# ============================================================
def income_dataframe() -> pd.DataFrame:
    """Return the income ledger as a DataFrame with parsed dates + YearMonth."""
    entries = load_income()
    if not entries:
        return pd.DataFrame(columns=["id", "Date", "Amount", "Source", "Note", "YearMonth"])
    df = pd.DataFrame(entries).rename(
        columns={"date": "Date", "amount": "Amount", "source": "Source", "note": "Note"}
    )
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
    df = df.dropna(subset=["Date"])
    df["YearMonth"] = df["Date"].dt.to_period("M").astype(str)
    return df


def monthly_income_map() -> dict:
    """Return {``'YYYY-MM'`` : total income that month}."""
    df = income_dataframe()
    if df.empty:
        return {}
    return df.groupby("YearMonth")["Amount"].sum().to_dict()


def income_for_month(when: Optional[date] = None) -> float:
    """Total income for the month containing *when* (default: current month)."""
    when = when or date.today()
    key = f"{when.year:04d}-{when.month:02d}"
    return float(monthly_income_map().get(key, 0.0))


def average_monthly_income() -> float:
    """Average income across the months that have any income recorded."""
    m = monthly_income_map()
    return float(sum(m.values()) / len(m)) if m else 0.0


def total_income() -> float:
    df = income_dataframe()
    return float(df["Amount"].sum()) if not df.empty else 0.0


# ============================================================
# UI
# ============================================================
def income_manager_ui(df: pd.DataFrame = None, save_fn=None, sheet=None) -> None:
    """Income ledger page — add/list/delete dated income entries."""
    st.markdown("## 💵 Income")
    st.caption("Record real income so savings rate and cash flow use actual figures.")

    inc_df = income_dataframe()

    # ── Summary ──────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric("This Month", f"{income_for_month():,.0f} SEK")
    c2.metric("Avg / Month", f"{average_monthly_income():,.0f} SEK")
    c3.metric("Total Recorded", f"{total_income():,.0f} SEK")

    st.markdown("---")

    # ── Add entry ────────────────────────────────────────────────────────
    st.markdown("### ➕ Add Income")
    with st.form("add_income_form", clear_on_submit=True):
        fc1, fc2 = st.columns(2)
        with fc1:
            when = st.date_input("Date", value=date.today())
            amount = st.number_input("Amount (SEK)", min_value=0.0, step=500.0, value=0.0)
        with fc2:
            source = st.text_input("Source", placeholder="e.g. Salary, Refund, Freelance")
            note = st.text_input("Note (optional)", placeholder="e.g. July paycheck")
        submitted = st.form_submit_button("💾 Add Income", type="primary")
        if submitted:
            if amount <= 0:
                st.error("Amount must be greater than 0.")
            else:
                add_income(when, amount, source, note)
                st.success(f"✅ Added {amount:,.0f} SEK ({source or 'Income'}).")
                st.rerun()

    # ── Monthly income chart ─────────────────────────────────────────────
    if not inc_df.empty:
        st.markdown("### 📊 Monthly Income")
        monthly = (
            inc_df.groupby("YearMonth")["Amount"].sum().reset_index()
            .sort_values("YearMonth")
        )
        st.bar_chart(monthly, x="YearMonth", y="Amount")

    # ── List + edit/delete ──────────────────────────────────
    st.markdown(f"### 📋 Entries ({len(inc_df)})")
    if inc_df.empty:
        st.info("No income recorded yet. Add your first entry above.")
        return

    for _, row in inc_df.sort_values("Date", ascending=False).iterrows():
        rid = row["id"]
        label = f"{row['Date'].date()} · {row['Amount']:,.0f} SEK · {row['Source']}"
        with st.expander(label):
            with st.form(f"edit_income_{rid}"):
                e1, e2 = st.columns(2)
                with e1:
                    ed_date = st.date_input("Date", value=row["Date"].date(), key=f"d_{rid}")
                    ed_amount = st.number_input(
                        "Amount (SEK)", min_value=0.0, step=500.0,
                        value=float(row["Amount"]), key=f"a_{rid}",
                    )
                with e2:
                    ed_source = st.text_input("Source", value=row["Source"], key=f"s_{rid}")
                    ed_note = st.text_input("Note", value=row["Note"], key=f"n_{rid}")
                bc1, bc2 = st.columns(2)
                if bc1.form_submit_button("💾 Save", type="primary"):
                    if ed_amount <= 0:
                        st.error("Amount must be greater than 0.")
                    else:
                        update_income(rid, ed_date, ed_amount, ed_source, ed_note)
                        st.success("Updated.")
                        st.rerun()
                if bc2.form_submit_button("🗑️ Delete"):
                    delete_income(rid)
                    st.rerun()
