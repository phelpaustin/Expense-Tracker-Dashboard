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
    """Sidebar for adding new expense entries."""
    st.sidebar.markdown("### ➕ Add Expense")
    with st.sidebar.expander("Add New Expense", expanded=True):
        date = st.date_input("Date")
        expense_type = st.selectbox("Expense Type", ["Goods", "Service"])
        category = st.text_input("Category")
        subcategory = st.text_input("Subcategory", "")
        item = st.text_input("Item")
        shop = st.text_input("Shop")
        brand = st.text_input("Brand", "")

        # 👇 Manually typed quantity
        quantity_str = st.text_input("Quantity")
        try:
            quantity = float(quantity_str) if quantity_str else 0.0
        except ValueError:
            st.warning("⚠️ Please enter a valid number for quantity.")
            quantity = 0.0

        unit = st.text_input("Unit", "Count")

        currency = st.selectbox("Currency", ["SEK", "INR"])
        if currency == "INR":
            rate = get_exchange_rate("INR", "SEK")
            # 👇 Manual amount entry
            amount_inr_str = st.text_input("Amount in INR")
            try:
                amount_inr = float(amount_inr_str) if amount_inr_str else 0.0
            except ValueError:
                st.warning("⚠️ Please enter a valid number for amount in INR.")
                amount_inr = 0.0

            price = round(amount_inr * (rate or 0), 2)
            st.caption(f"Live rate: 1 INR = {rate:.2f} SEK" if rate else "Rate unavailable")
        else:
            price_str = st.text_input("Price Paid (SEK)")
            try:
                price = float(price_str) if price_str else 0.0
            except ValueError:
                st.warning("⚠️ Please enter a valid number for price.")
                price = 0.0

        if st.button("Add Expense", use_container_width=True):
            new_row = {
                "Date": pd.to_datetime(date).strftime("%Y-%m-%d"),
                "ExpenseType": expense_type,
                "Category": category or "Uncategorized",
                "Subcategory": subcategory,
                "Item": item,
                "Brand": brand,
                "Shop": shop,
                "PricePaid": price,
                "Currency": currency,
                "Quantity": quantity,
                "QuantityUnit": unit,
                "PricePerUnit": round(price / quantity, 2) if quantity else 0,
            }

            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_fn(df)
            st.success("✅ Expense Added!")

            # 🚀 Trigger reactive reload
            bump_data_version()
            st.rerun()


# ====================================================
# 🔍 FILTERS
# ====================================================
def filter_section(df):
    """Sidebar filters for date, category, shop, etc."""
    st.sidebar.markdown("### 🔍 Filters")

    if df.empty:
        st.sidebar.info("No data available.")
        return df

    # --- ✅ Ensure Date column is datetime ---
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Safe unique lists
    categories = sorted(df["Category"].dropna().unique().tolist())
    shops = sorted(df["Shop"].dropna().unique().tolist())

    selected_categories = st.sidebar.multiselect("Category", options=categories)
    selected_shops = st.sidebar.multiselect("Shop", options=shops)

    # Determine min/max safely
    price_max = float(df["PricePaid"].max()) if not df["PricePaid"].isna().all() else 1000.0
    min_price, max_price = st.sidebar.slider(
        "Price Range (SEK)", 0.0, price_max,
        (0.0, price_max)
    )

    # --- Date Range Filter ---
    if df["Date"].notna().any():
        min_date = df["Date"].min().date()
        max_date = df["Date"].max().date()
        start_date, end_date = st.sidebar.date_input("📅 Date Range", [min_date, max_date])
        df = df[(df["Date"] >= pd.Timestamp(start_date)) & (df["Date"] <= pd.Timestamp(end_date))]
    else:
        st.sidebar.info("⚠️ No valid dates found in data.")

    # Apply filters
    df_filtered = df.copy()
    if selected_categories:
        df_filtered = df_filtered[df_filtered["Category"].isin(selected_categories)]
    if selected_shops:
        df_filtered = df_filtered[df_filtered["Shop"].isin(selected_shops)]
    if start_date and end_date:
        df_filtered = df_filtered[
            (df_filtered["Date"].dt.date >= start_date) &
            (df_filtered["Date"].dt.date <= end_date)
        ]
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

    # --- Editable and Deletable Table ---
    edited_df = st.data_editor(
        month_df.drop(columns=["Year", "Month", "MonthName"]),
        num_rows="dynamic",  # allows adding/deleting rows
        width="stretch",
        key=f"edit_{selected_year}_{selected_month}"
    )

    # Detect and handle any changes (added/edited/deleted rows)
    if not edited_df.equals(month_df.drop(columns=["Year", "Month", "MonthName"])):
        st.info("Unsaved changes detected. Click below to apply them.")

        if st.button("💾 Save Changes", key=f"save_{selected_year}_{selected_month}"):
            # Remove derived columns
            df_base = df.drop(columns=["Year", "Month", "MonthName"])

            # Drop old month entries and merge updated ones
            mask = (df["Year"] == selected_year) & (df["Month"] == selected_month)
            updated_df = pd.concat([df_base[~mask], edited_df], ignore_index=True)

            save_fn(updated_df, sheet)
            st.success("✅ Changes saved successfully!")
            st.cache_data.clear()
            bump_data_version()
            st.rerun()
