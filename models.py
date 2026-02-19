# models.py
"""
Pydantic models for type-safe data structures.
Provides validation, serialization, and type hints.
"""
from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


# ============================================================
# ENUMS
# ============================================================
class ExpenseTypeEnum(str, Enum):
    """Valid expense types."""
    GOODS = "Goods"
    SERVICE = "Service"


class CurrencyEnum(str, Enum):
    """Supported currencies."""
    SEK = "SEK"
    INR = "INR"
    USD = "USD"
    EUR = "EUR"


# ============================================================
# EXPENSE ITEM MODEL
# ============================================================
class ExpenseItem(BaseModel):
    """
    Single expense item with full validation.
    
    This ensures data integrity at the model level.
    """
    # Required fields
    date: date = Field(..., description="Date of expense")
    expense_type: ExpenseTypeEnum = Field(..., description="Type of expense")
    item: str = Field(..., min_length=1, max_length=200, description="Item name")
    price_paid: float = Field(..., gt=0, le=1_000_000, description="Price in SEK")
    quantity: float = Field(..., gt=0, le=100_000, description="Quantity purchased")
    
    # Optional fields with defaults
    category: Optional[str] = Field("Uncategorized", max_length=100)
    subcategory: Optional[str] = Field("", max_length=100)
    brand: Optional[str] = Field("", max_length=200)
    shop: Optional[str] = Field("", max_length=200)
    currency: CurrencyEnum = Field(CurrencyEnum.SEK)
    quantity_unit: str = Field("Count", max_length=50)
    
    class Config:
        use_enum_values = True
        validate_assignment = True
    
    @validator('item', 'brand', 'shop')
    def strip_whitespace(cls, v):
        """Strip whitespace from string fields."""
        return v.strip() if v else v
    
    @validator('date')
    def date_not_future(cls, v):
        """Ensure date is not in the future."""
        if v > datetime.now().date():
            raise ValueError("Date cannot be in the future")
        return v
    
    @validator('date')
    def date_not_too_old(cls, v):
        """Warn if date is very old."""
        years_ago = (datetime.now().date() - v).days / 365.25
        if years_ago > 10:
            raise ValueError(f"Date is {years_ago:.0f} years old - possibly incorrect?")
        return v
    
    @property
    def price_per_unit(self) -> float:
        """Calculate price per unit."""
        return round(self.price_paid / self.quantity, 2)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame."""
        return {
            "Date": self.date,
            "ExpenseType": self.expense_type,
            "Category": self.category,
            "Subcategory": self.subcategory,
            "Item": self.item,
            "Brand": self.brand,
            "Shop": self.shop,
            "PricePaid": self.price_paid,
            "Currency": self.currency,
            "Quantity": self.quantity,
            "QuantityUnit": self.quantity_unit,
            "PricePerUnit": self.price_per_unit,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ExpenseItem':
        """Create from dictionary."""
        return cls(
            date=data.get("Date"),
            expense_type=data.get("ExpenseType"),
            category=data.get("Category"),
            subcategory=data.get("Subcategory"),
            item=data.get("Item"),
            brand=data.get("Brand"),
            shop=data.get("Shop"),
            price_paid=data.get("PricePaid"),
            currency=data.get("Currency", "SEK"),
            quantity=data.get("Quantity"),
            quantity_unit=data.get("QuantityUnit", "Count"),
        )


# ============================================================
# EXPENSE BATCH MODEL
# ============================================================
class ExpenseBatch(BaseModel):
    """
    Batch of expenses from same shopping trip.
    """
    date: date
    expense_type: ExpenseTypeEnum
    shop: str
    currency: CurrencyEnum = CurrencyEnum.SEK
    items: List[ExpenseItem] = Field(..., min_items=1)
    
    class Config:
        use_enum_values = True
    
    @property
    def total_amount(self) -> float:
        """Total amount for batch."""
        return sum(item.price_paid for item in self.items)
    
    @property
    def item_count(self) -> int:
        """Number of items in batch."""
        return len(self.items)
    
    def to_dataframe_rows(self) -> List[dict]:
        """Convert to list of dictionaries for DataFrame."""
        return [item.to_dict() for item in self.items]


# ============================================================
# FILTER MODEL
# ============================================================
class ExpenseFilter(BaseModel):
    """Filter parameters for expense queries."""
    categories: Optional[List[str]] = None
    shops: Optional[List[str]] = None
    expense_types: Optional[List[ExpenseTypeEnum]] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    
    class Config:
        use_enum_values = True
    
    @root_validator
    def validate_price_range(cls, values):
        """Ensure min_price <= max_price."""
        min_p = values.get('min_price')
        max_p = values.get('max_price')
        
        if min_p is not None and max_p is not None:
            if min_p > max_p:
                raise ValueError("min_price cannot be greater than max_price")
        
        return values
    
    @root_validator
    def validate_date_range(cls, values):
        """Ensure start_date <= end_date."""
        start = values.get('start_date')
        end = values.get('end_date')
        
        if start is not None and end is not None:
            if start > end:
                raise ValueError("start_date cannot be after end_date")
        
        return values


# ============================================================
# IMPORT RESULT MODEL
# ============================================================
class ImportResult(BaseModel):
    """Result of data import operation."""
    success: bool
    rows_imported: int = 0
    rows_failed: int = 0
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    @property
    def has_errors(self) -> bool:
        """Check if import had errors."""
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if import had warnings."""
        return len(self.warnings) > 0
    
    def summary(self) -> str:
        """Get import summary."""
        parts = [
            f"Imported: {self.rows_imported} rows",
        ]
        
        if self.rows_failed > 0:
            parts.append(f"Failed: {self.rows_failed} rows")
        
        if self.has_warnings:
            parts.append(f"Warnings: {len(self.warnings)}")
        
        return " | ".join(parts)


# ============================================================
# VALIDATION RESULT MODEL
# ============================================================
class ValidationResult(BaseModel):
    """Result of validation operation."""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    @property
    def error_count(self) -> int:
        """Number of errors."""
        return len(self.errors)
    
    @property
    def warning_count(self) -> int:
        """Number of warnings."""
        return len(self.warnings)
    
    def add_error(self, error: str):
        """Add an error."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        """Add a warning."""
        self.warnings.append(warning)


# ============================================================
# USER PREFERENCES MODEL
# ============================================================
class UserPreferences(BaseModel):
    """User preferences and settings."""
    default_currency: CurrencyEnum = CurrencyEnum.SEK
    dark_mode: bool = False
    items_per_page: int = Field(50, ge=10, le=1000)
    show_onboarding: bool = True
    auto_save: bool = True
    date_format: str = "%Y-%m-%d"
    
    class Config:
        use_enum_values = True


# ============================================================
# STATISTICS MODEL
# ============================================================
class ExpenseStatistics(BaseModel):
    """Expense statistics summary."""
    total_expenses: int
    total_amount: float
    average_transaction: float
    categories_count: int
    shops_count: int
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    top_category: Optional[str] = None
    top_category_amount: Optional[float] = None
    
    @property
    def formatted_total(self) -> str:
        """Format total amount."""
        return f"{self.total_amount:,.2f} SEK"
    
    @property
    def formatted_average(self) -> str:
        """Format average transaction."""
        return f"{self.average_transaction:,.2f} SEK"


# ============================================================
# EXPORT CONFIGURATION MODEL
# ============================================================
class ExportConfig(BaseModel):
    """Configuration for data export."""
    file_format: str = Field("csv", pattern="^(csv|xlsx|json)$")
    include_columns: Optional[List[str]] = None
    date_format: str = "%Y-%m-%d"
    encoding: str = "utf-8"
    
    @validator('file_format')
    def validate_format(cls, v):
        """Validate file format."""
        valid_formats = ["csv", "xlsx", "json"]
        if v.lower() not in valid_formats:
            raise ValueError(f"Format must be one of: {', '.join(valid_formats)}")
        return v.lower()


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def validate_expense_dict(data: dict) -> ValidationResult:
    """
    Validate expense dictionary using Pydantic model.
    
    Args:
        data: Dictionary to validate
    
    Returns:
        ValidationResult with errors/warnings
    """
    result = ValidationResult(is_valid=True)
    
    try:
        # Try to create model
        ExpenseItem(**data)
    except Exception as e:
        result.is_valid = False
        # Parse pydantic errors
        if hasattr(e, 'errors'):
            for error in e.errors():
                field = error.get('loc', ['unknown'])[0]
                msg = error.get('msg', 'validation error')
                result.add_error(f"{field}: {msg}")
        else:
            result.add_error(str(e))
    
    return result


# ============================================================
# EXPORT
# ============================================================
__all__ = [
    # Enums
    "ExpenseTypeEnum",
    "CurrencyEnum",
    
    # Models
    "ExpenseItem",
    "ExpenseBatch",
    "ExpenseFilter",
    "ImportResult",
    "ValidationResult",
    "UserPreferences",
    "ExpenseStatistics",
    "ExportConfig",
    
    # Helpers
    "validate_expense_dict",
]