# trips_manager.py
# ──────────────────────────────────────────────────────────────
#  Trip Expense Tracker — data layer
#
#  Persists trips and their expenses to  data/trips.json
#  (same data/ folder used by dropdown_options.json).
#
#  Data model
#  ----------
#  Trip          → name, destination, dates, budget, currency, status
#  TripExpense   → item, category, amount, date (or stay period),
#                  is_stay flag, notes
#
#  All IDs are short UUIDs (first 8 hex chars).
# ──────────────────────────────────────────────────────────────
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime
from typing import Any

# ── Storage path ───────────────────────────────────────────────
_TRIPS_FILE = os.path.join("data", "trips.json")

# ── Trip categories ────────────────────────────────────────────
TRIP_CATEGORIES = [
    "🍽️ Food & Drink",
    "🚌 Transport",
    "🏨 Stay",
    "🎡 Activity",
    "🛍️ Shopping",
    "🏥 Health",
    "📱 Communication",
    "🎁 Gifts",
    "💡 Other",
]

TRIP_STATUSES = ["Planned", "Active", "Completed"]

# ── Serialisation helpers ──────────────────────────────────────

def _date_str(d: date | str | None) -> str | None:
    """Convert a date → ISO string; pass strings through."""
    if d is None:
        return None
    if isinstance(d, (date, datetime)):
        return d.isoformat()
    return str(d)


def _parse_date(s: str | None) -> date | None:
    """Parse ISO date string → date; return None if blank."""
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


# ═══════════════════════════════════════════════════════════════
#  LOW-LEVEL FILE I/O
# ═══════════════════════════════════════════════════════════════

def _load_raw() -> dict[str, Any]:
    """Load raw JSON dict from disk; return empty scaffold if missing."""
    if not os.path.exists(_TRIPS_FILE):
        return {"trips": [], "expenses": []}
    with open(_TRIPS_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _save_raw(data: dict[str, Any]) -> None:
    """Write raw JSON dict to disk (creates data/ if needed)."""
    os.makedirs("data", exist_ok=True)
    with open(_TRIPS_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════
#  TRIP CRUD
# ═══════════════════════════════════════════════════════════════

def load_trips() -> list[dict]:
    """Return all trips as a list of dicts (dates already as strings)."""
    return _load_raw().get("trips", [])


def get_trip(trip_id: str) -> dict | None:
    """Return a single trip by id, or None."""
    return next((t for t in load_trips() if t["id"] == trip_id), None)


def save_trip(
    name: str,
    destination: str,
    start_date: date,
    end_date: date,
    currency: str = "SEK",
    budget: float | None = None,
    description: str = "",
    status: str = "Planned",
    trip_id: str | None = None,
) -> str:
    """
    Create or update a trip.  Returns the trip id.

    If `trip_id` is given and found, that record is updated in-place;
    otherwise a new record is appended.
    """
    data = _load_raw()
    trips = data.get("trips", [])

    record: dict[str, Any] = {
        "id": trip_id or _new_id(),
        "name": name.strip(),
        "destination": destination.strip(),
        "start_date": _date_str(start_date),
        "end_date": _date_str(end_date),
        "currency": currency,
        "budget": budget,
        "description": description.strip(),
        "status": status,
        "created_at": _date_str(date.today()),
    }

    if trip_id:
        trips = [record if t["id"] == trip_id else t for t in trips]
    else:
        trips.append(record)

    data["trips"] = trips
    _save_raw(data)
    return record["id"]


def delete_trip(trip_id: str) -> None:
    """Delete a trip and all its expenses."""
    data = _load_raw()
    data["trips"]    = [t for t in data.get("trips", [])    if t["id"] != trip_id]
    data["expenses"] = [e for e in data.get("expenses", []) if e["trip_id"] != trip_id]
    _save_raw(data)


def update_trip_status(trip_id: str, status: str) -> None:
    """Quick-update just the status field."""
    data = _load_raw()
    for t in data.get("trips", []):
        if t["id"] == trip_id:
            t["status"] = status
            break
    _save_raw(data)


# ═══════════════════════════════════════════════════════════════
#  EXPENSE CRUD
# ═══════════════════════════════════════════════════════════════

def load_expenses(trip_id: str) -> list[dict]:
    """Return all expenses for a trip, sorted by date."""
    raw = _load_raw().get("expenses", [])
    exps = [e for e in raw if e.get("trip_id") == trip_id]
    return sorted(exps, key=lambda e: e.get("date") or e.get("check_in") or "")


def save_expense(
    trip_id: str,
    item: str,
    category: str,
    amount: float,
    currency: str = "SEK",
    expense_date: date | None = None,
    is_stay: bool = False,
    check_in: date | None = None,
    check_out: date | None = None,
    notes: str = "",
    expense_id: str | None = None,
) -> str:
    """
    Create or update an expense record.  Returns the expense id.

    For stays: set  is_stay=True  and supply check_in / check_out instead
    of expense_date.  The `date` field is set to check_in for sorting.
    """
    data = _load_raw()
    expenses = data.get("expenses", [])

    record: dict[str, Any] = {
        "id": expense_id or _new_id(),
        "trip_id": trip_id,
        "item": item.strip(),
        "category": category,
        "amount": float(amount),
        "currency": currency,
        "notes": notes.strip(),
        "is_stay": is_stay,
    }

    if is_stay:
        record["check_in"]  = _date_str(check_in)
        record["check_out"] = _date_str(check_out)
        record["date"]      = _date_str(check_in)   # for sort ordering
    else:
        record["date"] = _date_str(expense_date or date.today())
        record["check_in"]  = None
        record["check_out"] = None

    if expense_id:
        expenses = [record if e["id"] == expense_id else e for e in expenses]
    else:
        expenses.append(record)

    data["expenses"] = expenses
    _save_raw(data)
    return record["id"]


def delete_expense(expense_id: str) -> None:
    """Delete a single expense record."""
    data = _load_raw()
    data["expenses"] = [e for e in data.get("expenses", []) if e["id"] != expense_id]
    _save_raw(data)


# ═══════════════════════════════════════════════════════════════
#  AGGREGATION HELPERS
# ═══════════════════════════════════════════════════════════════

def trip_total(trip_id: str) -> float:
    """Sum of all expense amounts for a trip."""
    return sum(e["amount"] for e in load_expenses(trip_id))


def trip_by_category(trip_id: str) -> dict[str, float]:
    """Dict of category → total amount for a trip."""
    totals: dict[str, float] = {}
    for e in load_expenses(trip_id):
        cat = e.get("category", "Other")
        totals[cat] = totals.get(cat, 0.0) + e["amount"]
    return totals


def trip_by_day(trip_id: str) -> dict[str, float]:
    """
    Dict of date_string → total for that day.

    Stay expenses are spread evenly across their nights.
    """
    from datetime import timedelta

    totals: dict[str, float] = {}
    for e in load_expenses(trip_id):
        if e.get("is_stay") and e.get("check_in") and e.get("check_out"):
            ci = _parse_date(e["check_in"])
            co = _parse_date(e["check_out"])
            nights = max((co - ci).days, 1)
            per_night = e["amount"] / nights
            for n in range(nights):
                day_str = _date_str(ci + timedelta(days=n))
                totals[day_str] = totals.get(day_str, 0.0) + per_night
        else:
            d = e.get("date", "")
            if d:
                totals[d] = totals.get(d, 0.0) + e["amount"]
    return totals


def all_trips_summary() -> list[dict]:
    """
    Return trips enriched with total_spent field — suitable for
    rendering the trip list cards.
    """
    trips = load_trips()
    for t in trips:
        t["total_spent"] = trip_total(t["id"])
    return trips