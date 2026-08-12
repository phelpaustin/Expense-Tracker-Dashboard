# currency_manager.py
"""
Currency conversion with robust error handling and multiple fallback strategies.
"""
import requests
import pandas as pd
import streamlit as st
from typing import Tuple, Optional, Dict
from datetime import datetime, timedelta
from config import CACHE_TTL_LONG, SUPPORTED_CURRENCIES, DEFAULT_CURRENCY, Columns
from error_handler import (
    NetworkErrorHandler,
    ErrorHandler,
    retry_on_failure,
    handle_errors,
    logger
)


# ============================================================
# EXCHANGE RATE PROVIDERS
# ============================================================
class ExchangeRateProvider:
    """Base class for exchange rate providers."""
    
    def get_rate(self, base: str, target: str) -> Tuple[Optional[float], Optional[str]]:
        """
        Get exchange rate from provider.
        
        Returns:
            Tuple of (rate: float | None, error: str | None)
        """
        raise NotImplementedError


class ExchangeRateHostProvider(ExchangeRateProvider):
    """Exchange rate provider using exchangerate.host API."""
    
    API_URL = "https://api.exchangerate.host/convert"
    TIMEOUT = 10
    
    @retry_on_failure(max_attempts=2, delay=1.0, exceptions=(requests.Timeout,))
    def get_rate(self, base: str, target: str) -> Tuple[Optional[float], Optional[str]]:
        """
        Get exchange rate from exchangerate.host.
        
        Args:
            base: Base currency code (e.g., "INR")
            target: Target currency code (e.g., "SEK")
        
        Returns:
            Tuple of (rate: float | None, error_message: str | None)
        """
        url = f"{self.API_URL}?from={base}&to={target}"
        
        try:
            logger.info(f"Fetching exchange rate: {base} → {target}")
            
            response = requests.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            
            # Validate response
            if not data.get("success", False):
                error_msg = data.get("error", {}).get("info", "API returned unsuccessful response")
                logger.warning(f"Exchange rate API error: {error_msg}")
                return None, f"API error: {error_msg}"
            
            if "result" not in data:
                logger.error("Invalid API response format: 'result' field missing")
                return None, "Invalid API response format"
            
            # Extract and validate rate
            try:
                rate = float(data["result"])
                
                # Sanity check: rate should be positive and reasonable
                if rate <= 0:
                    return None, "Invalid exchange rate (negative or zero)"
                
                if rate > 10000:  # Unreasonably high
                    logger.warning(f"Suspicious exchange rate: {rate}")
                    return None, "Exchange rate seems unrealistic"
                
                logger.info(f"Successfully fetched rate: 1 {base} = {rate} {target}")
                return rate, None
                
            except (ValueError, TypeError) as e:
                logger.error(f"Could not parse exchange rate: {str(e)}")
                return None, f"Invalid rate format: {str(e)}"
        
        except requests.Timeout:
            return NetworkErrorHandler.handle_api_error(
                requests.Timeout("Request timed out"),
                "Exchange rate API",
                "Request timed out. Using fallback rate."
            )
        
        except requests.ConnectionError as e:
            return NetworkErrorHandler.handle_api_error(
                e,
                "Exchange rate API",
                "Connection failed. Check your internet connection."
            )
        
        except requests.HTTPError as e:
            return NetworkErrorHandler.handle_api_error(
                e,
                "Exchange rate API",
                f"Server error: {e.response.status_code}"
            )
        
        except requests.RequestException as e:
            return NetworkErrorHandler.handle_api_error(
                e,
                "Exchange rate API"
            )
        
        except Exception as e:
            logger.error(f"Unexpected error fetching exchange rate: {str(e)}")
            return None, f"Unexpected error: {str(e)}"


# ============================================================
# FALLBACK RATES
# ============================================================
class FallbackRates:
    """
    Fallback exchange rates for when API is unavailable.
    Updated periodically (these are approximate rates as of early 2024).
    """

    # Human-readable date these hardcoded rates were last reviewed.
    LAST_UPDATED = "early 2024"

    RATES = {
        ("INR", "SEK"): 0.12,   # 1 INR ≈ 0.12 SEK
        ("SEK", "INR"): 8.33,   # 1 SEK ≈ 8.33 INR
        ("USD", "SEK"): 10.50,  # 1 USD ≈ 10.50 SEK
        ("SEK", "USD"): 0.095,  # 1 SEK ≈ 0.095 USD
        ("EUR", "SEK"): 11.50,  # 1 EUR ≈ 11.50 SEK
        ("SEK", "EUR"): 0.087,  # 1 SEK ≈ 0.087 EUR
        ("USD", "INR"): 83.00,  # 1 USD ≈ 83 INR
        ("INR", "USD"): 0.012,  # 1 INR ≈ 0.012 USD
        ("EUR", "USD"): 1.08,   # 1 EUR ≈ 1.08 USD
        ("USD", "EUR"): 0.93,   # 1 USD ≈ 0.93 EUR
        # ── Additional currencies (rates vs SEK, inverse handled automatically) ──
        ("GBP", "SEK"): 13.30,  # 1 GBP ≈ 13.30 SEK
        ("JPY", "SEK"): 0.070,  # 1 JPY ≈ 0.070 SEK
        ("CHF", "SEK"): 11.90,  # 1 CHF ≈ 11.90 SEK
        ("AUD", "SEK"): 6.95,   # 1 AUD ≈ 6.95 SEK
        ("CAD", "SEK"): 7.70,   # 1 CAD ≈ 7.70 SEK
        ("CNY", "SEK"): 1.45,   # 1 CNY ≈ 1.45 SEK
        ("THB", "SEK"): 0.29,   # 1 THB ≈ 0.29 SEK
        ("SGD", "SEK"): 7.80,   # 1 SGD ≈ 7.80 SEK
        ("AED", "SEK"): 2.86,   # 1 AED ≈ 2.86 SEK
        ("NOK", "SEK"): 0.97,   # 1 NOK ≈ 0.97 SEK
        ("DKK", "SEK"): 1.54,   # 1 DKK ≈ 1.54 SEK
    }
    
    @classmethod
    def get(cls, base: str, target: str) -> Optional[float]:
        """Get fallback rate if available."""
        # Try direct lookup
        rate = cls.RATES.get((base, target))
        if rate:
            logger.info(f"Using fallback rate: 1 {base} = {rate} {target}")
            return rate
        
        # Try inverse lookup
        inverse_rate = cls.RATES.get((target, base))
        if inverse_rate and inverse_rate != 0:
            rate = 1.0 / inverse_rate
            logger.info(f"Using inverse fallback rate: 1 {base} = {rate} {target}")
            return rate
        
        return None


# ============================================================
# MAIN EXCHANGE RATE FUNCTION
# ============================================================
@st.cache_data(ttl=CACHE_TTL_LONG, show_spinner=False, max_entries=64)
def get_exchange_rate(
    base: str = "INR",
    target: str = "SEK",
    use_fallback: bool = True
) -> Tuple[Optional[float], Optional[str]]:
    """
    Get exchange rate with comprehensive error handling and fallback strategies.

    Results are cached by Streamlit via @st.cache_data (TTL = CACHE_TTL_LONG);
    call refresh_exchange_rates() to force a fresh fetch.
    
    Args:
        base: Base currency code (e.g., "INR")
        target: Target currency code (e.g., "SEK")
        use_fallback: Whether to use fallback rates on API failure
    
    Returns:
        Tuple of (rate: float | None, error_message: str | None)
        
    Examples:
        >>> rate, error = get_exchange_rate("INR", "SEK")
        >>> if error:
        ...     st.warning(f"⚠️ {error}")
        ...     rate = st.number_input("Enter rate manually:", value=0.12)
        >>> else:
        ...     st.success(f"1 INR = {rate:.4f} SEK")
    """
    # Validate currency codes
    if base not in SUPPORTED_CURRENCIES or target not in SUPPORTED_CURRENCIES:
        error_msg = f"Unsupported currency: {base} or {target}"
        logger.error(error_msg)
        return None, error_msg
    
    # Same currency
    if base == target:
        return 1.0, None
    
    # Try to get rate from API
    provider = ExchangeRateHostProvider()
    rate, error = provider.get_rate(base, target)
    
    if rate is not None:
        return rate, None
    
    # API failed - try fallback
    if use_fallback:
        fallback_rate = FallbackRates.get(base, target)
        if fallback_rate is not None:
            warning_msg = (
                f"Using approximate fallback rate from {FallbackRates.LAST_UPDATED} "
                f"— may be out of date (API unavailable: {error})"
            )
            logger.warning(warning_msg)
            return fallback_rate, warning_msg
    
    # All strategies failed
    error_msg = f"Could not get exchange rate for {base}→{target}: {error}"
    logger.error(error_msg)
    return None, error_msg


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def convert_amount(
    amount: float,
    from_currency: str,
    to_currency: str = "SEK"
) -> Tuple[Optional[float], Optional[str]]:
    """
    Convert amount from one currency to another.
    
    Args:
        amount: Amount to convert
        from_currency: Source currency
        to_currency: Target currency
    
    Returns:
        Tuple of (converted_amount: float | None, error: str | None)
    """
    if amount < 0:
        return None, "Amount cannot be negative"
    
    rate, error = get_exchange_rate(from_currency, to_currency)
    
    if error:
        return None, error
    
    if rate is None:
        return None, "Exchange rate not available"
    
    try:
        converted = round(amount * rate, 2)
        return converted, None
    except Exception as e:
        error_msg = f"Conversion calculation failed: {str(e)}"
        logger.error(error_msg)
        return None, error_msg


def normalize_currency_to_base(
    df: "pd.DataFrame",
    base: str = DEFAULT_CURRENCY,
) -> "pd.DataFrame":
    """
    Return a copy of *df* whose amounts are all expressed in a single *base*
    currency.

    For every row whose ``Currency`` differs from *base*, ``PricePaid`` (and
    ``PricePerUnit`` when present) is multiplied by the current exchange rate
    and the ``Currency`` cell is rewritten to *base*. Rows already in *base*
    (or with an unknown currency) are left untouched. Establishing this
    single-base-currency invariant is what makes the downstream ``.sum()``
    totals — which previously added raw amounts across currencies — correct.

    Conversion uses the cached :func:`get_exchange_rate`, so this performs at
    most one network call per distinct foreign currency.
    """
    if df is None or df.empty:
        return df
    if Columns.CURRENCY not in df.columns or Columns.PRICE_PAID not in df.columns:
        return df

    out = df.copy()
    currencies = (
        out[Columns.CURRENCY].fillna(base).astype(str).str.strip().str.upper()
    )
    price = pd.to_numeric(out[Columns.PRICE_PAID], errors="coerce")
    ppu = (
        pd.to_numeric(out[Columns.PRICE_PER_UNIT], errors="coerce")
        if Columns.PRICE_PER_UNIT in out.columns
        else None
    )

    for code in currencies.unique():
        if code == base or code not in SUPPORTED_CURRENCIES:
            continue
        rate, _ = get_exchange_rate(code, base)
        if not rate:
            logger.warning(f"Skipping normalisation for {code}: no rate available")
            continue
        mask = currencies == code
        out.loc[mask, Columns.PRICE_PAID] = (price[mask] * rate).round(2)
        if ppu is not None:
            out.loc[mask, Columns.PRICE_PER_UNIT] = (ppu[mask] * rate).round(2)

    out[Columns.CURRENCY] = base
    return out


def get_rate_with_ui_feedback(base: str, target: str) -> float:
    """
    Get exchange rate with automatic UI feedback in Streamlit.
    Shows warnings/errors to user and prompts for manual input if needed.
    
    Args:
        base: Base currency
        target: Target currency
    
    Returns:
        Exchange rate (either from API, fallback, or manual input)
    """
    rate, error = get_exchange_rate(base, target)
    
    if error:
        # Show warning to user
        if "fallback" in error.lower():
            st.warning(f"⚠️ {error}")
        else:
            st.error(f"❌ {error}")
        
        # Prompt for manual input
        default_rate = rate if rate else (FallbackRates.get(base, target) or 1.0)
        rate = st.number_input(
            f"Please enter exchange rate manually (1 {base} = ? {target}):",
            value=float(default_rate),
            min_value=0.0,
            step=0.01,
            format="%.4f",
            help=f"Enter the current exchange rate for {base} to {target}"
        )
    else:
        # Success - show rate to user
        st.caption(f"💱 Live rate: 1 {base} = {rate:.4f} {target}")
    
    return rate


def refresh_exchange_rates():
    """Force refresh of all cached exchange rates."""
    get_exchange_rate.clear()
    logger.info("Exchange rates refreshed")


# ============================================================
# STREAMLIT UI COMPONENT
# ============================================================
def show_exchange_rate_widget(base: str = "INR", target: str = "SEK"):
    """
    Display an exchange rate widget with refresh button.
    
    Args:
        base: Base currency
        target: Target currency
    """
    col1, col2 = st.columns([3, 1])
    
    with col1:
        rate, error = get_exchange_rate(base, target)
        
        if error:
            if "fallback" in error.lower():
                st.warning(f"⚠️ {error}")
            else:
                st.error(f"❌ {error}")
        
        if rate:
            st.metric(
                label=f"{base} → {target}",
                value=f"{rate:.4f}",
                help=f"1 {base} = {rate:.4f} {target}"
            )
    
    with col2:
        if st.button("🔄 Refresh", help="Refresh exchange rate"):
            refresh_exchange_rates()
            st.rerun()


# ============================================================
# EXPORT
# ============================================================
__all__ = [
    "get_exchange_rate",
    "convert_amount",
    "normalize_currency_to_base",
    "get_rate_with_ui_feedback",
    "refresh_exchange_rates",
    "show_exchange_rate_widget",
    "FallbackRates",
]