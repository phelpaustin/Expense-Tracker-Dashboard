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


# ============================================================
# CURRENCY SETTINGS
# ============================================================
DEFAULT_CURRENCY = "SEK"
SUPPORTED_CURRENCIES = ["SEK", "INR", "USD", "EUR"]


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
    symbols = {
        "SEK": "kr",
        "INR": "₹",
        "USD": "$",
        "EUR": "€"
    }
    return symbols.get(currency, currency)


def format_currency(amount: float, currency: str = DEFAULT_CURRENCY) -> str:
    """Format amount with currency symbol."""
    symbol = get_currency_symbol(currency)
    if currency in ["SEK", "EUR"]:
        return f"{amount:,.2f} {symbol}"
    else:
        return f"{symbol}{amount:,.2f}"


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
    
    # Currency
    "DEFAULT_CURRENCY",
    "SUPPORTED_CURRENCIES",
    
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