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


def get_theme() -> dict:
    """Return the currently active theme dict."""
    return THEMES.get(
        st.session_state.get("theme_name", DEFAULT_THEME),
        THEMES[DEFAULT_THEME],
    )


def apply_theme(t: dict) -> None:
    """Inject CSS for the given theme dict into the Streamlit page."""
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {{ font-family: 'Plus Jakarta Sans', sans-serif !important; }}
    .stApp {{ background-color: {t["app_bg"]} !important; color: {t["text_primary"]} !important; }}
    [data-testid="stSidebar"] {{ background-color: {t["sidebar_bg"]} !important; border-right: 1px solid {t["border"]} !important; }}
    [data-testid="stSidebar"] *, [data-testid="stSidebar"] label {{ color: {t["text_secondary"]} !important; }}
    .block-container {{ padding-top: 1.5rem; max-width: 1400px; }}
    h1, h2, h3, h4 {{ color: {t["text_primary"]} !important; letter-spacing: -0.025em; font-family: 'Plus Jakarta Sans', sans-serif !important; font-weight: 700 !important; }}
    .stTextInput > div > input, .stNumberInput > div > input, .stDateInput > div > input {{
        background: {t["input_bg"]} !important; border: 1.5px solid {t["border"]} !important;
        border-radius: 10px !important; color: {t["text_primary"]} !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important; padding: 0.5rem 0.75rem !important;
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
    .stButton > button:hover {{ opacity: 0.90; transform: translateY(-2px); box-shadow: 0 8px 25px {t["accent_soft"]}; }}
    .stButton > button[kind="secondary"] {{
        background: transparent !important; border: 1.5px solid {t["border"]} !important;
        color: {t["text_secondary"]} !important;
    }}
    [data-testid="stMetric"] {{
        background: {t["card_bg"]}; border: 1.5px solid {t["border"]};
        border-radius: 14px; padding: 1.1rem 1.3rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.04); transition: box-shadow 0.2s;
    }}
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
    }}
    .kpi-label {{ font-size: 0.72rem; color: {t["text_muted"]}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }}
    .kpi-value {{ font-size: 1.65rem; font-weight: 800; color: {t["text_primary"]}; margin-top: 0.2rem; letter-spacing: -0.02em; }}
    .stTabs [data-baseweb="tab-list"] {{
        background: {t["input_bg"]}; border-radius: 12px; border: 1.5px solid {t["border"]}; gap: 2px; padding: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background: transparent; border-radius: 9px; color: {t["text_muted"]}; font-weight: 500; font-size: 0.88rem;
    }}
    .stTabs [aria-selected="true"] {{
        background: {t["card_bg"]} !important; color: {t["accent"]} !important;
        font-weight: 700 !important; box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
    }}
    details {{ background: {t["card_bg"]}; border: 1.5px solid {t["border"]}; border-radius: 12px; }}
    details > summary {{ color: {t["text_primary"]} !important; padding: 0.75rem; }}
    .stSuccess, .stInfo, .stWarning, .stError {{ border-radius: 10px; }}
    .section-header {{
        font-size: 1rem; font-weight: 700; color: {t["text_primary"]};
        letter-spacing: -0.01em; margin: 1.2rem 0 0.6rem;
    }}
    .nav-active {{
        background: {t["accent_soft"]}; border-left: 3px solid {t["accent"]};
        border-radius: 0 9px 9px 0; padding: 0.2rem 0.5rem 0.2rem 0.35rem;
        margin-bottom: 0.15rem; font-weight: 700; color: {t["accent"]}; font-size: 0.88rem;
    }}
    hr {{ border-color: {t["border"]} !important; opacity: 0.6; margin: 1.25rem 0; }}
    ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
    ::-webkit-scrollbar-track {{ background: {t["app_bg"]}; }}
    ::-webkit-scrollbar-thumb {{ background: {t["border"]}; border-radius: 3px; }}
    #MainMenu, footer {{ visibility: hidden; }}
    .hero-banner {{
        background: {t["gradient"]}; border-radius: 16px; padding: 1.5rem 2rem;
        margin-bottom: 1.5rem; display: flex; align-items: center; justify-content: space-between;
    }}
    .hero-title {{ font-size: 1.6rem; font-weight: 800; color: white; letter-spacing: -0.03em; }}
    .hero-sub {{ font-size: 0.88rem; color: rgba(255,255,255,0.78); margin-top: 0.2rem; }}
    </style>
    """, unsafe_allow_html=True)
