# data_manager.py
import os
import pandas as pd
import streamlit as st
from config import (
    USE_GOOGLE_SHEETS, SHEET_NAME, WORKSHEET_NAME,
    LOCAL_CSV_FILE, CREDENTIALS_FILE, CACHE_TTL_MEDIUM
)

@st.cache_resource
def init_storage():
    """Return a gspread worksheet object or None if not available."""
    if not USE_GOOGLE_SHEETS:
        return None
    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials

        scope = ["https://spreadsheets.google.com/feeds",
                 "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        try:
            sheet = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            sh = client.open(SHEET_NAME)
            sheet = sh.add_worksheet(title=WORKSHEET_NAME, rows="1000", cols="12")
            sheet.append_row([
                "Date", "ExpenseType", "Category", "Subcategory", "Item",
                "Brand", "Shop", "PricePaid", "Currency", "Quantity",
                "QuantityUnit", "PricePerUnit"
            ])
        return sheet
    except Exception as e:
        st.warning(f"Google Sheets not available ({e}). Using local CSV fallback.")
        return None


EXPECTED_COLUMNS = [
    "Date", "ExpenseType", "Category", "Subcategory", "Item",
    "Brand", "Shop", "PricePaid", "Currency", "Quantity",
    "QuantityUnit", "PricePerUnit"
]


@st.cache_data(ttl=CACHE_TTL_MEDIUM, show_spinner=False)
def load_data(_sheet=None, version=0):
    """Load data from Google Sheets or local CSV (reactive via version)."""
    if USE_GOOGLE_SHEETS and _sheet is not None:
        try:
            records = _sheet.get_all_records()
            df = pd.DataFrame(records)
        except Exception as e:
            st.warning(f"⚠️ Could not fetch data from Google Sheets: {e}")
            df = pd.DataFrame()
    else:
        if os.path.exists(LOCAL_CSV_FILE):
            df = pd.read_csv(LOCAL_CSV_FILE)
        else:
            df = pd.DataFrame(columns=EXPECTED_COLUMNS)
    return df


def save_data(df, sheet=None):
    """Save DataFrame to Google Sheet or local CSV. This is not cached."""
    if sheet:
        # gspread: clear and push
        try:
            sheet.clear()
            sheet.append_row(df.columns.tolist())
            sheet.append_rows(df.astype(str).values.tolist())
        except Exception as e:
            st.error(f"Failed to save to Google Sheets: {e}")
    else:
        df.to_csv(LOCAL_CSV_FILE, index=False)
    
    bump_data_version()  # ensures cache invalidation

def import_data(uploaded_file):
    """Return DataFrame from uploaded CSV/XLSX file."""
    try:
        if uploaded_file.name.endswith(".csv"):
            return pd.read_csv(uploaded_file)
        else:
            return pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Failed to import file: {e}")
        return pd.DataFrame(columns=EXPECTED_COLUMNS)


def export_data_bytes(df, file_type="csv"):
    """Return bytes for a download_button (csv or xlsx)."""
    if file_type == "csv":
        return df.to_csv(index=False).encode("utf-8"), "text/csv"
    elif file_type == "xlsx":
        import io
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        return output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        return None, None

def bump_data_version():
    """Increment version counter so cached data refreshes."""
    st.session_state["data_version"] = st.session_state.get("data_version", 0) + 1
