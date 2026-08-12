# accounts_manager.py
"""
Accounts, balances, debt & net-worth tracking.

The app previously had no concept of accounts or liabilities. This module adds a
simple, manual account model: each account is an asset (checking, savings, cash,
investments, property, …) or a liability (credit card, loan, mortgage, …) with a
current balance. Net worth = total assets − total liabilities.

Optional dated snapshots let you track net worth over time. Everything persists
to ``data/accounts.json`` / ``data/networth_snapshots.json`` via the shared
JsonStore and mirrors to Drive.
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

import pandas as pd
import streamlit as st

from json_store import JsonStore
from config import DEFAULT_CURRENCY, SUPPORTED_CURRENCIES

ACCOUNTS_FILE = "data/accounts.json"
SNAPSHOTS_FILE = "data/networth_snapshots.json"
_ACCOUNTS = JsonStore(ACCOUNTS_FILE, default=[], sync=True)
_SNAPSHOTS = JsonStore(SNAPSHOTS_FILE, default=[], sync=True)

ASSET = "asset"
LIABILITY = "liability"

ASSET_CATEGORIES = ["Checking", "Savings", "Cash", "Investment", "Property", "Other Asset"]
LIABILITY_CATEGORIES = ["Credit Card", "Loan", "Mortgage", "Other Debt"]


# ============================================================
# STORAGE
# ============================================================
def load_accounts() -> list:
    data = _ACCOUNTS.load()
    return data if isinstance(data, list) else []


def save_accounts(accounts: list) -> bool:
    return _ACCOUNTS.save(accounts)


def add_account(name: str, kind: str, category: str, balance: float,
                currency: str = DEFAULT_CURRENCY, note: str = "") -> str:
    accounts = load_accounts()
    acc_id = uuid.uuid4().hex[:12]
    accounts.append({
        "id": acc_id,
        "name": (name or "").strip() or "Account",
        "kind": kind if kind in (ASSET, LIABILITY) else ASSET,
        "category": category,
        "balance": round(float(balance), 2),
        "currency": currency if currency in SUPPORTED_CURRENCIES else DEFAULT_CURRENCY,
        "note": (note or "").strip(),
    })
    save_accounts(accounts)
    return acc_id


def update_account(acc_id: str, name: str, kind: str, category: str,
                   balance: float, currency: str = DEFAULT_CURRENCY, note: str = "") -> bool:
    accounts = load_accounts()
    found = False
    for a in accounts:
        if a.get("id") == acc_id:
            a.update({
                "name": (name or "").strip() or "Account",
                "kind": kind if kind in (ASSET, LIABILITY) else ASSET,
                "category": category,
                "balance": round(float(balance), 2),
                "currency": currency if currency in SUPPORTED_CURRENCIES else DEFAULT_CURRENCY,
                "note": (note or "").strip(),
            })
            found = True
            break
    if found:
        save_accounts(accounts)
    return found


def delete_account(acc_id: str) -> None:
    save_accounts([a for a in load_accounts() if a.get("id") != acc_id])


# ============================================================
# NET WORTH
# ============================================================
def total_assets() -> float:
    return round(sum(float(a.get("balance", 0)) for a in load_accounts()
                     if a.get("kind") == ASSET), 2)


def total_liabilities() -> float:
    return round(sum(float(a.get("balance", 0)) for a in load_accounts()
                     if a.get("kind") == LIABILITY), 2)


def net_worth() -> float:
    return round(total_assets() - total_liabilities(), 2)


# ============================================================
# SNAPSHOTS (net worth over time)
# ============================================================
def load_snapshots() -> list:
    data = _SNAPSHOTS.load()
    return data if isinstance(data, list) else []


def record_snapshot() -> None:
    """Record today's net worth (replacing any existing entry for today)."""
    snaps = [s for s in load_snapshots() if s.get("date") != str(date.today())]
    snaps.append({
        "date": str(date.today()),
        "assets": total_assets(),
        "liabilities": total_liabilities(),
        "net_worth": net_worth(),
    })
    _SNAPSHOTS.save(snaps)


def snapshots_dataframe() -> pd.DataFrame:
    snaps = load_snapshots()
    if not snaps:
        return pd.DataFrame(columns=["Date", "assets", "liabilities", "net_worth"])
    df = pd.DataFrame(snaps).rename(columns={"date": "Date"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df.dropna(subset=["Date"]).sort_values("Date")


# ============================================================
# UI
# ============================================================
def accounts_dataframe() -> pd.DataFrame:
    accounts = load_accounts()
    if not accounts:
        return pd.DataFrame(columns=["id", "name", "kind", "category", "balance", "currency", "note"])
    return pd.DataFrame(accounts)


def _account_form(prefix: str, existing: dict = None):
    """Render account fields; return the collected dict (no persistence)."""
    existing = existing or {}
    is_liability = existing.get("kind") == LIABILITY
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Name", value=existing.get("name", ""),
                             placeholder="e.g. SEB Checking, Visa Card", key=f"{prefix}_name")
        kind = st.radio("Type", [ASSET, LIABILITY],
                        index=1 if is_liability else 0,
                        format_func=lambda k: "💰 Asset" if k == ASSET else "💳 Liability",
                        horizontal=True, key=f"{prefix}_kind")
    with c2:
        cats = ASSET_CATEGORIES if kind == ASSET else LIABILITY_CATEGORIES
        cur_cat = existing.get("category")
        category = st.selectbox("Category", cats,
                                index=cats.index(cur_cat) if cur_cat in cats else 0,
                                key=f"{prefix}_cat")
        balance = st.number_input("Balance (SEK)", min_value=0.0, step=100.0,
                                  value=float(existing.get("balance", 0.0)), key=f"{prefix}_bal")
    note = st.text_input("Note (optional)", value=existing.get("note", ""), key=f"{prefix}_note")
    return {"name": name, "kind": kind, "category": category, "balance": balance, "note": note}


def accounts_manager_ui(df: pd.DataFrame = None, save_fn=None, sheet=None) -> None:
    """Accounts & net-worth page."""
    st.markdown("## 🏦 Accounts & Net Worth")
    st.caption("Track balances across accounts and debts to see your true net worth.")

    assets, liabilities, nw = total_assets(), total_liabilities(), net_worth()
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Assets", f"{assets:,.0f} SEK")
    c2.metric("💳 Liabilities", f"{liabilities:,.0f} SEK")
    c3.metric("📊 Net Worth", f"{nw:,.0f} SEK",
              delta="Positive" if nw >= 0 else "Negative",
              delta_color="normal" if nw >= 0 else "inverse")

    # ── Net-worth trend ──────────────────────────────────────────────────
    sc1, sc2 = st.columns([1, 3])
    with sc1:
        if st.button("📸 Save snapshot", help="Record today's net worth for the trend"):
            record_snapshot()
            st.success("Snapshot saved.")
            st.rerun()
    snaps = snapshots_dataframe()
    if len(snaps) >= 2:
        st.markdown("### 📈 Net Worth Over Time")
        st.line_chart(snaps, x="Date", y="net_worth")

    st.markdown("---")

    # ── Add account ──────────────────────────────────────────────────────
    st.markdown("### ➕ Add Account")
    with st.form("add_account_form", clear_on_submit=True):
        data = _account_form("add")
        if st.form_submit_button("💾 Add Account", type="primary"):
            if not data["name"].strip():
                st.error("Name is required.")
            else:
                add_account(**data)
                st.success(f"✅ Added {data['name']}.")
                st.rerun()

    # ── List (grouped) with edit/delete ──────────────────────────────────
    accounts = load_accounts()
    if not accounts:
        st.info("No accounts yet. Add your first account above.")
        return

    for group, title in ((ASSET, "💰 Assets"), (LIABILITY, "💳 Liabilities")):
        rows = [a for a in accounts if a.get("kind") == group]
        if not rows:
            continue
        st.markdown(f"### {title}")
        for a in rows:
            with st.expander(f"{a['name']} · {a.get('category','')} · {float(a.get('balance',0)):,.0f} SEK"):
                with st.form(f"edit_account_{a['id']}"):
                    data = _account_form(f"e_{a['id']}", existing=a)
                    b1, b2 = st.columns(2)
                    if b1.form_submit_button("💾 Save", type="primary"):
                        update_account(a["id"], **data)
                        st.success("Updated.")
                        st.rerun()
                    if b2.form_submit_button("🗑️ Delete"):
                        delete_account(a["id"])
                        st.rerun()
