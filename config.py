# config.py
USE_GOOGLE_SHEETS = True
SHEET_NAME = "ExpenseTracker"
WORKSHEET_NAME = "Transactions"
LOCAL_CSV_FILE = "expenses_local.csv"
CREDENTIALS_FILE = "credentials.json"

# UI settings
DEFAULT_CURRENCY = "SEK"
SUPPORTED_CURRENCIES = ["SEK", "INR", "USD", "EUR"]

# Cache TTLs (seconds)
CACHE_TTL_SHORT = 60        # small operations
CACHE_TTL_MEDIUM = 300      # grouping / charts
CACHE_TTL_LONG = 3600       # exchange rates
