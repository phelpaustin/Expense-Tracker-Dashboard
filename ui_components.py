# ui_components.py
import streamlit as st
import pandas as pd
from currency_manager import get_exchange_rate
from utils import calculate_price_per_unit, load_dropdown_options
from config import SUPPORTED_CURRENCIES, DEFAULT_CURRENCY, Columns
from data_manager import bump_data_version
from validators import ExpenseValidator, ValidationError


# ====================================================
# 🌗 THEME CSS
# ====================================================
def theme_css(dark: bool):
    """Inject CSS for light/dark themes and KPI styling."""
    if dark:
        primary_bg = "#0b1220"
        secondary_bg = "#0f1724"
        text = "#e6eef6"
    else:
        primary_bg = "#f7fafc"
        secondary_bg = "#ffffff"
        text = "#0f1724"

    css = f"""
    <style>
    .stApp {{ background: {primary_bg}; color: {text}; }}
    .kpi-card {{ background: {secondary_bg}; padding: 14px; border-radius: 10px;
                 box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
    .kpi-label {{ font-size:14px; color: {text}; opacity:0.8; }}
    .kpi-value {{ font-size:20px; font-weight:700; color: {text}; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# ====================================================
# ➕ ADD EXPENSE
# ====================================================
def sidebar_add_expense(df, save_fn):
    """Sidebar for adding multiple expense items under same expense context."""
    st.sidebar.markdown("### ➕ Add Expense (Multi-Item Mode)")

    # ---------------- LOAD DROPDOWN DATA ----------------
    dropdowns = load_dropdown_options()
    categories = dropdowns.get("categories", [])
    subcategories_map = dropdowns.get("subcategories", {})
    shops = dropdowns.get("shops", [])
    units = dropdowns.get("units", ["Count"])

    with st.sidebar.expander("Add New Expense Batch", expanded=True):
        date = st.date_input("Date")
        expense_type = st.selectbox("Expense Type", ["Goods", "Service"])

        shop = st.selectbox("Shop", options=shops)

        currency = st.selectbox("Currency", ["SEK", "INR"])
        if currency == "INR":
            rate = get_exchange_rate("INR", "SEK")
            st.caption(f"Live rate: 1 INR = {rate:.2f} SEK" if rate else "Rate unavailable")
        else:
            rate = 1.0

        st.divider()
        st.markdown("#### 🧾 Add Items for this Expense")

        # ---------------- SESSION STATE ----------------
        if "multi_items" not in st.session_state:
            st.session_state["multi_items"] = []

        if "selected_category" not in st.session_state:
            st.session_state["selected_category"] = categories[0] if categories else ""

        if "selected_subcategory" not in st.session_state:
            st.session_state["selected_subcategory"] = ""

        if "temp_inputs" not in st.session_state:
            st.session_state["temp_inputs"] = {
                "item": "",
                "brand": "",
                "quantity": "",
                "unit": "Count",
                "amount": ""
            }

        # ---------------- CATEGORY & SUBCATEGORY (OUTSIDE FORM) ----------------
        category = st.selectbox(
            "Category",
            options=categories,
            key="selected_category"
        )

        subcategory_options = subcategories_map.get(category, [])

        subcategory = st.selectbox(
            "Subcategory",
            options=[""] + subcategory_options,
            key="selected_subcategory",
            disabled=len(subcategory_options) == 0
        )

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
                    Columns.CATEGORY: category or "Uncategorized",
                    Columns.SUBCATEGORY: subcategory,
                    Columns.ITEM: item_clean,
                    Columns.BRAND: brand_clean,
                    Columns.QUANTITY: quantity,
                    Columns.QUANTITY_UNIT: unit,
                    Columns.PRICE_PAID: price,
                    Columns.CURRENCY: currency,
                    Columns.PRICE_PER_UNIT: price_per_unit,
                }

                st.session_state["multi_items"].append(new_item)

                # Reset inputs
                st.session_state["temp_inputs"] = {
                    "item": "",
                    "brand": "",
                    "quantity": "",
                    "unit": "Count",
                    "amount": ""
                }

                st.success(f"✅ Added: {item_clean} ({price:.2f} SEK)")
                st.rerun()

    # ---------------- SHOW ITEMS + SAVE ----------------
        if st.session_state["multi_items"]:
            st.markdown("#### 🧮 Items Added So Far")
            st.dataframe(pd.DataFrame(st.session_state["multi_items"]), hide_index=True)

            total_price = sum(i.get(Columns.PRICE_PAID, 0) for i in st.session_state["multi_items"])
            st.markdown(f"### 💰 Total: **{total_price:.2f} SEK**")

            col_a, col_b = st.sidebar.columns(2)

            with col_a:
                if st.button("🗑️ Clear Items", width="stretch"):
                    st.session_state["multi_items"].clear()
                    st.rerun()

            with col_b:
                if st.button("💾 Add All Expenses", width="stretch"):
                    # Validate all items before saving
                    all_items_df = pd.DataFrame(st.session_state["multi_items"])
                    all_items_df[Columns.DATE] = date
                    all_items_df[Columns.EXPENSE_TYPE] = expense_type
                    all_items_df[Columns.SHOP] = shop
                    
                    # Final validation before save
                    is_valid, errors, _ = ExpenseValidator.validate_dataframe(all_items_df)
                    
                    if not is_valid:
                        st.error("**Cannot save - validation errors found:**")
                        for error in errors[:5]:
                            st.error(error)
                        st.stop()
                    
                    # All valid - save
                    new_rows = []
                    for entry in st.session_state["multi_items"]:
                        row = {
                            Columns.DATE: pd.to_datetime(date).date(),
                            Columns.EXPENSE_TYPE: expense_type,
                            Columns.SHOP: shop,
                            **entry,
                        }
                        new_rows.append(row)

                    df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                    save_fn(df)

                    st.success(f"✅ Added {len(new_rows)} expense entries successfully!")
                    st.session_state["multi_items"].clear()
                    bump_data_version()
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
    price_max = float(df[Columns.PRICE_PAID].max()) if Columns.PRICE_PAID in df.columns and not df[Columns.PRICE_PAID].isna().all() else 1000.0
    min_price, max_price = st.sidebar.slider("Price Range (SEK)", 0.0, price_max, (0.0, price_max))

    # --- Date Range Filter ---
    start_date, end_date = None, None
    if Columns.DATE in df.columns and df[Columns.DATE].notna().any():
        min_date = df[Columns.DATE].min().date()
        max_date = df[Columns.DATE].max().date()
        start_date, end_date = st.sidebar.date_input("📅 Date Range", [min_date, max_date])
    # If no valid dates, start_date/end_date remain None

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
    df["Year"] = df[Columns.DATE].dt.year
    df["Month"] = df[Columns.DATE].dt.month
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
    edited_df = st.data_editor(
        filtered_df.drop(columns=["Year", "Month", "MonthName"]),
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
            if "PricePaid" in edited_df.columns and "Quantity" in edited_df.columns:
                edited_df["PricePerUnit"] = edited_df.apply(
                    lambda x: round(x["PricePaid"] / x["Quantity"], 2)
                    if pd.notnull(x["PricePaid"]) and pd.notnull(x["Quantity"]) and x["Quantity"] != 0
                    else 0,
                    axis=1
                )

            df_base = df.drop(columns=["Year", "Month", "MonthName"])
            mask = df.index.isin(filtered_df.index)

            updated_df = pd.concat([df_base[~mask], edited_df], ignore_index=True)

            save_fn(updated_df, sheet)
            st.success("✅ Saved successfully!")
            st.cache_data.clear()

            from data_manager import bump_data_version
            bump_data_version()

            st.rerun()