# test_expense_tracker.py
"""
Comprehensive test suite for Expense Tracker.
Run with: pytest test_expense_tracker.py -v
"""
import pytest
import pandas as pd
from datetime import date, datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import modules to test
from validators import ExpenseValidator, ValidationError
from date_utils import (
    normalize_date, format_date, get_date_range,
    extract_year, extract_month, is_future_date
)
from models import ExpenseItem, ExpenseBatch, validate_expense_dict
from error_handler import safe_divide, safe_float_conversion


# ============================================================
# FIXTURES
# ============================================================
@pytest.fixture
def sample_expense_data():
    """Sample expense data for testing."""
    return {
        "date": date(2024, 1, 15),
        "expense_type": "Goods",
        "item": "Milk",
        "price_paid": 25.50,
        "quantity": 1.0,
        "category": "Groceries",
        "shop": "ICA",
        "currency": "SEK"
    }


@pytest.fixture
def sample_validator_kwargs():
    """
    Sample kwargs matching ExpenseValidator.validate_expense_item's signature.

    Note: the validator uses different parameter names than the ExpenseItem
    Pydantic model (``price``/``date_value`` vs ``price_paid``/``date`` and no
    ``shop``), so the two cannot share a single fixture.
    """
    return {
        "item": "Milk",
        "price": 25.50,
        "quantity": 1.0,
        "date_value": date(2024, 1, 15),
        "expense_type": "Goods",
        "currency": "SEK",
        "category": "Groceries",
    }


@pytest.fixture
def sample_dataframe():
    """Sample DataFrame for testing."""
    return pd.DataFrame({
        "Date": [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)],
        "ExpenseType": ["Goods", "Goods", "Service"],
        "Category": ["Groceries", "Groceries", "Transport"],
        "Item": ["Milk", "Bread", "Bus Ticket"],
        "PricePaid": [25.50, 15.00, 30.00],
        "Quantity": [1.0, 1.0, 1.0],
        "Shop": ["ICA", "ICA", "SL"],
        "Currency": ["SEK", "SEK", "SEK"]
    })


# ============================================================
# TEST VALIDATORS
# ============================================================
class TestValidators:
    """Test validation functions."""
    
    def test_valid_expense_item(self, sample_validator_kwargs):
        """Test validation of valid expense."""
        is_valid, errors = ExpenseValidator.validate_expense_item(**sample_validator_kwargs)
        assert is_valid is True
        assert len(errors) == 0
    
    def test_empty_item_name(self, sample_validator_kwargs):
        """Test validation fails for empty item name."""
        sample_validator_kwargs["item"] = ""
        is_valid, errors = ExpenseValidator.validate_expense_item(**sample_validator_kwargs)
        assert is_valid is False
        assert any("item" in error.lower() for error in errors)
    
    def test_zero_price(self, sample_validator_kwargs):
        """Test validation fails for zero price."""
        sample_validator_kwargs["price"] = 0.0
        is_valid, errors = ExpenseValidator.validate_expense_item(**sample_validator_kwargs)
        assert is_valid is False
        assert any("price" in error.lower() for error in errors)
    
    def test_negative_quantity(self, sample_validator_kwargs):
        """Test validation fails for negative quantity."""
        sample_validator_kwargs["quantity"] = -1.0
        is_valid, errors = ExpenseValidator.validate_expense_item(**sample_validator_kwargs)
        assert is_valid is False
        assert any("quantity" in error.lower() or "negative" in error.lower() for error in errors)
    
    def test_future_date(self, sample_validator_kwargs):
        """Test validation warns for future date."""
        sample_validator_kwargs["date_value"] = date.today() + timedelta(days=1)
        is_valid, errors = ExpenseValidator.validate_expense_item(**sample_validator_kwargs)
        assert is_valid is False
        assert any("future" in error.lower() for error in errors)
    
    def test_dataframe_validation(self, sample_dataframe):
        """Test DataFrame validation."""
        is_valid, errors, invalid_df = ExpenseValidator.validate_dataframe(sample_dataframe)
        assert is_valid is True
        assert len(errors) == 0
        assert invalid_df.empty


# ============================================================
# TEST DATE UTILITIES
# ============================================================
class TestDateUtils:
    """Test date utility functions."""
    
    def test_normalize_date_from_string(self):
        """Test date normalization from string."""
        result = normalize_date("2024-01-15")
        assert result == date(2024, 1, 15)
    
    def test_normalize_date_from_datetime(self):
        """Test date normalization from datetime."""
        dt = datetime(2024, 1, 15, 10, 30)
        result = normalize_date(dt)
        assert result == date(2024, 1, 15)
    
    def test_normalize_date_invalid(self):
        """Test date normalization with invalid input."""
        result = normalize_date("invalid-date")
        assert result is None
    
    def test_format_date(self):
        """Test date formatting."""
        d = date(2024, 1, 15)
        result = format_date(d)
        assert result == "2024-01-15"
    
    def test_extract_year(self):
        """Test year extraction."""
        d = date(2024, 1, 15)
        assert extract_year(d) == 2024
    
    def test_extract_month(self):
        """Test month extraction."""
        d = date(2024, 1, 15)
        assert extract_month(d) == 1
    
    def test_is_future_date(self):
        """Test future date detection."""
        future = date.today() + timedelta(days=1)
        assert is_future_date(future) is True
        
        past = date.today() - timedelta(days=1)
        assert is_future_date(past) is False
    
    def test_get_date_range_last_7_days(self):
        """Test date range calculation."""
        from date_utils import DateRanges
        start, end = get_date_range(DateRanges.LAST_7_DAYS)
        
        assert end == date.today()
        assert (end - start).days == 7


# ============================================================
# TEST MODELS
# ============================================================
class TestModels:
    """Test Pydantic models."""
    
    def test_expense_item_creation(self, sample_expense_data):
        """Test creating valid expense item."""
        item = ExpenseItem(**sample_expense_data)
        assert item.item == "Milk"
        assert item.price_paid == 25.50
    
    def test_expense_item_validation_error(self):
        """Test validation error on invalid data."""
        with pytest.raises(Exception):
            ExpenseItem(
                date=date.today(),
                expense_type="InvalidType",  # Invalid
                item="",  # Empty
                price_paid=-10,  # Negative
                quantity=0  # Zero
            )
    
    def test_expense_item_price_per_unit(self, sample_expense_data):
        """Test price per unit calculation."""
        sample_expense_data["quantity"] = 2.0
        sample_expense_data["price_paid"] = 50.0
        item = ExpenseItem(**sample_expense_data)
        assert item.price_per_unit == 25.0
    
    def test_expense_item_to_dict(self, sample_expense_data):
        """Test conversion to dictionary."""
        item = ExpenseItem(**sample_expense_data)
        result = item.to_dict()
        
        assert result["Item"] == "Milk"
        assert result["PricePaid"] == 25.50
        assert "PricePerUnit" in result
    
    def test_expense_batch(self, sample_expense_data):
        """Test expense batch."""
        item1 = ExpenseItem(**sample_expense_data)
        
        sample_expense_data["item"] = "Bread"
        sample_expense_data["price_paid"] = 15.0
        item2 = ExpenseItem(**sample_expense_data)
        
        batch = ExpenseBatch(
            date=date.today(),
            expense_type="Goods",
            shop="ICA",
            currency="SEK",
            items=[item1, item2]
        )
        
        assert batch.item_count == 2
        assert batch.total_amount == 40.50  # 25.50 + 15.0
    
    def test_validate_expense_dict(self, sample_expense_data):
        """Test dictionary validation."""
        # validate_expense_dict expects DataFrame-style (capitalized) keys.
        df_row = ExpenseItem(**sample_expense_data).to_dict()
        result = validate_expense_dict(df_row)
        assert result.is_valid is True
        assert len(result.errors) == 0


# ============================================================
# TEST ERROR HANDLING
# ============================================================
class TestErrorHandling:
    """Test error handling utilities."""
    
    def test_safe_divide_normal(self):
        """Test safe division with normal values."""
        result = safe_divide(10, 2)
        assert result == 5.0
    
    def test_safe_divide_by_zero(self):
        """Test safe division by zero."""
        result = safe_divide(10, 0, default=0.0)
        assert result == 0.0
    
    def test_safe_float_conversion_valid(self):
        """Test safe float conversion with valid input."""
        assert safe_float_conversion("10.5") == 10.5
        assert safe_float_conversion(10) == 10.0
    
    def test_safe_float_conversion_invalid(self):
        """Test safe float conversion with invalid input."""
        result = safe_float_conversion("invalid", default=0.0)
        assert result == 0.0


# ============================================================
# INTEGRATION TESTS
# ============================================================
class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_add_expense_workflow(self, sample_expense_data, sample_validator_kwargs):
        """Test complete add expense workflow."""
        # 1. Validate data
        is_valid, errors = ExpenseValidator.validate_expense_item(**sample_validator_kwargs)
        assert is_valid
        
        # 2. Create model
        item = ExpenseItem(**sample_expense_data)
        assert item is not None
        
        # 3. Convert to dict for DataFrame
        row = item.to_dict()
        assert "Date" in row
        assert "PricePaid" in row
        
        # 4. Add to DataFrame
        df = pd.DataFrame([row])
        assert len(df) == 1
        assert df.iloc[0]["Item"] == "Milk"
    
    def test_import_and_validate_workflow(self, sample_dataframe):
        """Test import and validation workflow."""
        # 1. Validate imported data
        is_valid, errors, invalid_df = ExpenseValidator.validate_dataframe(sample_dataframe)
        assert is_valid
        
        # 2. Normalize dates
        from date_utils import normalize_dataframe_dates
        df_normalized = normalize_dataframe_dates(sample_dataframe)
        
        # 3. Add temporal columns
        from date_utils import add_temporal_columns
        df_enhanced = add_temporal_columns(df_normalized)
        
        assert "Year" in df_enhanced.columns
        assert "Month" in df_enhanced.columns


# ============================================================
# PERFORMANCE TESTS
# ============================================================
class TestPerformance:
    """Performance benchmarks."""
    
    def test_large_dataframe_validation(self):
        """Test validation performance on large dataset."""
        import time
        
        # Create large dataset
        large_df = pd.DataFrame({
            "Date": [date.today()] * 10000,
            "ExpenseType": ["Goods"] * 10000,
            "Item": ["Test Item"] * 10000,
            "PricePaid": [10.0] * 10000,
            "Quantity": [1.0] * 10000,
        })
        
        start = time.time()
        is_valid, errors, invalid_df = ExpenseValidator.validate_dataframe(large_df)
        elapsed = time.time() - start
        
        assert is_valid
        assert elapsed < 5.0  # Should complete in under 5 seconds


# ============================================================
# EDGE CASES
# ============================================================
class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_dataframe(self):
        """Test handling empty DataFrame."""
        df = pd.DataFrame()
        is_valid, errors, invalid_df = ExpenseValidator.validate_dataframe(df)
        # Empty is considered valid
        assert invalid_df.empty
    
    def test_very_old_date(self):
        """Test very old dates."""
        old_date = date(1900, 1, 1)
        result = normalize_date(old_date)
        assert result == old_date
    
    def test_maximum_price(self):
        """Test maximum allowed price."""
        data = {
            "date_value": date.today(),
            "expense_type": "Goods",
            "item": "Expensive Item",
            "price": ExpenseValidator.MAX_PRICE,
            "quantity": 1.0
        }
        is_valid, errors = ExpenseValidator.validate_expense_item(**data)
        assert is_valid
    
    def test_minimum_quantity(self):
        """Test minimum allowed quantity."""
        data = {
            "date_value": date.today(),
            "expense_type": "Goods",
            "item": "Small Item",
            "price": 10.0,
            "quantity": ExpenseValidator.MIN_QUANTITY
        }
        is_valid, errors = ExpenseValidator.validate_expense_item(**data)
        assert is_valid


# ============================================================
# BILLS LEDGER
# ============================================================
import bills_ledger as bl


class TestBillsLedger:
    """Tests for the Bills Ledger projection + de-duplication."""

    def test_norm_date_variants(self):
        assert bl._norm_date("2026-06-20") == "2026-06-20"
        assert bl._norm_date(date(2026, 6, 20)) == "2026-06-20"
        assert bl._norm_date(datetime(2026, 6, 20, 9, 30)) == "2026-06-20"
        assert bl._norm_date("") == ""

    def test_dedup_key_is_normalised(self):
        # Same bill written slightly differently must share a key.
        a = bl._dedup_key("2026-06-20", "  ICA Maxi ", 742.5)
        b = bl._dedup_key(date(2026, 6, 20), "ica maxi", 742.50)
        assert a == b

    def test_expense_rows_group_by_shop_and_date(self):
        df = pd.DataFrame({
            "Date": ["2026-06-20", "2026-06-20", "2026-06-21"],
            "Shop": ["ICA", "ICA", "Lidl"],
            "PricePaid": [10.0, 15.0, 20.0],
            "Currency": ["SEK", "SEK", "SEK"],
        })
        rows = bl._expense_rows(df)
        by_key = {(r[bl.LEDGER_DATE], r[bl.LEDGER_SHOP]): r[bl.LEDGER_AMOUNT] for r in rows}
        assert by_key[("2026-06-20", "ICA")] == 25.0
        assert by_key[("2026-06-21", "Lidl")] == 20.0
        assert all(r[bl.LEDGER_SOURCE] == bl.SOURCE_EXPENSE for r in rows)

    def test_expense_rows_empty_df(self):
        assert bl._expense_rows(pd.DataFrame()) == []

    def test_build_ledger_dedup_prefers_expense(self, monkeypatch):
        # An expense and a manual entry describing the same bill collapse
        # into a single row, keeping the higher-priority Expense source.
        df = pd.DataFrame({
            "Date": ["2026-06-20"],
            "Shop": ["ICA"],
            "PricePaid": [25.0],
            "Currency": ["SEK"],
        })
        monkeypatch.setattr(bl, "_pending_rows", lambda: [])
        monkeypatch.setattr(bl, "_manual_rows", lambda: [{
            bl.LEDGER_DATE: "2026-06-20", bl.LEDGER_SHOP: "ica",
            bl.LEDGER_AMOUNT: 25.0, bl.LEDGER_CURRENCY: "SEK",
            bl.LEDGER_SOURCE: bl.SOURCE_MANUAL,
            "ledger_id": "x1", "note": "",
        }])
        led = bl.build_ledger(df)
        assert len(led) == 1
        assert led.iloc[0][bl.LEDGER_SOURCE] == bl.SOURCE_EXPENSE

    def test_build_ledger_keeps_distinct_amounts(self, monkeypatch):
        # Same shop + date but different amounts are two distinct bills.
        df = pd.DataFrame(columns=["Date", "Shop", "PricePaid", "Currency"])
        monkeypatch.setattr(bl, "_pending_rows", lambda: [])
        monkeypatch.setattr(bl, "_manual_rows", lambda: [
            {bl.LEDGER_DATE: "2026-06-20", bl.LEDGER_SHOP: "ICA",
             bl.LEDGER_AMOUNT: 25.0, bl.LEDGER_CURRENCY: "SEK",
             bl.LEDGER_SOURCE: bl.SOURCE_MANUAL, "ledger_id": "a", "note": ""},
            {bl.LEDGER_DATE: "2026-06-20", bl.LEDGER_SHOP: "ICA",
             bl.LEDGER_AMOUNT: 40.0, bl.LEDGER_CURRENCY: "SEK",
             bl.LEDGER_SOURCE: bl.SOURCE_MANUAL, "ledger_id": "b", "note": ""},
        ])
        led = bl.build_ledger(df)
        assert len(led) == 2

    def test_manual_duplicate_detection(self, monkeypatch):
        df = pd.DataFrame({
            "Date": ["2026-06-20"],
            "Shop": ["ICA"],
            "PricePaid": [25.0],
            "Currency": ["SEK"],
        })
        monkeypatch.setattr(bl, "_pending_rows", lambda: [])
        monkeypatch.setattr(bl, "_manual_rows", lambda: [])
        assert bl.manual_duplicate_exists("2026-06-20", "ica", 25.0, df=df) == bl.SOURCE_EXPENSE
        assert bl.manual_duplicate_exists("2000-01-01", "Nowhere", 1.0, df=df) is None


# ============================================================
# RUN TESTS
# ============================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])