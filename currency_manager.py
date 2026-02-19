# currency_manager.py
"""
Currency conversion with robust error handling and multiple fallback strategies.
"""
import requests
import streamlit as st
from typing import Tuple, Optional, Dict
from datetime import datetime, timedelta
from config import CACHE_TTL_LONG, SUPPORTED_CURRENCIES
from error_handler import (
    NetworkErrorHandler,
    ErrorHandler,
    retry_on_failure,
    handle_errors,
    logger
)


# ============================================================
# EXCHANGE RATE CACHE
# ============================================================
class ExchangeRateCache:
    """Simple in-memory cache for exchange rates."""
    
    _cache: Dict[str, Tuple[float, datetime]] = {}
    _cache_duration = timedelta(hours=1)
    
    @classmethod
    def get(cls, key: str) -> Optional[float]:
        """Get cached rate if not expired."""
        if key in cls._cache:
            rate, timestamp = cls._cache[key]
            if datetime.now() - timestamp < cls._cache_duration:
                logger.debug(f"Using cached rate for {key}: {rate}")
                return rate
            else:
                logger.debug(f"Cache expired for {key}")
                del cls._cache[key]
        return None
    
    @classmethod
    def set(cls, key: str, rate: float):
        """Cache exchange rate."""
        cls._cache[key] = (rate, datetime.now())
        logger.debug(f"Cached rate for {key}: {rate}")
    
    @classmethod
    def clear(cls):
        """Clear all cached rates."""
        cls._cache.clear()
        logger.info("Exchange rate cache cleared")


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
@st.cache_data(ttl=CACHE_TTL_LONG, show_spinner=False)
def get_exchange_rate(
    base: str = "INR",
    target: str = "SEK",
    use_cache: bool = True,
    use_fallback: bool = True
) -> Tuple[Optional[float], Optional[str]]:
    """
    Get exchange rate with comprehensive error handling and fallback strategies.
    
    Args:
        base: Base currency code (e.g., "INR")
        target: Target currency code (e.g., "SEK")
        use_cache: Whether to use cached rates
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
    
    # Check cache first
    if use_cache:
        cache_key = f"{base}_{target}"
        cached_rate = ExchangeRateCache.get(cache_key)
        if cached_rate is not None:
            return cached_rate, None
    
    # Try to get rate from API
    provider = ExchangeRateHostProvider()
    rate, error = provider.get_rate(base, target)
    
    if rate is not None:
        # Success - cache the rate
        if use_cache:
            ExchangeRateCache.set(cache_key, rate)
        return rate, None
    
    # API failed - try fallback
    if use_fallback:
        fallback_rate = FallbackRates.get(base, target)
        if fallback_rate is not None:
            warning_msg = f"Using approximate fallback rate (API unavailable: {error})"
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
    ExchangeRateCache.clear()
    st.cache_data.clear()
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
    "get_rate_with_ui_feedback",
    "refresh_exchange_rates",
    "show_exchange_rate_widget",
    "ExchangeRateCache",
    "FallbackRates",
]