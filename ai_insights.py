# ai_insights.py
"""
🤖 AI Financial Insights
────────────────────────────────────────────────────────────────
Two features:
  1. ai_monthly_report(df)   — AI-written narrative monthly report
                               called from spending_intelligence.py
                               inside budget_intelligence()

  2. ai_chat_ui(df)          — conversational Q&A page wired into
                               Main_Dashboard_App.py as "🤖 AI Insights"

Both use the same provider cascade:  Gemini → Claude → GPT-4o
(whichever key is in st.secrets / env)
"""

import json
import re
import requests
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List, Tuple


# ═══════════════════════════════════════════════════════════════
# KEY HELPERS
# ═══════════════════════════════════════════════════════════════

def _secret(key: str) -> str:
    try:
        return st.secrets.get(key, "")
    except Exception:
        return ""


def _get_keys() -> Dict[str, str]:
    return {
        "gemini":    _secret("GEMINI_API_KEY"),
        "anthropic": _secret("ANTHROPIC_API_KEY"),
        "openai":    _secret("OPENAI_API_KEY"),
    }


# ═══════════════════════════════════════════════════════════════
# DATA SUMMARISER  (keeps prompts small — never send raw rows)
# ═══════════════════════════════════════════════════════════════

def _summarise(df: pd.DataFrame) -> Dict:
    """
    Compress the full DataFrame into a compact JSON-serialisable summary
    that fits comfortably in an AI prompt.  Raw rows are never sent.
    """
    if df.empty:
        return {"error": "no data"}

    df2 = df.copy()
    df2["Date"] = pd.to_datetime(df2.get("Date", pd.Series()), errors="coerce")
    df2["PricePaid"] = pd.to_numeric(df2.get("PricePaid", pd.Series()), errors="coerce").fillna(0)
    df2["YM"] = df2["Date"].dt.to_period("M").astype(str)

    now    = pd.Timestamp.now()
    curr_m = now.to_period("M").strftime("%Y-%m")
    prev_m = (now - pd.DateOffset(months=1)).to_period("M").strftime("%Y-%m")

    monthly = df2.groupby("YM")["PricePaid"].sum().sort_index()

    def top_n(series, n=8):
        return series.nlargest(n).round(2).to_dict()

    summary = {
        "currency": "SEK",
        "date_range": {
            "from": str(df2["Date"].min().date()) if not df2["Date"].isna().all() else None,
            "to":   str(df2["Date"].max().date()) if not df2["Date"].isna().all() else None,
        },
        "total_all_time": round(float(df2["PricePaid"].sum()), 2),
        "monthly_totals": {k: round(float(v), 2) for k, v in monthly.items()},
        "monthly_avg":    round(float(monthly.mean()), 2) if not monthly.empty else 0,
        "this_month":     round(float(monthly.get(curr_m, 0)), 2),
        "last_month":     round(float(monthly.get(prev_m, 0)), 2),
    }

    if "Category" in df2.columns:
        summary["by_category_all_time"] = top_n(
            df2.groupby("Category")["PricePaid"].sum()
        )
        this = df2[df2["YM"] == curr_m]
        if not this.empty:
            summary["by_category_this_month"] = top_n(
                this.groupby("Category")["PricePaid"].sum()
            )
        prev = df2[df2["YM"] == prev_m]
        if not prev.empty:
            summary["by_category_last_month"] = top_n(
                prev.groupby("Category")["PricePaid"].sum()
            )

    if "Shop" in df2.columns:
        summary["top_shops"] = top_n(
            df2.groupby("Shop")["PricePaid"].sum()
        )

    if "Item" in df2.columns:
        summary["top_items"] = top_n(
            df2.groupby("Item")["PricePaid"].sum()
        )

    if "DayName" not in df2.columns:
        df2["DayName"] = df2["Date"].dt.day_name()
    summary["by_day_of_week"] = (
        df2.groupby("DayName")["PricePaid"].sum().round(2).to_dict()
    )

    return summary


# ═══════════════════════════════════════════════════════════════
# AI CALL  (Gemini → Claude → GPT-4o cascade)
# ═══════════════════════════════════════════════════════════════

def _call_ai(system: str, user: str, keys: Dict[str, str]) -> Tuple[str, str]:
    """
    Send a text prompt to the first available AI provider.
    Returns (response_text, provider_name).
    """
    if keys.get("gemini"):
        try:
            return _gemini(system, user, keys["gemini"]), "Gemini"
        except Exception as e:
            st.warning(f"Gemini: {e}")

    if keys.get("anthropic"):
        try:
            return _claude(system, user, keys["anthropic"]), "Claude"
        except Exception as e:
            st.warning(f"Claude: {e}")

    if keys.get("openai"):
        try:
            return _gpt4o(system, user, keys["openai"]), "GPT-4o"
        except Exception as e:
            st.warning(f"GPT-4o: {e}")

    return "", ""


def _gemini(system: str, user: str, api_key: str) -> str:
    models = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash-latest"]
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user}]}],
        "generationConfig": {"maxOutputTokens": 2048, "temperature": 0.4},
    }
    for model in models:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        resp = requests.post(url, json=payload, timeout=60)
        if resp.status_code != 200:
            st.error(f"Status: {resp.status_code}")
            st.code(resp.text)
            resp.raise_for_status()
        if resp.status_code == 404:
            continue
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    raise RuntimeError("No Gemini model available")


def _claude(system: str, user: str, api_key: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text.strip()


def _gpt4o(system: str, user: str, api_key: str) -> str:
    import openai
    client = openai.OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()


# ═══════════════════════════════════════════════════════════════
# FEATURE 1 — AI MONTHLY REPORT
# Called from spending_intelligence.budget_intelligence()
# ═══════════════════════════════════════════════════════════════

_REPORT_SYSTEM = """You are a sharp, friendly personal finance advisor.
The user will give you a JSON summary of their expense data.
Write a concise monthly financial report in plain English — 4 to 6 bullet points.
Each bullet should be one concrete insight or actionable tip.
Be specific with numbers. Tone: direct, encouraging, no fluff.
Do NOT use markdown headers. Use bullet points (•) only."""


def ai_monthly_report(df: pd.DataFrame) -> None:
    """
    Render an AI-written monthly narrative inside budget_intelligence().
    Drop this call at the bottom of that function.
    """
    keys = _get_keys()
    if not any(keys.values()):
        return   # no AI key → silently skip, rule-based cards still show

    st.markdown("#### 🤖 AI Monthly Summary")

    cache_key = f"ai_report_{pd.Timestamp.now().strftime('%Y-%m')}"
    if cache_key in st.session_state:
        _render_report(st.session_state[cache_key])
        return

    if st.button("✨ Generate AI Report", key="gen_report_btn"):
        with st.spinner("AI is reading your finances…"):
            summary = _summarise(df)
            user_msg = (
                f"Here is my expense summary for analysis:\n"
                f"{json.dumps(summary, indent=2)}\n\n"
                f"Today is {datetime.now().strftime('%B %Y')}. "
                f"Write my monthly financial report."
            )
            st.write("Gemini key found:", bool(keys.get("gemini")))
            text, provider = _call_ai(_REPORT_SYSTEM, user_msg, keys)

        if text:
            st.session_state[cache_key] = (text, provider)
            _render_report((text, provider))
        else:
            st.error("No AI provider available. Add a GEMINI_API_KEY to secrets.toml.")


def _render_report(cached: Tuple[str, str]) -> None:
    text, provider = cached
    t_colors = {
        "paper": "#ffffff", "border": "#e2e8f0",
        "fg": "#0f172a",    "muted": "#64748b",
        "accent": "#6366f1",
    }
    try:
        from spending_intelligence import _t
        t_colors = _t()
    except Exception:
        pass

    bullets = [b.strip().lstrip("•").strip()
               for b in text.split("\n") if b.strip().startswith("•") or
               (b.strip() and not b.strip().startswith("#"))]
    bullets = [b for b in bullets if len(b) > 10][:8]

    items_html = "".join(
        f"<li style='margin-bottom:0.45rem;color:{t_colors.get('fg','#0f172a')};'>{b}</li>"
        for b in bullets
    ) if bullets else f"<li style='color:{t_colors.get('fg','#0f172a')};'>{text}</li>"

    st.markdown(
        f"""<div style='background:{t_colors.get("paper","#fff")};
            border:1px solid {t_colors.get("border","#e2e8f0")};
            border-left:4px solid {t_colors.get("accent","#6366f1")};
            border-radius:12px;padding:1.1rem 1.4rem;margin-bottom:1rem;'>
            <ul style='margin:0;padding-left:1.2rem;line-height:1.75;font-size:0.92rem;'>
            {items_html}
            </ul>
            <div style='margin-top:0.6rem;font-size:0.72rem;
                color:{t_colors.get("muted","#64748b")};'>
                Generated by {provider}
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1, 6])
    with col1:
        if st.button("🔄 Refresh", key="refresh_report_btn"):
            cache_key = f"ai_report_{pd.Timestamp.now().strftime('%Y-%m')}"
            st.session_state.pop(cache_key, None)
            st.rerun()


# ═══════════════════════════════════════════════════════════════
# FEATURE 2 — AI CHAT PAGE
# Registered as "🤖 AI Insights" in Main_Dashboard_App.py
# ═══════════════════════════════════════════════════════════════

_CHAT_SYSTEM = """You are a personal finance assistant with access to the user's expense data.
Answer questions clearly and concisely. Be specific — use the numbers provided.
If the data doesn't contain enough information to answer, say so honestly.
Keep answers to 3–5 sentences unless a longer breakdown is genuinely useful.
Currency is SEK unless stated otherwise."""


def ai_chat_ui(df: pd.DataFrame) -> None:
    """Full-page conversational Q&A about the user's expense data."""

    st.title("🤖 AI Financial Insights")
    st.caption("Ask anything about your spending — the AI reads your data, not the internet.")

    keys = _get_keys()
    if not any(keys.values()):
        st.warning(
            "No AI key found. Add at least one to `.streamlit/secrets.toml`:\n\n"
            "```toml\nGEMINI_API_KEY = 'AIza...'\n```\n\n"
            "Gemini is free at https://aistudio.google.com/app/apikey"
        )
        return

    # ── Build data summary once per session ───────────────────
    if "ai_data_summary" not in st.session_state or st.button(
        "🔄 Refresh data snapshot", key="refresh_snapshot"
    ):
        with st.spinner("Summarising your expense data…"):
            st.session_state["ai_data_summary"] = _summarise(df)
        st.success("Data snapshot updated.")

    summary = st.session_state["ai_data_summary"]
    summary_json = json.dumps(summary, indent=2)

    # ── Suggested questions ────────────────────────────────────
    with st.expander("💡 Suggested questions", expanded=False):
        suggestions = [
            "What was my biggest spending category last month?",
            "How does this month compare to my average?",
            "Which shop do I spend the most at?",
            "What day of the week do I spend most?",
            "Where can I most easily cut back?",
            "What are my top 5 most bought items?",
            "Am I spending more or less than usual on groceries?",
            "Give me a summary of my finances in plain English.",
        ]
        cols = st.columns(2)
        for i, q in enumerate(suggestions):
            with cols[i % 2]:
                if st.button(q, key=f"sug_{i}"):
                    st.session_state.setdefault("ai_messages", [])
                    st.session_state["ai_messages"].append(
                        {"role": "user", "content": q}
                    )
                    st.rerun()

    # ── Chat history ───────────────────────────────────────────
    if "ai_messages" not in st.session_state:
        st.session_state["ai_messages"] = []

    messages: List[Dict] = st.session_state["ai_messages"]

    # Render past messages
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── New user input ─────────────────────────────────────────
    user_input = st.chat_input("Ask about your spending…")

    if user_input:
        messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Build conversation context for the AI
        # Include data summary in first message, keep full history after
        history_for_ai = []
        data_context = (
            f"Here is the user's expense data summary (JSON):\n{summary_json}\n\n"
            f"Today: {datetime.now().strftime('%B %d, %Y')}."
        )

        for i, m in enumerate(messages[:-1]):   # all but the latest
            if i == 0:
                # Prepend data context to first user message
                history_for_ai.append({
                    "role": m["role"],
                    "content": data_context + "\n\n" + m["content"]
                    if m["role"] == "user"
                    else m["content"],
                })
            else:
                history_for_ai.append(m)

        # Latest question also carries data context if history is empty
        latest_content = (
            data_context + "\n\nUser question: " + user_input
            if not history_for_ai
            else user_input
        )

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                reply, provider = _call_ai_chat(
                    _CHAT_SYSTEM, history_for_ai, latest_content, keys
                )

            if reply:
                st.markdown(reply)
                messages.append({"role": "assistant", "content": reply})
                st.caption(f"*{provider}*")
            else:
                err = "Sorry, no AI provider responded. Check your API keys in secrets.toml."
                st.error(err)
                messages.append({"role": "assistant", "content": err})

        st.session_state["ai_messages"] = messages

    # ── Clear chat ─────────────────────────────────────────────
    if messages:
        st.markdown("---")
        if st.button("🗑️ Clear chat", key="clear_chat"):
            st.session_state["ai_messages"] = []
            st.rerun()


def _call_ai_chat(
    system: str,
    history: List[Dict],
    latest: str,
    keys: Dict[str, str],
) -> Tuple[str, str]:
    """
    Multi-turn chat call. History is a list of {role, content} dicts.
    Returns (reply_text, provider_name).
    """
    if keys.get("gemini"):
        try:
            return _gemini_chat(system, history, latest, keys["gemini"]), "Gemini"
        except Exception as e:
            st.warning(f"Gemini: {e}")

    if keys.get("anthropic"):
        try:
            return _claude_chat(system, history, latest, keys["anthropic"]), "Claude"
        except Exception as e:
            st.warning(f"Claude: {e}")

    if keys.get("openai"):
        try:
            return _gpt4o_chat(system, history, latest, keys["openai"]), "GPT-4o"
        except Exception as e:
            st.warning(f"GPT-4o: {e}")

    return "", ""


def _gemini_chat(system, history, latest, api_key):
    # Gemini doesn't have a native multi-turn history API in the REST v1beta,
    # so we flatten history into a single user message
    flat = "\n\n".join(
        f"{'User' if m['role']=='user' else 'Assistant'}: {m['content']}"
        for m in history
    )
    user_msg = (flat + "\n\nUser: " + latest) if flat else latest
    return _gemini(system, user_msg, api_key)


def _claude_chat(system, history, latest, api_key):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msgs = history + [{"role": "user", "content": latest}]
    # Anthropic requires alternating user/assistant — ensure that
    cleaned = []
    for m in msgs:
        if cleaned and cleaned[-1]["role"] == m["role"]:
            cleaned[-1]["content"] += "\n" + m["content"]
        else:
            cleaned.append({"role": m["role"], "content": m["content"]})
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=system,
        messages=cleaned,
    )
    return msg.content[0].text.strip()


def _gpt4o_chat(system, history, latest, api_key):
    import openai
    client = openai.OpenAI(api_key=api_key)
    msgs = [{"role": "system", "content": system}]
    msgs += history
    msgs.append({"role": "user", "content": latest})
    resp = client.chat.completions.create(
        model="gpt-4o", max_tokens=2048, messages=msgs
    )
    return resp.choices[0].message.content.strip()
