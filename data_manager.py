# data_manager.py

import os
import uuid

import pandas as pd
import streamlit as st

from config import (
    USE_GOOGLE_SHEETS, SHEET_NAME, WORKSHEET_NAME,
    LOCAL_CSV_FILE, CREDENTIALS_FILE, CACHE_TTL_MEDIUM,
    GOOGLE_DRIVE_SCOPE,
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
from security_utils import (
    sanitize_df_for_export,
    validate_upload,
    UploadValidationError,
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
            GOOGLE_DRIVE_SCOPE
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

    Returns raw data as stored — deduplication and write-back are
    handled by ensure_no_duplicates() called once on app startup,
    so duplicates are removed from the source permanently rather
    than only in memory.

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
            if not df.empty:
                logger.info(f"Loaded {len(df)} rows from Google Sheets")
                return df
            # Sheet returned 0 rows. Rather than trust an empty/cleared Sheet,
            # fall through to the local CSV so good local data is never masked
            # (e.g. after an interrupted write). The startup write-back then
            # repopulates the Sheet from this data.
            logger.warning(
                "Google Sheets returned 0 rows — falling back to local CSV if available"
            )
        except Exception as e:
            DataErrorHandler.handle_load_error(e, "Google Sheets")
            # Fall through to local CSV

    # Try local CSV
    try:
        if os.path.exists(LOCAL_CSV_FILE):
            logger.info(f"Loading data from {LOCAL_CSV_FILE}")
            df = pd.read_csv(LOCAL_CSV_FILE)
            logger.info(f"Loaded {len(df)} rows from local CSV")
            return df
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


def ensure_no_duplicates(df: pd.DataFrame, sheet=None) -> pd.DataFrame:
    """
    One-time startup check: if the loaded DataFrame contains duplicates,
    remove them and immediately write the cleaned data back to the source
    (Google Sheets and/or local CSV) so the duplicates are gone permanently.

    Call this once in Main_Dashboard_App.py right after load_data().
    It is a no-op when no duplicates are found, so it is safe to call
    on every startup with zero performance cost in the normal case.

    Args:
        df:    The DataFrame returned by load_data().
        sheet: Google Sheets worksheet object (optional).

    Returns:
        pd.DataFrame: Deduplicated DataFrame (unchanged if no dupes found).
    """
    if df.empty:
        return df

    # Backfill stable ids for any legacy rows that predate them so future
    # dedup is identity-based (and this one-time migration is persisted below).
    had_id_col = Columns.ENTRY_ID in df.columns
    before_ids = (
        df[Columns.ENTRY_ID].astype(str).tolist() if had_id_col else None
    )
    df = ensure_entry_ids(df)
    ids_changed = (not had_id_col) or (
        df[Columns.ENTRY_ID].astype(str).tolist() != before_ids
    )

    clean_df = deduplicate_entries(df)
    removed = len(df) - len(clean_df)

    if removed > 0 or ids_changed:
        logger.info(
            f"ensure_no_duplicates: writing back {len(clean_df)} rows "
            f"(removed {removed} duplicate(s), ids_added={ids_changed})"
        )
        save_data(clean_df, sheet=sheet)
        if removed > 0:
            st.toast(
                f"🗑️ Removed {removed} duplicate entr{'y' if removed == 1 else 'ies'} and saved.",
                icon="ℹ️",
            )

    return clean_df


def restore_sheet_if_empty(df: pd.DataFrame, sheet=None) -> None:
    """
    Repopulate an empty Google Sheet from local data.

    If the worksheet has no data rows (e.g. after an interrupted write cleared
    it) but ``df`` — sourced from the local CSV fallback — has rows, write those
    rows back so the Sheet is restored. No-op when the Sheet already has data,
    when there is no sheet, or when ``df`` is empty.
    """
    if sheet is None or df is None or df.empty:
        return
    try:
        existing = sheet.get_all_values()
        # <= 1 means empty or header-only.
        if len(existing) <= 1:
            logger.warning(
                f"Google Sheet is empty — restoring {len(df)} row(s) from local data"
            )
            save_data(ensure_entry_ids(df), sheet=sheet)
            try:
                st.toast(
                    f"↩️ Restored {len(df)} rows to Google Sheets from local backup.",
                    icon="✅",
                )
            except Exception:  # noqa: BLE001 – toast is best-effort
                pass
    except Exception as e:  # noqa: BLE001 – restore is best-effort
        logger.warning(f"restore_sheet_if_empty failed: {e}")


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
    # Assign stable ids to any new rows, then deduplicate (identity-based when
    # ids are present) before persisting so duplicate rows are never written.
    df = ensure_entry_ids(df)
    before_count = len(df)
    df = deduplicate_entries(df)
    removed = before_count - len(df)
    if removed > 0:
        st.toast(
            f"🗑️ Removed {removed} duplicate entr{'y' if removed == 1 else 'ies'}.",
            icon="ℹ️",
        )

    # Point-in-time snapshot before persisting. Keeps a rotating history of
    # recent saved states under data/backups/ so any bad write can be rolled
    # back (see backup_manager.list_backups / restore_backup). Best-effort:
    # a snapshot failure must never block the actual save.
    if not df.empty:
        try:
            from backup_manager import create_backup
            snapshot_path = create_backup(df, label="autosave")
            # Mirror the snapshot to Drive so the history survives losing the
            # local machine (best-effort — never blocks the save).
            try:
                import data_sync
                data_sync.push_backup(snapshot_path)
            except Exception as e:  # noqa: BLE001 – remote mirror is best-effort
                logger.warning(f"Pushing snapshot to Drive failed: {e}")
        except Exception as e:  # noqa: BLE001 – backup is best-effort
            logger.warning(f"Pre-save snapshot failed: {e}")

    save_successful = False
    errors = []

    # Try Google Sheets first
    if sheet:
        try:
            logger.info(f"Saving {len(df)} rows to Google Sheets")
            # NaN/Inf are not JSON-compliant and this pandas version's
            # astype(str) leaves NaN as a float, so blank them explicitly
            # before serialising to the Sheets API.
            safe = df.replace([float("inf"), float("-inf")], pd.NA).fillna("").astype(str)
            data = [safe.columns.tolist()] + safe.values.tolist()

            # Skip the (O(n), quota-costing) upload when the data is byte-for-byte
            # identical to what we last wrote to Sheets this session. Avoids
            # redundant full rewrites; genuine edits change the signature and
            # still write. The local CSV below is always written regardless.
            try:
                import hashlib
                sig = hashlib.md5(repr(data).encode("utf-8")).hexdigest()
            except Exception:  # noqa: BLE001
                sig = None
            if sig is not None and st.session_state.get("_last_sheet_sig") == sig:
                logger.info("Google Sheets unchanged since last save — skipping upload")
                save_successful = True
            else:
                # Overwrite IN PLACE starting at A1 — do NOT clear() first. This
                # is the key safety property: if the write fails midway
                # (network/API error), the previous contents are still there, so
                # the sheet is never left empty. Only after the new rows are
                # written do we blank any leftover trailing rows from a
                # previously larger dataset.
                sheet.update(values=data, range_name="A1")
                if sheet.row_count > len(data):
                    sheet.batch_clear([f"A{len(data) + 1}:Z{sheet.row_count}"])
                if sig is not None:
                    st.session_state["_last_sheet_sig"] = sig
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
        # Reject oversized / wrong-type uploads before loading into memory.
        validate_upload(uploaded_file, max_mb=25, allowed_ext=(".csv", ".xlsx", ".xls"))
    except UploadValidationError as e:
        st.error(f"❌ {e}")
        return None

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(uploaded_file)
        else:
            raise ValueError(f"Unsupported file type: {filename}")

        # Imported data bypasses the entry form's conversion, so normalise any
        # foreign-currency rows to the base currency to keep totals correct.
        try:
            from currency_manager import normalize_currency_to_base
            df = normalize_currency_to_base(df)
        except Exception as e:  # noqa: BLE001 – normalisation is best-effort
            logger.warning(f"Currency normalisation skipped for import: {e}")

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

    # Neutralise spreadsheet formula injection before writing any download.
    df = sanitize_df_for_export(df)

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


def clean_data(df):
    """
    Standardizes and cleans expense data.

    - Strips whitespace
    - Normalizes 'Date' to date-only
    - Ensures consistent column types
    - Removes fully duplicate rows

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


def ensure_entry_ids(df: pd.DataFrame) -> pd.DataFrame:
    """
    Guarantee every row has a stable, unique ``EntryId``.

    Rows that are missing an id (blank/NaN) — or that share an id with an
    earlier row (e.g. after a copy) — are assigned a fresh short UUID. Existing
    ids are preserved so a row's identity is stable across saves/reloads.

    This is what lets deduplication be identity-based: two genuinely-identical
    purchases keep distinct ids and are therefore never merged.

    Returns the DataFrame (a copy only when changes are needed).
    """
    if df is None or df.empty:
        return df

    if Columns.ENTRY_ID not in df.columns:
        df = df.copy()
        df[Columns.ENTRY_ID] = ""

    ids = df[Columns.ENTRY_ID].astype("string").fillna("").str.strip()
    missing = ids.eq("") | ids.str.lower().isin(["nan", "none"])
    duplicated = ids.duplicated(keep="first") & ~missing
    need = missing | duplicated

    if need.any():
        df = df.copy()
        new_ids = [uuid.uuid4().hex[:12] for _ in range(int(need.sum()))]
        df.loc[need, Columns.ENTRY_ID] = new_ids

    return df


def deduplicate_entries(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove duplicate rows.

    Preferred path (identity-based): when every row carries an ``EntryId``,
    duplicates are rows sharing the same id. Two purchases that happen to be
    identical in every visible field keep distinct ids and are BOTH preserved.

    Fallback path (legacy value-based): for data that predates ids — e.g. a
    partial import — a duplicate is a row identical across every column of
    Columns.all_core(). If even one field differs the rows are kept.

    Keeps the first occurrence of each duplicate group. Safe to call from
    cached functions because it makes no Streamlit UI calls.

    Args:
        df: DataFrame to deduplicate

    Returns:
        pd.DataFrame: Deduplicated DataFrame with reset index
    """
    if df.empty:
        return df

    ids_present = (
        Columns.ENTRY_ID in df.columns
        and df[Columns.ENTRY_ID].astype("string").fillna("").str.strip().ne("").all()
    )

    if ids_present:
        dedup_cols = [Columns.ENTRY_ID]
    else:
        # Legacy value-based comparison over the columns that actually exist.
        dedup_cols = [col for col in Columns.all_core() if col in df.columns]
        if not dedup_cols:
            return df

    before = len(df)
    df = df.drop_duplicates(subset=dedup_cols, keep="first").reset_index(drop=True)
    removed = before - len(df)

    if removed > 0:
        logger.info(f"Removed {removed} duplicate row(s)")

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
        return True  # Empty is valid

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
    "ensure_no_duplicates",
    "save_data",
    "import_data",
    "export_data_bytes",
    "clean_data",
    "deduplicate_entries",
    "bump_data_version",
    "validate_dataframe_schema",
]