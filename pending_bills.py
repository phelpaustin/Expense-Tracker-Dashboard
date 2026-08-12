# pending_bills.py
"""
Data layer for *pending bills* — total-amount bills captured now and
itemised later.

Pending bills live in a SEPARATE store (``data/pending_bills.json``) and
never enter the main expense table, analytics, dedup or charts until they
are itemised. Itemising writes normal expense rows through the usual
``save_data()`` path; the bill is then archived here with
``status = "itemised"`` so the receipt link is never lost.

Record shape
------------
    {
        "bill_id":     "a1b2c3d4",
        "date":        "2026-06-20",
        "shop":        "ICA Maxi",
        "currency":    "SEK",
        "total_amount": 742.50,
        "note":        "Weekly groceries",
        "receipt": {
            "file_id":    "<drive id or null>",
            "web_link":   "<drive link or null>",
            "local_path": "<local path or null>",
            "filename":   "ICA_Maxi_2026-06-20_a1b2c3d4.jpg",
            "storage":    "drive" | "local" | "none"
        },
        "status":      "pending" | "itemised",
        "created_at":  "2026-06-20T18:35:00",
        "itemised_at": null
    }
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Optional

from config import PENDING_BILLS_FILE

log = logging.getLogger("pending_bills")


# ═══════════════════════════════════════════════════════════════
# LOW-LEVEL FILE I/O
# ═══════════════════════════════════════════════════════════════
def _new_id() -> str:
    return uuid.uuid4().hex[:8]


from json_store import JsonStore
_STORE = JsonStore(PENDING_BILLS_FILE, default=[], sync=True)


def _load_raw() -> list[dict]:
    data = _STORE.load()
    return data if isinstance(data, list) else []


def _save_raw(bills: list[dict]) -> bool:
    return _STORE.save(bills)


# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════
def load_pending_bills(include_itemised: bool = False) -> list[dict]:
    """Return bills; by default only those still pending."""
    bills = _load_raw()
    if include_itemised:
        return bills
    return [b for b in bills if b.get("status", "pending") == "pending"]


def get_bill(bill_id: str) -> Optional[dict]:
    return next((b for b in _load_raw() if b.get("bill_id") == bill_id), None)


def add_pending_bill(
    date: Any,
    shop: str,
    total_amount: float,
    currency: str = "SEK",
    note: str = "",
    receipt: Optional[dict] = None,
) -> str:
    """Create a new pending bill and persist it. Returns the new bill_id."""
    bills = _load_raw()
    bill_id = _new_id()
    bills.append({
        "bill_id": bill_id,
        "date": str(date),
        "shop": (shop or "").strip(),
        "currency": currency or "SEK",
        "total_amount": float(total_amount or 0.0),
        "note": (note or "").strip(),
        "receipt": receipt or {
            "file_id": None, "web_link": None, "local_path": None,
            "filename": None, "storage": "none",
        },
        "status": "pending",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "itemised_at": None,
    })
    _save_raw(bills)
    return bill_id


def update_pending_bill(bill_id: str, **fields) -> bool:
    """Update arbitrary fields on a pending bill."""
    bills = _load_raw()
    found = False
    for b in bills:
        if b.get("bill_id") == bill_id:
            b.update(fields)
            found = True
            break
    if found:
        _save_raw(bills)
    return found


def delete_pending_bill(bill_id: str) -> bool:
    """Permanently remove a bill from the store."""
    bills = _load_raw()
    new_bills = [b for b in bills if b.get("bill_id") != bill_id]
    if len(new_bills) == len(bills):
        return False
    return _save_raw(new_bills)


def mark_itemised(bill_id: str) -> bool:
    """
    Archive a bill as itemised (keeps the record + receipt link for
    traceability instead of deleting it).
    """
    return update_pending_bill(
        bill_id,
        status="itemised",
        itemised_at=datetime.now().isoformat(timespec="seconds"),
    )


def pending_count() -> int:
    return len(load_pending_bills())
