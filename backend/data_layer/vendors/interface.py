import logging
from typing import Annotated, Optional

# Import from vendor-specific modules
from .reddit_utils import get_reddit_global_news_online, get_reddit_company_social_online
from .y_finance import get_YFin_data_online, get_stock_stats_indicators_window, get_balance_sheet as get_yfinance_balance_sheet, get_cashflow as get_yfinance_cashflow, get_income_statement as get_yfinance_income_statement, get_insider_transactions as get_yfinance_insider_transactions, get_fundamentals as get_yfinance_fundamentals, get_yfinance_news
from .google import get_google_news, get_global_news_google
from .openai import get_stock_news_openai, get_global_news_openai, get_fundamentals_openai
from .serpapi_news import get_global_news_serpapi
from .alpha_vantage import (
    get_stock as get_alpha_vantage_stock,
    get_indicator as get_alpha_vantage_indicator,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_income_statement as get_alpha_vantage_income_statement,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news
)
from .alpha_vantage_common import AlphaVantageRateLimitError

# Configuration and routing logic
from .config import get_config

logger = logging.getLogger(__name__)

METHOD_ALIASES = {
    # Backward compatibility after stock->ticker rename.
    "get_stock_data": "get_ticker_data",
}

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_ticker_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "News (public/insiders, original/processed)",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_sentiment",
            "get_insider_transactions",
        ]
    }
}

VENDOR_LIST = [
    "yfinance",
    "openai",
    "google",
]

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_ticker_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
    },
    # fundamental_data
    "get_fundamentals": {
        # "alpha_vantage": get_alpha_vantage_fundamentals,  # Commented out - not using Alpha Vantage for fundamentals
        # "openai": get_fundamentals_openai,
        "yfinance": get_yfinance_fundamentals,
    },
    "get_balance_sheet": {
        "yfinance": get_yfinance_balance_sheet,
    },
    "get_cashflow": {
        "yfinance": get_yfinance_cashflow,
    },
    "get_income_statement": {
        "yfinance": get_yfinance_income_statement,
    },
    # news_data
    "get_news": {
        "alpha_vantage": get_alpha_vantage_news,
        "openai": get_stock_news_openai,
        "google": get_google_news,
        "yfinance": get_yfinance_news,
        "reddit_online": get_reddit_company_social_online,
    },
    "get_global_news": {
        "serpapi": get_global_news_serpapi,
        "openai": get_global_news_openai,
        "google": get_global_news_google,
        "reddit_online": get_reddit_global_news_online,
    },
    "get_insider_sentiment": {},
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
    },
}

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    method = METHOD_ALIASES.get(method, method)
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

def _backend_supports_openai_responses_api() -> bool:
    """Check if the configured backend supports OpenAI's Responses API.
    
    The Responses API (client.responses.create()) is only available on
    OpenAI's official API endpoint. Other backends (Azure, Ollama, Anthropic, etc.)
    do not support this API.
    """
    config = get_config()
    backend_url = config.get("backend_url", "")
    
    # Only OpenAI's official API supports the Responses API
    return backend_url == "https://api.openai.com/v1"

def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        method = METHOD_ALIASES.get(method, method)
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "yfinance")

def _route(method: str, *args, **kwargs):
    """Internal: route to configured vendor with fallback. Not part of the public API."""
    method = METHOD_ALIASES.get(method, method)
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)

    # Handle comma-separated vendors
    primary_vendors = [v.strip() for v in vendor_config.split(',')]

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    # Get all available vendors for this method for fallback
    all_available_vendors = list(VENDOR_METHODS[method].keys())
    
    # Filter out "openai" vendor if backend doesn't support OpenAI Responses API
    # The OpenAI dataflow functions use responses.create() which is only available
    # on OpenAI's official API endpoint
    if not _backend_supports_openai_responses_api():
        if "openai" in all_available_vendors:
            all_available_vendors.remove("openai")
            logger.info("Skipping 'openai' vendor for %s - backend does not support OpenAI Responses API", method)
        if "openai" in primary_vendors:
            primary_vendors.remove("openai")
            logger.info("Removing 'openai' from primary vendors for %s - backend does not support OpenAI Responses API", method)
    
    # Create fallback vendor list: primary vendors first, then remaining vendors as fallbacks
    fallback_vendors = primary_vendors.copy()
    for vendor in all_available_vendors:
        if vendor not in fallback_vendors:
            fallback_vendors.append(vendor)

    # Debug: log fallback ordering
    primary_str = " → ".join(primary_vendors)
    fallback_str = " → ".join(fallback_vendors)
    logger.debug("%s - Primary: [%s] | Full fallback order: [%s]", method, primary_str, fallback_str)

    # Track results and execution state
    results = []
    vendor_attempt_count = 0
    any_primary_vendor_attempted = False
    successful_vendor = None
    vendor_errors = []  # Track errors for better error messages

    for vendor in fallback_vendors:
        if vendor not in VENDOR_METHODS[method]:
            if vendor in primary_vendors:
                logger.info("Vendor '%s' not supported for method '%s', falling back to next vendor", vendor, method)
            continue

        vendor_impl = VENDOR_METHODS[method][vendor]
        is_primary_vendor = vendor in primary_vendors
        vendor_attempt_count += 1

        # Track if we attempted any primary vendor
        if is_primary_vendor:
            any_primary_vendor_attempted = True

        # Debug: log current attempt
        vendor_type = "PRIMARY" if is_primary_vendor else "FALLBACK"
        logger.debug("Attempting %s vendor '%s' for %s (attempt #%s)", vendor_type, vendor, method, vendor_attempt_count)

        # Handle list of methods for a vendor
        if isinstance(vendor_impl, list):
            vendor_methods = [(impl, vendor) for impl in vendor_impl]
            logger.debug("Vendor '%s' has multiple implementations: %s functions", vendor, len(vendor_methods))
        else:
            vendor_methods = [(vendor_impl, vendor)]

        # Run methods for this vendor
        vendor_results = []
        for impl_func, vendor_name in vendor_methods:
            try:
                logger.debug("Calling %s from vendor '%s'...", impl_func.__name__, vendor_name)
                result = impl_func(*args, **kwargs)
                vendor_results.append(result)
                logger.info("%s from vendor '%s' completed successfully", impl_func.__name__, vendor_name)

            except AlphaVantageRateLimitError as e:
                if vendor == "alpha_vantage":
                    logger.warning("Alpha Vantage rate limit exceeded, falling back to next available vendor")
                    logger.debug("Rate limit details: %s", e)
                vendor_errors.append(f"{vendor_name}: {type(e).__name__}: {str(e)}")
                # Continue to next vendor for fallback
                continue
            except Exception as e:
                # Log error but continue with other implementations
                error_msg = f"{impl_func.__name__} from vendor '{vendor_name}' failed: {type(e).__name__}: {str(e)}"
                logger.warning("FAILED: %s", error_msg)
                vendor_errors.append(f"{vendor_name}: {type(e).__name__}: {str(e)}")
                continue

        # Add this vendor's results
        if vendor_results:
            # For string-returning news methods, treat empty/whitespace as no result and try next vendor
            if method in ("get_global_news", "get_news") and len(vendor_results) == 1:
                single = vendor_results[0]
                if isinstance(single, str) and not single.strip():
                    logger.info(
                        "Vendor '%s' returned empty for %s, trying next vendor",
                        vendor,
                        method,
                    )
                    continue
            results.extend(vendor_results)
            successful_vendor = vendor
            result_summary = f"Got {len(vendor_results)} result(s)"
            logger.info("Vendor '%s' succeeded - %s", vendor, result_summary)

            # Stopping logic: Stop after first successful vendor for single-vendor configs
            # Multiple vendor configs (comma-separated) may want to collect from multiple sources
            if len(primary_vendors) == 1:
                logger.debug("Stopping after successful vendor '%s' (single-vendor config)", vendor)
                break
        else:
            logger.warning("Vendor '%s' produced no results", vendor)

    # Final result summary
    if not results:
        logger.error("FAILURE: All %s vendor attempts failed for method '%s'", vendor_attempt_count, method)
        # For news methods, return a clear message instead of raising so the UI/LLM get something
        if method == "get_global_news":
            return (
                "No global news could be retrieved from the configured sources (Google, OpenAI, or Reddit). "
                "Possible causes: Google News scrape returned no results, OpenAI Responses API not in use or returned empty, "
                "or Reddit not configured. Check backend logs for which vendor was tried and any errors."
            )
        if method == "get_news":
            return (
                "No company news could be retrieved for the given ticker and date range. "
                "Check that the configured news vendor (OpenAI, Google, etc.) is set up and returning data."
            )
        error_details = "\n".join(f"  - {err}" for err in vendor_errors) if vendor_errors else "  (No detailed error information available)"
        error_message = (
            f"All vendor implementations failed for method '{method}'. "
            f"Attempted {vendor_attempt_count} vendor(s).\n"
            f"Errors:\n{error_details}"
        )
        raise RuntimeError(error_message)
    else:
        logger.info("Method '%s' completed with %s result(s) from %s vendor attempt(s)", method, len(results), vendor_attempt_count)

    # Return single result if only one, otherwise concatenate as string
    if len(results) == 1:
        return results[0]
    else:
        # Convert all results to strings and concatenate
        return '\n'.join(str(result) for result in results)


# --- Public domain API: callers use these, not _route ---

def get_ticker_data(ticker: str, start_date: str, end_date: str) -> str:
    """OHLCV time series for a ticker. Vendor selection and fallback are internal."""
    return _route("get_ticker_data", ticker.upper(), start_date, end_date)


def get_indicators(
    ticker: str,
    indicator: str,
    curr_date: str,
    look_back_days: int = 30,
) -> str:
    """Technical indicators (RSI, MACD, etc.). Vendor selection and fallback are internal."""
    return _route("get_indicators", ticker.upper(), indicator, curr_date, look_back_days)


def get_global_news(
    curr_date: str,
    lookback_days: int = 7,
    limit: int = 10,
    query: Optional[str] = None,
) -> str:
    """Global/macro news. Vendor selection and fallback are internal."""
    return _route("get_global_news", curr_date, lookback_days, limit, query=query)


def get_insider_sentiment(ticker: str, curr_date: str) -> str:
    """Insider sentiment for a ticker. Vendor selection and fallback are internal."""
    return _route("get_insider_sentiment", ticker.upper(), curr_date)
