# config.py
"""
Centralized configuration and constants for the Expense Tracker application.
All magic strings and constants should be defined here.
"""
from enum import Enum
from typing import List


# ============================================================
# STORAGE CONFIGURATION
# ============================================================
USE_GOOGLE_SHEETS = True
SHEET_NAME = "ExpenseTracker"
WORKSHEET_NAME = "Transactions"
LOCAL_CSV_FILE = "expenses_local.csv"
CREDENTIALS_FILE = "credentials.json"

# OAuth *user* credentials for Google Drive file storage.
# A service account has no Drive storage quota, so it cannot create/own
# files in a personal My Drive folder. Logging in as a real user (whose
# account has quota) fixes receipt uploads and data-file sync.
#   - OAUTH_CLIENT_FILE : OAuth 2.0 "Desktop app" client downloaded from
#                         Google Cloud Console.
#   - OAUTH_TOKEN_FILE  : generated once by running ``authorize_drive.py``;
#                         holds the saved/refreshable user token.
OAUTH_CLIENT_FILE = "oauth_client.json"
OAUTH_TOKEN_FILE = "token.json"

# OAuth scope for Google Drive / Sheets access.
#
# NOTE: this must stay as the full ``drive`` scope for the current setup:
#   * the gspread client opens the spreadsheet BY NAME with a *service
#     account*, which requires Drive access to a sheet shared with it —
#     ``drive.file`` only exposes files the app itself created, so open-by-name
#     returns nothing and the connection fails.
#   * the existing user token (token.json) was authorized with this broad
#     scope; changing it here without re-running authorize_drive.py causes a
#     scope-mismatch on refresh.
#
# To move to least privilege later, do BOTH: open the sheet by key/URL (so only
# the ``spreadsheets`` scope is needed) and re-run authorize_drive.py with
# ``drive.file`` for the user token. Until then, keep the full scope.
GOOGLE_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"


# ============================================================
# PENDING BILLS (total-bill entry, itemise later)
# ============================================================
# Separate store so pending/total bills never touch the itemised
# expense data, analytics, dedup or charts until they are itemised.
PENDING_BILLS_FILE = "data/pending_bills.json"

# ============================================================
# BILLS LEDGER (consolidated shop / date / amount view)
# ============================================================
# Manually-added ledger entries live in their own store. The Bills
# Ledger page merges these with bill-level totals derived from itemised
# expenses and from pending bills (read-only) into one simple list.
BILLS_LEDGER_FILE = "data/bills_ledger.json"

# Local folder used to keep a copy of receipts when Google Drive is
# unavailable (mirrors the local-CSV fallback for expense data).
RECEIPTS_LOCAL_DIR = "receipts"

# Name of the sub-folder created inside the same Drive folder that
# holds the expense spreadsheet ("Expense Manager" location) where
# receipt copies are uploaded.
DRIVE_RECEIPTS_FOLDER_NAME = "Expense Receipts"


# ============================================================
# RECEIPT SCANNER PIPELINE (3 stages: upload → translate → archive)
# ============================================================
# A crash-resumable pipeline where a receipt physically MOVES between
# folders as it progresses. State is implicit in which folder a file
# lives in, so a restart simply re-lists the folders. Files are mirrored
# locally (works offline) and synced to a "Scanner" sub-folder inside the
# shared spreadsheet folder on Google Drive.
SCANNER_LOCAL_DIR = "scanner"
SCANNER_DRIVE_ROOT = "Scanner"

SCANNER_STAGE_UPLOAD = 1       # uploaded, awaiting translation
SCANNER_STAGE_TRANSLATED = 2   # translated, editable, awaiting push
SCANNER_STAGE_FINAL = 3        # pushed to expense table, archived

# Local mirror sub-directories per stage (under SCANNER_LOCAL_DIR).
SCANNER_LOCAL_SUBDIRS = {
    SCANNER_STAGE_UPLOAD: "1_uploads",
    SCANNER_STAGE_TRANSLATED: "2_translated",
    SCANNER_STAGE_FINAL: "3_final",
}

# Google Drive sub-folder names per stage (under SCANNER_DRIVE_ROOT).
SCANNER_DRIVE_SUBFOLDERS = {
    SCANNER_STAGE_UPLOAD: "1_Uploads_For_Translation",
    SCANNER_STAGE_TRANSLATED: "2_Translated_Data",
    SCANNER_STAGE_FINAL: "3_Final_Expense_Receipts",
}


# ============================================================
# CURRENCY SETTINGS
# ============================================================
DEFAULT_CURRENCY = "SEK"
SUPPORTED_CURRENCIES = [
    "SEK", "INR", "USD", "EUR", "GBP", "JPY", "CHF",
    "AUD", "CAD", "CNY", "THB", "SGD", "AED", "NOK", "DKK",
]

# Display symbols for each supported currency. Falls back to the ISO code.
CURRENCY_SYMBOLS = {
    "SEK": "kr",
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CHF": "CHF",
    "AUD": "A$",
    "CAD": "C$",
    "CNY": "¥",
    "THB": "฿",
    "SGD": "S$",
    "AED": "د.إ",
    "NOK": "kr",
    "DKK": "kr",
}

# Currencies conventionally written with the symbol before the amount.
CURRENCY_SYMBOL_PREFIX = {
    "USD", "INR", "GBP", "JPY", "CNY", "AUD", "CAD", "SGD", "THB", "AED", "EUR",
}


# ============================================================
# AI MODELS
# ============================================================
CLAUDE_MODEL = "claude-sonnet-4-20250514"


# ============================================================
# CACHE TTLs (seconds)
# ============================================================
CACHE_TTL_SHORT = 60        # small operations
CACHE_TTL_MEDIUM = 300      # grouping / charts
CACHE_TTL_LONG = 3600       # exchange rates


# ============================================================
# COLUMN NAMES - CENTRALIZED
# ============================================================
class Columns:
    """
    Centralized column names for the expense DataFrame.
    Use these constants instead of hardcoded strings throughout the app.
    
    Example:
        df[Columns.PRICE_PAID].sum()  # ✅ Good
        df["PricePaid"].sum()          # ❌ Bad (magic string)
    """
    # Core columns
    DATE = "Date"
    EXPENSE_TYPE = "ExpenseType"
    CATEGORY = "Category"
    SUBCATEGORY = "Subcategory"
    ITEM = "Item"
    BRAND = "Brand"
    SHOP = "Shop"

    # Stable per-row identity. Assigned once (short UUID) and never reused, so
    # deduplication is identity-based and two genuinely-identical purchases are
    # never silently merged. Excluded from all_core() so it does not take part
    # in value-based comparisons or the visible schema.
    ENTRY_ID = "EntryId"

    # Financial columns
    PRICE_PAID = "PricePaid"
    CURRENCY = "Currency"
    QUANTITY = "Quantity"
    QUANTITY_UNIT = "QuantityUnit"
    PRICE_PER_UNIT = "PricePerUnit"
    
    # Computed/temporary columns
    YEAR = "Year"
    MONTH = "Month"
    MONTH_NAME = "MonthName"
    YEAR_MONTH = "YearMonth"
    DAY_OF_WEEK = "dow"
    WEEK = "week"
    
    @classmethod
    def all_core(cls) -> List[str]:
        """Get all core column names (excluding computed columns)."""
        return [
            cls.DATE,
            cls.EXPENSE_TYPE,
            cls.CATEGORY,
            cls.SUBCATEGORY,
            cls.ITEM,
            cls.BRAND,
            cls.SHOP,
            cls.PRICE_PAID,
            cls.CURRENCY,
            cls.QUANTITY,
            cls.QUANTITY_UNIT,
            cls.PRICE_PER_UNIT,
        ]
    
    @classmethod
    def required(cls) -> List[str]:
        """Get required column names."""
        return [
            cls.DATE,
            cls.EXPENSE_TYPE,
            cls.ITEM,
            cls.PRICE_PAID,
            cls.QUANTITY,
        ]
    
    @classmethod
    def optional(cls) -> List[str]:
        """Get optional column names."""
        return [
            cls.CATEGORY,
            cls.SUBCATEGORY,
            cls.BRAND,
            cls.SHOP,
            cls.CURRENCY,
            cls.QUANTITY_UNIT,
            cls.PRICE_PER_UNIT,
        ]
    
    @classmethod
    def financial(cls) -> List[str]:
        """Get financial column names."""
        return [
            cls.PRICE_PAID,
            cls.CURRENCY,
            cls.QUANTITY,
            cls.QUANTITY_UNIT,
            cls.PRICE_PER_UNIT,
        ]
    
    @classmethod
    def temporal(cls) -> List[str]:
        """Get temporal/date-related column names."""
        return [
            cls.DATE,
            cls.YEAR,
            cls.MONTH,
            cls.MONTH_NAME,
            cls.YEAR_MONTH,
        ]


# ============================================================
# EXPENSE TYPES
# ============================================================
class ExpenseType:
    """Valid expense types."""
    GOODS = "Goods"
    SERVICE = "Service"
    
    @classmethod
    def all(cls) -> List[str]:
        """Get all valid expense types."""
        return [cls.GOODS, cls.SERVICE]
    
    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if expense type is valid."""
        return value in cls.all()


# ============================================================
# QUANTITY UNITS
# ============================================================
class QuantityUnit:
    """Valid quantity units."""
    COUNT = "Count"
    KG = "Kg"
    LITRE = "Litre"
    METER = "Meter"
    GRAM = "g"
    MILLILITRE = "ml"
    
    @classmethod
    def all(cls) -> List[str]:
        """Get all valid quantity units."""
        return [cls.COUNT, cls.KG, cls.LITRE, cls.METER, cls.GRAM, cls.MILLILITRE]
    
    @classmethod
    def default(cls) -> str:
        """Get default quantity unit."""
        return cls.COUNT


# ============================================================
# FILE PATHS
# ============================================================
class FilePaths:
    """Centralized file paths."""
    DATA_DIR = "data"
    DROPDOWN_OPTIONS = "data/dropdown_options.json"
    EXPORT_CSV = "expenses_export.csv"
    EXPORT_EXCEL = "expenses_export.xlsx"
    LOCAL_STORAGE = "expenses_local.csv"


# ============================================================
# UI CONSTANTS
# ============================================================
class UIConstants:
    """Constants for UI elements."""
    # Page titles
    DASHBOARD_TITLE = "💰 Expense Dashboard"
    ANALYTICS_TITLE = "📊 Analytics & Trends"
    EDIT_TITLE = "✏️ Edit or Delete Entries"
    
    # Section headers
    ADD_EXPENSE_HEADER = "➕ Add Expense (Multi-Item Mode)"
    FILTERS_HEADER = "🔍 Filters"
    EXPORT_HEADER = "📤 Export Data"
    IMPORT_HEADER = "📥 Import Data"
    
    # Button labels
    BTN_ADD_ITEM = "➕ Add Item"
    BTN_CLEAR_ITEMS = "🗑️ Clear Items"
    BTN_SAVE_EXPENSES = "💾 Add All Expenses"
    BTN_SAVE_CHANGES = "💾 Save Changes"
    BTN_CANCEL = "❌ Cancel"
    BTN_CONFIRM = "✅ Confirm"
    BTN_DOWNLOAD_CSV = "💾 Download CSV"
    BTN_DOWNLOAD_EXCEL = "📘 Download Excel"
    
    # Messages
    MSG_NO_DATA = "No data available."
    MSG_NO_EXPENSES = "No expense records available yet."
    MSG_SAVE_SUCCESS = "✅ Saved successfully!"
    MSG_VALIDATION_FAILED = "**Validation Failed:**"
    MSG_UNSAVED_CHANGES = "⚠️ Unsaved changes detected!"
    
    # Placeholders
    PLACEHOLDER_ITEM = "e.g., Milk, Bread, Coffee"
    PLACEHOLDER_QUANTITY = "e.g., 1, 2.5, 0.5"
    PLACEHOLDER_AMOUNT = "e.g., 25.50"
    PLACEHOLDER_BRAND = "Optional"
    
    # Field labels
    LABEL_ITEM_REQUIRED = "Item *"
    LABEL_QUANTITY_REQUIRED = "Quantity *"
    LABEL_AMOUNT_REQUIRED = "Amount ({currency}) *"
    LABEL_BRAND = "Brand"
    LABEL_CATEGORY = "Category"
    LABEL_SUBCATEGORY = "Subcategory"
    LABEL_SHOP = "Shop"
    LABEL_DATE = "Date"
    LABEL_EXPENSE_TYPE = "Expense Type"
    LABEL_CURRENCY = "Currency"
    LABEL_UNIT = "Unit"
    
    # Help text
    HELP_REQUIRED_FIELDS = "* Required fields"
    HELP_LIVE_RATE = "Live rate: 1 {from_curr} = {rate:.2f} {to_curr}"
    HELP_RATE_UNAVAILABLE = "Rate unavailable"


# ============================================================
# VALIDATION CONSTANTS
# ============================================================
class ValidationLimits:
    """Validation limits for data entry."""
    # Price limits (in SEK)
    MIN_PRICE = 0.01
    MAX_PRICE = 1_000_000.00
    
    # Quantity limits
    MIN_QUANTITY = 0.01
    MAX_QUANTITY = 100_000.00
    
    # Text field limits
    MAX_ITEM_NAME_LENGTH = 200
    MAX_BRAND_NAME_LENGTH = 200
    MAX_CATEGORY_NAME_LENGTH = 100
    
    # Date limits
    MAX_YEARS_OLD = 5  # Warning if expense is older than this


# ============================================================
# SESSION STATE KEYS
# ============================================================
class SessionKeys:
    """Keys for Streamlit session state."""
    # Data management
    DATA_VERSION = "data_version"
    MULTI_ITEMS = "multi_items"
    
    # Pending bills (total-bill entry, itemise later)
    PENDING_BILLS = "pending_bills"
    DRIVE_RECEIPTS_FOLDER_ID = "drive_receipts_folder_id"
    ITEMISING_BILL_ID = "itemising_bill_id"
    PENDING_ITEMS = "pending_items"
    
    # Google Drive data-file sync
    DRIVE_SPREADSHEET_ID = "drive_spreadsheet_id"
    DRIVE_DATA_FOLDER_ID = "drive_data_folder_id"
    DATA_SYNC_PULLED = "data_sync_pulled"
    # Set once a non-recoverable Drive write error (e.g. service-account
    # storageQuotaExceeded) is seen, to stop retrying for the session.
    DRIVE_WRITE_DISABLED = "drive_write_disabled"

    # Receipt scanner pipeline (3-stage Drive/local folders)
    SCANNER_ROOT_FOLDER_ID = "scanner_root_folder_id"
    SCANNER_STAGE_FOLDER_IDS = "scanner_stage_folder_ids"
    SCANNER_SYNCED = "scanner_synced"
    
    # UI state
    SELECTED_CATEGORY = "selected_category"
    SELECTED_SUBCATEGORY = "selected_subcategory"
    TEMP_INPUTS = "temp_inputs"
    
    # Filter state
    FILTER_EXPENSE_TYPE = "filter_exp"
    FILTER_CATEGORY = "filter_cat"
    FILTER_SUBCATEGORY = "filter_sub"
    FILTER_ITEM = "filter_item"
    FILTER_BRAND = "filter_brand"
    FILTER_SHOP = "filter_shop"
    
    # Year/Month selection
    YEAR_SELECT = "year_select"
    MONTH_SELECT = "month_select"
    OVERVIEW_YEAR = "overview_year"
    OVERVIEW_MONTH = "overview_month"
    
    # Editor state
    EDIT_FILTERED = "edit_filtered"
    EDIT_MISSING_ENTRIES = "edit_missing_entries"
    IMPORT_DATA_EDITOR = "import_data_editor"


# ============================================================
# CHART CONFIGURATION
# ============================================================
class ChartConfig:
    """Configuration for charts and visualizations."""
    # Plotly config
    PLOTLY_CONFIG = {"displayModeBar": False}
    
    # Color schemes
    COLOR_SCALE_HEATMAP = "Blues"
    
    # Chart titles
    TITLE_SPENDING_BY_CATEGORY = "💸 Spending by Category"
    TITLE_MONTHLY_TREND = "📈 Monthly Spending Trend"
    TITLE_CALENDAR_HEATMAP = "📆 Spending Heatmap (week vs weekday)"
    TITLE_STACKED_AREA = "📊 Monthly Spending by Category (Stacked)"
    TITLE_YEARLY_COMPARISON = "📅 Yearly Comparison by Category"
    
    # Chart layout
    CHART_MARGIN = dict(t=50, b=0, l=0, r=0)
    PIE_HOLE_SIZE = 0.3


# ============================================================
# THEME COLORS
# ============================================================
class ThemeColors:
    """Color schemes for light and dark themes."""
    # Dark theme
    DARK_PRIMARY_BG = "#0b1220"
    DARK_SECONDARY_BG = "#0f1724"
    DARK_TEXT = "#e6eef6"
    
    # Light theme
    LIGHT_PRIMARY_BG = "#f7fafc"
    LIGHT_SECONDARY_BG = "#ffffff"
    LIGHT_TEXT = "#0f1724"


# ============================================================
# IMPORT STATE MANAGEMENT
# ============================================================
class ImportState(Enum):
    """States for the import workflow."""
    IDLE = "idle"                   # No import in progress
    FILE_UPLOADED = "file_uploaded" # File uploaded, preview shown
    EDITING = "editing"             # User editing imported data
    CONFIRMED = "confirmed"         # User confirmed, ready to merge
    MERGING = "merging"             # Merge in progress
    COMPLETED = "completed"         # Merge completed successfully
    ERROR = "error"                 # Error occurred


class ImportStateManager:
    """Manages import state transitions."""
    
    STATE_KEY = "import_state"
    DATA_KEY = "pending_import_df"
    ERROR_KEY = "import_error"
    SUCCESS_MESSAGE_KEY = "import_success_message"
    
    @staticmethod
    def get_state():
        """Get current import state."""
        import streamlit as st
        return st.session_state.get(
            ImportStateManager.STATE_KEY, 
            ImportState.IDLE
        )
    
    @staticmethod
    def set_state(new_state: ImportState, message: str = None):
        """Set import state with optional message."""
        import streamlit as st
        st.session_state[ImportStateManager.STATE_KEY] = new_state
        
        if message:
            if new_state == ImportState.ERROR:
                st.session_state[ImportStateManager.ERROR_KEY] = message
            elif new_state == ImportState.COMPLETED:
                st.session_state[ImportStateManager.SUCCESS_MESSAGE_KEY] = message
    
    @staticmethod
    def get_pending_data():
        """Get pending import DataFrame."""
        import streamlit as st
        return st.session_state.get(ImportStateManager.DATA_KEY)
    
    @staticmethod
    def set_pending_data(df):
        """Set pending import DataFrame."""
        import streamlit as st
        st.session_state[ImportStateManager.DATA_KEY] = df
    
    @staticmethod
    def clear_pending_data():
        """Clear pending import data."""
        import streamlit as st
        if ImportStateManager.DATA_KEY in st.session_state:
            del st.session_state[ImportStateManager.DATA_KEY]
    
    @staticmethod
    def get_error():
        """Get error message if any."""
        import streamlit as st
        return st.session_state.get(ImportStateManager.ERROR_KEY)
    
    @staticmethod
    def get_success_message():
        """Get success message if any."""
        import streamlit as st
        return st.session_state.get(ImportStateManager.SUCCESS_MESSAGE_KEY)
    
    @staticmethod
    def reset():
        """Reset all import state."""
        import streamlit as st
        keys_to_clear = [
            ImportStateManager.STATE_KEY,
            ImportStateManager.DATA_KEY,
            ImportStateManager.ERROR_KEY,
            ImportStateManager.SUCCESS_MESSAGE_KEY
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
    
    @staticmethod
    def can_show_upload_ui():
        """Determine if upload UI should be shown."""
        state = ImportStateManager.get_state()
        return state in [ImportState.IDLE, ImportState.ERROR]
    
    @staticmethod
    def should_show_preview():
        """Determine if preview should be shown."""
        state = ImportStateManager.get_state()
        return state in [
            ImportState.FILE_UPLOADED, 
            ImportState.EDITING
        ]
    
    @staticmethod
    def is_ready_to_merge():
        """Check if data is ready to be merged."""
        return ImportStateManager.get_state() == ImportState.CONFIRMED


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def get_currency_symbol(currency: str) -> str:
    """Get currency symbol for display."""
    return CURRENCY_SYMBOLS.get(currency, currency)


def format_currency(amount: float, currency: str = DEFAULT_CURRENCY) -> str:
    """Format amount with currency symbol."""
    symbol = get_currency_symbol(currency)
    if currency in CURRENCY_SYMBOL_PREFIX:
        return f"{symbol}{amount:,.2f}"
    else:
        return f"{amount:,.2f} {symbol}"


# ============================================================
# EXPORT FOR EASY IMPORTS
# ============================================================
__all__ = [
    # Storage
    "USE_GOOGLE_SHEETS",
    "SHEET_NAME",
    "WORKSHEET_NAME",
    "LOCAL_CSV_FILE",
    "CREDENTIALS_FILE",
    "GOOGLE_DRIVE_SCOPE",
    
    # Currency
    "DEFAULT_CURRENCY",
    "SUPPORTED_CURRENCIES",
    "CURRENCY_SYMBOLS",
    "CURRENCY_SYMBOL_PREFIX",
    
    # Cache
    "CACHE_TTL_SHORT",
    "CACHE_TTL_MEDIUM",
    "CACHE_TTL_LONG",
    
    # Classes
    "Columns",
    "ExpenseType",
    "QuantityUnit",
    "FilePaths",
    "UIConstants",
    "ValidationLimits",
    "SessionKeys",
    "ChartConfig",
    "ThemeColors",
    "ImportState",
    "ImportStateManager",
    
    # Functions
    "get_currency_symbol",
    "format_currency",
]