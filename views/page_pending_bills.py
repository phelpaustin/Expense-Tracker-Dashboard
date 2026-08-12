# views/page_pending_bills.py
# ──────────────────────────────────────────────────────────────
#  Pending Bills page
#
#  Capture a bill by TOTAL amount now (with a receipt copy) and
#  itemise it later. Pending bills live in a separate store and do
#  NOT affect the itemised expense data until itemised — at which
#  point normal expense rows are written through save_data() and
#  appear across the whole app.
# ──────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd

from config import Columns, SessionKeys, SUPPORTED_CURRENCIES
from page_helpers import hero, empty_state
from utils import load_dropdown_options, save_dropdown_options
from currency_manager import get_exchange_rate
from validators import ExpenseValidator, ValidationError

import pending_bills as pb
import drive_storage as ds


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════
def render(df: pd.DataFrame, save_data, sheet, **_) -> None:
    hero(
        "Pending Bills",
        "Add a bill by total now, attach the copy, and itemise it later",
        "🧾",
    )

    if "dropdowns" not in st.session_state:
        st.session_state["dropdowns"] = load_dropdown_options()
    dropdowns: dict = st.session_state["dropdowns"]

    # If the user is mid-itemising a bill, show that flow exclusively.
    active_id = st.session_state.get(SessionKeys.ITEMISING_BILL_ID)
    if active_id:
        _itemise_view(active_id, df, save_data, sheet, dropdowns)
        return

    tab_add, tab_list = st.tabs(["➕ Add Total Bill", "📋 Pending Bills"])
    with tab_add:
        _add_bill_form(sheet, dropdowns)
    with tab_list:
        _pending_list(dropdowns)


# ═══════════════════════════════════════════════════════════════
# ADD TOTAL BILL
# ═══════════════════════════════════════════════════════════════
def _add_bill_form(sheet, dropdowns: dict) -> None:
    shops: list = dropdowns.get("shops", [])

    st.markdown("#### 🧾 New Total Bill")
    st.caption("Only the total amount is required now — add items whenever you're ready.")

    with st.form("add_pending_bill", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            bill_date = st.date_input("Date *")
            shop = st.selectbox("Shop", options=[""] + shops, index=0)
            new_shop = st.text_input("…or add a new shop", placeholder="Optional")
        with c2:
            currency = st.selectbox("Currency", SUPPORTED_CURRENCIES)
            total_str = st.text_input("Total Bill Amount *", placeholder="e.g., 742.50")
            note = st.text_input("Note", placeholder="Optional")

        receipt_file = st.file_uploader(
            "Bill copy (image or PDF)",
            type=["png", "jpg", "jpeg", "webp", "pdf"],
            accept_multiple_files=False,
        )

        submitted = st.form_submit_button("💾 Save Pending Bill", type="primary")

    if not submitted:
        return

    # ── Resolve shop (existing selection or newly typed) ──────────────────
    final_shop = (new_shop or "").strip() or (shop or "").strip()

    # ── Validate total amount ─────────────────────────────────────────────
    errors = []
    try:
        total_amount = ExpenseValidator.validate_numeric_input(
            total_str, "Total Bill Amount",
            min_value=ExpenseValidator.MIN_PRICE,
            max_value=ExpenseValidator.MAX_PRICE,
        )
    except ValidationError as e:
        errors.append(str(e))
        total_amount = 0.0

    if not final_shop:
        errors.append("❌ Please choose or add a shop.")

    if errors:
        for e in errors:
            st.error(e)
        return

    # ── Persist a newly added shop into the dropdown taxonomy ─────────────
    if new_shop and new_shop not in shops:
        dropdowns["shops"] = sorted(shops + [new_shop])
        save_dropdown_options(dropdowns)
        st.session_state["dropdowns"] = dropdowns

    # ── Generate id first so the receipt filename can reference it ────────
    bill_id = pb._new_id()

    receipt_ref = {
        "file_id": None, "web_link": None, "local_path": None,
        "filename": None, "storage": "none",
    }
    if receipt_file is not None:
        filename = ds.build_receipt_filename(
            final_shop, bill_date, bill_id, receipt_file.name
        )
        with st.spinner("Uploading receipt…"):
            receipt_ref = ds.store_receipt(
                file_bytes=receipt_file.getvalue(),
                filename=filename,
                mime_type=receipt_file.type or "application/octet-stream",
                spreadsheet_id=ds.get_spreadsheet_id(sheet),
            )

    # ── Save the pending bill (reuse the pre-generated id) ────────────────
    bills = pb._load_raw()
    from datetime import datetime
    bills.append({
        "bill_id": bill_id,
        "date": str(bill_date),
        "shop": final_shop,
        "currency": currency,
        "total_amount": float(total_amount),
        "note": (note or "").strip(),
        "receipt": receipt_ref,
        "status": "pending",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "itemised_at": None,
    })
    pb._save_raw(bills)

    if receipt_ref.get("storage") == "drive":
        st.success(f"✅ Pending bill saved. Receipt uploaded to Drive.")
    elif receipt_ref.get("storage") == "local":
        st.success("✅ Pending bill saved. Receipt stored locally (Drive unavailable).")
    else:
        st.success("✅ Pending bill saved (no receipt attached).")
    st.rerun()


# ═══════════════════════════════════════════════════════════════
# PENDING LIST
# ═══════════════════════════════════════════════════════════════
def _receipt_link(receipt: dict, show_thumbnail: bool = False) -> None:
    if not receipt:
        return
    web = receipt.get("web_link")
    local = receipt.get("local_path")

    if show_thumbnail and ds.is_image_receipt(receipt):
        img_bytes = ds.get_receipt_bytes(receipt)
        if img_bytes:
            st.image(img_bytes, width=140, caption=receipt.get("filename") or "")

    if web:
        st.markdown(f"[📎 View receipt]({web})")
    elif local:
        st.caption(f"📎 {receipt.get('filename') or local} (local)")


def _pending_list(dropdowns: dict) -> None:
    bills = pb.load_pending_bills()
    if not bills:
        empty_state("No pending bills. Add one from the Add Total Bill tab.")
        return

    st.markdown(f"#### 📋 {len(bills)} Pending Bill(s)")
    for b in sorted(bills, key=lambda x: x.get("date", ""), reverse=True):
        bid = b["bill_id"]
        title = f"**{b.get('shop','?')}** · {b.get('date','?')} · " \
                f"{b.get('total_amount',0):,.2f} {b.get('currency','')}"
        with st.container(border=True):
            top = st.columns([4, 1, 1])
            with top[0]:
                st.markdown(title)
                if b.get("note"):
                    st.caption(b["note"])
                _receipt_link(b.get("receipt", {}), show_thumbnail=True)
            with top[1]:
                if st.button("🧮 Itemise", key=f"item_{bid}", width="stretch"):
                    st.session_state[SessionKeys.ITEMISING_BILL_ID] = bid
                    st.session_state[SessionKeys.PENDING_ITEMS] = []
                    st.rerun()
            with top[2]:
                if st.button("🗑️ Delete", key=f"del_{bid}", width="stretch"):
                    pb.delete_pending_bill(bid)
                    st.toast("Deleted pending bill.", icon="🗑️")
                    st.rerun()


# ═══════════════════════════════════════════════════════════════
# ITEMISE FLOW
# ═══════════════════════════════════════════════════════════════
def _itemise_view(bill_id: str, df, save_data, sheet, dropdowns: dict) -> None:
    bill = pb.get_bill(bill_id)
    if not bill:
        st.session_state.pop(SessionKeys.ITEMISING_BILL_ID, None)
        st.rerun()
        return

    bill_currency = bill.get("currency", "SEK")
    bill_total = float(bill.get("total_amount", 0.0))

    st.markdown(
        f"### 🧮 Itemising: **{bill.get('shop','?')}** · {bill.get('date','?')}"
    )
    st.caption(
        f"Bill total: **{bill_total:,.2f} {bill_currency}** — "
        "add the individual items below, then save."
    )
    _receipt_link(bill.get("receipt", {}), show_thumbnail=True)

    if st.button("← Back to Pending Bills"):
        for k in (SessionKeys.ITEMISING_BILL_ID, SessionKeys.PENDING_ITEMS):
            st.session_state.pop(k, None)
        st.rerun()

    categories: list = dropdowns.get("categories", [])
    subcategories_map: dict = dropdowns.get("subcategories", {})
    units: list = dropdowns.get("units", ["Count"])
    expense_types: list = dropdowns.get("expense_types", ["Goods", "Service"])

    if SessionKeys.PENDING_ITEMS not in st.session_state:
        st.session_state[SessionKeys.PENDING_ITEMS] = []

    # ── Currency → SEK conversion (parity with sidebar entry) ─────────────
    if bill_currency == "SEK":
        rate = 1.0
    else:
        rate = get_exchange_rate(bill_currency, "SEK") or 1.0
        st.caption(f"Live rate: 1 {bill_currency} = {rate:.2f} SEK")

    st.divider()
    expense_type = st.selectbox("Expense Type", options=expense_types, key="pb_etype")
    category = st.selectbox("Category", options=categories or [""], key="pb_cat")
    sub_options = subcategories_map.get(category, [])
    subcategory = st.selectbox(
        "Subcategory", options=[""] + sub_options, key="pb_sub"
    )

    with st.form("pb_add_item", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            item = st.text_input("Item *", placeholder="e.g., Milk")
            brand = st.text_input("Brand", placeholder="Optional")
        with c2:
            qty_str = st.text_input("Quantity *", placeholder="e.g., 1")
            unit = st.selectbox(
                "Unit", options=units,
                index=units.index("Count") if "Count" in units else 0,
            )
            amount_str = st.text_input(f"Amount ({bill_currency}) *", placeholder="e.g., 25.50")
        add_item = st.form_submit_button("➕ Add Item", type="primary")

    if add_item:
        _add_itemise_row(
            item, brand, qty_str, amount_str, unit, rate,
            bill, expense_type, category, subcategory,
        )

    items = st.session_state[SessionKeys.PENDING_ITEMS]
    if items:
        st.markdown("#### 🧾 Items so far")
        st.dataframe(pd.DataFrame(items), hide_index=True, width="stretch")

        items_total_sek = sum(i.get(Columns.PRICE_PAID, 0) for i in items)
        bill_total_sek = bill_total * rate
        st.markdown(f"**Items total:** {items_total_sek:,.2f} SEK")
        diff = bill_total_sek - items_total_sek
        if abs(diff) < 0.01:
            st.success("✅ Items match the bill total.")
        else:
            st.info(
                f"Difference vs bill total: {diff:,.2f} SEK "
                f"({'remaining' if diff > 0 else 'over'})."
            )

        b1, b2 = st.columns(2)
        with b1:
            if st.button("🗑️ Clear Items", width="stretch"):
                st.session_state[SessionKeys.PENDING_ITEMS] = []
                st.rerun()
        with b2:
            if st.button("💾 Save Items & Complete", type="primary", width="stretch"):
                _commit_itemised(bill_id, items, df, save_data, sheet)


def _add_itemise_row(
    item, brand, qty_str, amount_str, unit, rate,
    bill, expense_type, category, subcategory,
) -> None:
    """Validate one item and append it to the in-progress list."""
    errors = []
    item_clean = ExpenseValidator.sanitize_text(item)
    brand_clean = ExpenseValidator.sanitize_text(brand)

    try:
        quantity = ExpenseValidator.validate_numeric_input(
            qty_str, "Quantity",
            min_value=ExpenseValidator.MIN_QUANTITY,
            max_value=ExpenseValidator.MAX_QUANTITY,
        )
    except ValidationError as e:
        errors.append(str(e))
        quantity = 0.0

    try:
        amount = ExpenseValidator.validate_numeric_input(
            amount_str, "Amount",
            min_value=ExpenseValidator.MIN_PRICE,
            max_value=ExpenseValidator.MAX_PRICE,
        )
    except ValidationError as e:
        errors.append(str(e))
        amount = 0.0

    price = round(amount * rate, 2) if amount and rate else 0.0
    price_per_unit = round(price / quantity, 2) if quantity else 0.0

    is_valid, item_errors = ExpenseValidator.validate_expense_item(
        item=item_clean, price=price, quantity=quantity,
        date_value=pd.to_datetime(bill.get("date")).date(),
        expense_type=expense_type, currency=bill.get("currency"),
        category=category,
    )
    all_errors = errors + item_errors
    if all_errors:
        for e in all_errors:
            st.error(e)
        return

    st.session_state[SessionKeys.PENDING_ITEMS].append({
        Columns.DATE:          pd.to_datetime(bill.get("date")).date(),
        Columns.EXPENSE_TYPE:  expense_type,
        Columns.CATEGORY:      category or "Uncategorized",
        Columns.SUBCATEGORY:   subcategory,
        Columns.ITEM:          item_clean,
        Columns.BRAND:         brand_clean,
        Columns.SHOP:          bill.get("shop", ""),
        Columns.PRICE_PAID:    price,
        Columns.CURRENCY:      bill.get("currency", "SEK"),
        Columns.QUANTITY:      quantity,
        Columns.QUANTITY_UNIT: unit,
        Columns.PRICE_PER_UNIT: price_per_unit,
    })
    st.success(f"✅ Added: {item_clean} ({price:,.2f} SEK)")
    st.rerun()


def _commit_itemised(bill_id, items, df, save_data, sheet) -> None:
    """Write the items into the main expense table and archive the bill."""
    if not items:
        st.warning("Add at least one item before saving.")
        return

    rows_df = pd.DataFrame(items)
    is_valid, v_errors, _ = ExpenseValidator.validate_dataframe(rows_df)
    if not is_valid:
        st.error("**Cannot save — validation errors found:**")
        for err in v_errors[:5]:
            st.error(err)
        return

    updated = pd.concat([df, rows_df], ignore_index=True)
    save_data(updated, sheet)
    pb.mark_itemised(bill_id)

    for k in (SessionKeys.ITEMISING_BILL_ID, SessionKeys.PENDING_ITEMS):
        st.session_state.pop(k, None)

    st.success(
        f"✅ Added {len(items)} item(s) to your expenses. "
        "They now appear across the Dashboard and Analytics."
    )
    st.rerun()
