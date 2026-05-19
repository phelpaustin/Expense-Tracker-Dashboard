# date_utils.py
"""
Centralized date handling utilities.
Ensures consistent date formatting and conversion throughout the application.
"""
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Union, Optional, List, Tuple
from config import Columns
from error_handler import logger, handle_errors


# ============================================================
# DATE CONSTANTS
# ============================================================
class DateFormats:
    """Standard date format strings."""
    DISPLAY = "%Y-%m-%d"          # 2024-01-15
    DISPLAY_LONG = "%B %d, %Y"    # January 15, 2024
    MONTH_YEAR = "%B %Y"          # January 2024
    FILENAME = "%Y%m%d"           # 20240115
    DATABASE = "%Y-%m-%d"         # ISO format


class DateRanges:
    """Predefined date ranges for filters."""
    TODAY = "Today"
    LAST_7_DAYS = "Last 7 Days"
    LAST_30_DAYS = "Last 30 Days"
    THIS_MONTH = "This Month"
    LAST_MONTH = "Last Month"
    THIS_YEAR = "This Year"
    LAST_YEAR = "Last Year"
    ALL_TIME = "All Time"
    CUSTOM = "Custom Range"


# ============================================================
# DATE NORMALIZATION
# ============================================================
def normalize_date(date_value: Union[str, datetime, date, pd.Timestamp]) -> Optional[date]:
    """
    Convert any date-like value to a standard Python date object.
    
    Args:
        date_value: Date in any format
    
    Returns:
        date object or None if conversion fails
    
    Examples:
        >>> normalize_date("2024-01-15")
        date(2024, 1, 15)
        >>> normalize_date(pd.Timestamp("2024-01-15"))
        date(2024, 1, 15)
    """
    if date_value is None or (isinstance(date_value, str) and not date_value.strip()):
        return None
    
    try:
        # Already a date object
        if isinstance(date_value, date) and not isinstance(date_value, datetime):
            return date_value
        
        # datetime object
        if isinstance(date_value, datetime):
            return date_value.date()
        
        # pandas Timestamp
        if isinstance(date_value, pd.Timestamp):
            return date_value.date()
        
        # String - let pandas handle parsing
        if isinstance(date_value, str):
            parsed = pd.to_datetime(date_value, errors="coerce")
            if pd.isna(parsed):
                logger.warning(f"Could not parse date: {date_value}")
                return None
            return parsed.date()
        
        # Try generic conversion
        parsed = pd.to_datetime(date_value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date()
        
    except Exception as e:
        logger.error(f"Date normalization failed for {date_value}: {str(e)}")
        return None


def normalize_dataframe_dates(df: pd.DataFrame, date_column: str = None) -> pd.DataFrame:
    """
    Normalize all date columns in a DataFrame.
    
    Args:
        df: DataFrame to normalize
        date_column: Specific column to normalize (if None, normalizes DATE column)
    
    Returns:
        DataFrame with normalized dates
    """
    if df.empty:
        return df
    
    df = df.copy()
    
    # Normalize specific column or default DATE column
    col = date_column or Columns.DATE
    
    if col in df.columns:
        logger.debug(f"Normalizing dates in column: {col}")
        df[col] = df[col].apply(normalize_date)
    
    return df


# ============================================================
# DATE VALIDATION
# ============================================================
def is_valid_date(date_value: any) -> bool:
    """Check if value is a valid date."""
    return normalize_date(date_value) is not None


def is_future_date(date_value: Union[str, datetime, date]) -> bool:
    """Check if date is in the future."""
    normalized = normalize_date(date_value)
    if normalized is None:
        return False
    return normalized > datetime.now().date()


def is_too_old(date_value: Union[str, datetime, date], max_years: int = 5) -> bool:
    """Check if date is older than specified years."""
    normalized = normalize_date(date_value)
    if normalized is None:
        return False
    
    years_ago = (datetime.now().date() - normalized).days / 365.25
    return years_ago > max_years


# ============================================================
# DATE FORMATTING
# ============================================================
def format_date(date_value: Union[str, datetime, date], format_str: str = DateFormats.DISPLAY) -> str:
    """
    Format date for display.
    
    Args:
        date_value: Date to format
        format_str: Format string
    
    Returns:
        Formatted date string
    """
    normalized = normalize_date(date_value)
    if normalized is None:
        return ""
    
    try:
        return normalized.strftime(format_str)
    except Exception as e:
        logger.error(f"Date formatting failed: {str(e)}")
        return str(normalized)


def format_date_long(date_value: Union[str, datetime, date]) -> str:
    """Format date in long format (e.g., January 15, 2024)."""
    return format_date(date_value, DateFormats.DISPLAY_LONG)


def format_month_year(date_value: Union[str, datetime, date]) -> str:
    """Format date as month and year (e.g., January 2024)."""
    return format_date(date_value, DateFormats.MONTH_YEAR)


# ============================================================
# DATE RANGES
# ============================================================
def get_date_range(range_type: str) -> Tuple[date, date]:
    """
    Get start and end dates for predefined ranges.
    
    Args:
        range_type: One of DateRanges constants
    
    Returns:
        Tuple of (start_date, end_date)
    """
    today = datetime.now().date()
    
    if range_type == DateRanges.TODAY:
        return today, today
    
    elif range_type == DateRanges.LAST_7_DAYS:
        return today - timedelta(days=7), today
    
    elif range_type == DateRanges.LAST_30_DAYS:
        return today - timedelta(days=30), today
    
    elif range_type == DateRanges.THIS_MONTH:
        start = today.replace(day=1)
        return start, today
    
    elif range_type == DateRanges.LAST_MONTH:
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start, last_month_end
    
    elif range_type == DateRanges.THIS_YEAR:
        start = today.replace(month=1, day=1)
        return start, today
    
    elif range_type == DateRanges.LAST_YEAR:
        start = today.replace(year=today.year - 1, month=1, day=1)
        end = today.replace(year=today.year - 1, month=12, day=31)
        return start, end
    
    else:  # ALL_TIME or CUSTOM
        # Return very wide range for ALL_TIME
        return date(2000, 1, 1), today


def filter_dataframe_by_date_range(
    df: pd.DataFrame,
    range_type: str,
    custom_start: Optional[date] = None,
    custom_end: Optional[date] = None,
    date_column: str = None
) -> pd.DataFrame:
    """
    Filter DataFrame by date range.
    
    Args:
        df: DataFrame to filter
        range_type: Range type from DateRanges
        custom_start: Start date for custom range
        custom_end: End date for custom range
        date_column: Column to filter on (defaults to Columns.DATE)
    
    Returns:
        Filtered DataFrame
    """
    if df.empty:
        return df
    
    col = date_column or Columns.DATE
    
    if col not in df.columns:
        logger.warning(f"Date column {col} not found in DataFrame")
        return df
    
    # Normalize dates
    df = normalize_dataframe_dates(df, col)
    
    # Get date range
    if range_type == DateRanges.CUSTOM:
        if custom_start is None or custom_end is None:
            logger.warning("Custom range selected but dates not provided")
            return df
        start_date, end_date = custom_start, custom_end
    elif range_type == DateRanges.ALL_TIME:
        return df  # No filtering
    else:
        start_date, end_date = get_date_range(range_type)
    
    # Filter
    mask = (df[col] >= start_date) & (df[col] <= end_date)
    filtered = df[mask]
    
    logger.info(f"Filtered {len(df)} rows to {len(filtered)} rows ({range_type})")
    return filtered


# ============================================================
# DATE EXTRACTION
# ============================================================
def extract_year(date_value: Union[str, datetime, date]) -> Optional[int]:
    """Extract year from date."""
    normalized = normalize_date(date_value)
    return normalized.year if normalized else None


def extract_month(date_value: Union[str, datetime, date]) -> Optional[int]:
    """Extract month number (1-12) from date."""
    normalized = normalize_date(date_value)
    return normalized.month if normalized else None


def extract_month_name(date_value: Union[str, datetime, date]) -> Optional[str]:
    """Extract month name from date."""
    normalized = normalize_date(date_value)
    if normalized is None:
        return None
    return normalized.strftime("%B")


def extract_quarter(date_value: Union[str, datetime, date]) -> Optional[int]:
    """Extract quarter (1-4) from date."""
    month = extract_month(date_value)
    if month is None:
        return None
    return (month - 1) // 3 + 1


def extract_day_of_week(date_value: Union[str, datetime, date]) -> Optional[str]:
    """Extract day of week name from date."""
    normalized = normalize_date(date_value)
    if normalized is None:
        return None
    return normalized.strftime("%A")


def extract_week_number(date_value: Union[str, datetime, date]) -> Optional[int]:
    """Extract ISO week number from date."""
    normalized = normalize_date(date_value)
    if normalized is None:
        return None
    return normalized.isocalendar()[1]


def add_temporal_columns(df: pd.DataFrame, date_column: str = None) -> pd.DataFrame:
    """
    Add temporal columns (Year, Month, Quarter, etc.) to DataFrame.
    
    Args:
        df: DataFrame to enhance
        date_column: Date column to extract from
    
    Returns:
        DataFrame with additional temporal columns
    """
    if df.empty:
        return df
    
    col = date_column or Columns.DATE
    
    if col not in df.columns:
        return df
    
    df = df.copy()
    
    # Normalize dates first
    df = normalize_dataframe_dates(df, col)
    
    # Extract temporal components
    df[Columns.YEAR] = df[col].apply(extract_year)
    df[Columns.MONTH] = df[col].apply(extract_month)
    df[Columns.MONTH_NAME] = df[col].apply(extract_month_name)
    df["Quarter"] = df[col].apply(extract_quarter)
    df[Columns.DAY_OF_WEEK] = df[col].apply(extract_day_of_week)
    df[Columns.WEEK] = df[col].apply(extract_week_number)
    
    # Year-Month combination for grouping
    df[Columns.YEAR_MONTH] = df[col].apply(
        lambda d: f"{extract_year(d)}-{extract_month(d):02d}" if d else None
    )
    
    logger.info("Added temporal columns to DataFrame")
    return df


# ============================================================
# DATE COMPARISON
# ============================================================
def get_date_diff_days(date1: Union[str, datetime, date], date2: Union[str, datetime, date]) -> Optional[int]:
    """Get difference between two dates in days."""
    d1 = normalize_date(date1)
    d2 = normalize_date(date2)
    
    if d1 is None or d2 is None:
        return None
    
    return (d2 - d1).days


def is_same_month(date1: Union[str, datetime, date], date2: Union[str, datetime, date]) -> bool:
    """Check if two dates are in the same month."""
    d1 = normalize_date(date1)
    d2 = normalize_date(date2)
    
    if d1 is None or d2 is None:
        return False
    
    return d1.year == d2.year and d1.month == d2.month


def is_same_year(date1: Union[str, datetime, date], date2: Union[str, datetime, date]) -> bool:
    """Check if two dates are in the same year."""
    d1 = normalize_date(date1)
    d2 = normalize_date(date2)
    
    if d1 is None or d2 is None:
        return False
    
    return d1.year == d2.year


# ============================================================
# DATE AGGREGATION HELPERS
# ============================================================
def get_month_start(date_value: Union[str, datetime, date]) -> Optional[date]:
    """Get first day of the month for given date."""
    normalized = normalize_date(date_value)
    if normalized is None:
        return None
    return normalized.replace(day=1)


def get_month_end(date_value: Union[str, datetime, date]) -> Optional[date]:
    """Get last day of the month for given date."""
    normalized = normalize_date(date_value)
    if normalized is None:
        return None
    
    # Go to first day of next month, then subtract one day
    if normalized.month == 12:
        next_month = normalized.replace(year=normalized.year + 1, month=1, day=1)
    else:
        next_month = normalized.replace(month=normalized.month + 1, day=1)
    
    return next_month - timedelta(days=1)


def get_year_start(date_value: Union[str, datetime, date]) -> Optional[date]:
    """Get first day of the year for given date."""
    normalized = normalize_date(date_value)
    if normalized is None:
        return None
    return normalized.replace(month=1, day=1)


def get_year_end(date_value: Union[str, datetime, date]) -> Optional[date]:
    """Get last day of the year for given date."""
    normalized = normalize_date(date_value)
    if normalized is None:
        return None
    return normalized.replace(month=12, day=31)


# ============================================================
# STREAMLIT HELPERS
# ============================================================
def get_unique_years(df: pd.DataFrame, date_column: str = None) -> List[int]:
    """Get sorted list of unique years from DataFrame."""
    col = date_column or Columns.DATE
    
    if df.empty or col not in df.columns:
        return []
    
    df = normalize_dataframe_dates(df, col)
    years = df[col].apply(extract_year).dropna().unique()
    return sorted(years, reverse=True)


def get_unique_months(df: pd.DataFrame, year: Optional[int] = None, date_column: str = None) -> List[Tuple[int, str]]:
    """
    Get sorted list of unique months from DataFrame.
    
    Args:
        df: DataFrame
        year: Filter to specific year (optional)
        date_column: Date column name
    
    Returns:
        List of (month_number, month_name) tuples
    """
    col = date_column or Columns.DATE
    
    if df.empty or col not in df.columns:
        return []
    
    df = normalize_dataframe_dates(df, col)
    
    # Filter by year if specified
    if year is not None:
        df = df[df[col].apply(extract_year) == year]
    
    months = df[col].dropna().apply(lambda d: (extract_month(d), extract_month_name(d)))
    unique_months = months.drop_duplicates().dropna()
    
    # Sort by month number
    return sorted(unique_months.tolist(), key=lambda x: x[0])


# ============================================================
# EXPORT
# ============================================================
__all__ = [
    # Constants
    "DateFormats",
    "DateRanges",
    
    # Normalization
    "normalize_date",
    "normalize_dataframe_dates",
    
    # Validation
    "is_valid_date",
    "is_future_date",
    "is_too_old",
    
    # Formatting
    "format_date",
    "format_date_long",
    "format_month_year",
    
    # Ranges
    "get_date_range",
    "filter_dataframe_by_date_range",
    
    # Extraction
    "extract_year",
    "extract_month",
    "extract_month_name",
    "extract_quarter",
    "extract_day_of_week",
    "extract_week_number",
    "add_temporal_columns",
    
    # Comparison
    "get_date_diff_days",
    "is_same_month",
    "is_same_year",
    
    # Aggregation helpers
    "get_month_start",
    "get_month_end",
    "get_year_start",
    "get_year_end",
    
    # Streamlit helpers
    "get_unique_years",
    "get_unique_months",
]