# utils.py
import json
import streamlit as st
import pandas as pd
from pathlib import Path

from config import Columns


def prepare_expense_df(
    df: pd.DataFrame,
    *,
    dropna_dates: bool = True,
    numeric_price: bool = True,
) -> pd.DataFrame:
    """
    Shared expense-frame preparation used across analytics modules.

    Applies the idiom that was duplicated in ~12 places:
      * parse ``Date`` to datetime (``errors="coerce"``),
      * optionally drop rows with an unparseable date,
      * optionally coerce ``PricePaid`` to numeric and fill NaN with 0,
      * add the ``YearMonth`` period string.

    Returns a copy; callers add any module-specific columns on top. Flags let
    callers match their previous exact behaviour (e.g. some sites did not touch
    ``PricePaid``): pass ``numeric_price=False`` to leave it untouched.
    """
    if df is None:
        return df

    out = df.copy()
    if Columns.DATE not in out.columns:
        return out
    out[Columns.DATE] = pd.to_datetime(out[Columns.DATE], errors="coerce")
    if dropna_dates:
        out = out.dropna(subset=[Columns.DATE])
    if numeric_price and Columns.PRICE_PAID in out.columns:
        out[Columns.PRICE_PAID] = pd.to_numeric(
            out[Columns.PRICE_PAID], errors="coerce"
        ).fillna(0)
    out[Columns.YEAR_MONTH] = out[Columns.DATE].dt.to_period("M").astype(str)
    return out


@st.cache_data(show_spinner=False)
def load_dropdown_options():
    path = Path("data/dropdown_options.json")
    with open(path, "r") as f:
        return json.load(f)


def save_dropdown_options(data: dict) -> None:
    """Persist updated dropdown options to JSON and clear the in-memory cache."""
    path = Path("data/dropdown_options.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    load_dropdown_options.clear()          # bust the @st.cache_data cache
    st.session_state["dropdowns"] = data   # keep session state in sync
    try:
        import data_sync
        data_sync.push("data/dropdown_options.json")
    except Exception:  # noqa: BLE001 – sync is best-effort
        pass

def calculate_price_per_unit(price, qty):
    try:
        qty = float(qty)
    except Exception:
        qty = 0.0
    if qty == 0:
        return 0.0
    return round(float(price) / qty, 2)