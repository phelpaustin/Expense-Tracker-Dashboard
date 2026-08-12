# page_helpers.py
# ──────────────────────────────────────────────────────────────
#  Shared UI helpers used across page modules.
#
#  KEY DESIGN RULE: every function that builds a Plotly figure
#  receives `t` (the theme dict) as an explicit parameter.
#  Nothing here reads `t` from the module's global scope, so
#  every function is independently unit-testable.
# ──────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from config import Columns
from date_utils import normalize_dataframe_dates


def hero(title: str, subtitle: str, emoji: str = "") -> None:
    """Render the gradient hero banner at the top of a page."""
    st.markdown(
        f"""<div class="hero-banner">
            <div>
                <div class="hero-title">{emoji} {title}</div>
                <div class="hero-sub">{subtitle}</div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = "") -> None:
    """
    Render a themed section header with a short gradient accent underline.

    Theme-aware alternative to streamlit-extras' ``colored_header`` (which
    uses a fixed preset palette that wouldn't match the app's themes).
    """
    from theme import get_theme

    t = get_theme()
    sub = (
        f"<div style='font-size:0.8rem;color:{t['text_muted']};margin-top:2px'>{subtitle}</div>"
        if subtitle else ""
    )
    st.markdown(
        f"""<div style="margin:1.2rem 0 0.7rem;">
            <div style="font-size:1.05rem;font-weight:800;color:{t['text_primary']};letter-spacing:-0.01em;">{title}</div>
            {sub}
            <div style="height:3px;width:46px;border-radius:3px;margin-top:6px;background:{t['gradient']};"></div>
        </div>""",
        unsafe_allow_html=True,
    )


def _render_html_iframe(html_str: str, height: int) -> None:
    """
    Render a self-contained HTML/JS string inside a sandboxed iframe.

    Uses ``st.iframe`` with a ``data:`` URI on modern Streamlit (the
    non-deprecated replacement for ``st.components.v1.html``), falling back
    to ``components.html`` on older versions. Both isolate the markup in an
    iframe so embedded ``<script>`` runs and styles never leak into the app.
    """
    if hasattr(st, "iframe"):
        import urllib.parse
        src = "data:text/html;charset=utf-8," + urllib.parse.quote(html_str)
        st.iframe(src, height=height)
    else:  # pragma: no cover - legacy Streamlit
        import streamlit.components.v1 as components
        components.html(html_str, height=height)


def skeleton_dashboard() -> None:
    """Render shimmer placeholders that mimic the dashboard layout while
    the (potentially slow) first data load runs."""
    st.markdown(
        """
        <div style='display:flex;gap:14px;margin-bottom:16px'>
          <div class='skel' style='flex:1;height:96px'></div>
          <div class='skel' style='flex:1;height:96px'></div>
          <div class='skel' style='flex:1;height:96px'></div>
        </div>
        <div style='display:flex;gap:14px'>
          <div class='skel' style='flex:1.4;height:300px'></div>
          <div class='skel' style='flex:1;height:300px'></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def animated_bar_chart(
    x: list, y: list, colors: list, avg_val: float,
    roll: "list | None", t: dict, title: str = "", height: int = 390,
) -> bool:
    """
    Render a themed bar chart whose bars grow from zero on load.

    Uses an embedded Plotly.js (CDN) instance so ``Plotly.animate`` can run
    the grow-in animation the moment the chart is drawn — something the
    server-rendered ``st.plotly_chart`` cannot do on first paint. Honours
    ``prefers-reduced-motion``. Returns True once rendered so callers can
    skip their static fallback.
    """
    import json

    traces = [{
        "type": "bar", "x": x, "y": [0] * len(y),
        "marker": {"color": colors}, "opacity": 0.85,
        "hovertemplate": "<b>%{x}</b><br>%{y:,.0f} SEK<extra></extra>",
        "name": "Monthly total",
    }]
    show_roll = roll is not None
    if show_roll:
        roll_clean = [None if (v != v) else v for v in roll]  # NaN → null
        traces.append({
            "type": "scatter", "x": x, "y": roll_clean, "mode": "lines",
            "line": {"color": t["accent2"], "dash": "dot", "width": 2},
            "name": "3-mo avg",
        })

    layout = {
        "title": {"text": title, "font": {"color": t["text_secondary"], "size": 13, "family": "Plus Jakarta Sans"}},
        "paper_bgcolor": t["chart_paper"], "plot_bgcolor": t["chart_paper"],
        "font": {"color": t["text_secondary"], "family": "Plus Jakarta Sans"},
        "xaxis": {"showgrid": False, "tickcolor": t["border"], "linecolor": t["border"], "automargin": True},
        "yaxis": {"showgrid": True, "gridcolor": t["chart_grid"], "zeroline": False, "automargin": True},
        "legend": {"bgcolor": "rgba(0,0,0,0)", "font": {"color": t["text_secondary"]},
                   "orientation": "h", "y": 1.15, "x": 1, "xanchor": "right"},
        "margin": {"t": 48, "b": 56, "l": 0, "r": 0}, "height": height, "showlegend": show_roll,
        "barcornerradius": 6,
        "shapes": [{
            "type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": avg_val, "y1": avg_val,
            "line": {"color": t["text_muted"], "width": 1.5, "dash": "dot"},
        }],
        "annotations": [{
            "xref": "paper", "x": 1, "y": avg_val, "yanchor": "bottom", "xanchor": "right",
            "text": f"Avg {avg_val:,.0f}", "showarrow": False,
            "font": {"color": t["text_muted"], "size": 11},
        }],
    }

    html = f"""
    <div id="mbc"></div>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <script>
      const traces = {json.dumps(traces)};
      const layout = {json.dumps(layout)};
      const finalY = {json.dumps(list(y))};
      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      Plotly.newPlot('mbc', traces, layout, {{displayModeBar: false, responsive: true}}).then(function() {{
        if (reduce) {{ Plotly.restyle('mbc', {{y: [finalY]}}, [0]); return; }}
        Plotly.animate('mbc', {{data: [{{y: finalY}}], traces: [0]}},
          {{transition: {{duration: 900, easing: 'cubic-out'}}, frame: {{duration: 900, redraw: false}}}});
      }});
    </script>
    """
    _render_html_iframe(html, height=height + 16)
    return True


# ── Lottie-powered empty state ────────────────────────────────
# Small, cached loader for a friendly animated "no data" placeholder.
# Best-effort: falls back to a plain st.info when streamlit-lottie is
# unavailable or the animation can't be fetched (offline, etc.).
_LOTTIE_EMPTY_URL = "https://assets9.lottiefiles.com/packages/lf20_ukwlivpc.json"


@st.cache_data(ttl=86400, show_spinner=False, max_entries=32)
def _load_lottie(url: str) -> "dict | None":
    """Fetch and cache a Lottie animation JSON. Returns None on failure."""
    try:
        import requests
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:  # noqa: BLE001 – purely cosmetic, never fatal
        pass
    return None


def empty_state(message: str, url: str = _LOTTIE_EMPTY_URL, height: int = 180) -> None:
    """
    Render an animated Lottie empty-state with a caption.

    Degrades gracefully to ``st.info(message)`` when streamlit-lottie is
    not installed or the animation cannot be loaded.
    """
    import feature_flags as ff
    from theme import get_theme

    if ff.HAS_LOTTIE:
        anim = _load_lottie(url)
        if anim is not None:
            muted = get_theme().get("text_muted", "#94a3b8")
            _, mid, _ = st.columns([1, 2, 1])
            with mid:
                ff.st_lottie(anim, height=height, loop=True, quality="high")
                st.markdown(
                    f"<div style='text-align:center;color:{muted};font-size:0.85rem'>{message}</div>",
                    unsafe_allow_html=True,
                )
            return
    st.info(message)


# ── Animated count-up KPI cards ───────────────────────────────
def animated_metric_row(metrics: list[dict]) -> None:
    """
    Render a row of KPI cards whose numbers animate (count up) on load.

    Each metric dict supports:
        label      : str   — card caption (may include emoji)
        value      : float — target number to count up to
        prefix     : str   — text before the number (e.g. "")
        suffix     : str   — text after the number  (e.g. " SEK")
        decimals   : int   — decimal places (default 0)
        delta      : str   — optional comparison text (e.g. "12.4% vs last month")
        delta_good : bool  — True → green pill, False → red pill (default True)
        delta_dir  : str   — "up" or "down" arrow (default derived / none)

    Rendered via a single sandboxed HTML component so the JS count-up
    animation runs reliably. Colours come from the active theme, so the
    cards match every palette.
    """
    import html as _html
    from theme import get_theme

    t = get_theme()
    has_delta = any(m.get("delta") for m in metrics)
    cards = ""
    for i, m in enumerate(metrics):
        delta_html = ""
        if m.get("delta"):
            good = m.get("delta_good", True)
            color = t["success"] if good else t["danger"]
            arrow = {"up": "▲", "down": "▼"}.get(m.get("delta_dir", ""), "")
            delta_html = (
                f"<div class='delta' style='color:{color};background:{color}1a'>"
                f"{arrow} {_html.escape(str(m['delta']))}</div>"
            )
        cards += (
            f"<div class='kpi' style='animation-delay:{i * 0.10:.2f}s'>"
            f"<span class='bar'></span>"
            f"<div class='label'>{m.get('label', '')}</div>"
            f"<div class='value' data-target='{float(m.get('value', 0))}' "
            f"data-decimals='{int(m.get('decimals', 0))}' "
            f"data-prefix='{m.get('prefix', '')}' data-suffix='{m.get('suffix', '')}'>0</div>"
            f"{delta_html}"
            f"</div>"
        )

    html = f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;700;800&display=swap');
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; font-family: 'Plus Jakarta Sans', sans-serif; }}
      .row {{ display: flex; gap: 14px; }}
      .kpi {{
        flex: 1; background: {t['card_bg']}; border: 1.5px solid {t['border']};
        border-radius: 14px; padding: 1.05rem 1.25rem; position: relative; overflow: hidden;
        box-shadow: 0 2px 12px rgba(0,0,0,0.05);
        animation: rise 0.55s cubic-bezier(0.22,1,0.36,1) both;
        transition: transform 0.25s cubic-bezier(0.22,1,0.36,1), box-shadow 0.25s ease, border-color 0.25s ease;
      }}
      .kpi:hover {{ transform: translateY(-4px); box-shadow: 0 14px 32px rgba(0,0,0,0.12); border-color: {t['accent']}; }}
      .kpi .bar {{
        position: absolute; top: 0; left: 0; height: 3px; width: 100%;
        background: {t['gradient']}; transform: scaleX(0); transform-origin: left;
        transition: transform 0.35s ease;
      }}
      .kpi:hover .bar {{ transform: scaleX(1); }}
      .label {{
        font-size: 0.70rem; color: {t['text_muted']}; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.08em;
      }}
      .value {{
        font-size: 1.7rem; font-weight: 800; color: {t['text_primary']};
        margin-top: 0.25rem; letter-spacing: -0.02em; font-variant-numeric: tabular-nums;
      }}
      .delta {{
        display: inline-block; margin-top: 0.5rem; padding: 0.12rem 0.5rem;
        font-size: 0.72rem; font-weight: 700; border-radius: 999px; letter-spacing: 0.01em;
      }}
      @keyframes rise {{ from {{ opacity: 0; transform: translateY(14px); }} to {{ opacity: 1; transform: translateY(0); }} }}
      @media (prefers-reduced-motion: reduce) {{ .kpi {{ animation: none; }} }}
    </style>
    <div class="row">{cards}</div>
    <script>
      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      document.querySelectorAll('.value').forEach(function(el) {{
        const target = parseFloat(el.dataset.target) || 0;
        const dec = parseInt(el.dataset.decimals) || 0;
        const prefix = el.dataset.prefix || '';
        const suffix = el.dataset.suffix || '';
        const fmt = function(n) {{
          return prefix + n.toLocaleString(undefined, {{minimumFractionDigits: dec, maximumFractionDigits: dec}}) + suffix;
        }};
        if (reduce) {{ el.textContent = fmt(target); return; }}
        const dur = 1100, start = performance.now();
        function step(now) {{
          let p = Math.min((now - start) / dur, 1);
          p = 1 - Math.pow(1 - p, 3);
          el.textContent = fmt(target * p);
          if (p < 1) requestAnimationFrame(step); else el.textContent = fmt(target);
        }}
        requestAnimationFrame(step);
      }});
    </script>
    """
    _render_html_iframe(html, height=150 if has_delta else 118)



def style_fig(fig: go.Figure, t: dict, height: int = 360) -> go.Figure:
    """
    Apply the active theme to a Plotly figure.

    Parameters
    ----------
    fig    : Plotly figure to style
    t      : Theme dict returned by theme.get_theme()
    height : Chart height in pixels
    """
    fig.update_layout(
        paper_bgcolor=t["chart_paper"],
        plot_bgcolor=t["chart_paper"],
        font=dict(color=t["text_secondary"], family="Plus Jakarta Sans"),
        xaxis=dict(showgrid=False, tickcolor=t["border"], linecolor=t["border"]),
        yaxis=dict(showgrid=True, gridcolor=t["chart_grid"], zeroline=False),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=t["text_secondary"])),
        margin=dict(t=48, b=16, l=0, r=0),
        height=height,
        title_font=dict(color=t["text_secondary"], size=13, family="Plus Jakarta Sans"),
        # Smooth animated transitions when data / layout updates (hover,
        # theme switch, filter change) — modern feel with zero CSS.
        transition=dict(duration=450, easing="cubic-in-out"),
    )
    return fig


def donut_chart(df_in: pd.DataFrame, t: dict) -> None:
    """
    Render a donut chart of spending by category.

    Parameters
    ----------
    df_in : Filtered expense DataFrame
    t     : Theme dict — passed explicitly so this fn is testable
    """
    if df_in.empty or "Category" not in df_in.columns:
        return

    agg = (
        df_in.groupby("Category")["PricePaid"]
        .sum()
        .reset_index()
        .sort_values("PricePaid", ascending=False)
    )
    if len(agg) > 8:
        rest = agg.iloc[8:]["PricePaid"].sum()
        agg = pd.concat(
            [agg.head(8), pd.DataFrame([{"Category": "Other", "PricePaid": rest}])]
        )

    palette = [
        "#5a67d8", "#38b2ac", "#f6ad55", "#68d391",
        "#fc8181", "#76e4f7", "#b794f4", "#fc8181", "#a0aec0",
    ]
    total = agg["PricePaid"].sum()

    fig = go.Figure(
        go.Pie(
            labels=agg["Category"],
            values=agg["PricePaid"],
            hole=0.62,
            marker=dict(
                colors=palette[: len(agg)],
                line=dict(color=t["app_bg"], width=3),
            ),
            hovertemplate="<b>%{label}</b><br>%{value:,.0f} SEK — %{percent}<extra></extra>",
            textfont=dict(color=t["text_secondary"]),
        )
    )
    fig.add_annotation(
        text=f"<b>{total:,.0f}</b><br><span style='font-size:11px'>SEK total</span>",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=16, color=t["text_primary"], family="Plus Jakarta Sans"),
    )
    fig.update_layout(
        title="Spending by Category",
        paper_bgcolor=t["chart_paper"],
        plot_bgcolor=t["chart_paper"],
        font=dict(color=t["text_secondary"], family="Plus Jakarta Sans"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=t["text_secondary"])),
        margin=dict(t=48, b=8, l=0, r=0),
        height=360,
        title_font=dict(color=t["text_secondary"], size=13),
    )
    st.plotly_chart(fig, config={"displayModeBar": False})


def render_ai_card(
    body_html: str,
    provider: str,
    *,
    cache_key: str,
    refresh_key: str,
    accent: str = "#6366f1",
    bg: str = "#f8fafc",
    border: str = "#e2e8f0",
    fg: str = "#0f172a",
    muted: str = "#94a3b8",
    with_refresh: bool = True,
) -> None:
    """
    Render an AI-narrative card and (optionally) its Refresh button.

    Centralises the wrapper + "Generated by …" footer + refresh/cache-clear
    logic that was duplicated across every AI section. Each caller builds its
    own ``body_html`` (a text block or a ``<ul>`` of bullets — already
    HTML-escaped where user/AI text is interpolated) and passes the colours it
    wants, so appearance is preserved per section while the boilerplate lives
    in one place. ``provider`` is always escaped here.

    When ``with_refresh`` is False the button is skipped so callers that place
    it inside their own column layout can render it themselves.
    """
    from security_utils import escape_html

    st.markdown(
        f"<div style='background:{bg};border:1px solid {border};"
        f"border-left:4px solid {accent};border-radius:12px;"
        f"padding:1.1rem 1.4rem;font-size:0.9rem;line-height:1.7;color:{fg};'>"
        f"{body_html}"
        f"<div style='margin-top:0.5rem;font-size:0.72rem;color:{muted};'>"
        f"Generated by {escape_html(provider)}</div></div>",
        unsafe_allow_html=True,
    )
    if with_refresh and st.button("🔄 Refresh", key=refresh_key):
        st.session_state.pop(cache_key, None)
        st.rerun()


def monthly_bar_chart(df_in: pd.DataFrame, t: dict) -> None:
    """
    Render a monthly spending bar chart with a rolling-average overlay.

    Parameters
    ----------
    df_in : Expense DataFrame (any date range)
    t     : Theme dict — passed explicitly so this fn is testable
    """
    df2 = df_in.copy()
    df2["Date"] = pd.to_datetime(
        normalize_dataframe_dates(df2, "Date")["Date"], errors="coerce"
    )
    df2 = df2.dropna(subset=["Date"])
    if df2.empty:
        return

    df2[Columns.YEAR_MONTH] = df2["Date"].dt.to_period("M").astype(str)
    monthly = (
        df2.groupby(Columns.YEAR_MONTH)["PricePaid"]
        .sum()
        .reset_index()
        .sort_values(Columns.YEAR_MONTH)
    )
    avg_val = monthly["PricePaid"].mean()
    colors = [
        t["danger"] if v > avg_val * 1.2 else (t["warning"] if v > avg_val else t["accent"])
        for v in monthly["PricePaid"]
    ]

    # Bars grow from zero on load via an embedded Plotly.animate call.
    roll = (
        monthly["PricePaid"].rolling(3).mean().tolist()
        if len(monthly) >= 3 else None
    )
    if animated_bar_chart(
        x=monthly[Columns.YEAR_MONTH].tolist(),
        y=monthly["PricePaid"].tolist(),
        colors=colors,
        avg_val=float(avg_val),
        roll=roll,
        t=t,
        title="Monthly Spending",
    ):
        return

    # Fallback: static Plotly chart (used if the animated renderer is skipped)
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=monthly[Columns.YEAR_MONTH],
            y=monthly["PricePaid"],
            marker_color=colors,
            opacity=0.85,
            hovertemplate="<b>%{x}</b><br>%{y:,.0f} SEK<extra></extra>",
            name="Monthly total",
        )
    )
    fig.add_hline(
        y=avg_val,
        line_dash="dot",
        line_color=t["text_muted"],
        line_width=1.5,
        annotation_text=f"Avg {avg_val:,.0f}",
        annotation_font_color=t["text_muted"],
    )
    if len(monthly) >= 3:
        roll_series = monthly["PricePaid"].rolling(3).mean()
        fig.add_trace(
            go.Scatter(
                x=monthly[Columns.YEAR_MONTH],
                y=roll_series,
                mode="lines",
                line=dict(color=t["accent2"], dash="dot", width=2),
                name="3-mo avg",
            )
        )
    fig.update_layout(title="Monthly Spending", showlegend=len(monthly) >= 3)
    st.plotly_chart(style_fig(fig, t), config={"displayModeBar": False})


def period_selector(df_in: pd.DataFrame) -> pd.DataFrame:
    """Year / Month selector widget — returns filtered slice."""
    if df_in.empty or "Date" not in df_in.columns:
        return pd.DataFrame()

    df2 = df_in.copy()
    df2["Date"] = pd.to_datetime(
        normalize_dataframe_dates(df2, "Date")["Date"], errors="coerce"
    )
    if df2["Date"].isna().all():
        return pd.DataFrame()

    years = sorted(df2["Date"].dt.year.dropna().unique().tolist(), reverse=True)
    months = sorted(df2["Date"].dt.month.dropna().unique().tolist())

    col_y, col_m = st.columns(2)
    with col_y:
        sel_year = st.selectbox("Year", years, key="period_year")
    with col_m:
        month_names = ["All"] + [pd.Timestamp(2000, m, 1).strftime("%B") for m in months]
        sel_month = st.selectbox("Month", month_names, key="period_month")

    result = df2[df2["Date"].dt.year == sel_year]
    if sel_month != "All":
        mn = pd.to_datetime(sel_month, format="%B").month
        result = result[result["Date"].dt.month == mn]
    return result


def incomplete_entries_expander(df: pd.DataFrame, save_data, sheet) -> None:
    """Show a warning expander for rows missing Date or ExpenseType."""
    from date_utils import normalize_dataframe_dates
    from data_manager import bump_data_version

    if df.empty or not all(c in df.columns for c in ["Date", "ExpenseType"]):
        return

    missing = df[
        df["Date"].isna() | (df["Date"] == "")
        | df["ExpenseType"].isna() | (df["ExpenseType"] == "")
    ].copy()
    if missing.empty:
        return

    with st.expander(f"⚠️ {len(missing)} Incomplete Entries", expanded=False):
        st.warning("Some entries are missing **Date** or **Expense Type**.")
        missing["Date"] = normalize_dataframe_dates(missing, "Date")["Date"]
        edited = st.data_editor(
            missing, num_rows="dynamic", width="stretch",
            key="edit_missing", hide_index=True,
        )
        if st.button("💾 Save Fixed Entries"):
            updated = pd.concat([df.drop(missing.index), edited], ignore_index=True)
            save_data(updated, sheet)
            bump_data_version()
            st.success("✅ Saved!")
            st.rerun()


def handle_import_merge(df: pd.DataFrame, save_data, sheet) -> None:
    """
    Shared import → preview → merge workflow.

    Used by both the Dashboard and Import/Export pages so the logic lives in
    exactly one place. Renders the import widget, previews pending data, and
    merges it into the existing DataFrame (via the optional import_export
    helpers when present, or a manual concat+clean fallback otherwise).
    """
    import feature_flags as ff
    from data_manager import bump_data_version, clean_data

    show_import = (
        not st.session_state.get("merge_complete", False)
        and not st.session_state.get("merge_complete_flagged", False)
    )
    if show_import:
        existing_cols = df.columns.tolist() if not df.empty else None
        if ff.HAS_IMPORT_WORKFLOW:
            ff.import_workflow(existing_columns=existing_cols)
        elif ff.import_button is not None:
            imported = ff.import_button(existing_columns=existing_cols)
            if imported is not None and not imported.empty:
                if "Date" in imported.columns:
                    imported["Date"] = normalize_dataframe_dates(imported, "Date")["Date"]
                st.session_state["pending_import_df"] = imported
                st.session_state["merge_ready"] = True
                st.subheader("📄 Preview")
                st.dataframe(imported, width="stretch", hide_index=True)
    else:
        if st.session_state.get("merge_complete"):
            st.sidebar.success("✅ Last import merged.")

    if st.session_state.get("merge_ready", False):
        if ff.HAS_MERGE:
            ff.perform_merge_if_ready(df, save_data, sheet)
        else:
            pending = st.session_state.get("pending_import_df", pd.DataFrame())
            if not pending.empty:
                try:
                    combined = pd.concat([df, pending], ignore_index=True)
                    combined = clean_data(combined)
                    save_data(combined, sheet)
                    st.cache_data.clear()
                    bump_data_version()
                    st.success("✅ Imported data merged successfully!")
                    for k in ["merge_ready", "pending_import_df"]:
                        st.session_state.pop(k, None)
                    st.session_state["merge_complete_flagged"] = True
                    st.session_state["merge_complete"] = True
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Merge failed: {e}")

