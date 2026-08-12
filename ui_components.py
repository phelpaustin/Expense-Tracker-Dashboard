# ui_components.py
import streamlit as st
import pandas as pd
from currency_manager import get_exchange_rate
from utils import calculate_price_per_unit, load_dropdown_options, save_dropdown_options
from config import SUPPORTED_CURRENCIES, DEFAULT_CURRENCY, Columns
from data_manager import bump_data_version
from validators import ExpenseValidator, ValidationError
from models import ExpenseItem
from pydantic import ValidationError as PydanticValidationError


# ── Helper: inline "Add new option" widget ───────────────────────────────────
def _add_new_widget(label: str, session_key: str) -> "str | None":
    """
    Compact text-input + ➕ button rendered side-by-side.
    Returns the new value (stripped) if the user clicked ➕ with non-empty text,
    otherwise returns None.  Must be called OUTSIDE any st.form block.
    """
    col_in, col_btn = st.columns([5, 1])
    with col_in:
        new_val = st.text_input(
            f"New {label}",
            key=f"_new_{session_key}",
            placeholder=f"✏️  Add new {label}…",
            label_visibility="collapsed",
        )
    with col_btn:
        add_clicked = st.button("➕", key=f"_add_{session_key}", help=f"Save new {label}")
    if add_clicked and new_val.strip():
        return new_val.strip()
    return None


# ── Duplicate detection ───────────────────────────────────────────────────────
def _check_duplicates(new_rows: list, df: pd.DataFrame) -> list:
    """
    Return human-readable descriptions of any new_rows that are exact
    duplicates of rows already in df.
    Matches on: Date, Shop, Item, PricePaid, and Quantity.
    """
    if df.empty or not new_rows:
        return []
    key_cols = [Columns.DATE, Columns.SHOP, Columns.ITEM, Columns.PRICE_PAID, Columns.QUANTITY]
    descs = []
    for row in new_rows:
        mask = pd.Series([True] * len(df), index=df.index)
        all_present = True
        for col in key_cols:
            if col not in df.columns or col not in row:
                all_present = False
                break
            mask &= df[col].astype(str) == str(row[col])
        if all_present and mask.any():
            descs.append(
                f"**{row.get(Columns.ITEM, '?')}** — "
                f"{float(row.get(Columns.PRICE_PAID, 0)):,.2f} SEK "
                f"(×{row.get(Columns.QUANTITY, '?')}) "
                f"on {row.get(Columns.DATE, '?')} @ {row.get(Columns.SHOP, '?')}"
            )
    return descs


# ── Persist + record last batch ───────────────────────────────────────────────
def _do_save(new_rows: list, df: pd.DataFrame, save_fn) -> None:
    """
    Concatenate new_rows onto df, call save_fn, clear the item list,
    and store metadata so the 'Edit Last Saved' panel can offer corrections.
    """
    n = len(new_rows)
    updated = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    save_fn(updated)
    st.toast(f"Added {n} expense entr{'y' if n == 1 else 'ies'}", icon="✅")
    # Store for quick-edit panel
    st.session_state["_last_saved_batch"] = new_rows
    st.session_state["_last_saved_count"] = n
    st.session_state["multi_items"].clear()
    bump_data_version()


# ====================================================
# ➕ ADD EXPENSE
# ====================================================
def sidebar_add_expense(df, save_fn):
    """Sidebar for adding multiple expense items under same expense context."""
    st.sidebar.markdown("### ➕ Add Expense (Multi-Item Mode)")

    # ── Seed session-state dropdowns once (survives reruns; avoids full reload) ──
    if "dropdowns" not in st.session_state:
        st.session_state["dropdowns"] = load_dropdown_options()

    dropdowns: dict = st.session_state["dropdowns"]
    categories: list        = dropdowns.get("categories", [])
    subcategories_map: dict = dropdowns.get("subcategories", {})
    shops: list             = dropdowns.get("shops", [])
    units: list             = dropdowns.get("units", ["Count"])
    expense_types: list     = dropdowns.get("expense_types", ["Goods", "Service"])

    # ── Initialise persistent session state ──────────────────────────────────
    if "multi_items" not in st.session_state:
        st.session_state["multi_items"] = []
    if "selected_category" not in st.session_state:
        st.session_state["selected_category"] = categories[0] if categories else ""
    if "selected_subcategory" not in st.session_state:
        st.session_state["selected_subcategory"] = ""
    if "temp_inputs" not in st.session_state:
        st.session_state["temp_inputs"] = {
            "item": "", "brand": "", "quantity": "", "unit": "Count", "amount": ""
        }

    with st.sidebar.expander("Add New Expense Batch", expanded=True):
        date = st.date_input("Date")

        # ── Expense Type with inline "add new" ───────────────────────────────
        st.caption("Expense Type")
        expense_type = st.selectbox(
            "Expense Type", options=expense_types,
            key="selected_expense_type", label_visibility="collapsed",
        )
        new_etype = _add_new_widget("Expense Type", "expense_type")
        if new_etype and new_etype not in expense_types:
            dropdowns["expense_types"] = sorted(expense_types + [new_etype])
            save_dropdown_options(dropdowns)
            st.toast(f"Added expense type: {new_etype}", icon="✅")
            st.rerun()

        # ── Shop with inline "add new" ────────────────────────────────────────
        st.caption("Shop")
        shop = st.selectbox(
            "Shop", options=shops, key="selected_shop", label_visibility="collapsed",
        )
        new_shop = _add_new_widget("Shop", "shop")
        if new_shop and new_shop not in shops:
            dropdowns["shops"] = sorted(shops + [new_shop])
            save_dropdown_options(dropdowns)
            st.toast(f"Added shop: {new_shop}", icon="🏪")
            st.rerun()

        # ── Currency ─────────────────────────────────────────────────────────
        currency = st.selectbox(
            "Currency",
            SUPPORTED_CURRENCIES,
            index=SUPPORTED_CURRENCIES.index(DEFAULT_CURRENCY)
            if DEFAULT_CURRENCY in SUPPORTED_CURRENCIES else 0,
        )
        if currency != DEFAULT_CURRENCY:
            # get_exchange_rate returns (rate, error) — unpack it before use.
            rate, _rate_err = get_exchange_rate(currency, DEFAULT_CURRENCY)
            st.caption(
                f"Live rate: 1 {currency} = {rate:.2f} {DEFAULT_CURRENCY}"
                if rate else "Rate unavailable — amount will be saved as-entered"
            )
            if not rate:
                rate = 1.0
        else:
            rate = 1.0

        st.divider()
        st.markdown("#### 🧾 Add Items for this Expense")

        # ── Category with inline "add new" ────────────────────────────────────
        st.caption("Category")
        category = st.selectbox(
            "Category", options=categories,
            key="selected_category", label_visibility="collapsed",
        )
        new_cat = _add_new_widget("Category", "category")
        if new_cat and new_cat not in categories:
            dropdowns["categories"] = sorted(categories + [new_cat])
            if new_cat not in dropdowns.get("subcategories", {}):
                dropdowns.setdefault("subcategories", {})[new_cat] = []
            save_dropdown_options(dropdowns)
            st.toast(f"Added category: {new_cat}", icon="📂")
            st.rerun()

        # ── Subcategory with inline "add new" ─────────────────────────────────
        subcategory_options: list = subcategories_map.get(category, [])
        st.caption("Subcategory")
        subcategory = st.selectbox(
            "Subcategory",
            options=[""] + subcategory_options,
            key="selected_subcategory",
            label_visibility="collapsed",
            disabled=False,
        )
        new_sub = _add_new_widget("Subcategory", "subcategory")
        if new_sub and new_sub not in subcategory_options:
            dropdowns.setdefault("subcategories", {}).setdefault(category, [])
            dropdowns["subcategories"][category] = sorted(
                dropdowns["subcategories"][category] + [new_sub]
            )
            save_dropdown_options(dropdowns)
            st.toast(f"Added subcategory: {new_sub} → {category}", icon="✅")
            st.rerun()

    # ---------------- ADD ITEM FORM (WITH VALIDATION) ----------------
        with st.form("add_item_form", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                item = st.text_input(
                    "Item *",
                    st.session_state["temp_inputs"]["item"],
                    placeholder="e.g., Milk, Bread, Coffee"
                )
                brand = st.text_input(
                    "Brand",
                    st.session_state["temp_inputs"]["brand"],
                    placeholder="Optional"
                )

            with col2:
                quantity_str = st.text_input(
                    "Quantity *",
                    st.session_state["temp_inputs"]["quantity"],
                    placeholder="e.g., 1, 2.5, 0.5"
                )

                unit = st.selectbox(
                    "Unit",
                    options=units,
                    index=units.index("Count") if "Count" in units else 0
                )

                amount_label = f"Amount ({currency}) *"
                amount_str = st.text_input(
                    amount_label,
                    st.session_state["temp_inputs"]["amount"],
                    placeholder="e.g., 25.50"
                )

            st.caption("* Required fields")
            submitted_item = st.form_submit_button("➕ Add Item", type="primary")

            if submitted_item:
                # ============ VALIDATION STARTS HERE ============
                validation_errors = []

                # Sanitize text inputs
                item_clean = ExpenseValidator.sanitize_text(item)
                brand_clean = ExpenseValidator.sanitize_text(brand)

                # Validate and parse quantity
                try:
                    quantity = ExpenseValidator.validate_numeric_input(
                        quantity_str,
                        "Quantity",
                        min_value=ExpenseValidator.MIN_QUANTITY,
                        max_value=ExpenseValidator.MAX_QUANTITY
                    )
                except ValidationError as e:
                    validation_errors.append(str(e))
                    quantity = 0.0

                # Validate and parse amount
                try:
                    amount = ExpenseValidator.validate_numeric_input(
                        amount_str,
                        "Amount",
                        min_value=ExpenseValidator.MIN_PRICE,
                        max_value=ExpenseValidator.MAX_PRICE
                    )
                except ValidationError as e:
                    validation_errors.append(str(e))
                    amount = 0.0

                # Calculate price in SEK
                price = round(amount * rate, 2) if amount and rate else 0.0
                price_per_unit = round(price / quantity, 2) if quantity and quantity > 0 else 0.0

                # Perform comprehensive validation
                is_valid, item_errors = ExpenseValidator.validate_expense_item(
                    item=item_clean,
                    price=price,
                    quantity=quantity,
                    date_value=date,
                    expense_type=expense_type,
                    currency=currency,
                    category=category
                )

                # Combine all errors
                all_errors = validation_errors + item_errors

                # Display errors or add item
                if all_errors:
                    st.error("**Validation Failed:**")
                    for error in all_errors:
                        st.error(error)
                    st.stop()

                # All validations passed - add item
                new_item = {
                    Columns.CATEGORY:      category or "Uncategorized",
                    Columns.SUBCATEGORY:   subcategory,
                    Columns.ITEM:          item_clean,
                    Columns.BRAND:         brand_clean,
                    Columns.QUANTITY:      quantity,
                    Columns.QUANTITY_UNIT: unit,
                    Columns.PRICE_PAID:    price,
                    # price is already converted to the base currency above, so
                    # the stored currency is the base — not the entry currency —
                    # keeping every stored amount in one currency for correct totals.
                    Columns.CURRENCY:      DEFAULT_CURRENCY,
                    Columns.PRICE_PER_UNIT: price_per_unit,
                }

                st.session_state["multi_items"].append(new_item)

                # Reset inputs
                st.session_state["temp_inputs"] = {
                    "item": "", "brand": "", "quantity": "", "unit": "Count", "amount": ""
                }

                st.toast(f"Added: {item_clean} ({price:.2f} SEK)", icon="➕")
                st.rerun()

        # ---------------- SHOW ITEMS + SAVE ----------------
        if st.session_state["multi_items"]:
            st.markdown("#### 🧮 Items Added So Far")

            # ── Edit last item ────────────────────────────────────────────────
            last_idx = len(st.session_state["multi_items"]) - 1
            with st.expander("✏️ Edit Last Item", expanded=False):
                last = st.session_state["multi_items"][last_idx]
                st.caption(f"Editing: **{last.get(Columns.ITEM, '?')}** — "
                           f"{float(last.get(Columns.PRICE_PAID, 0)):,.2f} SEK")
                with st.form("edit_last_item_form"):
                    ec1, ec2 = st.columns(2)
                    ei_name  = ec1.text_input(
                        "Item *", value=str(last.get(Columns.ITEM, "")))
                    ei_brand = ec1.text_input(
                        "Brand",  value=str(last.get(Columns.BRAND, "")))
                    ei_qty   = ec2.number_input(
                        "Quantity *",
                        value=float(last.get(Columns.QUANTITY, 1.0)),
                        min_value=0.001, step=0.1, format="%.3f",
                    )
                    ei_price = ec2.number_input(
                        "Price (SEK) *",
                        value=float(last.get(Columns.PRICE_PAID, 0.01)),
                        min_value=0.01, step=1.0,
                    )
                    _u_opts = units if units else ["Count"]
                    _u_curr = last.get(Columns.QUANTITY_UNIT, "Count")
                    ei_unit = st.selectbox(
                        "Unit", _u_opts,
                        index=_u_opts.index(_u_curr) if _u_curr in _u_opts else 0,
                    )
                    if st.form_submit_button("💾 Update Last Item", type="primary"):
                        ppu = round(ei_price / ei_qty, 2) if ei_qty > 0 else 0
                        st.session_state["multi_items"][last_idx].update({
                            Columns.ITEM:           ei_name.strip(),
                            Columns.BRAND:          ei_brand.strip(),
                            Columns.QUANTITY:       ei_qty,
                            Columns.PRICE_PAID:     ei_price,
                            Columns.PRICE_PER_UNIT: ppu,
                            Columns.QUANTITY_UNIT:  ei_unit,
                        })
                        st.toast("Item updated", icon="✏️")
                        st.rerun()

            # Items table
            st.dataframe(
                pd.DataFrame(st.session_state["multi_items"]), hide_index=True
            )

            total_price = sum(
                i.get(Columns.PRICE_PAID, 0) for i in st.session_state["multi_items"]
            )
            st.markdown(f"### 💰 Total: **{total_price:.2f} SEK**")

            # ── Duplicate confirmation UI (shown on rerun after check) ────────
            if st.session_state.get("_dup_warning_active"):
                st.warning("⚠️ **Possible Duplicate Entries Detected**")
                st.markdown(
                    "The following items look identical to existing records "
                    "for the same date and shop:"
                )
                for desc in st.session_state.get("_dup_descs", []):
                    st.markdown(f"- {desc}")
                st.markdown("Do you want to add them anyway?")
                cy, cn = st.columns(2)
                with cy:
                    if st.button(
                        "✅ Yes, add anyway", key="dup_yes", width='stretch'
                    ):
                        _do_save(
                            st.session_state["_pending_new_rows"], df, save_fn
                        )
                        for k in ("_dup_warning_active", "_dup_descs", "_pending_new_rows"):
                            st.session_state.pop(k, None)
                        st.rerun()
                with cn:
                    if st.button(
                        "❌ Cancel", key="dup_no", width='stretch'
                    ):
                        for k in ("_dup_warning_active", "_dup_descs", "_pending_new_rows"):
                            st.session_state.pop(k, None)
                        st.rerun()

            else:
                # ── Normal save / clear buttons ───────────────────────────────
                col_a, col_b = st.sidebar.columns(2)

                with col_a:
                    if st.button("🗑️ Clear Items", width="stretch"):
                        st.session_state["multi_items"].clear()
                        for k in ("_dup_warning_active", "_dup_descs", "_pending_new_rows"):
                            st.session_state.pop(k, None)
                        st.rerun()

                with col_b:
                    if st.button("💾 Add All Expenses", width="stretch"):
                        # Build candidate rows for validation + duplicate check
                        all_items_df = pd.DataFrame(st.session_state["multi_items"])
                        all_items_df[Columns.DATE]         = date
                        all_items_df[Columns.EXPENSE_TYPE] = expense_type
                        all_items_df[Columns.SHOP]         = shop

                        is_valid, v_errors, _ = ExpenseValidator.validate_dataframe(
                            all_items_df
                        )
                        if not is_valid:
                            st.error("**Cannot save — validation errors found:**")
                            for err in v_errors[:5]:
                                st.error(err)
                        else:
                            # Build full rows, then pass each through the
                            # ExpenseItem model as a persistence-time
                            # validation + normalisation step (the model's
                            # constraints are the last line of defence, and
                            # to_dict() yields the canonical row shape).
                            new_rows = []
                            model_errors = []
                            for entry in st.session_state["multi_items"]:
                                row = {
                                    Columns.DATE:         pd.to_datetime(date).date(),
                                    Columns.EXPENSE_TYPE: expense_type,
                                    Columns.SHOP:         shop,
                                    **entry,
                                }
                                try:
                                    row = ExpenseItem.from_dict(row).to_dict()
                                except PydanticValidationError as e:
                                    item_name = entry.get(Columns.ITEM, "?")
                                    model_errors.append(f"{item_name}: {e.errors()[0]['msg']}")
                                new_rows.append(row)

                            if model_errors:
                                st.error("**Cannot save — invalid item(s):**")
                                for err in model_errors[:5]:
                                    st.error(err)
                            else:
                                # ── Duplicate check ───────────────────────────
                                dups = _check_duplicates(new_rows, df)
                                if dups:
                                    st.session_state["_dup_warning_active"] = True
                                    st.session_state["_dup_descs"]          = dups
                                    st.session_state["_pending_new_rows"]   = new_rows
                                    st.rerun()
                                else:
                                    _do_save(new_rows, df, save_fn)
                                    st.rerun()

    # ── Quick-edit last saved expense ─────────────────────────────────────────
    last_batch = st.session_state.get("_last_saved_batch")
    if last_batch:
        _shop = last_batch[0].get(Columns.SHOP, "") if last_batch else ""
        _date = str(last_batch[0].get(Columns.DATE, "")) if last_batch else ""
        with st.sidebar.expander(
            f"✏️ Quick-Edit Last Save  ({_shop} · {_date})",
            expanded=True,
        ):
            st.caption(
                "Spot a mistake? Edit the rows below and re-save. "
                "This replaces only the entries you just added."
            )
            batch_df    = pd.DataFrame(last_batch)
            edited_batch = st.data_editor(
                batch_df, num_rows="fixed", hide_index=True, key="quick_edit_last",
            )
            qc1, qc2 = st.columns(2)
            with qc1:
                if st.button(
                    "💾 Re-save", key="resave_last",
                    type="primary", width='stretch'
                ):
                    n = st.session_state.get("_last_saved_count", len(last_batch))
                    # Strip the last n rows from current df, append edited rows
                    trimmed = df.iloc[:-n].copy() if n <= len(df) else df.iloc[0:0].copy()
                    merged  = pd.concat([trimmed, edited_batch], ignore_index=True)
                    save_fn(merged)
                    st.toast("Changes re-saved", icon="💾")
                    for k in ("_last_saved_batch", "_last_saved_count"):
                        st.session_state.pop(k, None)
                    bump_data_version()
                    st.rerun()
            with qc2:
                if st.button("✖ Dismiss", key="dismiss_last", width='stretch'):
                    for k in ("_last_saved_batch", "_last_saved_count"):
                        st.session_state.pop(k, None)
                    st.rerun()


# ====================================================
# 🔍 FILTERS
# ====================================================
def filter_section(df):
    """Sidebar filters for date, category, shop, price, etc."""
    import streamlit as st
    import pandas as pd

    st.sidebar.markdown("### 🔍 Filters")

    if df.empty:
        st.sidebar.info("No data available.")
        return df

    # --- Ensure Date column is datetime ---
    if Columns.DATE in df.columns:
        df[Columns.DATE] = pd.to_datetime(df[Columns.DATE], errors="coerce")

    # Safe unique lists
    categories = sorted(df[Columns.CATEGORY].dropna().unique().tolist()) if Columns.CATEGORY in df.columns else []
    shops = sorted(df[Columns.SHOP].dropna().unique().tolist()) if Columns.SHOP in df.columns else []

    selected_categories = st.sidebar.multiselect("Category", options=categories)
    selected_shops = st.sidebar.multiselect("Shop", options=shops)

    # Price slider
    if Columns.PRICE_PAID in df.columns:
        df[Columns.PRICE_PAID] = pd.to_numeric(df[Columns.PRICE_PAID], errors="coerce")
    price_max = float(df[Columns.PRICE_PAID].max()) if Columns.PRICE_PAID in df.columns and not df[Columns.PRICE_PAID].isna().all() else 1000.0
    min_price, max_price = st.sidebar.slider("Price Range (SEK)", 0.0, price_max, (0.0, price_max))

    # --- Date Range Filter ---
    start_date, end_date = None, None
    if Columns.DATE in df.columns and df[Columns.DATE].notna().any():
        min_date = df[Columns.DATE].min().date()
        max_date = df[Columns.DATE].max().date()
        start_date, end_date = st.sidebar.date_input("📅 Date Range", [min_date, max_date])

    # --- Apply filters ---
    df_filtered = df.copy()

    if selected_categories and Columns.CATEGORY in df_filtered.columns:
        df_filtered = df_filtered[df_filtered[Columns.CATEGORY].isin(selected_categories)]
    if selected_shops and Columns.SHOP in df_filtered.columns:
        df_filtered = df_filtered[df_filtered[Columns.SHOP].isin(selected_shops)]
    if start_date and end_date and Columns.DATE in df_filtered.columns:
        df_filtered = df_filtered[
            (df_filtered[Columns.DATE].dt.date >= start_date) &
            (df_filtered[Columns.DATE].dt.date <= end_date)
        ]
    if Columns.PRICE_PAID in df_filtered.columns:
        df_filtered = df_filtered[
            (df_filtered[Columns.PRICE_PAID] >= min_price) &
            (df_filtered[Columns.PRICE_PAID] <= max_price)
        ]

    return df_filtered


# ====================================================
# ✏️ INLINE EDITOR (EDIT / DELETE)
# ====================================================
def inline_edit_table(df, save_fn, sheet=None):
    import streamlit as st
    import pandas as pd

    st.subheader("✏️ Edit or Delete Entries (by Year → Month)")

    if df.empty:
        st.info("No data to edit.")
        return

    # Ensure Date is datetime
    df[Columns.DATE] = pd.to_datetime(df[Columns.DATE], errors="coerce")

    # Extract year/month
    df["Year"]      = df[Columns.DATE].dt.year
    df["Month"]     = df[Columns.DATE].dt.month
    df["MonthName"] = df[Columns.DATE].dt.strftime("%B")

    df[Columns.DATE] = df[Columns.DATE].dt.date

    # ---------------- YEAR & MONTH FILTERS ----------------
    col_year, col_month = st.columns([1, 1])

    years = sorted(df["Year"].dropna().unique().tolist(), reverse=True)
    years_display = ["All"] + [str(y) for y in years]

    with col_year:
        selected_year = st.selectbox("📅 Select Year", years_display, key="year_select")

    if selected_year != "All":
        months = (
            df[df["Year"] == int(selected_year)][["Month", "MonthName"]]
            .drop_duplicates()
            .sort_values("Month")
        )
    else:
        months = df[["Month", "MonthName"]].drop_duplicates().sort_values("Month")

    month_options = ["All"] + months["MonthName"].tolist()
    month_map = dict(zip(months["MonthName"], months["Month"]))

    with col_month:
        selected_month_name = st.selectbox("🗓️ Select Month", month_options, key="month_select")

    # ---------------- DEPENDENT FILTERS ----------------
    st.markdown("### 🔍 Filter by Expense Details")
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    base_df = df.copy()

    # Expense Type
    with col1:
        f_exp = st.multiselect(
            "Expense Type",
            sorted(base_df["ExpenseType"].dropna().unique()),
            key="filter_exp"
        )
    df1 = base_df[base_df["ExpenseType"].isin(f_exp)] if f_exp else base_df

    # Category
    with col2:
        f_cat = st.multiselect(
            "Category",
            sorted(df1["Category"].dropna().unique()),
            key="filter_cat"
        )
    df2 = df1[df1["Category"].isin(f_cat)] if f_cat else df1

    # Subcategory
    with col3:
        f_sub = st.multiselect(
            "Subcategory",
            sorted(df2["Subcategory"].dropna().unique()),
            key="filter_sub"
        )
    df3 = df2[df2["Subcategory"].isin(f_sub)] if f_sub else df2

    # Item
    with col4:
        f_item = st.multiselect(
            "Item",
            sorted(df3["Item"].dropna().unique()),
            key="filter_item"
        )
    df4 = df3[df3["Item"].isin(f_item)] if f_item else df3

    # Brand
    with col5:
        f_brand = st.multiselect(
            "Brand",
            sorted(df4["Brand"].dropna().unique()),
            key="filter_brand"
        )
    df5 = df4[df4["Brand"].isin(f_brand)] if f_brand else df4

    # Shop
    with col6:
        f_shop = st.multiselect(
            "Shop",
            sorted(df5["Shop"].dropna().unique()),
            key="filter_shop"
        )
    df6 = df5[df5["Shop"].isin(f_shop)] if f_shop else df5

    # -------------- FINAL FILTER APPLICATION --------------
    filtered_df = df6.copy()

    if selected_year != "All":
        filtered_df = filtered_df[filtered_df["Year"] == int(selected_year)]

    if selected_month_name != "All":
        filtered_df = filtered_df[filtered_df["Month"] == month_map[selected_month_name]]

    filtered_df["Date"] = filtered_df["Date"]

    st.markdown("### 🧾 Filtered Entries")

    if filtered_df.empty:
        st.info("No entries match your filters.")
        return

    # ---------------- EDITABLE TABLE ----------------
    editable_df = (
        filtered_df
        .drop(columns=["Year", "Month", "MonthName"])
        .reset_index(drop=True)
    )
    
    edited_df = st.data_editor(
        editable_df,
        num_rows="dynamic",
        width="stretch",
        key="edit_filtered",
        hide_index=True
)

    # ---------------- SAVE CHANGES ----------------
    if not edited_df.equals(filtered_df.drop(columns=["Year", "Month", "MonthName"])):
        st.warning("⚠️ Unsaved changes detected!")

        if st.button("💾 Save Changes", key="save_filtered_btn"):
            # Validate edited data before saving
            is_valid, errors, invalid_rows = ExpenseValidator.validate_dataframe(edited_df)

            if not is_valid:
                st.error("**Cannot save - validation errors found:**")
                for error in errors[:10]:
                    st.error(error)

                if not invalid_rows.empty:
                    st.markdown("**Invalid rows:**")
                    st.dataframe(invalid_rows, hide_index=True)
                st.stop()

            # Auto-recompute PricePerUnit
            # Ensure numeric columns are numeric
            if "PricePaid" in edited_df.columns:
                edited_df["PricePaid"] = pd.to_numeric(
                    edited_df["PricePaid"],
                    errors="coerce"
                )
            
            if "Quantity" in edited_df.columns:
                edited_df["Quantity"] = pd.to_numeric(
                    edited_df["Quantity"],
                    errors="coerce"
                )
            
            # Auto-recompute PricePerUnit safely
            if "PricePaid" in edited_df.columns and "Quantity" in edited_df.columns:
                edited_df["PricePerUnit"] = edited_df.apply(
                    lambda x: round(x["PricePaid"] / x["Quantity"], 2)
                    if (
                        pd.notnull(x["PricePaid"])
                        and pd.notnull(x["Quantity"])
                        and x["Quantity"] != 0
                    )
                    else 0,
                    axis=1
                )

            df_base = df.drop(columns=["Year", "Month", "MonthName"])
            mask = df.index.isin(filtered_df.index)

            updated_df = pd.concat([df_base[~mask], edited_df], ignore_index=True)

            save_fn(updated_df, sheet)
            st.toast("Changes saved", icon="💾")
            st.cache_data.clear()

            from data_manager import bump_data_version
            bump_data_version()

            st.rerun()