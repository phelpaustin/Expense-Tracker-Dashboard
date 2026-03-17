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

    df2["YM"] = df2["Date"].dt.to_period("M").astype(str)
    monthly = (
        df2.groupby("YM")["PricePaid"]
        .sum()
        .reset_index()
        .sort_values("YM")
    )
    avg_val = monthly["PricePaid"].mean()
    colors = [
        t["danger"] if v > avg_val * 1.2 else (t["warning"] if v > avg_val else t["accent"])
        for v in monthly["PricePaid"]
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=monthly["YM"],
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
        roll = monthly["PricePaid"].rolling(3).mean()
        fig.add_trace(
            go.Scatter(
                x=monthly["YM"],
                y=roll,
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
