# pages/page_intelligence.py
# ──────────────────────────────────────────────────────────────
#  Intelligence page — hotspots, temporal patterns, savings
# ──────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd

from page_helpers import hero
import feature_flags as ff


def render(df: pd.DataFrame, **_) -> None:
    hero(
        "Spending Intelligence",
        "Deep analysis of your purchase behaviour — hotspots, velocity & savings",
        "🧠",
    )

    if not ff.HAS_INTELLIGENCE:
        st.error("❌ `spending_intelligence.py` not found. Add it to your project directory.")
        return

    if df.empty:
        st.info("No data available yet. Add some expenses to unlock intelligence.")
        return

    tabs = st.tabs(["🔥 Hotspots", "⚡ Budget Intelligence", "💰 Savings", "📆 Patterns"])
    with tabs[0]:
        ff.hotspot_analysis(df)
    with tabs[1]:
        ff.budget_intelligence(df)
    with tabs[2]:
        ff.savings_opportunities(df)
    with tabs[3]:
        ff.temporal_patterns(df)
