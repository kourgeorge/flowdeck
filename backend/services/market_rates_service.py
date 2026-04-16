"""
Service for fetching market rates and economic indicators from FRED (Federal Reserve Economic Data).

Provides treasury rates, risk-free rates, and other economic indicators needed for valuation models.
Uses caching to minimize API calls and improve performance.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)

# FRED API configuration
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Cache for market rates (refresh daily)
_market_rates_cache: Optional[Dict[str, Any]] = None
_cache_timestamp: Optional[datetime] = None
_CACHE_DURATION_HOURS = 24


class MarketRatesService:
    """Service for fetching market rates from FRED API."""

    @staticmethod
    def _fetch_fred_series(series_id: str, limit: int = 1) -> Optional[float]:
        """
        Fetch the latest value from a FRED series.
        
        Args:
            series_id: FRED series ID (e.g., 'DGS10' for 10-year treasury)
            limit: Number of observations to fetch (default 1 for latest)
            
        Returns:
            Latest value as float (in decimal form, e.g., 0.043 for 4.3%), or None if error
        """
        if not FRED_API_KEY:
            logger.warning("FRED_API_KEY not configured, cannot fetch market rates")
            return None
            
        try:
            response = requests.get(
                FRED_BASE_URL,
                params={
                    "series_id": series_id,
                    "api_key": FRED_API_KEY,
                    "file_type": "json",
                    "limit": limit,
                    "sort_order": "desc"  # Get most recent first
                },
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            observations = data.get("observations", [])
            
            if not observations:
                logger.warning(f"No observations returned for FRED series {series_id}")
                return None
                
            value = observations[0].get("value")
            date = observations[0].get("date")
            
            # FRED returns "." for missing values
            if value is None or value == ".":
                logger.warning(f"Missing value for FRED series {series_id} on {date}")
                return None
                
            # Convert from percentage to decimal (e.g., "4.3" -> 0.043)
            rate = float(value) / 100.0
            logger.info(f"Fetched {series_id} = {rate:.4f} ({value}%) as of {date}")
            return rate
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching FRED series {series_id}: {e}")
            return None
        except (ValueError, KeyError) as e:
            logger.error(f"Error parsing FRED response for {series_id}: {e}")
            return None

    @staticmethod
    def _should_refresh_cache() -> bool:
        """Check if cache should be refreshed."""
        global _cache_timestamp
        
        if _cache_timestamp is None:
            return True
            
        age = datetime.now() - _cache_timestamp
        return age > timedelta(hours=_CACHE_DURATION_HOURS)

    @staticmethod
    def get_market_rates(force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get current market rates including treasury yields.
        
        Uses caching to minimize API calls. Cache refreshes every 24 hours.
        
        Args:
            force_refresh: Force cache refresh even if not expired
            
        Returns:
            Dictionary with market rates:
            {
                "risk_free_rate": float,  # 10-year treasury (standard for WACC)
                "treasury_10y": float,
                "treasury_2y": float,
                "treasury_3m": float,
                "last_updated": str (ISO format),
                "source": "FRED",
                "cache_age_hours": float
            }
        """
        global _market_rates_cache, _cache_timestamp
        
        # Return cached data if valid
        if not force_refresh and _market_rates_cache and not MarketRatesService._should_refresh_cache():
            if _cache_timestamp:
                cache_age = (datetime.now() - _cache_timestamp).total_seconds() / 3600
            else:
                cache_age = 0.0
            result = _market_rates_cache.copy()
            result["cache_age_hours"] = round(cache_age, 2)
            logger.debug(f"Returning cached market rates (age: {cache_age:.1f}h)")
            return result
        
        logger.info("Fetching fresh market rates from FRED")
        
        # Fetch treasury rates from FRED
        # DGS10 = 10-Year Treasury Constant Maturity Rate
        # DGS2 = 2-Year Treasury Constant Maturity Rate
        # DGS3MO = 3-Month Treasury Constant Maturity Rate
        treasury_10y = MarketRatesService._fetch_fred_series("DGS10")
        treasury_2y = MarketRatesService._fetch_fred_series("DGS2")
        treasury_3m = MarketRatesService._fetch_fred_series("DGS3MO")
        
        # Use 10-year as risk-free rate (standard for DCF/WACC)
        # Fallback to reasonable defaults if API fails
        risk_free_rate = treasury_10y if treasury_10y is not None else 0.045
        
        # Fetch VIX and calculate market risk premium
        vix = MarketRatesService.get_vix()
        market_risk_premium = MarketRatesService.calculate_market_risk_premium(vix)
        
        rates = {
            "risk_free_rate": risk_free_rate,
            "treasury_10y": treasury_10y if treasury_10y is not None else risk_free_rate,
            "treasury_2y": treasury_2y if treasury_2y is not None else risk_free_rate,
            "treasury_3m": treasury_3m if treasury_3m is not None else 0.050,
            "vix": vix,
            "market_risk_premium": market_risk_premium,
            "last_updated": datetime.now().isoformat(),
            "source": "FRED" if FRED_API_KEY else "fallback",
            "cache_age_hours": 0.0
        }
        
        # Update cache
        _market_rates_cache = rates.copy()
        _cache_timestamp = datetime.now()
        
        if not FRED_API_KEY:
            logger.warning("FRED_API_KEY not configured, using fallback rates")
        
        return rates

    @staticmethod
    def get_risk_free_rate() -> float:
        """
        Get current risk-free rate (10-year treasury).
        
        Convenience method for valuation calculations.
        
        Returns:
            Risk-free rate as decimal (e.g., 0.043 for 4.3%)
        """
        rates = MarketRatesService.get_market_rates()
        return rates["risk_free_rate"]

    @staticmethod
    def get_vix() -> Optional[float]:
        """
        Fetch current VIX (volatility index) level.
        
        VIX measures market volatility expectations and is used to calculate
        dynamic market risk premium for equity valuations.
        
        Returns:
            Current VIX level (e.g., 18.5), or None if unavailable
        """
        try:
            import yfinance as yf
            vix_ticker = yf.Ticker("^VIX")
            hist = vix_ticker.history(period="1d")
            
            if not hist.empty and 'Close' in hist.columns:
                vix_value = float(hist['Close'].iloc[-1])
                logger.info(f"Fetched VIX = {vix_value:.2f}")
                return vix_value
        except Exception as e:
            logger.error(f"Error fetching VIX: {e}")
        
        return None

    @staticmethod
    def calculate_market_risk_premium(vix: Optional[float] = None) -> float:
        """
        Calculate market risk premium based on VIX (volatility index).
        
        Uses empirical relationship between VIX and equity risk premium:
        - VIX < 15: Low volatility → 4.5-5.0% premium
        - VIX 15-25: Normal → 5.0-5.5% premium
        - VIX 25-35: Elevated → 5.5-6.5% premium
        - VIX > 35: High stress → 6.5-8.0% premium
        
        Args:
            vix: Current VIX level. If None, will fetch automatically.
            
        Returns:
            Market risk premium as decimal (e.g., 0.055 for 5.5%)
        """
        # Fetch VIX if not provided
        if vix is None:
            vix = MarketRatesService.get_vix()
        
        # Default to historical average if VIX unavailable
        if vix is None:
            logger.warning("VIX unavailable, using historical average market risk premium (5.5%)")
            return 0.055
        
        # VIX-based premium calculation
        if vix < 15:
            # Low volatility: below-average premium
            premium = 0.045 + (vix / 15) * 0.005  # 4.5-5.0%
        elif vix < 25:
            # Normal volatility: standard premium
            premium = 0.050 + ((vix - 15) / 10) * 0.005  # 5.0-5.5%
        elif vix < 35:
            # Elevated volatility: above-average premium
            premium = 0.055 + ((vix - 25) / 10) * 0.010  # 5.5-6.5%
        else:
            # High stress: maximum premium (capped at 8%)
            premium = min(0.065 + ((vix - 35) / 20) * 0.015, 0.080)  # 6.5-8.0%
        
        logger.info(f"Calculated market risk premium = {premium:.4f} ({premium*100:.2f}%) for VIX = {vix:.2f}")
        return premium

    @staticmethod
    def clear_cache() -> None:
        """Clear the market rates cache. Useful for testing or forcing refresh."""
        global _market_rates_cache, _cache_timestamp
        _market_rates_cache = None
        _cache_timestamp = None
        logger.info("Market rates cache cleared")

# Made with Bob
