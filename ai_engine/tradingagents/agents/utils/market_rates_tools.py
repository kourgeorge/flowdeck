"""
Tools for fetching market rates and economic indicators for valuation models.
"""

from langchain_core.tools import tool
import json

from ...datasources.info_service_client import (
    get_market_rates as get_market_rates_via_service,
    require_info_service,
)

_RATE_FIELDS = (
    "risk_free_rate",
    "treasury_10y",
    "treasury_2y",
    "treasury_3m",
    "vix",
    "market_risk_premium",
)


@tool
def get_market_rates() -> str:
    """
    Retrieve current market rates including treasury yields and risk-free rate.

    Essential for valuation models (DCF, WACC calculations).
    Treasury yields come from FRED (Federal Reserve Economic Data) when it is
    reachable. A full FRED success is cached for 24 hours; a partial or failed
    fetch is cached for about 15 minutes. Any rate that could not be fetched is
    null - never a default value.

    Returns:
        str: JSON string containing:
        - risk_free_rate: 10-year treasury rate (standard for WACC/DCF), or null
        - treasury_10y: 10-year treasury constant maturity rate, or null
        - treasury_2y: 2-year treasury constant maturity rate, or null
        - treasury_3m: 3-month treasury constant maturity rate, or null
        - vix, market_risk_premium: volatility index and equity risk premium, or null
        - last_updated: ISO timestamp of last update, or null
        - source: "FRED" (all yields from FRED), "partial" (some yields missing)
          or "unavailable" (no rates could be fetched)
        - field_sources: where each field came from (null when missing)
        - cache_age_hours: Age of cached data in hours
        - note: present when source is "unavailable"

    If source is "unavailable" or a rate is null, do not state a current value
    for it; say the rate is unavailable instead.

    Example:
        {
            "risk_free_rate": 0.043,
            "treasury_10y": 0.043,
            "treasury_2y": 0.045,
            "treasury_3m": 0.052,
            "last_updated": "2026-04-15T10:30:00+00:00",
            "source": "FRED",
            "field_sources": {"risk_free_rate": "FRED", "treasury_10y": "FRED", ...},
            "cache_age_hours": 2.5
        }
    """
    require_info_service()

    rates = get_market_rates_via_service()

    if rates is None:
        # get_market_rates turns every error, including a timeout, into None.
        # We used to answer with 0.045/0.045/0.045/0.05 here, which the analyst
        # then quoted as current FRED yields. Report honest emptiness instead.
        return json.dumps({
            **{name: None for name in _RATE_FIELDS},
            "last_updated": None,
            "source": "unavailable",
            "field_sources": {name: None for name in _RATE_FIELDS},
            "cache_age_hours": None,
            "note": (
                "Market rates could not be fetched. Do not state current "
                "treasury yields or a risk-free rate; say they are unavailable."
            ),
        }, indent=2)

    # Partial data (some fields None, per-field sources) passes through as is.
    return json.dumps(rates, indent=2)
