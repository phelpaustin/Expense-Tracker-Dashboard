# data_manager.py

import os

import pandas as pd
import streamlit as st

from config import (
    USE_GOOGLE_SHEETS, SHEET_NAME, WORKSHEET_NAME,
    LOCAL_CSV_FILE, CREDENTIALS_FILE, CACHE_TTL_MEDIUM,
    Columns, SessionKeys
)
from error_handler import (
    DataErrorHandler,
    handle_errors,
    log_function_call,
    ErrorHandler,
    ErrorRecovery,
    logger
)


@st.cache_resource
@handle_errors(context="initializing storage", fallback_value=None, show_user=True)
def init_storage():
    """
    Return a gspread worksheet object or None if not available.

    Returns:
        gspread.Worksheet | None
    """
    if not USE_GOOGLE_SHEETS:
        logger.info("Google Sheets disabled, using local storage")
        return None

    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials

        logger.info("Initializing Google Sheets connection")

        if not os.path.exists(CREDENTIALS_FILE):
            raise FileNotFoundError(
                f"Credentials file not found: {CREDENTIALS_FILE}"
            )

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        creds = ServiceAccountCredentials.from_json_keyfile_name(
            CREDENTIALS_FILE,
            scope
        )
        client = gspread.authorize(creds)

        try:
            sheet = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
            logger.info(f"Connected to existing worksheet: {WORKSHEET_NAME}")
        except gspread.exceptions.WorksheetNotFound:
            logger.info(f"Worksheet not found, creating: {WORKSHEET_NAME}")
            sh = client.open(SHEET_NAME)
            sheet = sh.add_worksheet(title=WORKSHEET_NAME, rows="1000", cols="12")
            sheet.append_row(Columns.all_core())
            logger.info("Created new worksheet with headers")

        return sheet

    except FileNotFoundError as e:
        ErrorHandler.log_error(
            e,
            "Google Sheets setup",
            user_message="⚠️ Credentials file not found. Using local CSV storage."
        )
        return None
    except gspread.exceptions.APIError as e:
        ErrorHandler.log_error(
            e,
            "Google Sheets API",
            user_message="⚠️ Google Sheets API error. Using local CSV storage."
        )
        return None
    except Exception as e:
        ErrorHandler.log_error(
            e,
            "Google Sheets connection",
            user_message=f"⚠️ Google Sheets not available: {str(e)}. Using local CSV fallback."
        )
        return None


EXPECTED_COLUMNS = Columns.all_core()


@st.cache_data(ttl=CACHE_TTL_MEDIUM, show_spinner=False)
@log_function_call
def load_data(_sheet=None, version=0):
    """
    Load data from Google Sheets or local CSV (reactive via version).

    Deduplication is applied immediately after loading so the returned
    DataFrame is always free of fully identical rows.

    Args:
        _sheet: Google Sheets worksheet object
        version: Version number for cache invalidation

    Returns:
        pd.DataFrame: Loaded expense data (empty DataFrame on error)
    """
    if USE_GOOGLE_SHEETS and _sheet is not None:
        try:
            logger.info("Loading data from Google Sheets")
            records = _sheet.get_all_records()
            df = pd.DataFrame(records)
            logger.info(f"Loaded {len(df)} rows from Google Sheets")
            return deduplicate_entries(df)
        except Exception as e:
            DataErrorHandler.handle_load_error(e, "Google Sheets")
            # Fall through to local CSV

    # Try local CSV
    try:
        if os.path.exists(LOCAL_CSV_FILE):
            logger.info(f"Loading data from {LOCAL_CSV_FILE}")
            df = pd.read_csv(LOCAL_CSV_FILE)
            logger.info(f"Loaded {len(df)} rows from local CSV")
            return deduplicate_entries(df)
        else:
            logger.info("No local CSV found, returning empty DataFrame")
            return pd.DataFrame(columns=EXPECTED_COLUMNS)

    except pd.errors.EmptyDataError:
        logger.warning(f"CSV file is empty: {LOCAL_CSV_FILE}")
        return pd.DataFrame(columns=EXPECTED_COLUMNS)

    except pd.errors.ParserError as e:
        ErrorHandler.log_error(
            e,
            f"parsing CSV file {LOCAL_CSV_FILE}",
            user_message="⚠️ CSV file is corrupted. Starting with empty dataset."
        )
        return pd.DataFrame(columns=EXPECTED_COLUMNS)

    except Exception as e:
        DataErrorHandler.handle_load_error(e, "local CSV")
        return pd.DataFrame(columns=EXPECTED_COLUMNS)


@log_function_call
def save_data(df, sheet=None):
    """
    Save DataFrame to Google Sheet or local CSV.

    Deduplicates entries before saving to prevent identical rows
    from being persisted.

    Args:
        df: DataFrame to save
        sheet: Google Sheets worksheet object (optional)

    Raises:
        Exception: If save fails to all destinations
    """
    # Deduplicate before saving to prevent persisting duplicate entries
    before_count = len(df)
    df = deduplicate_entries(df)
    removed = before_count - len(df)
    if removed > 0:
        st.toast(
            f"🗑️ Removed {removed} duplicate entr{'y' if removed == 1 else 'ies'}.",
            icon="ℹ️"
        )

    save_successful = False
    errors = []

    # Try Google Sheets first
    if sheet:
        try:
            logger.info(f"Saving {len(df)} rows to Google Sheets")
            sheet.clear()
            sheet.append_row(df.columns.tolist())
            sheet.append_rows(df.astype(str).values.tolist())
            logger.info("Successfully saved to Google Sheets")
            save_successful = True
        except Exception as e:
            error_msg = f"Google Sheets save failed: {str(e)}"
            errors.append(error_msg)
            ErrorHandler.log_error(e, "saving to Google Sheets", show_user=False)

    # Always try local CSV as backup
    try:
        logger.info(f"Saving {len(df)} rows to {LOCAL_CSV_FILE}")
        csv_dir = os.path.dirname(LOCAL_CSV_FILE)
        if csv_dir:
            os.makedirs(csv_dir, exist_ok=True)
        df.to_csv(LOCAL_CSV_FILE, index=False)
        logger.info("Successfully saved to local CSV")
        save_successful = True

    except PermissionError as e:
        error_msg = f"Permission denied: {LOCAL_CSV_FILE}"
        errors.append(error_msg)
        ErrorHandler.log_error(
            e,
            "saving to CSV",
            user_message=f"❌ Cannot save to {LOCAL_CSV_FILE}. Check file permissions."
        )

    except Exception as e:
        error_msg = f"CSV save failed: {str(e)}"
        errors.append(error_msg)
        ErrorHandler.log_error(e, "saving to local CSV", show_user=False)

    # If all saves failed, try backup
    if not save_successful:
        logger.error("All save attempts failed, trying backup location")
        try:
            ErrorRecovery.save_to_backup(df)
            save_successful = True
        except Exception as backup_error:
            logger.error(f"Backup save also failed: {str(backup_error)}")

    # Show appropriate message to user
    if save_successful:
        if len(errors) > 0:
            st.warning(f"⚠️ Saved to backup location. Primary save failed: {errors[0]}")
    else:
        error_list = "\n".join(errors)
        st.error(f"❌ Failed to save data:\n{error_list}")
        raise Exception("Save failed to all destinations")

    bump_data_version()  # ensures cache invalidation


@handle_errors(context="importing file", fallback_value=None, show_user=True)
def import_data(uploaded_file):
    """
    Return DataFrame from uploaded CSV/XLSX file.

    Args:
        uploaded_file: Streamlit UploadedFile object

    Returns:
        pd.DataFrame | None: Imported data or None on error
    """
    if not uploaded_file:
        return None

    filename = uploaded_file.name
    logger.info(f"Importing file: {filename}")

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(uploaded_file)
        else:
            raise ValueError(f"Unsupported file type: {filename}")

        logger.info(f"Successfully imported {len(df)} rows from {filename}")
        return df

    except pd.errors.EmptyDataError:
        st.error(f"❌ File is empty: {filename}")
        return None
    except pd.errors.ParserError as e:
        st.error(f"❌ Could not parse file: {filename}\nError: {str(e)}")
        return None
    except ValueError as e:
        st.error(f"❌ {str(e)}")
        return None
    except Exception as e:
        st.error(f"❌ Failed to import {filename}: {str(e)}")
        logger.error(f"Import error: {str(e)}")
        return None


@handle_errors(context="exporting data", fallback_value=(None, None), show_user=True)
def export_data_bytes(df, file_type="csv"):
    """
    Return bytes for a download_button (csv or xlsx).

    Args:
        df: DataFrame to export
        file_type: "csv" or "xlsx"

    Returns:
        Tuple of (bytes, mime_type) or (None, None) on error
    """
    logger.info(f"Exporting data as {file_type}")

    try:
        if file_type == "csv":
            data = df.to_csv(index=False).encode("utf-8")
            mime_type = "text/csv"
            logger.info("CSV export successful")
            return data, mime_type

        elif file_type == "xlsx":
            import io
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Expenses")
            data = output.getvalue()
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            logger.info("Excel export successful")
            return data, mime_type

        else:
            raise ValueError(f"Unsupported export type: {file_type}")

    except ImportError:
        st.error("❌ openpyxl not installed. Cannot export to Excel.")
        st.info("Install with: pip install openpyxl")
        return None, None
    except Exception as e:
        st.error(f"❌ Export failed: {str(e)}")
        logger.error(f"Export error: {str(e)}")
        return None, None


def deduplicate_entries(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove fully duplicate rows — identical across all core columns.

    Keeps the first occurrence of each duplicate group. Called from
    load_data() (fixes existing stored data), save_data() (prevents
    new duplicates from being persisted), and clean_data() (when
    called explicitly from the app layer).

    A duplicate is two or more rows sharing the same value in every
    column of Columns.all_core():
        Date, ExpenseType, Category, Subcategory, Item, Brand, Shop,
        PricePaid, Currency, Quantity, QuantityUnit, PricePerUnit.

    If even one field differs the rows are treated as distinct and
    both are kept.

    Args:
        df: DataFrame to deduplicate

    Returns:
        pd.DataFrame: Deduplicated DataFrame with reset index
    """
    if df.empty:
        return df

    # Only use columns that actually exist (guards partial-schema imports)
    dedup_cols = [col for col in Columns.all_core() if col in df.columns]
    if not dedup_cols:
        return df

    before = len(df)
    df = df.drop_duplicates(subset=dedup_cols, keep="first").reset_index(drop=True)
    removed = before - len(df)

    if removed > 0:
        logger.info(f"Removed {removed} duplicate row(s)")

    return df


def clean_data(df):
    """
    Standardises and cleans expense data.

    - Strips whitespace from string columns
    - Normalises 'Date' to date-only
    - Removes fully duplicate rows via deduplicate_entries()

    Args:
        df: DataFrame to clean

    Returns:
        pd.DataFrame: Cleaned DataFrame
    """
    try:
        logger.info("Cleaning data")

        if Columns.DATE in df.columns:
            df[Columns.DATE] = pd.to_datetime(
                df[Columns.DATE],
                errors="coerce"
            ).dt.date

        for col in df.select_dtypes(include=["object"]).columns:
            df[col] = df[col].astype(str).str.strip()

        # Remove duplicate entries
        df = deduplicate_entries(df)

        logger.info("Data cleaning completed")
        return df

    except Exception as e:
        ErrorHandler.log_error(e, "cleaning data", show_user=False)
        return df


def bump_data_version():
    """Increment version counter so cached data refreshes."""
    try:
        current_version = st.session_state.get(SessionKeys.DATA_VERSION, 0)
        st.session_state[SessionKeys.DATA_VERSION] = current_version + 1
        logger.debug(f"Data version bumped to {current_version + 1}")
    except Exception as e:
        logger.error(f"Failed to bump data version: {str(e)}")


# ============================================================
# DATA VALIDATION HELPERS
# ============================================================

def validate_dataframe_schema(df: pd.DataFrame) -> bool:
    """
    Validate that DataFrame has expected schema.

    Args:
        df: DataFrame to validate

    Returns:
        bool: True if valid, False otherwise
    """
    if df.empty:
        return True

    missing_required = [
        col for col in Columns.required()
        if col not in df.columns
    ]

    if missing_required:
        logger.warning(f"Missing required columns: {missing_required}")
        st.warning(f"⚠️ Dataset missing columns: {', '.join(missing_required)}")
        return False

    return True


# ============================================================
# EXPORT
# ============================================================

__all__ = [
    "init_storage",
    "load_data",
    "save_data",
    "import_data",
    "export_data_bytes",
    "clean_data",
    "deduplicate_entries",
    "bump_data_version",
    "validate_dataframe_schema",
]