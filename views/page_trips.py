# views/page_trips.py
# ──────────────────────────────────────────────────────────────
#  Travel Expense Tracker page
#
#  UI flow
#  -------
#  1.  Trip List  — cards for every trip; "New Trip" button
#  2.  Trip Detail — selected trip → KPIs, day-by-day ledger,
#                    category breakdown, add/delete expenses
#  3.  Add/Edit Trip  form (modal-style expander)
#
#  All Plotly figures receive `t` (theme dict) explicitly — never
#  reads theme as a global, matching the rest of the codebase.
# ──────────────────────────────────────────────────────────────
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import date, timedelta

from page_helpers import hero, style_fig
from trips_manager import (
    TRIP_CATEGORIES,
    TRIP_STATUSES,
    all_trips_summary,
    delete_expense,
    delete_trip,
    get_trip,
    load_expenses,
    save_expense,
    save_trip,
    trip_by_category,
    trip_by_day,
    trip_total,
    update_trip_status,
    _parse_date,
)


# ═══════════════════════════════════════════════════════════════
#  SMALL UI HELPERS
# ═══════════════════════════════════════════════════════════════

_STATUS_COLORS = {
    "Planned": "#f59e0b",
    "Active":  "#22c55e",
    "Completed": "#6b7280",
}

_CAT_ICON = {
    "🍽️ Food & Drink": "🍽️",
    "🚌 Transport":    "🚌",
    "🏨 Stay":         "🏨",
    "🎡 Activity":     "🎡",
    "🛍️ Shopping":    "🛍️",
    "🏥 Health":       "🏥",
    "📱 Communication": "📱",
    "🎁 Gifts":         "🎁",
    "💡 Other":         "💡",
}


def _currency_symbol(c: str) -> str:
    return {"SEK": "kr", "USD": "$", "EUR": "€", "INR": "₹"}.get(c, c)


def _fmt(amount: float, currency: str) -> str:
    sym = _currency_symbol(currency)
    if currency in ("USD", "INR"):
        return f"{sym}{amount:,.0f}"
    return f"{amount:,.0f} {sym}"


def _badge(label: str, color: str) -> str:
    return (
        f"<span style='background:{color}22;color:{color};"
        f"border-radius:6px;padding:2px 10px;font-size:0.72rem;"
        f"font-weight:700;letter-spacing:0.05em;'>{label}</span>"
    )


def _card_style(t: dict) -> str:
    return (
        f"background:{t['card_bg']};border:1.5px solid {t['border']};"
        "border-radius:16px;padding:1.2rem 1.4rem;margin-bottom:0.75rem;"
        "box-shadow:0 2px 12px rgba(0,0,0,0.04);"
    )


# ═══════════════════════════════════════════════════════════════
#  TRIP LIST VIEW
# ═══════════════════════════════════════════════════════════════

def _render_trip_list(t: dict) -> None:
    """Show all trip cards + 'New Trip' button."""
    trips = all_trips_summary()

    col_hdr, col_btn = st.columns([3, 1])
    with col_hdr:
        st.markdown("### ✈️ Your Trips")
    with col_btn:
        if st.button("＋ New Trip", key="btn_new_trip"):
            st.session_state["trip_form_open"] = True
            st.session_state["trip_form_edit_id"] = None
            st.rerun()

    # ── New / Edit Trip form ───────────────────────────────────
    if st.session_state.get("trip_form_open"):
        _render_trip_form(t)
        st.markdown("---")

    if not trips:
        st.info("No trips yet — click **＋ New Trip** to get started.")
        return

    # ── Trip cards grid ────────────────────────────────────────
    for trip in sorted(trips, key=lambda x: x.get("start_date", ""), reverse=True):
        _render_trip_card(trip, t)


def _render_trip_card(trip: dict, t: dict) -> None:
    start = _parse_date(trip.get("start_date"))
    end   = _parse_date(trip.get("end_date"))
    dur   = (end - start).days + 1 if start and end else "?"
    cur   = trip.get("currency", "SEK")
    spent = trip.get("total_spent", 0.0)
    budget = trip.get("budget")
    status = trip.get("status", "Planned")
    status_color = _STATUS_COLORS.get(status, "#9ca3af")

    date_range = ""
    if start and end:
        date_range = f"{start.strftime('%d %b %Y')}  →  {end.strftime('%d %b %Y')}"

    pct = min((spent / budget * 100), 100) if budget else None
    bar_color = t["danger"] if pct and pct > 90 else (t["warning"] if pct and pct > 70 else t["success"])

    st.markdown(
        f"""<div style='{_card_style(t)}'>
            <div style='display:flex;align-items:flex-start;justify-content:space-between;'>
                <div>
                    <div style='font-size:1.15rem;font-weight:800;
                                color:{t["text_primary"]};letter-spacing:-0.02em;'>
                        🗺️ {trip['name']}
                    </div>
                    <div style='font-size:0.82rem;color:{t["text_muted"]};margin-top:2px;'>
                        📍 {trip.get('destination','—')} &nbsp;·&nbsp; {date_range}
                        &nbsp;·&nbsp; {dur} day{'s' if dur != 1 else ''}
                    </div>
                </div>
                <div style='text-align:right;'>
                    {_badge(status, status_color)}
                    <div style='font-size:1.35rem;font-weight:800;color:{t["text_primary"]};
                                margin-top:6px;letter-spacing:-0.02em;'>
                        {_fmt(spent, cur)}
                    </div>
                    {'<div style="font-size:0.75rem;color:' + t["text_muted"] + ';">of ' +
                     _fmt(budget, cur) + ' budget</div>' if budget else ''}
                </div>
            </div>
            {_budget_bar(pct, bar_color, t) if pct is not None else ""}
        </div>""",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        if st.button(f"📂 Open  {trip['name']}", key=f"open_{trip['id']}"):
            st.session_state["active_trip_id"] = trip["id"]
            st.session_state["trip_form_open"] = False
            st.rerun()
    with c2:
        if st.button("✏️ Edit", key=f"edit_{trip['id']}"):
            st.session_state["trip_form_open"] = True
            st.session_state["trip_form_edit_id"] = trip["id"]
            st.rerun()
    with c3:
        if st.button("🗑️ Delete", key=f"del_{trip['id']}"):
            st.session_state[f"confirm_del_{trip['id']}"] = True
            st.rerun()

    if st.session_state.get(f"confirm_del_{trip['id']}"):
        st.warning(f"Delete **{trip['name']}** and all its expenses?")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("✅ Yes, delete", key=f"yes_del_{trip['id']}"):
                delete_trip(trip["id"])
                st.session_state.pop(f"confirm_del_{trip['id']}", None)
                st.success("Trip deleted.")
                st.rerun()
        with cc2:
            if st.button("❌ Cancel", key=f"no_del_{trip['id']}"):
                st.session_state.pop(f"confirm_del_{trip['id']}", None)
                st.rerun()


def _budget_bar(pct: float, bar_color: str, t: dict) -> str:
    return f"""
    <div style='margin-top:10px;'>
        <div style='background:{t["border"]};border-radius:99px;height:6px;'>
            <div style='width:{pct:.1f}%;background:{bar_color};border-radius:99px;height:6px;
                        transition:width 0.4s ease;'></div>
        </div>
        <div style='font-size:0.7rem;color:{t["text_muted"]};margin-top:3px;'>{pct:.0f}% of budget used</div>
    </div>"""


# ═══════════════════════════════════════════════════════════════
#  NEW / EDIT TRIP FORM
# ═══════════════════════════════════════════════════════════════

def _render_trip_form(t: dict) -> None:
    edit_id = st.session_state.get("trip_form_edit_id")
    existing = get_trip(edit_id) if edit_id else None
    label = "✏️ Edit Trip" if existing else "✈️ New Trip"

    with st.expander(label, expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input(
                "Trip Name *",
                value=existing["name"] if existing else "",
                placeholder="e.g. Bangkok Backpacking",
                key="tf_name",
            )
            destination = st.text_input(
                "Destination *",
                value=existing.get("destination", "") if existing else "",
                placeholder="e.g. Thailand",
                key="tf_dest",
            )
            status = st.selectbox(
                "Status",
                TRIP_STATUSES,
                index=TRIP_STATUSES.index(existing["status"]) if existing else 0,
                key="tf_status",
            )
        with c2:
            start = st.date_input(
                "Start Date *",
                value=_parse_date(existing["start_date"]) if existing else date.today(),
                key="tf_start",
            )
            end = st.date_input(
                "End Date *",
                value=_parse_date(existing["end_date"]) if existing else date.today() + timedelta(days=7),
                key="tf_end",
            )
            currency = st.selectbox(
                "Base Currency",
                ["SEK", "USD", "EUR", "INR"],
                index=["SEK", "USD", "EUR", "INR"].index(existing.get("currency", "SEK")) if existing else 0,
                key="tf_currency",
            )

        c3, c4 = st.columns(2)
        with c3:
            budget_val = existing.get("budget") if existing else None
            budget = st.number_input(
                "Budget (optional)",
                min_value=0.0,
                value=float(budget_val) if budget_val else 0.0,
                step=100.0,
                key="tf_budget",
            )
        with c4:
            desc = st.text_input(
                "Description",
                value=existing.get("description", "") if existing else "",
                placeholder="Optional notes",
                key="tf_desc",
            )

        b1, b2 = st.columns([1, 3])
        with b1:
            if st.button("💾 Save Trip", key="tf_save"):
                if not name or not destination:
                    st.error("Name and Destination are required.")
                elif start > end:
                    st.error("Start date must be before end date.")
                else:
                    tid = save_trip(
                        name=name,
                        destination=destination,
                        start_date=start,
                        end_date=end,
                        currency=currency,
                        budget=budget if budget > 0 else None,
                        description=desc,
                        status=status,
                        trip_id=edit_id,
                    )
                    st.success("✅ Trip saved!")
                    st.session_state["trip_form_open"] = False
                    st.session_state["trip_form_edit_id"] = None
                    st.session_state["active_trip_id"] = tid
                    st.rerun()
        with b2:
            if st.button("Cancel", key="tf_cancel"):
                st.session_state["trip_form_open"] = False
                st.session_state["trip_form_edit_id"] = None
                st.rerun()


# ═══════════════════════════════════════════════════════════════
#  TRIP DETAIL VIEW
# ═══════════════════════════════════════════════════════════════

def _render_trip_detail(trip_id: str, t: dict) -> None:
    trip = get_trip(trip_id)
    if not trip:
        st.error("Trip not found.")
        st.session_state.pop("active_trip_id", None)
        st.rerun()
        return

    cur      = trip.get("currency", "SEK")
    start    = _parse_date(trip.get("start_date"))
    end      = _parse_date(trip.get("end_date"))
    budget   = trip.get("budget")
    spent    = trip_total(trip_id)
    expenses = load_expenses(trip_id)

    # ── Breadcrumb / back button ───────────────────────────────
    if st.button("← All Trips", key="back_to_list"):
        st.session_state.pop("active_trip_id", None)
        st.rerun()

    # ── Hero ──────────────────────────────────────────────────
    status        = trip.get("status", "Planned")
    status_color  = _STATUS_COLORS.get(status, "#9ca3af")
    dur           = (end - start).days + 1 if start and end else "?"
    date_range    = ""
    if start and end:
        date_range = f"{start.strftime('%d %b %Y')}  →  {end.strftime('%d %b %Y')}"

    st.markdown(
        f"""<div style='{_card_style(t)}background:{t["gradient"]};border:none;'>
            <div style='display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem;'>
                <div>
                    <div style='font-size:1.6rem;font-weight:800;color:white;letter-spacing:-0.03em;'>
                        🗺️ {trip['name']}
                    </div>
                    <div style='font-size:0.85rem;color:rgba(255,255,255,0.8);margin-top:4px;'>
                        📍 {trip.get('destination','—')} &nbsp;·&nbsp; {date_range}
                        &nbsp;·&nbsp; {dur} day{'s' if dur != 1 else ''}
                    </div>
                    {('<div style="margin-top:6px;font-size:0.8rem;color:rgba(255,255,255,0.7);">' +
                      trip.get("description","") + '</div>') if trip.get("description") else ""}
                </div>
                <div style='text-align:right;'>
                    <div style='font-size:2rem;font-weight:800;color:white;letter-spacing:-0.03em;'>
                        {_fmt(spent, cur)}
                    </div>
                    {'<div style="font-size:0.8rem;color:rgba(255,255,255,0.7);">of ' +
                     _fmt(budget, cur) + ' budget</div>' if budget else
                     '<div style="font-size:0.8rem;color:rgba(255,255,255,0.7);">total spent</div>'}
                    <div style='margin-top:4px;'>
                        <span style='background:rgba(255,255,255,0.2);color:white;border-radius:6px;
                                     padding:2px 10px;font-size:0.72rem;font-weight:700;'>
                            {status}
                        </span>
                    </div>
                </div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── KPI row ────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💰 Total Spent",   _fmt(spent, cur))
    k2.metric("📋 Expenses",       len(expenses))
    k3.metric("📅 Trip Length",    f"{dur} days")
    if budget:
        remaining = budget - spent
        k4.metric(
            "🎯 Budget Left",
            _fmt(max(remaining, 0), cur),
            delta=f"{(remaining/budget*100):+.0f}%" if budget else None,
            delta_color="normal",
        )
    else:
        daily_avg = spent / dur if dur and isinstance(dur, int) and dur > 0 else 0
        k4.metric("📊 Daily Average", _fmt(daily_avg, cur))

    st.markdown("---")

    # ── Main tabs ──────────────────────────────────────────────
    tab_days, tab_all, tab_charts, tab_add = st.tabs([
        "📅 Day by Day",
        "📋 All Expenses",
        "📊 Charts",
        "➕ Add Expense",
    ])

    with tab_days:
        _render_day_view(trip, expenses, cur, t)

    with tab_all:
        _render_all_expenses(expenses, cur, t)

    with tab_charts:
        _render_charts(trip_id, expenses, cur, t)

    with tab_add:
        _render_add_expense_form(trip, t)

    # ── Status quick-change ────────────────────────────────────
    st.markdown("---")
    with st.expander("⚙️ Trip Settings", expanded=False):
        new_status = st.selectbox(
            "Status",
            TRIP_STATUSES,
            index=TRIP_STATUSES.index(status),
            key=f"status_{trip_id}",
        )
        if st.button("Update Status"):
            update_trip_status(trip_id, new_status)
            st.success("Status updated.")
            st.rerun()

        st.markdown("---")
        st.markdown("**⚠️ Danger Zone**")
        if st.button("🗑️ Delete this trip"):
            st.session_state[f"confirm_del_detail_{trip_id}"] = True
            st.rerun()
        if st.session_state.get(f"confirm_del_detail_{trip_id}"):
            st.warning("This will permanently delete the trip and all its expenses.")
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("✅ Confirm Delete", key="confirm_del_detail_yes"):
                    delete_trip(trip_id)
                    st.session_state.pop("active_trip_id", None)
                    st.success("Trip deleted.")
                    st.rerun()
            with cc2:
                if st.button("❌ Cancel", key="confirm_del_detail_no"):
                    st.session_state.pop(f"confirm_del_detail_{trip_id}", None)
                    st.rerun()


# ═══════════════════════════════════════════════════════════════
#  DAY-BY-DAY LEDGER
# ═══════════════════════════════════════════════════════════════

def _render_day_view(trip: dict, expenses: list[dict], cur: str, t: dict) -> None:
    start = _parse_date(trip.get("start_date"))
    end   = _parse_date(trip.get("end_date"))

    if not start or not end:
        st.info("Set trip dates to see the day-by-day view.")
        return

    # Collect stay expenses separately (they span multiple days)
    stays   = [e for e in expenses if e.get("is_stay")]
    day_exp = [e for e in expenses if not e.get("is_stay")]

    # Build list of all trip days
    total_days = (end - start).days + 1
    days = [start + timedelta(days=i) for i in range(total_days)]

    # Show a stay summary banner at the top if any
    if stays:
        st.markdown("##### 🏨 Accommodation")
        for stay in stays:
            ci = _parse_date(stay.get("check_in"))
            co = _parse_date(stay.get("check_out"))
            nights = (co - ci).days if ci and co else "?"
            ci_str = ci.strftime("%d %b") if ci else "?"
            co_str = co.strftime("%d %b") if co else "?"
            st.markdown(
                f"""<div style='background:{t["card_bg"]};border:1.5px solid {t["border"]};
                     border-left:4px solid #7c3aed;border-radius:10px;
                     padding:0.75rem 1rem;margin-bottom:0.5rem;
                     display:flex;align-items:center;justify-content:space-between;'>
                    <div>
                        <span style='font-weight:700;color:{t["text_primary"]};'>
                            🏨 {stay['item']}
                        </span>
                        <span style='font-size:0.8rem;color:{t["text_muted"]};margin-left:8px;'>
                            {ci_str} → {co_str} · {nights} night{'s' if nights != 1 else ''}
                        </span>
                    </div>
                    <div style='font-weight:700;color:{t["text_primary"]};'>
                        {_fmt(stay["amount"], cur)}
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button("🗑️", key=f"del_stay_{stay['id']}", help="Delete stay"):
                delete_expense(stay["id"])
                st.rerun()
        st.markdown("---")

    # Day cards
    for day in days:
        day_str = day.isoformat()
        day_expenses = [e for e in day_exp if e.get("date") == day_str]
        day_total = sum(e["amount"] for e in day_expenses)
        day_label = day.strftime("%A, %d %B")
        day_num   = (day - start).days + 1

        is_today = day == date.today()
        border_color = t["accent"] if is_today else t["border"]
        label_extra  = " 📍 Today" if is_today else ""

        with st.expander(
            f"Day {day_num} — {day_label}{label_extra}  ·  {_fmt(day_total, cur) if day_expenses else 'No expenses'}",
            expanded=(is_today or day_num == 1),
        ):
            if not day_expenses:
                st.caption("No expenses recorded for this day.")
            else:
                for exp in day_expenses:
                    _expense_row(exp, cur, t)

            # Quick add for this day
            with st.form(key=f"quick_add_{day_str}", clear_on_submit=True):
                st.markdown(f"<small>Quick-add for {day.strftime('%d %b')}</small>", unsafe_allow_html=True)
                qc1, qc2, qc3, qc4 = st.columns([2, 1, 1, 1])
                with qc1:
                    q_item = st.text_input("Item", placeholder="e.g. Pad Thai", label_visibility="collapsed", key=f"qi_{day_str}")
                with qc2:
                    q_cat = st.selectbox("Category", TRIP_CATEGORIES, index=0, label_visibility="collapsed", key=f"qc_{day_str}")
                with qc3:
                    q_amt = st.number_input("Amount", min_value=0.0, step=1.0, label_visibility="collapsed", key=f"qa_{day_str}")
                with qc4:
                    q_submit = st.form_submit_button("＋ Add")

                if q_submit and q_item and q_amt > 0:
                    trip_id = st.session_state.get("active_trip_id", "")
                    save_expense(
                        trip_id=trip_id,
                        item=q_item,
                        category=q_cat,
                        amount=q_amt,
                        currency=cur,
                        expense_date=day,
                    )
                    st.rerun()


def _expense_row(exp: dict, cur: str, t: dict) -> None:
    """Single expense row with delete button."""
    cat_icon = _CAT_ICON.get(exp.get("category", ""), "💡")
    notes    = f" — {exp['notes']}" if exp.get("notes") else ""

    col_a, col_b = st.columns([4, 1])
    with col_a:
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:8px;padding:4px 0;'>"
            f"<span style='font-size:1.2rem;'>{cat_icon}</span>"
            f"<div>"
            f"<span style='font-weight:600;color:{t['text_primary']};'>{exp['item']}</span>"
            f"<span style='font-size:0.78rem;color:{t['text_muted']};'>&nbsp;{exp.get('category','')}{notes}</span>"
            f"</div>"
            f"<div style='margin-left:auto;font-weight:700;color:{t['text_primary']};'>"
            f"{_fmt(exp['amount'], cur)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_b:
        if st.button("🗑️", key=f"del_exp_{exp['id']}", help="Delete"):
            delete_expense(exp["id"])
            st.rerun()


# ═══════════════════════════════════════════════════════════════
#  ALL EXPENSES TABLE
# ═══════════════════════════════════════════════════════════════

def _render_all_expenses(expenses: list[dict], cur: str, t: dict) -> None:
    if not expenses:
        st.info("No expenses added yet.")
        return

    rows = []
    for e in expenses:
        row: dict = {
            "Category": e.get("category", "—"),
            "Item": e.get("item", "—"),
            f"Amount ({cur})": e.get("amount", 0),
            "Notes": e.get("notes", ""),
        }
        if e.get("is_stay"):
            ci = _parse_date(e.get("check_in"))
            co = _parse_date(e.get("check_out"))
            row["Date"] = f"{ci.strftime('%d %b') if ci else '?'} → {co.strftime('%d %b') if co else '?'}"
        else:
            d = _parse_date(e.get("date"))
            row["Date"] = d.strftime("%d %b %Y") if d else "—"
        rows.append(row)

    df = pd.DataFrame(rows, columns=["Date", "Category", "Item", f"Amount ({cur})", "Notes"])
    st.dataframe(df, hide_index=True, use_container_width=True)

    total = sum(e["amount"] for e in expenses)
    st.markdown(
        f"<div style='text-align:right;font-weight:700;font-size:1rem;"
        f"color:{t['text_primary']};margin-top:0.5rem;'>"
        f"Total: {_fmt(total, cur)}</div>",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════
#  CHARTS
# ═══════════════════════════════════════════════════════════════

def _render_charts(trip_id: str, expenses: list[dict], cur: str, t: dict) -> None:
    if not expenses:
        st.info("Add some expenses to see charts.")
        return

    col1, col2 = st.columns(2)

    # ── Category donut ─────────────────────────────────────────
    with col1:
        cat_totals = trip_by_category(trip_id)
        if cat_totals:
            palette = [
                "#5a67d8","#38b2ac","#f6ad55","#68d391",
                "#fc8181","#76e4f7","#b794f4","#f687b3","#a0aec0",
            ]
            labels = list(cat_totals.keys())
            values = list(cat_totals.values())
            total  = sum(values)

            fig = go.Figure(
                go.Pie(
                    labels=labels, values=values, hole=0.62,
                    marker=dict(colors=palette[:len(labels)],
                                line=dict(color=t["app_bg"], width=3)),
                    hovertemplate="<b>%{label}</b><br>%{value:,.0f} "
                                  + cur + " — %{percent}<extra></extra>",
                    textfont=dict(color=t["text_secondary"]),
                )
            )
            fig.add_annotation(
                text=f"<b>{_fmt(total, cur)}</b>",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color=t["text_primary"], family="Plus Jakarta Sans"),
            )
            fig.update_layout(
                title="Spending by Category",
                paper_bgcolor=t["chart_paper"], plot_bgcolor=t["chart_paper"],
                font=dict(color=t["text_secondary"], family="Plus Jakarta Sans"),
                legend=dict(bgcolor="rgba(0,0,0,0)"),
                margin=dict(t=48, b=8, l=0, r=0), height=340,
                title_font=dict(color=t["text_secondary"], size=13),
            )
            st.plotly_chart(fig, config={"displayModeBar": False}, use_container_width=True)

    # ── Daily spending bar ─────────────────────────────────────
    with col2:
        day_totals = trip_by_day(trip_id)
        if day_totals:
            sorted_days = sorted(day_totals.items())
            x_labels = [_parse_date(d).strftime("%d %b") if _parse_date(d) else d
                        for d, _ in sorted_days]
            y_vals   = [v for _, v in sorted_days]
            avg      = sum(y_vals) / len(y_vals) if y_vals else 0
            colors   = [
                t["danger"] if v > avg * 1.3 else
                (t["warning"] if v > avg else t["accent"])
                for v in y_vals
            ]

            fig2 = go.Figure(go.Bar(
                x=x_labels, y=y_vals,
                marker_color=colors, opacity=0.85,
                hovertemplate="<b>%{x}</b><br>%{y:,.0f} " + cur + "<extra></extra>",
            ))
            fig2.add_hline(
                y=avg, line_dash="dot", line_color=t["text_muted"], line_width=1.5,
                annotation_text=f"Avg {avg:,.0f}", annotation_font_color=t["text_muted"],
            )
            fig2.update_layout(title="Daily Spending")
            st.plotly_chart(style_fig(fig2, t, height=340),
                            config={"displayModeBar": False}, use_container_width=True)

    # ── Category breakdown table ───────────────────────────────
    st.markdown("##### 📋 Category Breakdown")
    cat_rows = [
        {"Category": cat, f"Amount ({cur})": amt,
         "% of Total": f"{amt / sum(cat_totals.values()) * 100:.1f}%"}
        for cat, amt in sorted(trip_by_category(trip_id).items(),
                                key=lambda x: x[1], reverse=True)
    ]
    if cat_rows:
        st.dataframe(pd.DataFrame(cat_rows), hide_index=True, use_container_width=True)


# ═══════════════════════════════════════════════════════════════
#  ADD EXPENSE FORM (full)
# ═══════════════════════════════════════════════════════════════

def _render_add_expense_form(trip: dict, t: dict) -> None:
    trip_id = trip["id"]
    cur     = trip.get("currency", "SEK")
    start   = _parse_date(trip.get("start_date"))
    end     = _parse_date(trip.get("end_date"))

    st.markdown("#### ➕ Add Expense")

    is_stay = st.toggle("🏨 This is a Stay / Accommodation booking", key="add_is_stay")

    with st.form("add_expense_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            item = st.text_input("Item / Description *", placeholder="e.g. Hotel Riverside, Taxi, Lunch")
            category = st.selectbox(
                "Category *",
                TRIP_CATEGORIES,
                index=TRIP_CATEGORIES.index("🏨 Stay") if is_stay else 0,
            )
        with c2:
            amount = st.number_input(f"Amount ({cur}) *", min_value=0.0, step=1.0)
            notes  = st.text_input("Notes", placeholder="Optional")

        if is_stay:
            sc1, sc2 = st.columns(2)
            with sc1:
                check_in = st.date_input(
                    "Check-in Date *",
                    value=start or date.today(),
                    min_value=start,
                    max_value=end,
                    key="add_check_in",
                )
            with sc2:
                check_out = st.date_input(
                    "Check-out Date *",
                    value=(end or date.today() + timedelta(days=1)),
                    min_value=start,
                    max_value=end,
                    key="add_check_out",
                )
            expense_date = None
        else:
            expense_date = st.date_input(
                "Date *",
                value=date.today() if not start else max(start, min(date.today(), end or date.today())),
                min_value=start,
                max_value=end or date(2100, 12, 31),
                key="add_exp_date",
            )
            check_in = check_out = None

        submitted = st.form_submit_button("💾 Add Expense")

        if submitted:
            if not item:
                st.error("Item / Description is required.")
            elif amount <= 0:
                st.error("Amount must be greater than 0.")
            elif is_stay and (not check_in or not check_out or check_in >= check_out):
                st.error("Check-out must be after check-in.")
            else:
                save_expense(
                    trip_id=trip_id,
                    item=item,
                    category=category,
                    amount=amount,
                    currency=cur,
                    expense_date=expense_date,
                    is_stay=is_stay,
                    check_in=check_in if is_stay else None,
                    check_out=check_out if is_stay else None,
                    notes=notes,
                )
                st.success("✅ Expense added!")
                st.rerun()


# ═══════════════════════════════════════════════════════════════
#  PUBLIC ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def render(df, save_data, sheet, t: dict) -> None:
    """
    Render the Trips page.

    Parameters
    ----------
    df        : Main expense DataFrame (unused here, kept for ctx compat)
    save_data : Main save callable (unused here)
    sheet     : Storage handle (unused here)
    t         : Active theme dict — passed explicitly
    """
    hero("Trip Expense Tracker", "Track every spending on every trip", "✈️")

    # Init session state
    if "trip_form_open" not in st.session_state:
        st.session_state["trip_form_open"] = False
    if "trip_form_edit_id" not in st.session_state:
        st.session_state["trip_form_edit_id"] = None

    active_trip_id = st.session_state.get("active_trip_id")

    if active_trip_id:
        _render_trip_detail(active_trip_id, t)
    else:
        _render_trip_list(t)