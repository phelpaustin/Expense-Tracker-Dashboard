# ui_components.py
import streamlit as st
import pandas as pd
from currency_manager import get_exchange_rate
from utils import calculate_price_per_unit
from config import SUPPORTED_CURRENCIES, DEFAULT_CURRENCY
from data_manager import bump_data_version


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

    with st.sidebar.expander("Add New Expense Batch", expanded=True):
        date = st.date_input("Date")
        expense_type = st.selectbox("Expense Type", ["Goods", "Service"])
        shop = st.text_input("Shop")
        currency = st.selectbox("Currency", ["SEK", "INR"])
        if currency == "INR":
            rate = get_exchange_rate("INR", "SEK")
            st.caption(f"Live rate: 1 INR = {rate:.2f} SEK" if rate else "Rate unavailable")
        else:
            rate = 1.0

        st.divider()
        st.markdown("#### 🧾 Add Items for this Expense")

        # Keep multi-items in session
        if "multi_items" not in st.session_state:
            st.session_state["multi_items"] = []

        # Track temporary inputs to clear them later
        if "temp_inputs" not in st.session_state:
            st.session_state["temp_inputs"] = {
                "category": "", "subcategory": "", "item": "", "brand": "",
                "quantity": "", "unit": "Count", "amount": ""
            }

        with st.form("add_item_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                category = st.text_input("Category", st.session_state["temp_inputs"]["category"])
                subcategory = st.text_input("Subcategory", st.session_state["temp_inputs"]["subcategory"])
                item = st.text_input("Item", st.session_state["temp_inputs"]["item"])
                brand = st.text_input("Brand", st.session_state["temp_inputs"]["brand"])
            with col2:
                quantity_str = st.text_input("Quantity", st.session_state["temp_inputs"]["quantity"])
                unit = st.text_input("Unit", st.session_state["temp_inputs"]["unit"])

                # Amount input
                if currency == "INR":
                    amount_str = st.text_input("Amount (INR)", st.session_state["temp_inputs"]["amount"])
                else:
                    amount_str = st.text_input("Amount (SEK)", st.session_state["temp_inputs"]["amount"])

            submitted_item = st.form_submit_button("➕ Add Item")
            if submitted_item:
                try:
                    quantity = float(quantity_str) if quantity_str else 0.0
                except ValueError:
                    st.warning("⚠️ Invalid quantity entered.")
                    quantity = 0.0
                try:
                    amount = float(amount_str) if amount_str else 0.0
                except ValueError:
                    st.warning("⚠️ Invalid amount entered.")
                    amount = 0.0

                price = round(amount * rate, 2)
                price_per_unit = round(price / quantity, 2) if quantity else 0

                new_item = {
                    "Category": category or "Uncategorized",
                    "Subcategory": subcategory,
                    "Item": item,
                    "Brand": brand,
                    "Quantity": quantity,
                    "QuantityUnit": unit,
                    "PricePaid": price,
                    "Currency": currency,
                    "PricePerUnit": price_per_unit,
                }

                st.session_state["multi_items"].append(new_item)

                # ✅ Clear form inputs after adding
                st.session_state["temp_inputs"] = {
                    "category": "", "subcategory": "", "item": "", "brand": "",
                    "quantity": "", "unit": "Count", "amount": ""
                }

                st.success(f"✅ Added: {item} ({price} {currency})")
                st.rerun()

        # Show added items
        if st.session_state["multi_items"]:
            st.markdown("#### 🧮 Items Added So Far")
            st.dataframe(pd.DataFrame(st.session_state["multi_items"]))

            # 🔹 Display total amount dynamically
            total_price = sum(i.get("PricePaid", 0) for i in st.session_state["multi_items"])
            st.markdown(f"### 💰 Total: **{total_price:.2f} {currency}**")

            col_a, col_b = st.sidebar.columns(2)
            with col_a:
                if st.button("🗑️ Clear Items", use_container_width=True):
                    st.session_state["multi_items"].clear()
                    st.rerun()
            with col_b:
                if st.button("💾 Add All Expenses", use_container_width=True):
                    # Save each as separate row
                    new_rows = []
                    for entry in st.session_state["multi_items"]:
                        row = {
                            "Date": pd.to_datetime(date).strftime("%Y-%m-%d"),
                            "ExpenseType": expense_type,
                            "Shop": shop,
                            **entry,
                        }
                        new_rows.append(row)

                    df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                    save_fn(df)
                    st.success(f"✅ Added {len(new_rows)} expense entries successfully!")

                    # Clear all after saving
                    st.session_state["multi_items"].clear()
                    st.session_state["temp_inputs"] = {
                        "category": "", "subcategory": "", "item": "", "brand": "",
                        "quantity": "", "unit": "Count", "amount": ""
                    }

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
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Safe unique lists
    categories = sorted(df["Category"].dropna().unique().tolist()) if "Category" in df.columns else []
    shops = sorted(df["Shop"].dropna().unique().tolist()) if "Shop" in df.columns else []

    selected_categories = st.sidebar.multiselect("Category", options=categories)
    selected_shops = st.sidebar.multiselect("Shop", options=shops)

    # Price slider
    price_max = float(df["PricePaid"].max()) if "PricePaid" in df.columns and not df["PricePaid"].isna().all() else 1000.0
    min_price, max_price = st.sidebar.slider("Price Range (SEK)", 0.0, price_max, (0.0, price_max))

    # --- Date Range Filter ---
    start_date, end_date = None, None
    if "Date" in df.columns and df["Date"].notna().any():
        min_date = df["Date"].min().date()
        max_date = df["Date"].max().date()
        start_date, end_date = st.sidebar.date_input("📅 Date Range", [min_date, max_date])
    # If no valid dates, start_date/end_date remain None

    # --- Apply filters ---
    df_filtered = df.copy()

    if selected_categories and "Category" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["Category"].isin(selected_categories)]
    if selected_shops and "Shop" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["Shop"].isin(selected_shops)]
    if start_date and end_date and "Date" in df_filtered.columns:
        df_filtered = df_filtered[
            (df_filtered["Date"].dt.date >= start_date) &
            (df_filtered["Date"].dt.date <= end_date)
        ]
    if "PricePaid" in df_filtered.columns:
        df_filtered = df_filtered[
            (df_filtered["PricePaid"] >= min_price) &
            (df_filtered["PricePaid"] <= max_price)
        ]

    return df_filtered


# ====================================================
# ✏️ INLINE EDITOR (EDIT / DELETE)
# ====================================================
def inline_edit_table(df, save_fn, sheet=None):
    st.subheader("✏️ Edit or Delete Entries (by Year → Month)")

    if df.empty:
        st.info("No data to edit.")
        return

    # Ensure Date is datetime
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Extract year and month
    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month
    df["MonthName"] = df["Date"].dt.strftime("%B")

    # --- Year selection ---
    years = sorted(df["Year"].dropna().unique().tolist(), reverse=True)
    selected_year = st.selectbox("📅 Select Year", years, key="year_select")

    # --- Month selection ---
    months = (
        df[df["Year"] == selected_year][["Month", "MonthName"]]
        .drop_duplicates()
        .sort_values("Month")
    )
    month_options = months["MonthName"].tolist()
    month_numbers = months["Month"].tolist()
    month_map = dict(zip(month_options, month_numbers))

    selected_month_name = st.selectbox("🗓️ Select Month", month_options, key="month_select")
    selected_month = month_map[selected_month_name]

    # Filter entries for the selected month
    month_df = df[(df["Year"] == selected_year) & (df["Month"] == selected_month)]

    st.markdown(f"### 🧾 Entries for {selected_month_name} {selected_year}")

    if month_df.empty:
        st.info("No entries for this month.")
        return

    # --- Editable Table ---
    edited_df = st.data_editor(
        month_df.drop(columns=["Year", "Month", "MonthName"]),
        num_rows="dynamic",  # allows adding/deleting rows
        width="stretch",
        key=f"edit_{selected_year}_{selected_month}"
    )

    # Detect and handle any changes
    if not edited_df.equals(month_df.drop(columns=["Year", "Month", "MonthName"])):
        st.info("Unsaved changes detected. Click below to apply them.")

        if st.button("💾 Save Changes", key=f"save_{selected_year}_{selected_month}"):
            # Recalculate PricePerUnit if Quantity or PricePaid changed
            if "PricePaid" in edited_df.columns and "Quantity" in edited_df.columns:
                edited_df["PricePerUnit"] = edited_df.apply(
                    lambda x: round(x["PricePaid"] / x["Quantity"], 2)
                    if pd.notnull(x["PricePaid"]) and pd.notnull(x["Quantity"]) and x["Quantity"] != 0
                    else 0,
                    axis=1
                )

            # Remove derived columns before saving
            df_base = df.drop(columns=["Year", "Month", "MonthName"])

            # Replace entries for this month with updated data
            mask = (df["Year"] == selected_year) & (df["Month"] == selected_month)
            updated_df = pd.concat([df_base[~mask], edited_df], ignore_index=True)

            save_fn(updated_df, sheet)
            st.success("✅ Changes saved successfully!")
            st.cache_data.clear()
            bump_data_version()
            st.rerun()
