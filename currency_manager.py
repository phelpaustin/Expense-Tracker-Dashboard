# currency_manager.py
import requests
import streamlit as st
from config import CACHE_TTL_LONG

@st.cache_data(ttl=CACHE_TTL_LONG)
def get_exchange_rate(base="INR", target="SEK"):
    """Return conversion factor: 1 base = X target. Uses exchangerate.host"""
    url = f"https://api.exchangerate.host/convert?from={base}&to={target}"
    try:
        resp = requests.get(url, timeout=10).json()
        # 'result' contains converted amount for 1 unit
        return float(resp.get("result", None))
    except Exception:
        return None
