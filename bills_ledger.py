# bills_ledger.py
"""
Data layer for the *Bills Ledger* — a simple, consolidated view of every
bill showing only three things: **shop, date and amount**.

The ledger is a read-mostly *projection* built from three sources:

    1. Itemised expenses  → each (date, shop) group is collapsed into a
       single bill total (sum of ``PricePaid``).                (source: "Expense")
    2. Pending bills      → total-amount bills captured but not yet
       itemised.                                                 (source: "Pending")
    3. Manual entries     → bills typed straight into the ledger for
       receipts that never made it into the app.                 (source: "Manual")

Only the manual entries own their storage here
(``data/bills_ledger.json``); the other two sources are derived live so
the ledger always mirrors the rest of the app. Duplicates across the
three sources are removed by a ``(date, shop, amount)`` key, keeping the
richest source first (Expense > Pending > Manual).

Manual record shape
--------------------
    {
        "ledger_id":  "a1b2c3d4",
        "date":       "2026-06-20",
        "shop":       "ICA Maxi",
        "currency":   "SEK",
        "amount":     742.50,
        "note":       "Cash receipt, never itemised",
        "created_at": "2026-06-20T18:35:00"
    }
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Optional

import pandas as pd

from config import BILLS_LEDGER_FILE, Columns, DEFAULT_CURRENCY

log = logging.getLogger("bills_ledger")

# Ledger column names (kept local — this is a display-only projection).
LEDGER_DATE = "Date"
LEDGER_SHOP = "Shop"
LEDGER_AMOUNT = "Amount"
LEDGER_CURRENCY = "Currency"
LEDGER_SOURCE = "Source"

SOURCE_EXPENSE = "Expense"
SOURCE_PENDING = "Pending"
SOURCE_MANUAL = "Manual"

# Lower number = higher priority when de-duplicating.
_SOURCE_PRIORITY = {SOURCE_EXPENSE: 0, SOURCE_PENDING: 1, SOURCE_MANUAL: 2}


# ═══════════════════════════════════════════════════════════════
# LOW-LEVEL FILE I/O  (mirrors pending_bills.py)
# ═══════════════════════════════════════════════════════════════
def _new_id() -> str:
    return uuid.uuid4().hex[:8]


from json_store import JsonStore
_STORE = JsonStore(BILLS_LEDGER_FILE, default=[], sync=True)


def _load_raw() -> list[dict]:
    data = _STORE.load()
    return data if isinstance(data, list) else []


def _save_raw(entries: list[dict]) -> bool:
    return _STORE.save(entries)


# ═══════════════════════════════════════════════════════════════
# DE-DUPLICATION KEY
# ═══════════════════════════════════════════════════════════════
def _norm_date(value: Any) -> str:
    """Return a canonical ``YYYY-MM-DD`` string for any date-ish value."""
    if value is None or value == "":
        return ""
    try:
        ts = pd.to_datetime(value, errors="coerce")
        if pd.isna(ts):
            return str(value).strip()
        return ts.strftime("%Y-%m-%d")
    except Exception:
        return str(value).strip()


def _dedup_key(date: Any, shop: Any, amount: Any) -> tuple[str, str, float]:
    shop_norm = str(shop or "").strip().lower()
    try:
        amt = round(float(amount or 0.0), 2)
    except (TypeError, ValueError):
        amt = 0.0
    return (_norm_date(date), shop_norm, amt)


# ═══════════════════════════════════════════════════════════════
# MANUAL ENTRIES — PUBLIC API
# ═══════════════════════════════════════════════════════════════
def load_manual_bills() -> list[dict]:
    """Return all manually-added ledger entries."""
    return _load_raw()


def add_manual_bill(
    date: Any,
    shop: str,
    amount: float,
    currency: str = DEFAULT_CURRENCY,
    note: str = "",
) -> str:
    """Create and persist a manual ledger entry. Returns the new id."""
    entries = _load_raw()
    ledger_id = _new_id()
    entries.append({
        "ledger_id": ledger_id,
        "date": _norm_date(date),
        "shop": (shop or "").strip(),
        "currency": currency or DEFAULT_CURRENCY,
        "amount": round(float(amount or 0.0), 2),
        "note": (note or "").strip(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })
    _save_raw(entries)
    return ledger_id


def delete_manual_bill(ledger_id: str) -> bool:
    """Permanently remove a manual ledger entry."""
    entries = _load_raw()
    kept = [e for e in entries if e.get("ledger_id") != ledger_id]
    if len(kept) == len(entries):
        return False
    return _save_raw(kept)


def promote_manual_to_pending(ledger_id: str) -> Optional[str]:
    """
    Convert a manual ledger entry into a real *pending bill* so it can be
    itemised through the normal flow. The manual entry is removed on
    success. Returns the new ``bill_id`` or ``None`` if unavailable.
    """
    entry = next((e for e in _load_raw() if e.get("ledger_id") == ledger_id), None)
    if entry is None:
        return None
    try:
        import pending_bills as pb
    except Exception:  # noqa: BLE001 – pending bills is optional
        return None
    bill_id = pb.add_pending_bill(
        date=entry.get("date"),
        shop=entry.get("shop", ""),
        total_amount=float(entry.get("amount", 0.0) or 0.0),
        currency=entry.get("currency", DEFAULT_CURRENCY),
        note=entry.get("note", ""),
    )
    delete_manual_bill(ledger_id)
    return bill_id


def manual_duplicate_exists(
    date: Any, shop: str, amount: float, df: Optional[pd.DataFrame] = None,
) -> Optional[str]:
    """
    Check whether a proposed manual entry duplicates an existing bill in
    ANY source (expenses, pending bills or an existing manual entry).

    Returns the source name of the first match, or ``None`` if unique.
    """
    key = _dedup_key(date, shop, amount)
    existing = _build_source_rows(df if df is not None else pd.DataFrame())
    for row in existing:
        if _dedup_key(row[LEDGER_DATE], row[LEDGER_SHOP], row[LEDGER_AMOUNT]) == key:
            return row[LEDGER_SOURCE]
    return None


# ═══════════════════════════════════════════════════════════════
# LEDGER PROJECTION
# ═══════════════════════════════════════════════════════════════
def _expense_rows(df: pd.DataFrame) -> list[dict]:
    """Collapse itemised expenses into one bill total per (date, shop)."""
    if df is None or df.empty:
        return []
    if Columns.DATE not in df.columns or Columns.PRICE_PAID not in df.columns:
        return []

    work = df.copy()
    work[Columns.SHOP] = (
        work.get(Columns.SHOP, "").fillna("").astype(str).str.strip()
        if Columns.SHOP in work.columns else ""
    )
    work["_date"] = work[Columns.DATE].map(_norm_date)
    work["_amount"] = pd.to_numeric(work[Columns.PRICE_PAID], errors="coerce").fillna(0.0)

    currency_col = Columns.CURRENCY if Columns.CURRENCY in work.columns else None

    rows: list[dict] = []
    grouped = work.groupby(["_date", Columns.SHOP], dropna=False)
    for (date_str, shop), grp in grouped:
        if currency_col:
            modes = grp[currency_col].dropna()
            currency = modes.iloc[0] if not modes.empty else DEFAULT_CURRENCY
        else:
            currency = DEFAULT_CURRENCY
        rows.append({
            LEDGER_DATE: date_str,
            LEDGER_SHOP: str(shop or "").strip(),
            LEDGER_AMOUNT: round(float(grp["_amount"].sum()), 2),
            LEDGER_CURRENCY: currency,
            LEDGER_SOURCE: SOURCE_EXPENSE,
        })
    return rows


def _pending_rows() -> list[dict]:
    """Read pending (not-yet-itemised) bills as ledger rows."""
    try:
        import pending_bills as pb
        bills = pb.load_pending_bills()
    except Exception:  # noqa: BLE001 – pending bills is optional
        return []
    return [{
        LEDGER_DATE: _norm_date(b.get("date")),
        LEDGER_SHOP: str(b.get("shop", "")).strip(),
        LEDGER_AMOUNT: round(float(b.get("total_amount", 0.0) or 0.0), 2),
        LEDGER_CURRENCY: b.get("currency", DEFAULT_CURRENCY),
        LEDGER_SOURCE: SOURCE_PENDING,
        "bill_id": b.get("bill_id"),
        "receipt": b.get("receipt") or {},
    } for b in bills]


def _manual_rows() -> list[dict]:
    return [{
        LEDGER_DATE: _norm_date(e.get("date")),
        LEDGER_SHOP: str(e.get("shop", "")).strip(),
        LEDGER_AMOUNT: round(float(e.get("amount", 0.0) or 0.0), 2),
        LEDGER_CURRENCY: e.get("currency", DEFAULT_CURRENCY),
        LEDGER_SOURCE: SOURCE_MANUAL,
        "ledger_id": e.get("ledger_id"),
        "note": e.get("note", ""),
    } for e in _load_raw()]


def _build_source_rows(df: pd.DataFrame) -> list[dict]:
    """All rows from all three sources, before de-duplication."""
    return _expense_rows(df) + _pending_rows() + _manual_rows()


def build_ledger(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the consolidated, de-duplicated Bills Ledger.

    Returns a DataFrame sorted newest-first with columns:
    ``Date, Shop, Amount, Currency, Source`` (plus internal ``ledger_id``
    / ``note`` for manual rows, used by the management UI).
    """
    rows = _build_source_rows(df)

    # De-duplicate on (date, shop, amount), keeping the highest-priority
    # source so an itemised expense or pending bill always wins over a
    # redundant manual entry.
    rows.sort(key=lambda r: _SOURCE_PRIORITY.get(r[LEDGER_SOURCE], 9))
    seen: set[tuple[str, str, float]] = set()
    unique: list[dict] = []
    for r in rows:
        key = _dedup_key(r[LEDGER_DATE], r[LEDGER_SHOP], r[LEDGER_AMOUNT])
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)

    columns = [LEDGER_DATE, LEDGER_SHOP, LEDGER_AMOUNT, LEDGER_CURRENCY,
               LEDGER_SOURCE, "ledger_id", "bill_id", "receipt", "note"]
    if not unique:
        return pd.DataFrame(columns=columns)

    out = pd.DataFrame(unique)
    for col in columns:
        if col not in out.columns:
            out[col] = None
    out = out[columns]
    out = out.sort_values(LEDGER_DATE, ascending=False, na_position="last")
    return out.reset_index(drop=True)
