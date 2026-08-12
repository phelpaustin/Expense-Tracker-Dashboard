# theme.py
# ──────────────────────────────────────────────────────────────
#  Theme system — 8 palettes, all access through get_theme().
#  chart functions receive `t` explicitly — never read it as a global.
# ──────────────────────────────────────────────────────────────
import streamlit as st

THEMES: dict[str, dict] = {
    "☀️ Light": {
        "app_bg": "#f5f7fa", "sidebar_bg": "#ffffff", "card_bg": "#ffffff",
        "border": "#e8ecf0", "text_primary": "#0d1117", "text_secondary": "#4a5568",
        "text_muted": "#9aa5b4", "accent": "#5a67d8", "accent_soft": "rgba(90,103,216,0.10)",
        "accent2": "#38b2ac", "input_bg": "#f0f4f8", "chart_paper": "#ffffff", "chart_grid": "#edf2f7",
        "gradient": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        "success": "#38a169", "warning": "#d69e2e", "danger": "#e53e3e",
    },
    "🌑 Dark": {
        "app_bg": "#0d1117", "sidebar_bg": "#161b22", "card_bg": "#21262d",
        "border": "#30363d", "text_primary": "#e6edf3", "text_secondary": "#8b949e",
        "text_muted": "#484f58", "accent": "#79c0ff", "accent_soft": "rgba(121,192,255,0.12)",
        "accent2": "#56d364", "input_bg": "#0d1117", "chart_paper": "#21262d", "chart_grid": "#30363d",
        "gradient": "linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)",
        "success": "#56d364", "warning": "#e3b341", "danger": "#f85149",
    },
    "🌊 Ocean": {
        "app_bg": "#f0f9ff", "sidebar_bg": "#e0f2fe", "card_bg": "#ffffff",
        "border": "#bae6fd", "text_primary": "#0c4a6e", "text_secondary": "#0369a1",
        "text_muted": "#38bdf8", "accent": "#0284c7", "accent_soft": "rgba(2,132,199,0.10)",
        "accent2": "#0d9488", "input_bg": "#e0f2fe", "chart_paper": "#f0f9ff", "chart_grid": "#bae6fd",
        "gradient": "linear-gradient(135deg, #0284c7 0%, #0d9488 100%)",
        "success": "#0d9488", "warning": "#d97706", "danger": "#dc2626",
    },
    "🌿 Forest": {
        "app_bg": "#f0fdf4", "sidebar_bg": "#dcfce7", "card_bg": "#ffffff",
        "border": "#bbf7d0", "text_primary": "#14532d", "text_secondary": "#15803d",
        "text_muted": "#4ade80", "accent": "#16a34a", "accent_soft": "rgba(22,163,74,0.10)",
        "accent2": "#0f766e", "input_bg": "#dcfce7", "chart_paper": "#f0fdf4", "chart_grid": "#bbf7d0",
        "gradient": "linear-gradient(135deg, #16a34a 0%, #0f766e 100%)",
        "success": "#16a34a", "warning": "#ca8a04", "danger": "#dc2626",
    },
    "🌅 Sunset": {
        "app_bg": "#fff7ed", "sidebar_bg": "#ffedd5", "card_bg": "#ffffff",
        "border": "#fed7aa", "text_primary": "#7c2d12", "text_secondary": "#c2410c",
        "text_muted": "#fb923c", "accent": "#ea580c", "accent_soft": "rgba(234,88,12,0.10)",
        "accent2": "#db2777", "input_bg": "#ffedd5", "chart_paper": "#fff7ed", "chart_grid": "#fed7aa",
        "gradient": "linear-gradient(135deg, #ea580c 0%, #db2777 100%)",
        "success": "#16a34a", "warning": "#ca8a04", "danger": "#dc2626",
    },
    "🌙 Midnight": {
        "app_bg": "#0d0d1a", "sidebar_bg": "#0a0a14", "card_bg": "#13131f",
        "border": "#1e1e3f", "text_primary": "#e2e2ff", "text_secondary": "#a5b4fc",
        "text_muted": "#4f4f7a", "accent": "#7c3aed", "accent_soft": "rgba(124,58,237,0.15)",
        "accent2": "#db2777", "input_bg": "#13131f", "chart_paper": "#13131f", "chart_grid": "#1e1e3f",
        "gradient": "linear-gradient(135deg, #7c3aed 0%, #db2777 100%)",
        "success": "#22c55e", "warning": "#f59e0b", "danger": "#ef4444",
    },
    "🌸 Rose": {
        "app_bg": "#fff1f2", "sidebar_bg": "#ffe4e6", "card_bg": "#ffffff",
        "border": "#fecdd3", "text_primary": "#881337", "text_secondary": "#be123c",
        "text_muted": "#fb7185", "accent": "#e11d48", "accent_soft": "rgba(225,29,72,0.10)",
        "accent2": "#9333ea", "input_bg": "#ffe4e6", "chart_paper": "#fff1f2", "chart_grid": "#fecdd3",
        "gradient": "linear-gradient(135deg, #e11d48 0%, #9333ea 100%)",
        "success": "#16a34a", "warning": "#ca8a04", "danger": "#e11d48",
    },
    "⬜ Slate": {
        "app_bg": "#f8fafc", "sidebar_bg": "#f1f5f9", "card_bg": "#ffffff",
        "border": "#cbd5e1", "text_primary": "#1e293b", "text_secondary": "#475569",
        "text_muted": "#94a3b8", "accent": "#475569", "accent_soft": "rgba(71,85,105,0.10)",
        "accent2": "#0f766e", "input_bg": "#f1f5f9", "chart_paper": "#ffffff", "chart_grid": "#e2e8f0",
        "gradient": "linear-gradient(135deg, #475569 0%, #0f766e 100%)",
        "success": "#16a34a", "warning": "#ca8a04", "danger": "#dc2626",
    },
}

DEFAULT_THEME = "☀️ Light"


# ──────────────────────────────────────────────────────────────
#  Chart palette — single source of truth for the compact colour
#  keys used by Plotly chart modules (analytics_advanced.py,
#  spending_intelligence.py, budget_manager.py).  Previously each
#  of those modules carried its own divergent copy of this table.
#  Access through get_chart_theme().
# ──────────────────────────────────────────────────────────────
CHART_PALETTES: dict[str, dict] = {
    "☀️ Light":    {"paper": "#ffffff", "grid": "#e2e8f0", "text": "#475569", "muted": "#94a3b8", "fg": "#0f172a", "border": "#e2e8f0", "accent": "#6366f1", "card": "#ffffff", "bg": "#f8fafc", "bar_bg": "#f1f5f9"},
    "🌑 Dark":     {"paper": "#1e293b", "grid": "#334155", "text": "#94a3b8", "muted": "#64748b", "fg": "#f1f5f9", "border": "#334155", "accent": "#818cf8", "card": "#1e293b", "bg": "#0f172a", "bar_bg": "#334155"},
    "🌊 Ocean":    {"paper": "#f0f9ff", "grid": "#bae6fd", "text": "#0369a1", "muted": "#38bdf8", "fg": "#0c4a6e", "border": "#bae6fd", "accent": "#0284c7", "card": "#ffffff", "bg": "#f0f9ff", "bar_bg": "#bae6fd"},
    "🌿 Forest":   {"paper": "#f0fdf4", "grid": "#bbf7d0", "text": "#15803d", "muted": "#4ade80", "fg": "#14532d", "border": "#bbf7d0", "accent": "#16a34a", "card": "#ffffff", "bg": "#f0fdf4", "bar_bg": "#bbf7d0"},
    "🌅 Sunset":   {"paper": "#fff7ed", "grid": "#fed7aa", "text": "#c2410c", "muted": "#fb923c", "fg": "#7c2d12", "border": "#fed7aa", "accent": "#ea580c", "card": "#ffffff", "bg": "#fff7ed", "bar_bg": "#fed7aa"},
    "🌙 Midnight": {"paper": "#13131f", "grid": "#1e1e3f", "text": "#a5b4fc", "muted": "#4f4f7a", "fg": "#e2e2ff", "border": "#1e1e3f", "accent": "#7c3aed", "card": "#13131f", "bg": "#0d0d1a", "bar_bg": "#1e1e3f"},
    "🌸 Rose":     {"paper": "#fff1f2", "grid": "#fecdd3", "text": "#be123c", "muted": "#fb7185", "fg": "#881337", "border": "#fecdd3", "accent": "#e11d48", "card": "#ffffff", "bg": "#fff1f2", "bar_bg": "#fecdd3"},
    "⬜ Slate":    {"paper": "#ffffff", "grid": "#e2e8f0", "text": "#475569", "muted": "#94a3b8", "fg": "#1e293b", "border": "#cbd5e1", "accent": "#64748b", "card": "#ffffff", "bg": "#f8fafc", "bar_bg": "#e2e8f0"},
}


def get_theme() -> dict:
    """Return the currently active theme dict."""
    return THEMES.get(
        st.session_state.get("theme_name", DEFAULT_THEME),
        THEMES[DEFAULT_THEME],
    )


def get_chart_theme() -> dict:
    """
    Return the compact chart colour palette for the active theme.

    Single source of truth for the Plotly chart modules — replaces the
    per-module ``_THEME_PALETTES`` copies that previously had to be kept
    in sync by hand.
    """
    return CHART_PALETTES.get(
        st.session_state.get("theme_name", DEFAULT_THEME),
        CHART_PALETTES[DEFAULT_THEME],
    )


def apply_theme(t: dict) -> None:
    """Inject CSS for the given theme dict into the Streamlit page."""
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap');

    /* ── Keyframes ─────────────────────────────────────────── */
    @keyframes fadeInUp {{
        from {{ opacity: 0; transform: translateY(14px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes shimmer {{
        0%   {{ background-position: -500px 0; }}
        100% {{ background-position: 500px 0; }}
    }}
    @keyframes floatY {{
        0%, 100% {{ transform: translateY(0); }}
        50%      {{ transform: translateY(-4px); }}
    }}
    @keyframes pulseGlow {{
        0%, 100% {{ box-shadow: 0 0 0 0 {t["accent_soft"]}; }}
        50%      {{ box-shadow: 0 0 0 6px transparent; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
        *, *::before, *::after {{ animation: none !important; transition: none !important; }}
    }}

    html, body, [class*="css"] {{ font-family: 'Plus Jakarta Sans', sans-serif !important; }}
    .stApp {{ background-color: {t["app_bg"]} !important; color: {t["text_primary"]} !important; }}
    [data-testid="stSidebar"] {{ background-color: {t["sidebar_bg"]} !important; border-right: 1px solid {t["border"]} !important; }}
    [data-testid="stSidebar"] *, [data-testid="stSidebar"] label {{ color: {t["text_secondary"]} !important; }}
    .block-container {{ padding-top: 1.5rem; max-width: 1400px; animation: fadeInUp 0.5s ease both; }}
    /* Stagger the entrance of top-level blocks for a lively page load */
    .block-container > div > div > div[data-testid="stVerticalBlock"] > div {{ animation: fadeInUp 0.45s ease both; }}
    h1, h2, h3, h4 {{ color: {t["text_primary"]} !important; letter-spacing: -0.025em; font-family: 'Plus Jakarta Sans', sans-serif !important; font-weight: 700 !important; }}
    .stTextInput > div > input, .stNumberInput > div > input, .stDateInput > div > input {{
        background: {t["input_bg"]} !important; border: 1.5px solid {t["border"]} !important;
        border-radius: 10px !important; color: {t["text_primary"]} !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important; padding: 0.5rem 0.75rem !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }}
    .stTextInput > div > input:focus, .stNumberInput > div > input:focus, .stDateInput > div > input:focus {{
        border-color: {t["accent"]} !important; box-shadow: 0 0 0 3px {t["accent_soft"]} !important;
    }}
    .stSelectbox > div > div {{
        background: {t["input_bg"]} !important; border: 1.5px solid {t["border"]} !important;
        border-radius: 10px !important; color: {t["text_primary"]} !important;
    }}
    .stButton > button {{
        background: {t["gradient"]} !important; color: white !important;
        border: none !important; border-radius: 10px !important; font-weight: 600 !important;
        letter-spacing: 0.01em; transition: all 0.2s ease; font-family: 'Plus Jakarta Sans', sans-serif !important;
        padding: 0.45rem 1.1rem !important;
    }}
    .stButton > button:hover {{ opacity: 0.96; transform: translateY(-2px); box-shadow: 0 10px 28px {t["accent_soft"]}, 0 2px 6px rgba(0,0,0,0.08); }}
    .stButton > button:active {{ transform: translateY(0) scale(0.98); transition: all 0.08s ease; }}
    .stButton > button[kind="secondary"] {{
        background: transparent !important; border: 1.5px solid {t["border"]} !important;
        color: {t["text_secondary"]} !important;
    }}
    [data-testid="stMetric"] {{
        background: {t["card_bg"]}; border: 1.5px solid {t["border"]};
        border-radius: 14px; padding: 1.1rem 1.3rem; position: relative; overflow: hidden;
        box-shadow: 0 2px 12px rgba(0,0,0,0.04);
        transition: transform 0.25s cubic-bezier(0.22,1,0.36,1), box-shadow 0.25s ease, border-color 0.25s ease;
        animation: fadeInUp 0.5s ease both;
    }}
    /* Accent bar that grows in on hover */
    [data-testid="stMetric"]::before {{
        content: ""; position: absolute; top: 0; left: 0; height: 3px; width: 100%;
        background: {t["gradient"]}; transform: scaleX(0); transform-origin: left;
        transition: transform 0.3s ease;
    }}
    [data-testid="stMetric"]:hover {{
        transform: translateY(-4px);
        box-shadow: 0 14px 32px rgba(0,0,0,0.10); border-color: {t["accent"]};
    }}
    [data-testid="stMetric"]:hover::before {{ transform: scaleX(1); }}
    [data-testid="stMetricLabel"] {{
        color: {t["text_muted"]} !important; font-size: 0.72rem !important;
        font-weight: 700 !important; text-transform: uppercase; letter-spacing: 0.08em;
    }}
    [data-testid="stMetricValue"] {{
        color: {t["text_primary"]} !important; font-size: 1.65rem !important;
        font-weight: 800 !important; letter-spacing: -0.02em;
    }}
    .kpi-card {{
        background: {t["card_bg"]}; border: 1.5px solid {t["border"]};
        padding: 1.1rem 1.3rem; border-radius: 14px; box-shadow: 0 2px 12px rgba(0,0,0,0.04);
        transition: transform 0.25s cubic-bezier(0.22,1,0.36,1), box-shadow 0.25s ease, border-color 0.25s ease;
        animation: fadeInUp 0.5s ease both;
    }}
    .kpi-card:hover {{ transform: translateY(-4px); box-shadow: 0 14px 32px rgba(0,0,0,0.10); border-color: {t["accent"]}; }}
    .kpi-label {{ font-size: 0.72rem; color: {t["text_muted"]}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }}
    .kpi-value {{ font-size: 1.65rem; font-weight: 800; color: {t["text_primary"]}; margin-top: 0.2rem; letter-spacing: -0.02em; }}
    .stTabs [data-baseweb="tab-list"] {{
        background: {t["input_bg"]}; border-radius: 12px; border: 1.5px solid {t["border"]}; gap: 3px; padding: 5px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background: transparent; border-radius: 9px; color: {t["text_muted"]}; font-weight: 600; font-size: 0.92rem;
        padding: 0.5rem 1.1rem;
        transition: color 0.2s ease, background 0.2s ease, transform 0.15s ease;
    }}
    .stTabs [data-baseweb="tab"]:hover {{ color: {t["accent"]}; background: {t["accent_soft"]}; transform: translateY(-1px); }}
    .stTabs [aria-selected="true"] {{
        background: {t["card_bg"]} !important; color: {t["accent"]} !important;
        font-weight: 700 !important; box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
    }}
    details {{ background: {t["card_bg"]}; border: 1.5px solid {t["border"]}; border-radius: 12px; transition: border-color 0.2s ease, box-shadow 0.2s ease; }}
    details:hover {{ border-color: {t["accent"]}; box-shadow: 0 6px 18px rgba(0,0,0,0.06); }}
    details > summary {{ color: {t["text_primary"]} !important; padding: 0.75rem; transition: color 0.2s ease; }}
    details > summary:hover {{ color: {t["accent"]} !important; }}
    /* Dataframe / table container polish — rounded, bordered, hover-lift */
    [data-testid="stDataFrame"], [data-testid="stTable"] {{
        border: 1.5px solid {t["border"]}; border-radius: 12px; overflow: hidden;
        box-shadow: 0 2px 12px rgba(0,0,0,0.04);
        transition: box-shadow 0.25s ease, border-color 0.25s ease;
    }}
    [data-testid="stDataFrame"]:hover, [data-testid="stTable"]:hover {{
        box-shadow: 0 10px 26px rgba(0,0,0,0.09); border-color: {t["accent"]};
    }}
    /* Skeleton shimmer placeholders */
    .skel {{
        background: linear-gradient(90deg, {t["input_bg"]} 25%, {t["border"]} 37%, {t["input_bg"]} 63%);
        background-size: 400% 100%; border-radius: 10px; animation: skelShimmer 1.3s ease infinite;
    }}
    @keyframes skelShimmer {{ 0% {{ background-position: 100% 0; }} 100% {{ background-position: 0 0; }} }}
    .stSuccess, .stInfo, .stWarning, .stError {{ border-radius: 10px; }}
    .section-header {{
        font-size: 1rem; font-weight: 700; color: {t["text_primary"]};
        letter-spacing: -0.01em; margin: 1.2rem 0 0.6rem;
    }}
    .nav-active {{
        background: {t["accent_soft"]}; border-left: 3px solid {t["accent"]};
        border-radius: 0 9px 9px 0; padding: 0.35rem 0.5rem 0.35rem 0.55rem;
        margin-bottom: 0.15rem; font-weight: 700; color: {t["accent"]}; font-size: 0.88rem;
        display: flex; align-items: center; gap: 0.4rem;
        animation: navIn 0.32s cubic-bezier(0.22,1,0.36,1) both;
    }}
    /* Pulsing dot marks the active page */
    .nav-active::before {{
        content: ""; width: 6px; height: 6px; border-radius: 50%;
        background: {t["accent"]}; flex: 0 0 auto; animation: navDot 1.8s ease-in-out infinite;
    }}
    @keyframes navIn {{ from {{ opacity: 0; transform: translateX(-8px); }} to {{ opacity: 1; transform: translateX(0); }} }}
    @keyframes navDot {{ 0%, 100% {{ box-shadow: 0 0 0 0 {t["accent_soft"]}; }} 50% {{ box-shadow: 0 0 0 4px transparent; }} }}
    /* Flat, left-aligned sidebar nav buttons (override global gradient) */
    [data-testid="stSidebar"] .stButton > button {{
        background: transparent !important; color: {t["text_secondary"]} !important;
        border: none !important; box-shadow: none !important;
        text-align: left !important; justify-content: flex-start !important;
        font-weight: 500 !important; font-size: 0.88rem !important;
        padding: 0.35rem 0.55rem !important; border-radius: 9px !important;
        transition: background 0.18s ease, color 0.18s ease, transform 0.18s ease !important;
    }}
    [data-testid="stSidebar"] .stButton > button:hover {{
        background: {t["accent_soft"]} !important; color: {t["accent"]} !important;
        transform: translateX(4px) !important; box-shadow: none !important;
    }}
    hr {{ border-color: {t["border"]} !important; opacity: 0.6; margin: 1.25rem 0; }}
    ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
    ::-webkit-scrollbar-track {{ background: {t["app_bg"]}; }}
    ::-webkit-scrollbar-thumb {{ background: {t["border"]}; border-radius: 3px; }}
    #MainMenu, footer {{ visibility: hidden; }}
    .hero-banner {{
        background: {t["gradient"]}; border-radius: 16px; padding: 1.5rem 2rem;
        margin-bottom: 1.5rem; display: flex; align-items: center; justify-content: space-between;
        position: relative; overflow: hidden;
        box-shadow: 0 10px 30px {t["accent_soft"]};
        animation: fadeInUp 0.55s ease both;
    }}
    /* Moving light sweep across the hero */
    .hero-banner::after {{
        content: ""; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
        background: linear-gradient(105deg, transparent 30%, rgba(255,255,255,0.18) 45%, transparent 60%);
        background-size: 500px 100%; animation: shimmer 3.5s infinite linear; pointer-events: none;
    }}
    .hero-title {{ font-size: 1.6rem; font-weight: 800; color: white; letter-spacing: -0.03em; position: relative; z-index: 1; }}
    .hero-sub {{ font-size: 0.88rem; color: rgba(255,255,255,0.78); margin-top: 0.2rem; position: relative; z-index: 1; }}
    </style>
    """, unsafe_allow_html=True)
