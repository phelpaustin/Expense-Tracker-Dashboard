# validators.py
"""
Comprehensive validation for expense tracker data.
Centralizes all validation logic to ensure data integrity.
"""
import pandas as pd
from typing import Tuple, List, Optional, Dict, Any
from datetime import datetime, date
from config import (
    Columns, 
    ExpenseType, 
    SUPPORTED_CURRENCIES,
    ValidationLimits
)


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


class ExpenseValidator:
    """Centralized validation for expense data."""
    
    # Import constants from config
    REQUIRED_COLUMNS = Columns.required()
    OPTIONAL_COLUMNS = Columns.optional()
    VALID_EXPENSE_TYPES = ExpenseType.all()
    VALID_CURRENCIES = SUPPORTED_CURRENCIES
    
    # Validation limits from config
    MIN_PRICE = ValidationLimits.MIN_PRICE
    MAX_PRICE = ValidationLimits.MAX_PRICE
    MIN_QUANTITY = ValidationLimits.MIN_QUANTITY
    MAX_QUANTITY = ValidationLimits.MAX_QUANTITY
    
    @staticmethod
    def validate_expense_item(
        item: str,
        price: float,
        quantity: float,
        date_value: Optional[date] = None,
        expense_type: Optional[str] = None,
        currency: Optional[str] = None,
        category: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validate a single expense item before adding to database.
        
        Args:
            item: Item name/description
            price: Price paid (in base currency)
            quantity: Quantity purchased
            date_value: Transaction date
            expense_type: Type of expense (Goods/Service)
            currency: Currency code
            category: Expense category
        
        Returns:
            Tuple of (is_valid: bool, errors: List[str])
        """
        errors = []
        
        # Validate item name
        if not item or not str(item).strip():
            errors.append("❌ Item name is required and cannot be empty")
        elif len(str(item).strip()) > 200:
            errors.append("❌ Item name too long (max 200 characters)")
        
        # Validate price
        try:
            price_float = float(price)
            if price_float < ExpenseValidator.MIN_PRICE:
                errors.append(f"❌ Price must be at least {ExpenseValidator.MIN_PRICE} SEK")
            elif price_float > ExpenseValidator.MAX_PRICE:
                errors.append(f"❌ Price too high (max {ExpenseValidator.MAX_PRICE:,.0f} SEK)")
            elif price_float < 0:
                errors.append("❌ Price cannot be negative")
        except (ValueError, TypeError):
            errors.append("❌ Price must be a valid number")
        
        # Validate quantity
        try:
            quantity_float = float(quantity)
            if quantity_float < ExpenseValidator.MIN_QUANTITY:
                errors.append(f"❌ Quantity must be at least {ExpenseValidator.MIN_QUANTITY}")
            elif quantity_float > ExpenseValidator.MAX_QUANTITY:
                errors.append(f"❌ Quantity too high (max {ExpenseValidator.MAX_QUANTITY:,.0f})")
            elif quantity_float < 0:
                errors.append("❌ Quantity cannot be negative")
        except (ValueError, TypeError):
            errors.append("❌ Quantity must be a valid number")
        
        # Validate date
        if date_value:
            if isinstance(date_value, str):
                try:
                    date_value = pd.to_datetime(date_value).date()
                except (ValueError, TypeError):
                    errors.append("❌ Invalid date format")
                    date_value = None
            
            if date_value:
                today = datetime.now().date()
                if date_value > today:
                    errors.append("❌ Date cannot be in the future")
                
                # Warn if date is too old (more than 5 years)
                years_ago = (today - date_value).days / 365.25
                if years_ago > 5:
                    errors.append(f"⚠️ Warning: Date is {years_ago:.0f} years old")
        
        # Validate expense type
        if expense_type and expense_type not in ExpenseValidator.VALID_EXPENSE_TYPES:
            errors.append(f"❌ Expense type must be one of: {', '.join(ExpenseValidator.VALID_EXPENSE_TYPES)}")
        
        # Validate currency
        if currency and currency not in ExpenseValidator.VALID_CURRENCIES:
            errors.append(f"❌ Currency must be one of: {', '.join(ExpenseValidator.VALID_CURRENCIES)}")
        
        # Validate category (should not be empty if provided)
        if category is not None and not str(category).strip():
            errors.append("⚠️ Warning: Category is empty")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_dataframe(df: pd.DataFrame) -> Tuple[bool, List[str], pd.DataFrame]:
        """
        Validate entire DataFrame of expenses.
        
        Args:
            df: DataFrame to validate
        
        Returns:
            Tuple of (is_valid: bool, errors: List[str], invalid_rows: DataFrame)
        """
        errors = []
        invalid_indices = []
        
        if df.empty:
            return True, [], pd.DataFrame()
        
        # Check required columns
        missing_cols = [col for col in ExpenseValidator.REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            errors.append(f"❌ Missing required columns: {', '.join(missing_cols)}")
            return False, errors, df
        
        # Validate each row
        for idx, row in df.iterrows():
            row_errors = []
            
            # Check for missing critical data
            if pd.isna(row.get("Date")) or row.get("Date") == "":
                row_errors.append("Missing date")
            
            if pd.isna(row.get("ExpenseType")) or row.get("ExpenseType") == "":
                row_errors.append("Missing expense type")
            
            if pd.isna(row.get("Item")) or not str(row.get("Item", "")).strip():
                row_errors.append("Missing item name")
            
            # Validate price
            try:
                price = float(row.get("PricePaid", 0))
                if price <= 0:
                    row_errors.append(f"Invalid price: {price}")
                elif price > ExpenseValidator.MAX_PRICE:
                    row_errors.append(f"Price too high: {price:,.2f}")
            except (ValueError, TypeError):
                row_errors.append("Invalid price value")
            
            # Validate quantity
            try:
                qty = float(row.get("Quantity", 0))
                if qty <= 0:
                    row_errors.append(f"Invalid quantity: {qty}")
            except (ValueError, TypeError):
                row_errors.append("Invalid quantity value")
            
            # Validate date format
            if not pd.isna(row.get("Date")):
                try:
                    date_val = pd.to_datetime(row["Date"], errors="coerce")
                    if pd.isna(date_val):
                        row_errors.append("Invalid date format")
                    elif date_val.date() > datetime.now().date():
                        row_errors.append("Date in future")
                except (ValueError, TypeError):
                    row_errors.append("Cannot parse date")
            
            if row_errors:
                invalid_indices.append(idx)
                errors.append(f"Row {idx + 1}: {', '.join(row_errors)}")
        
        # Create DataFrame of invalid rows
        invalid_rows = df.loc[invalid_indices] if invalid_indices else pd.DataFrame()
        
        is_valid = len(invalid_indices) == 0
        
        return is_valid, errors, invalid_rows
    
    @staticmethod
    def validate_import_data(df: pd.DataFrame) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validate imported data with detailed statistics.
        
        Args:
            df: Imported DataFrame
        
        Returns:
            Tuple of (is_valid: bool, errors: List[str], stats: Dict)
        """
        errors = []
        stats = {
            "total_rows": len(df),
            "valid_rows": 0,
            "invalid_rows": 0,
            "missing_dates": 0,
            "missing_items": 0,
            "invalid_prices": 0,
            "invalid_quantities": 0,
            "future_dates": 0
        }
        
        if df.empty:
            errors.append("❌ Import file is empty")
            return False, errors, stats
        
        # Run full validation
        is_valid, validation_errors, invalid_df = ExpenseValidator.validate_dataframe(df)
        
        # Compute statistics
        stats["invalid_rows"] = len(invalid_df)
        stats["valid_rows"] = stats["total_rows"] - stats["invalid_rows"]
        
        if "Date" in df.columns:
            stats["missing_dates"] = df["Date"].isna().sum()
            
            try:
                dates = pd.to_datetime(df["Date"], errors="coerce")
                today = pd.Timestamp.now().normalize()
                stats["future_dates"] = (dates > today).sum()
            except Exception:
                pass
        
        if "Item" in df.columns:
            stats["missing_items"] = df["Item"].isna().sum() + (df["Item"] == "").sum()
        
        if "PricePaid" in df.columns:
            try:
                prices = pd.to_numeric(df["PricePaid"], errors="coerce")
                stats["invalid_prices"] = (prices <= 0).sum() + prices.isna().sum()
            except Exception:
                pass
        
        if "Quantity" in df.columns:
            try:
                quantities = pd.to_numeric(df["Quantity"], errors="coerce")
                stats["invalid_quantities"] = (quantities <= 0).sum() + quantities.isna().sum()
            except Exception:
                pass
        
        # Add validation errors to errors list
        errors.extend(validation_errors[:10])  # Limit to first 10 errors
        if len(validation_errors) > 10:
            errors.append(f"... and {len(validation_errors) - 10} more errors")
        
        return is_valid, errors, stats
    
    @staticmethod
    def sanitize_text(text: str, max_length: int = 200) -> str:
        """
        Sanitize text input by trimming whitespace and limiting length.
        
        Args:
            text: Input text
            max_length: Maximum allowed length
        
        Returns:
            Sanitized text
        """
        if not text:
            return ""
        
        sanitized = str(text).strip()
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized
    
    @staticmethod
    def validate_numeric_input(
        value_str: str,
        field_name: str,
        min_value: float = 0.01,
        max_value: float = None
    ) -> float:
        """
        Validate and parse numeric input with detailed error messages.
        
        Args:
            value_str: String value to parse
            field_name: Name of the field (for error messages)
            min_value: Minimum allowed value
            max_value: Maximum allowed value
        
        Returns:
            Parsed float value
        
        Raises:
            ValidationError: If validation fails
        """
        # Check if empty
        if not value_str or not str(value_str).strip():
            raise ValidationError(f"{field_name} is required")
        
        # Try to parse as number
        try:
            value = float(str(value_str).strip())
        except ValueError:
            raise ValidationError(f"{field_name} must be a valid number (got: '{value_str}')")
        
        # Check if negative
        if value < 0:
            raise ValidationError(f"{field_name} cannot be negative")
        
        # Check minimum
        if min_value is not None and value < min_value:
            raise ValidationError(f"{field_name} must be at least {min_value}")
        
        # Check maximum
        if max_value is not None and value > max_value:
            raise ValidationError(f"{field_name} cannot exceed {max_value:,.2f}")
        
        return value
    
    @staticmethod
    def get_validation_summary(df: pd.DataFrame) -> str:
        """
        Get a human-readable validation summary.
        
        Args:
            df: DataFrame to summarize
        
        Returns:
            Formatted summary string
        """
        is_valid, errors, invalid_df = ExpenseValidator.validate_dataframe(df)
        
        if is_valid:
            return f"✅ All {len(df)} rows are valid!"
        else:
            summary = f"⚠️ Found {len(invalid_df)} invalid rows out of {len(df)} total:\n\n"
            summary += "\n".join(errors[:5])  # Show first 5 errors
            if len(errors) > 5:
                summary += f"\n... and {len(errors) - 5} more issues"
            return summary


# Convenience function for quick validation
def validate_expense(**kwargs) -> Tuple[bool, List[str]]:
    """
    Quick validation function for expense items.
    
    Usage:
        is_valid, errors = validate_expense(
            item="Milk",
            price=25.50,
            quantity=1,
            date_value=datetime.now().date()
        )
    """
    return ExpenseValidator.validate_expense_item(**kwargs)