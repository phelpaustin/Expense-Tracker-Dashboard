# utils.py
import json
import streamlit as st
from pathlib import Path

@st.cache_data(show_spinner=False)
def load_dropdown_options():
    path = Path("data/dropdown_options.json")
    with open(path, "r") as f:
        return json.load(f)

def calculate_price_per_unit(price, qty):
    try:
        qty = float(qty)
    except Exception:
        qty = 0.0
    if qty == 0:
        return 0.0
    return round(float(price) / qty, 2)
