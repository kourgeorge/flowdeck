"""
Tools for fetching market rates and economic indicators for valuation models.
"""

from langchain_core.tools import tool
from typing import Annotated
import json

from ...datasources.info_service_client import (
    get_market_rates as get_market_rates_via_service,
    require_info_service,
)


@tool
def get_market_rates() -> str:
    """
    Retrieve current market rates including treasury yields and risk-free rate.
    
    Essential for valuation models (DCF, WACC calculations).
    Data is fetched from FRED (Federal Reserve Economic Data) and cached for 24 hours.
    
    Returns:
        str: JSON string containing:
        - risk_free_rate: 10-year treasury rate (standard for WACC/DCF)
        - treasury_10y: 10-year treasury constant maturity rate
        - treasury_2y: 2-year treasury constant maturity rate
        - treasury_3m: 3-month treasury constant maturity rate
        - last_updated: ISO timestamp of last update
        - source: Data source (FRED)
        - cache_age_hours: Age of cached data in hours
        
    Example:
        {
            "risk_free_rate": 0.043,
            "treasury_10y": 0.043,
            "treasury_2y": 0.045,
            "treasury_3m": 0.052,
            "last_updated": "2026-04-15T10:30:00",
            "source": "FRED",
            "cache_age_hours": 2.5
        }
    """
    require_info_service()
    
    rates = get_market_rates_via_service()
    
    if rates is None:
        # Fallback if service unavailable
        return json.dumps({
            "risk_free_rate": 0.045,
            "treasury_10y": 0.045,
            "treasury_2y": 0.045,
            "treasury_3m": 0.050,
            "last_updated": None,
            "source": "fallback",
            "cache_age_hours": 0.0,
            "note": "Using fallback rates - FRED API unavailable"
        })
    
    return json.dumps(rates, indent=2)

# Made with Bob
