# views/page_bills_ledger.py
# ──────────────────────────────────────────────────────────────
#  Bills Ledger page
#
#  A single, simple list of every bill showing only SHOP, DATE and
#  AMOUNT. It consolidates three sources into one view:
#     • itemised expenses  (one row per shop+date bill total)
#     • pending bills      (captured by total, not yet itemised)
#     • manual entries     (typed here for receipts that never made
#                           it into the app — the "missing bills"
#                           corner case)
#
#  Duplicates across sources are removed automatically. This page is
#  read-only for the first two sources; only manual entries can be
#  added or deleted here (they live in data/bills_ledger.json).
# ──────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd

from config import (
    SUPPORTED_CURRENCIES, DEFAULT_CURRENCY, format_currency, SessionKeys,
)
from page_helpers import hero
from utils import load_dropdown_options, save_dropdown_options
from validators import ExpenseValidator, ValidationError

import bills_ledger as bl
import drive_storage as ds


# ═════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════
def _has_receipt(receipt) -> bool:
    """True if a receipt is attached in any storage (drive or local)."""
    if not isinstance(receipt, dict):
        return False
    return bool(
        receipt.get("web_link")
        or receipt.get("file_id")
        or receipt.get("local_path")
    )


def _receipt_marker(receipt) -> str:
    """Short indicator shown in the ledger table's Receipt column."""
    return "📎" if _has_receipt(receipt) else ""


def _render_receipt(receipt: dict, key: str) -> None:
    """Show a receipt inline: thumbnail for images, download for anything
    else, plus a Drive link when available. Works for local + Drive."""
    if not _has_receipt(receipt):
        return
    web = receipt.get("web_link")
    filename = receipt.get("filename") or "receipt"

    if ds.is_image_receipt(receipt):
        img = ds.get_receipt_bytes(receipt)
        if img:
            st.image(img, width=160, caption=filename)
    else:
        data = ds.get_receipt_bytes(receipt)
        if data:
            st.download_button(
                "📎 Download receipt", data=data, file_name=filename,
                key=f"rcpt_dl_{key}", width="stretch",
            )

    if web:
        st.markdown(f"[📎 Open in Drive]({web})")


def _converted_total(view: pd.DataFrame, base: str) -> tuple[float, bool]:
    """
    Sum every bill converted into ``base`` currency. Groups by currency so
    at most one exchange-rate lookup happens per currency. Returns
    ``(total, all_ok)`` where ``all_ok`` is False if any rate was missing.
    """
    from currency_manager import convert_amount

    total = 0.0
    all_ok = True
    for ccy, grp in view.groupby(bl.LEDGER_CURRENCY):
        subtotal = float(grp[bl.LEDGER_AMOUNT].sum())
        if not ccy or ccy == base:
            total += subtotal
            continue
        converted, err = convert_amount(subtotal, ccy, base)
        if err or converted is None:
            all_ok = False
        else:
            total += converted
    return round(total, 2), all_ok


def _jump_to_itemise(bill_id: str) -> None:
    """Send the user into the Pending Bills itemise flow for one bill."""
    st.session_state[SessionKeys.ITEMISING_BILL_ID] = bill_id
    st.session_state[SessionKeys.PENDING_ITEMS] = []
    st.session_state["page"] = "pending_bills"
    st.rerun()


def _base_amount_series(view: pd.DataFrame, base: str) -> tuple[pd.Series, bool]:
    """
    Convert every bill's amount into ``base`` currency. Looks up each
    currency's rate once. Returns ``(series, all_ok)`` where unconvertible
    rows are NaN and ``all_ok`` is False if any rate was missing.
    """
    from currency_manager import get_exchange_rate

    rate_cache: dict[str, float | None] = {}

    def _rate(ccy: str) -> float | None:
        if not ccy or ccy == base:
            return 1.0
        if ccy not in rate_cache:
            r, _err = get_exchange_rate(ccy, base)
            rate_cache[ccy] = r  # r is not None even when a fallback rate is used
        return rate_cache[ccy]

    all_ok = True
    values = []
    for _, row in view.iterrows():
        rate = _rate(row[bl.LEDGER_CURRENCY])
        if rate is None:
            all_ok = False
            values.append(float("nan"))
        else:
            values.append(round(float(row[bl.LEDGER_AMOUNT]) * rate, 2))
    return pd.Series(values, index=view.index), all_ok


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════
def render(df: pd.DataFrame, save_data, sheet, t: dict | None = None, **_) -> None:
    hero(
        "Bills Ledger",
        "Every bill at a glance — just shop, date and amount",
        "📒",
    )

    if "dropdowns" not in st.session_state:
        st.session_state["dropdowns"] = load_dropdown_options()
    dropdowns: dict = st.session_state["dropdowns"]

    ledger = bl.build_ledger(df)

    tab_view, tab_stats, tab_add = st.tabs(
        ["📒 Ledger", "📊 Stats", "➕ Add Missing Bill"]
    )
    with tab_view:
        _ledger_view(ledger)
    with tab_stats:
        _stats_view(ledger, t)
    with tab_add:
        _add_manual_form(df, dropdowns)


# ═══════════════════════════════════════════════════════════════
# LEDGER VIEW
# ═══════════════════════════════════════════════════════════════
def _ledger_view(ledger: pd.DataFrame) -> None:
    if ledger.empty:
        st.info(
            "No bills yet. Itemised expenses and pending bills appear here "
            "automatically, or add a missing bill from the next tab."
        )
        return

    # Parse dates once for range filtering / sorting.
    ledger = ledger.copy()
    ledger["_dt"] = pd.to_datetime(ledger[bl.LEDGER_DATE], errors="coerce")

    # ── Filters ───────────────────────────────────────────────────────────
    f1, f2, f3 = st.columns([2, 2, 2])
    with f1:
        sources = sorted(ledger[bl.LEDGER_SOURCE].dropna().unique().tolist())
        picked = st.multiselect("Source", options=sources, default=sources)
    with f2:
        search = st.text_input("Search shop", placeholder="Optional")
    with f3:
        valid_dt = ledger["_dt"].dropna()
        if not valid_dt.empty:
            dmin, dmax = valid_dt.min().date(), valid_dt.max().date()
            date_range = st.date_input(
                "Date range", value=(dmin, dmax),
                min_value=dmin, max_value=dmax,
            )
        else:
            date_range = None

    s1, s2 = st.columns([2, 1])
    with s1:
        sort_by = st.selectbox(
            "Sort by",
            [bl.LEDGER_DATE, bl.LEDGER_AMOUNT, bl.LEDGER_SHOP, bl.LEDGER_SOURCE],
            index=0,
        )
    with s2:
        order = st.radio(
            "Order", ["Descending", "Ascending"], horizontal=True,
            label_visibility="visible",
        )

    view = ledger.copy()
    if picked:
        view = view[view[bl.LEDGER_SOURCE].isin(picked)]
    if search.strip():
        view = view[view[bl.LEDGER_SHOP].str.contains(search.strip(), case=False, na=False)]
    if date_range and isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start, end = date_range
        view = view[
            (view["_dt"].isna())
            | ((view["_dt"].dt.date >= start) & (view["_dt"].dt.date <= end))
        ]

    if view.empty:
        st.info("No bills match the current filters.")
        return

    # Sort (Date sorts by parsed datetime; others by their column).
    ascending = order == "Ascending"
    sort_col = "_dt" if sort_by == bl.LEDGER_DATE else sort_by
    view = view.sort_values(sort_col, ascending=ascending, na_position="last")

    # ── Summary metrics ───────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Bills", f"{len(view):,}")
    top_ccy = view[bl.LEDGER_CURRENCY].mode()
    top_ccy = top_ccy.iloc[0] if not top_ccy.empty else DEFAULT_CURRENCY
    ccy_total = view.loc[view[bl.LEDGER_CURRENCY] == top_ccy, bl.LEDGER_AMOUNT].sum()
    m2.metric(f"Total ({top_ccy})", format_currency(ccy_total, top_ccy))
    with st.spinner("Converting…"):
        conv_total, all_ok = _converted_total(view, DEFAULT_CURRENCY)
    m3.metric(
        f"Total ({DEFAULT_CURRENCY})",
        format_currency(conv_total, DEFAULT_CURRENCY),
        help=None if all_ok else "Some currencies used approximate/fallback rates.",
    )
    m4.metric("Shops", f"{view[bl.LEDGER_SHOP].nunique():,}")
    if not all_ok:
        st.caption("⚠️ Some currencies could not be converted with a live rate.")

    # ── Simple table (shop / date / amount + context + receipt) ───────────
    display = view[[
        bl.LEDGER_DATE, bl.LEDGER_SHOP, bl.LEDGER_AMOUNT,
        bl.LEDGER_CURRENCY, bl.LEDGER_SOURCE,
    ]].copy()
    display["Receipt"] = view["receipt"].map(_receipt_marker)
    display = display.reset_index(drop=True)

    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            bl.LEDGER_DATE: st.column_config.TextColumn("Date"),
            bl.LEDGER_SHOP: st.column_config.TextColumn("Shop"),
            bl.LEDGER_AMOUNT: st.column_config.NumberColumn("Amount", format="%.2f"),
            bl.LEDGER_CURRENCY: st.column_config.TextColumn("Currency"),
            bl.LEDGER_SOURCE: st.column_config.TextColumn("Source"),
            "Receipt": st.column_config.TextColumn("Receipt", help="📎 = receipt attached"),
        },
    )

    st.download_button(
        "⬇️ Download CSV",
        data=display.to_csv(index=False).encode("utf-8"),
        file_name="bills_ledger.csv",
        mime="text/csv",
    )

    # ── Pending bills: view receipt + one-click itemise ───────────────────
    pending = view[view[bl.LEDGER_SOURCE] == bl.SOURCE_PENDING]
    if not pending.empty:
        with st.expander(f"🧾 Pending bills — receipts & itemise ({len(pending)})"):
            st.caption("View the attached receipt or break a captured total into items.")
            for _, row in pending.iterrows():
                bid = row.get("bill_id")
                cols = st.columns([4, 1])
                with cols[0]:
                    st.markdown(
                        f"**{row[bl.LEDGER_SHOP] or '?'}** · {row[bl.LEDGER_DATE]} · "
                        f"{format_currency(row[bl.LEDGER_AMOUNT], row[bl.LEDGER_CURRENCY])}"
                    )
                    _render_receipt(row.get("receipt") or {}, key=str(bid))
                with cols[1]:
                    if bid and st.button("Itemise", key=f"item_ledger_{bid}", width="stretch"):
                        _jump_to_itemise(bid)

    # ── Manual entries: promote or delete (only these are editable here) ──
    manual = view[view[bl.LEDGER_SOURCE] == bl.SOURCE_MANUAL]
    if not manual.empty:
        with st.expander(f"🗂️ Manage manual entries ({len(manual)})"):
            for _, row in manual.iterrows():
                lid = row.get("ledger_id")
                cols = st.columns([4, 1, 1])
                with cols[0]:
                    st.markdown(
                        f"**{row[bl.LEDGER_SHOP] or '?'}** · {row[bl.LEDGER_DATE]} · "
                        f"{format_currency(row[bl.LEDGER_AMOUNT], row[bl.LEDGER_CURRENCY])}"
                    )
                    if row.get("note"):
                        st.caption(row["note"])
                with cols[1]:
                    if lid and st.button("Itemise", key=f"promote_{lid}", width="stretch",
                                         help="Convert to a pending bill and itemise it"):
                        new_bid = bl.promote_manual_to_pending(lid)
                        if new_bid:
                            _jump_to_itemise(new_bid)
                        else:
                            st.error("Could not promote (Pending Bills unavailable).")
                with cols[2]:
                    if lid and st.button("Delete", key=f"del_ledger_{lid}", width="stretch"):
                        bl.delete_manual_bill(lid)
                        st.toast("Deleted manual bill.", icon="🗑️")
                        st.rerun()


# ═══════════════════════════════════════════════════════════════
# STATS  (month-wise / year-wise reconciliation)
# ═══════════════════════════════════════════════════════════════
def _stats_view(ledger: pd.DataFrame, t: dict | None) -> None:
    if ledger.empty:
        st.info("No bills yet — totals will appear once you have some.")
        return

    st.caption(
        "Month-wise and year-wise totals to cross-check against your bank / "
        "card statement. Pick a period below to see every bill that makes it up."
    )

    # Convert to the base currency so totals line up with a card statement.
    work = ledger.copy()
    work["_dt"] = pd.to_datetime(work[bl.LEDGER_DATE], errors="coerce")
    with st.spinner("Converting currencies…"):
        base_amt, all_ok = _base_amount_series(work, DEFAULT_CURRENCY)
    work["_base"] = base_amt
    work = work.dropna(subset=["_dt", "_base"])

    if work.empty:
        st.info("No dated bills available to summarise.")
        return

    work["_year"] = work["_dt"].dt.year
    work["_ym"] = work["_dt"].dt.strftime("%Y-%m")

    if not all_ok:
        st.caption(
            f"⚠️ Some currencies used approximate rates when converting to {DEFAULT_CURRENCY}."
        )

    # ── Granularity ───────────────────────────────────────────────────────
    gran = st.radio("Group by", ["Monthly", "Yearly"], horizontal=True)
    if gran == "Monthly":
        period_col, label = "_ym", "Month"
    else:
        period_col, label = "_year", "Year"

    totals = (
        work.groupby(period_col)
        .agg(Bills=("_base", "size"), Total=("_base", "sum"))
        .reset_index()
        .rename(columns={period_col: label})
        .sort_values(label, ascending=False)
    )
    totals["Total"] = totals["Total"].round(2)

    g1, g2 = st.columns(2)
    g1.metric(f"{label}s tracked", f"{len(totals):,}")
    g2.metric(f"Grand total ({DEFAULT_CURRENCY})",
              format_currency(work["_base"].sum(), DEFAULT_CURRENCY))

    st.dataframe(
        totals,
        hide_index=True,
        width="stretch",
        column_config={
            label: st.column_config.TextColumn(label),
            "Bills": st.column_config.NumberColumn("Bills", format="%d"),
            "Total": st.column_config.NumberColumn(
                f"Total ({DEFAULT_CURRENCY})", format="%.2f"),
        },
    )
    st.download_button(
        f"⬇️ Download {label.lower()} totals (CSV)",
        data=totals.to_csv(index=False).encode("utf-8"),
        file_name=f"bills_{label.lower()}_totals.csv",
        mime="text/csv",
    )

    # ── Drill-down: reconcile one period against the statement ────────────
    st.markdown(f"#### 🔎 Reconcile a {label.lower()}")
    options = totals[label].astype(str).tolist()
    if not options:
        return
    pick = st.selectbox(label, options=options)

    detail = work[work[period_col].astype(str) == pick].sort_values("_dt")
    disp = pd.DataFrame({
        bl.LEDGER_DATE: detail[bl.LEDGER_DATE].values,
        bl.LEDGER_SHOP: detail[bl.LEDGER_SHOP].values,
        "Amount": detail[bl.LEDGER_AMOUNT].round(2).values,
        bl.LEDGER_CURRENCY: detail[bl.LEDGER_CURRENCY].values,
        f"Amount ({DEFAULT_CURRENCY})": detail["_base"].round(2).values,
        bl.LEDGER_SOURCE: detail[bl.LEDGER_SOURCE].values,
    })

    d1, d2 = st.columns(2)
    d1.metric("Bills in period", f"{len(disp):,}")
    d2.metric(f"Period total ({DEFAULT_CURRENCY})",
              format_currency(detail["_base"].sum(), DEFAULT_CURRENCY))

    st.dataframe(
        disp,
        hide_index=True,
        width="stretch",
        column_config={
            bl.LEDGER_DATE: st.column_config.TextColumn("Date"),
            bl.LEDGER_SHOP: st.column_config.TextColumn("Shop"),
            "Amount": st.column_config.NumberColumn("Amount", format="%.2f"),
            bl.LEDGER_CURRENCY: st.column_config.TextColumn("Currency"),
            f"Amount ({DEFAULT_CURRENCY})": st.column_config.NumberColumn(
                f"Amount ({DEFAULT_CURRENCY})", format="%.2f"),
            bl.LEDGER_SOURCE: st.column_config.TextColumn("Source"),
        },
    )
    st.download_button(
        f"⬇️ Download {pick} bills (CSV)",
        data=disp.to_csv(index=False).encode("utf-8"),
        file_name=f"bills_{pick}.csv",
        mime="text/csv",
        key=f"dl_detail_{pick}",
    )


# ═══════════════════════════════════════════════════════════════
# ADD MISSING BILL (manual entry)
# ═══════════════════════════════════════════════════════════════
def _add_manual_form(df: pd.DataFrame, dropdowns: dict) -> None:
    shops: list = dropdowns.get("shops", [])

    st.markdown("#### ➕ Add a Missing Bill")
    st.caption(
        "For receipts that were never itemised or captured as pending bills. "
        "Only shop, date and amount are needed. Duplicates are blocked."
    )

    with st.form("add_ledger_bill", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            bill_date = st.date_input("Date *")
            shop = st.selectbox("Shop", options=[""] + shops, index=0)
            new_shop = st.text_input("…or add a new shop", placeholder="Optional")
        with c2:
            currency = st.selectbox(
                "Currency", SUPPORTED_CURRENCIES,
                index=SUPPORTED_CURRENCIES.index(DEFAULT_CURRENCY)
                if DEFAULT_CURRENCY in SUPPORTED_CURRENCIES else 0,
            )
            amount_str = st.text_input("Bill Amount *", placeholder="e.g., 742.50")
            note = st.text_input("Note", placeholder="Optional")

        submitted = st.form_submit_button("💾 Add to Ledger", type="primary")

    if not submitted:
        return

    final_shop = (new_shop or "").strip() or (shop or "").strip()

    errors: list[str] = []
    try:
        amount = ExpenseValidator.validate_numeric_input(
            amount_str, "Bill Amount",
            min_value=ExpenseValidator.MIN_PRICE,
            max_value=ExpenseValidator.MAX_PRICE,
        )
    except ValidationError as e:
        errors.append(str(e))
        amount = 0.0

    if not final_shop:
        errors.append("❌ Please choose or add a shop.")

    if errors:
        for e in errors:
            st.error(e)
        return

    # ── Block duplicates against expenses / pending / existing manual ─────
    dup_source = bl.manual_duplicate_exists(bill_date, final_shop, amount, df=df)
    if dup_source:
        st.warning(
            f"⚠️ A matching bill already exists (source: **{dup_source}**) for "
            f"**{final_shop}** on {bill_date} at "
            f"{format_currency(amount, currency)}. Not adding a duplicate."
        )
        return

    # ── Persist a newly typed shop into the dropdown taxonomy ─────────────
    if new_shop and new_shop not in shops:
        dropdowns["shops"] = sorted(shops + [new_shop])
        save_dropdown_options(dropdowns)
        st.session_state["dropdowns"] = dropdowns

    bl.add_manual_bill(
        date=bill_date, shop=final_shop, amount=float(amount),
        currency=currency, note=note,
    )
    st.success(
        f"✅ Added to ledger: {final_shop} · {bill_date} · "
        f"{format_currency(amount, currency)}"
    )
    st.rerun()
