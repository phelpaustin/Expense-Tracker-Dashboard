# utils.py
import json
import streamlit as st
from pathlib import Path

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

def calculate_price_per_unit(price, qty):
    try:
        qty = float(qty)
    except Exception:
        qty = 0.0
    if qty == 0:
        return 0.0
    return round(float(price) / qty, 2)