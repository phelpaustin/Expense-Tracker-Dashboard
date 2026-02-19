# error_handler.py
"""
Centralized error handling and logging for the Expense Tracker.
Provides consistent error handling patterns across the application.
"""
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Any, Tuple
from functools import wraps
import streamlit as st


# ============================================================
# LOGGING CONFIGURATION
# ============================================================
def setup_logging(log_file: str = "logs/expense_tracker.log", level: int = logging.INFO):
    """
    Setup application logging.
    
    Args:
        log_file: Path to log file
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # Also log to console
        ]
    )
    
    return logging.getLogger(__name__)


# Global logger instance
logger = setup_logging()


# ============================================================
# CUSTOM EXCEPTIONS
# ============================================================
class ExpenseTrackerError(Exception):
    """Base exception for all Expense Tracker errors."""
    pass


class DataLoadError(ExpenseTrackerError):
    """Raised when data cannot be loaded from storage."""
    pass


class DataSaveError(ExpenseTrackerError):
    """Raised when data cannot be saved to storage."""
    pass


class ValidationError(ExpenseTrackerError):
    """Raised when data validation fails."""
    pass


class NetworkError(ExpenseTrackerError):
    """Raised when network operations fail."""
    pass


class CurrencyConversionError(ExpenseTrackerError):
    """Raised when currency conversion fails."""
    pass


class ImportError(ExpenseTrackerError):
    """Raised when file import fails."""
    pass


class ExportError(ExpenseTrackerError):
    """Raised when file export fails."""
    pass


# ============================================================
# ERROR HANDLERS
# ============================================================
class ErrorHandler:
    """Centralized error handling with logging and user feedback."""
    
    @staticmethod
    def log_error(
        error: Exception,
        context: str = "",
        show_user: bool = True,
        user_message: Optional[str] = None
    ):
        """
        Log error with context and optionally show to user.
        
        Args:
            error: The exception that occurred
            context: Context where error occurred (e.g., "loading data")
            show_user: Whether to show error to user via Streamlit
            user_message: Custom message to show user (if None, uses error message)
        """
        # Log the full error with traceback
        error_msg = f"{context}: {str(error)}" if context else str(error)
        logger.error(error_msg)
        logger.debug(traceback.format_exc())
        
        # Show to user if requested
        if show_user:
            display_msg = user_message or f"❌ Error {context}: {str(error)}"
            st.error(display_msg)
    
    @staticmethod
    def log_warning(
        message: str,
        show_user: bool = True,
        user_message: Optional[str] = None
    ):
        """
        Log warning and optionally show to user.
        
        Args:
            message: Warning message
            show_user: Whether to show warning to user
            user_message: Custom message to show user
        """
        logger.warning(message)
        
        if show_user:
            display_msg = user_message or f"⚠️ {message}"
            st.warning(display_msg)
    
    @staticmethod
    def log_info(message: str, show_user: bool = False):
        """
        Log informational message.
        
        Args:
            message: Info message
            show_user: Whether to show info to user
        """
        logger.info(message)
        
        if show_user:
            st.info(f"ℹ️ {message}")
    
    @staticmethod
    def handle_exception(
        error: Exception,
        context: str = "",
        fallback_value: Any = None,
        show_user: bool = True
    ) -> Any:
        """
        Handle exception with logging and return fallback value.
        
        Args:
            error: The exception
            context: Context string
            fallback_value: Value to return on error
            show_user: Whether to show error to user
        
        Returns:
            fallback_value
        """
        ErrorHandler.log_error(error, context, show_user)
        return fallback_value


# ============================================================
# DECORATORS FOR ERROR HANDLING
# ============================================================
def handle_errors(
    context: str = "",
    fallback_value: Any = None,
    show_user: bool = True,
    reraise: bool = False
):
    """
    Decorator to handle errors in functions.
    
    Args:
        context: Description of what the function does
        fallback_value: Value to return on error
        show_user: Whether to show error to user
        reraise: Whether to re-raise the exception after handling
    
    Usage:
        @handle_errors(context="loading data", fallback_value=pd.DataFrame())
        def load_data():
            # ... code that might fail ...
            return df
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_context = context or f"in {func.__name__}"
                ErrorHandler.log_error(e, error_context, show_user)
                
                if reraise:
                    raise
                
                return fallback_value
        
        return wrapper
    return decorator


def log_function_call(func: Callable) -> Callable:
    """
    Decorator to log function calls with arguments.
    Useful for debugging.
    
    Usage:
        @log_function_call
        def save_data(df, sheet):
            # ... code ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        logger.debug(f"Calling {func_name} with args={args}, kwargs={kwargs}")
        
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func_name} completed successfully")
            return result
        except Exception as e:
            logger.error(f"{func_name} failed with error: {str(e)}")
            raise
    
    return wrapper


# ============================================================
# SPECIFIC ERROR HANDLERS
# ============================================================
class DataErrorHandler:
    """Error handling specific to data operations."""
    
    @staticmethod
    def handle_load_error(error: Exception, source: str = "storage") -> None:
        """Handle data loading errors."""
        ErrorHandler.log_error(
            error,
            context=f"loading data from {source}",
            user_message=f"⚠️ Could not load data from {source}. Using empty dataset."
        )
    
    @staticmethod
    def handle_save_error(error: Exception, destination: str = "storage") -> None:
        """Handle data saving errors."""
        ErrorHandler.log_error(
            error,
            context=f"saving data to {destination}",
            user_message=f"❌ Failed to save data to {destination}. Please try again."
        )
    
    @staticmethod
    def handle_validation_error(error: Exception, item: str = "data") -> None:
        """Handle validation errors."""
        ErrorHandler.log_error(
            error,
            context=f"validating {item}",
            user_message=f"❌ Validation failed: {str(error)}"
        )


class NetworkErrorHandler:
    """Error handling specific to network operations."""
    
    @staticmethod
    def handle_api_error(
        error: Exception,
        api_name: str = "API",
        fallback_message: Optional[str] = None
    ) -> Tuple[None, str]:
        """
        Handle API errors with specific error types.
        
        Returns:
            Tuple of (None, error_message)
        """
        import requests
        
        if isinstance(error, requests.Timeout):
            msg = f"{api_name} request timed out. Please check your internet connection."
        elif isinstance(error, requests.ConnectionError):
            msg = f"Cannot connect to {api_name}. Please check your internet connection."
        elif isinstance(error, requests.HTTPError):
            msg = f"{api_name} returned an error: {error.response.status_code}"
        else:
            msg = fallback_message or f"{api_name} request failed: {str(error)}"
        
        logger.error(f"{api_name} error: {msg}")
        return None, msg
    
    @staticmethod
    def handle_currency_error(error: Exception, base: str, target: str) -> Tuple[None, str]:
        """Handle currency conversion errors."""
        msg = f"Could not convert {base} to {target}: {str(error)}"
        logger.error(msg)
        return None, msg


class FileErrorHandler:
    """Error handling specific to file operations."""
    
    @staticmethod
    def handle_import_error(error: Exception, filename: str) -> None:
        """Handle file import errors."""
        ErrorHandler.log_error(
            error,
            context=f"importing {filename}",
            user_message=f"❌ Could not import {filename}. Please check the file format."
        )
    
    @staticmethod
    def handle_export_error(error: Exception, filename: str) -> None:
        """Handle file export errors."""
        ErrorHandler.log_error(
            error,
            context=f"exporting to {filename}",
            user_message=f"❌ Could not export to {filename}. Please try again."
        )


# ============================================================
# RETRY LOGIC
# ============================================================
def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator to retry function on failure.
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Delay between attempts in seconds
        exceptions: Tuple of exceptions to catch
    
    Usage:
        @retry_on_failure(max_attempts=3, delay=2.0)
        def fetch_data_from_api():
            # ... code that might fail ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time
            
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {str(e)}"
                    )
                    
                    if attempt < max_attempts:
                        time.sleep(delay)
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
            
            # All attempts failed
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


# ============================================================
# CONTEXT MANAGERS
# ============================================================
class suppress_and_log:
    """
    Context manager to suppress exceptions and log them.
    
    Usage:
        with suppress_and_log(ValueError, context="parsing date"):
            date = parse_date(date_string)
    """
    
    def __init__(self, *exceptions, context: str = "", fallback: Any = None):
        self.exceptions = exceptions or (Exception,)
        self.context = context
        self.fallback = fallback
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and issubclass(exc_type, self.exceptions):
            ErrorHandler.log_error(exc_val, self.context, show_user=False)
            return True  # Suppress the exception
        return False


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default if division fails.
    
    Args:
        numerator: Number to divide
        denominator: Number to divide by
        default: Default value if division fails
    
    Returns:
        Result of division or default value
    """
    try:
        if denominator == 0:
            logger.warning(f"Division by zero: {numerator}/{denominator}")
            return default
        return numerator / denominator
    except Exception as e:
        logger.error(f"Division error: {numerator}/{denominator} - {str(e)}")
        return default


def safe_float_conversion(value: Any, default: float = 0.0) -> float:
    """
    Safely convert value to float.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
    
    Returns:
        Float value or default
    """
    try:
        return float(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not convert '{value}' to float: {str(e)}")
        return default


def safe_int_conversion(value: Any, default: int = 0) -> int:
    """
    Safely convert value to int.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
    
    Returns:
        Int value or default
    """
    try:
        return int(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not convert '{value}' to int: {str(e)}")
        return default


# ============================================================
# STREAMLIT ERROR DISPLAY
# ============================================================
def show_error_with_details(error: Exception, context: str = "", show_traceback: bool = False):
    """
    Show error to user with optional traceback in expander.
    
    Args:
        error: The exception
        context: Context string
        show_traceback: Whether to show full traceback
    """
    st.error(f"❌ Error {context}: {str(error)}")
    
    if show_traceback:
        with st.expander("🔍 Show technical details"):
            st.code(traceback.format_exc())


def show_warning_with_retry(
    message: str,
    retry_callback: Optional[Callable] = None,
    button_label: str = "🔄 Retry"
):
    """
    Show warning with optional retry button.
    
    Args:
        message: Warning message
        retry_callback: Function to call on retry
        button_label: Label for retry button
    """
    st.warning(f"⚠️ {message}")
    
    if retry_callback:
        if st.button(button_label):
            retry_callback()


# ============================================================
# ERROR RECOVERY STRATEGIES
# ============================================================
class ErrorRecovery:
    """Strategies for recovering from errors."""
    
    @staticmethod
    def provide_fallback_data(error: Exception, data_type: str = "data"):
        """Provide fallback data when loading fails."""
        import pandas as pd
        
        ErrorHandler.log_warning(
            f"Using empty {data_type} due to error: {str(error)}",
            show_user=True,
            user_message=f"⚠️ Could not load {data_type}. Starting with empty dataset."
        )
        return pd.DataFrame()
    
    @staticmethod
    def prompt_manual_input(field_name: str, error: Exception, default_value: Any = None):
        """Prompt user for manual input when automatic method fails."""
        st.warning(f"⚠️ Could not automatically get {field_name}: {str(error)}")
        
        if isinstance(default_value, float):
            return st.number_input(
                f"Please enter {field_name} manually:",
                value=default_value or 0.0,
                min_value=0.0
            )
        else:
            return st.text_input(
                f"Please enter {field_name} manually:",
                value=default_value or ""
            )
    
    @staticmethod
    def save_to_backup(data, backup_path: str = "data/backup.csv"):
        """Save data to backup location on save failure."""
        try:
            Path(backup_path).parent.mkdir(parents=True, exist_ok=True)
            data.to_csv(backup_path, index=False)
            st.success(f"✅ Data saved to backup: {backup_path}")
            logger.info(f"Data backed up to {backup_path}")
        except Exception as e:
            ErrorHandler.log_error(e, "saving backup", show_user=True)


# ============================================================
# EXPORT
# ============================================================
__all__ = [
    # Setup
    "setup_logging",
    "logger",
    
    # Exceptions
    "ExpenseTrackerError",
    "DataLoadError",
    "DataSaveError",
    "ValidationError",
    "NetworkError",
    "CurrencyConversionError",
    "ImportError",
    "ExportError",
    
    # Handlers
    "ErrorHandler",
    "DataErrorHandler",
    "NetworkErrorHandler",
    "FileErrorHandler",
    
    # Decorators
    "handle_errors",
    "log_function_call",
    "retry_on_failure",
    
    # Context managers
    "suppress_and_log",
    
    # Helpers
    "safe_divide",
    "safe_float_conversion",
    "safe_int_conversion",
    
    # Display
    "show_error_with_details",
    "show_warning_with_retry",
    
    # Recovery
    "ErrorRecovery",
]