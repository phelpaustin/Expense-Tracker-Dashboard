# trips_manager.py
# ──────────────────────────────────────────────────────────────
#  Trip Expense Tracker — data layer
#
#  Persists trips and their expenses to  data/trips.json
#  (same data/ folder used by dropdown_options.json).
#  Also syncs to Google Sheets (worksheets: "Trips", "TripExpenses")
#  when a gspread connection is available.
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

import streamlit as st

# ── Storage path ───────────────────────────────────────────────
_TRIPS_FILE = os.path.join("data", "trips.json")

# ── Trip categories ────────────────────────────────────────────
TRIP_CATEGORIES = [
    # Food & Drink
    "🍽️ Food & Drink",
    "🌅 Breakfast",
    "☀️ Lunch",
    "🌙 Dinner",
    "☕ Coffee",
    "🍵 Tea",
    "☕ Café",
    "🍺 Alcohol",
    "🧃 Groceries",
    "🍕 Takeaway",
    # Transport
    "🚌 Bus Fare",
    "🚆 Train Fare",
    "✈️ Flights",
    "🚢 Ferry / Cruise",
    "🚇 Metro / Subway",
    "🚡 Cable Car / Tram",
    "🚕 Taxi / Rideshare",
    "🛵 Moped / Scooter",
    "🚲 Bicycle / E-Bike",
    "🎫 Travel Pass",
    "⛽ Petrol / Fuel",
    "🛣️ Toll",
    "🅿️ Parking",
    "🚗 Car Rental",
    # Stay
    "🏨 Stay",
    "🏕️ Camping",
    "🏠 Airbnb / Rental",
    "🛏️ Hostel",
    # Activities
    "🎡 Activity",
    "🏛️ Museum / Sights",
    "🎭 Shows / Events",
    "🏖️ Beach / Water",
    "⛷️ Sports / Adventure",
    "🧖 Spa / Wellness",
    "🎲 Nightlife",
    "🗺️ Tours / Guides",
    # Shopping
    "🛍️ Shopping",
    "👗 Clothing",
    "💄 Beauty",
    "📸 Electronics",
    "📚 Books / Media",
    "🧴 Toiletries",
    # Health
    "🏥 Health",
    "💊 Pharmacy",
    "🦷 Dental",
    "🩺 Doctor / Clinic",
    "🧪 Tests / Lab",
    # Communication
    "📱 Communication",
    "📶 SIM / Data",
    "🌐 Internet / WiFi",
    "📞 Phone Calls",
    "📬 Postage / Courier",
    # Money
    "💱 Currency Exchange",
    "🏧 ATM Fees",
    "🧾 Visa / Permits",
    "🔒 Insurance",
    # Other
    "🎁 Gifts & Souvenirs",
    "🧺 Laundry",
    "👶 Kids / Family",
    "🐾 Pet Care",
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
#  GOOGLE SHEETS SYNC
# ═══════════════════════════════════════════════════════════════

# Per-session state — stored in st.session_state so concurrent users in the
# same Streamlit server process never share one another's GSheets connection.
_SPREADSHEET_KEY = "_trips_spreadsheet"
_SYNCED_KEY      = "_trips_synced_from_gsheets"


def _get_spreadsheet():
    return st.session_state.get(_SPREADSHEET_KEY)


def _set_spreadsheet(value) -> None:
    st.session_state[_SPREADSHEET_KEY] = value


TRIPS_WS_NAME    = "Trips"
EXPENSES_WS_NAME = "TripExpenses"

_TRIP_HEADERS = [
    "id", "name", "destination", "start_date", "end_date",
    "currency", "budget", "description", "status", "created_at",
]
_EXPENSE_HEADERS = [
    "id", "trip_id", "item", "category", "amount", "currency",
    "date", "is_stay", "check_in", "check_out", "notes",
]


def init_gsheets(sheet) -> None:
    """
    Call once at page render time with the main gspread worksheet object
    (the same `sheet` passed through ctx in Main_Dashboard_App.py).

    On the first call per session it pulls GSheets data into local JSON
    so all reads stay fast.  Every subsequent _save_raw() call will also
    write back to Google Sheets automatically.
    """
    if sheet is None:
        return
    try:
        _set_spreadsheet(sheet.spreadsheet)       # worksheet  →  spreadsheet
        if not st.session_state.get(_SYNCED_KEY, False):
            _pull_from_gsheets()                  # one-time startup sync
            st.session_state[_SYNCED_KEY] = True
    except Exception as exc:
        print(f"[trips_manager] GSheets init failed: {exc}")
        _set_spreadsheet(None)


def _get_or_create_ws(name: str, headers: list):
    """Return a worksheet by name, creating it (with header row) if missing."""
    spreadsheet = _get_spreadsheet()
    if spreadsheet is None:
        return None
    try:
        try:
            return spreadsheet.worksheet(name)
        except Exception:
            ws = spreadsheet.add_worksheet(
                title=name, rows=1000, cols=len(headers)
            )
            ws.append_row(headers)
            return ws
    except Exception as exc:
        print(f"[trips_manager] Could not get/create worksheet '{name}': {exc}")
        return None



def _load_from_gsheets() -> dict[str, Any] | None:
    """Read trips + expenses from GSheets; return None on any failure."""
    trips_ws    = _get_or_create_ws(TRIPS_WS_NAME,    _TRIP_HEADERS)
    expenses_ws = _get_or_create_ws(EXPENSES_WS_NAME, _EXPENSE_HEADERS)
    if trips_ws is None or expenses_ws is None:
        return None
    try:
        trips    = trips_ws.get_all_records()
        expenses = expenses_ws.get_all_records()

        # Normalise types after GSheets string round-trip
        for t in trips:
            t["budget"] = float(t["budget"]) if t.get("budget") else None
            for k in ("start_date", "end_date", "created_at"):
                if not t.get(k):
                    t[k] = None

        for e in expenses:
            e["amount"]  = float(e["amount"]) if e.get("amount") else 0.0
            e["is_stay"] = str(e.get("is_stay", "")).lower() in ("true", "1", "yes")
            for k in ("check_in", "check_out", "date"):
                if not e.get(k):
                    e[k] = None

        return {"trips": trips, "expenses": expenses}
    except Exception as exc:
        print(f"[trips_manager] GSheets load failed: {exc}")
        return None


def _save_to_gsheets(data: dict[str, Any]) -> bool:
    """Overwrite both GSheets worksheets with current data."""
    trips_ws    = _get_or_create_ws(TRIPS_WS_NAME,    _TRIP_HEADERS)
    expenses_ws = _get_or_create_ws(EXPENSES_WS_NAME, _EXPENSE_HEADERS)
    if trips_ws is None or expenses_ws is None:
        return False
    try:
        trips_ws.clear()
        trips_ws.append_row(_TRIP_HEADERS)
        for t in data.get("trips", []):
            trips_ws.append_row(
                [str(t.get(h, "") if t.get(h) is not None else "") for h in _TRIP_HEADERS]
            )

        expenses_ws.clear()
        expenses_ws.append_row(_EXPENSE_HEADERS)
        for e in data.get("expenses", []):
            expenses_ws.append_row(
                [str(e.get(h, "") if e.get(h) is not None else "") for h in _EXPENSE_HEADERS]
            )
        return True
    except Exception as exc:
        print(f"[trips_manager] GSheets save failed: {exc}")
        return False


def _pull_from_gsheets() -> None:
    """
    One-time startup pull: GSheets → local JSON.
    Keeps reads fast (local file) while GSheets stays the source of truth.
    """
    data = _load_from_gsheets()
    if data is not None:
        os.makedirs("data", exist_ok=True)
        with open(_TRIPS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
        print("[trips_manager] Pulled trip data from Google Sheets.")


# ═══════════════════════════════════════════════════════════════
#  LOW-LEVEL FILE I/O  (reads JSON; writes JSON + GSheets)
# ═══════════════════════════════════════════════════════════════

def _load_raw() -> dict[str, Any]:
    """Load from local JSON (fast). GSheets is only read once at startup."""
    if not os.path.exists(_TRIPS_FILE):
        return {"trips": [], "expenses": []}
    with open(_TRIPS_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _save_raw(data: dict[str, Any]) -> None:
    """Write to local JSON AND sync to GSheets if connected."""
    os.makedirs("data", exist_ok=True)
    with open(_TRIPS_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    if _get_spreadsheet() is not None:
        _save_to_gsheets(data)


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