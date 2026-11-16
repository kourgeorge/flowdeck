"""
Service for fetching market rates and economic indicators from FRED (Federal Reserve Economic Data).

Provides treasury rates, risk-free rates, and other economic indicators needed for valuation models.
Uses caching to minimize API calls and improve performance.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
import requests

logger = logging.getLogger(__name__)

# FRED API configuration
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


class MarketRatesService:
    """Service for fetching market rates from FRED API."""

    # Cache for market rates (refresh daily)
    _cache: Optional[Dict[str, Any]] = None
    _cache_timestamp: Optional[datetime] = None
    _CACHE_DURATION_HOURS = 24
    # A failed or partial FRED fetch is kept only briefly so we pick FRED back up
    # soon after it recovers, instead of serving gaps for a whole day.
    _FAILED_CACHE_DURATION_MINUTES = 15
    _cache_ttl: timedelta = timedelta(hours=_CACHE_DURATION_HOURS)

    @classmethod
    def _fetch_fred_series(
        cls, series_id: str, limit: int = 5, is_percentage: bool = True
    ) -> Optional[float]:
        """
        Fetch the latest valid observation from a FRED series.

        FRED daily series carry a "." value on market holidays and publish with a
        1-2 day lag, so several observations are scanned rather than just the newest.

        Args:
            series_id: FRED series ID (e.g., 'DGS10' for 10-year treasury)
            limit: Number of recent observations to scan for a valid value
            is_percentage: If True, convert percent to decimal (4.3 -> 0.043)

        Returns:
            Latest valid value, or None if unavailable
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

            # Scan newest-first for the first non-missing value (FRED uses "." for missing)
            for obs in observations:
                value = obs.get("value")
                date = obs.get("date")

                if value is None or value == ".":
                    continue

                parsed = float(value)
                result = parsed / 100.0 if is_percentage else parsed
                logger.info(f"Fetched {series_id} = {result:.4f} (raw: {value}) as of {date}")
                return result

            logger.warning(
                f"No valid observations in latest {limit} entries for FRED series {series_id}"
            )
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching FRED series {series_id}: {e}")
            return None
        except (ValueError, KeyError) as e:
            logger.error(f"Error parsing FRED response for {series_id}: {e}")
            return None

    @classmethod
    def _should_refresh_cache(cls) -> bool:
        """Check if cache should be refreshed."""
        if cls._cache_timestamp is None:
            return True

        age = datetime.now(timezone.utc) - cls._cache_timestamp
        return age > cls._cache_ttl

    @classmethod
    def get_market_rates(cls, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get current market rates including treasury yields.

        A full FRED success is cached for 24 hours. A partial or failed fetch is
        cached only for a few minutes so we retry soon after FRED recovers.

        Args:
            force_refresh: Force cache refresh even if not expired

        Returns:
            Dictionary with market rates:
            {
                "risk_free_rate": float | None,  # 10-year treasury (standard for WACC)
                "treasury_10y": float | None,
                "treasury_2y": float | None,
                "treasury_3m": float | None,
                "vix": float | None,
                "market_risk_premium": float,
                "last_updated": str (ISO format, UTC),
                "source": "FRED" | "partial" | "unavailable",
                "field_sources": {field: "FRED" | "yfinance" | ... | None},
                "cache_age_hours": float
            }
        """
        now = datetime.now(timezone.utc)

        # Return cached data if valid
        if not force_refresh and cls._cache and not cls._should_refresh_cache():
            if cls._cache_timestamp:
                cache_age = (now - cls._cache_timestamp).total_seconds() / 3600
            else:
                cache_age = 0.0
            result = cls._cache.copy()
            result["field_sources"] = dict(result.get("field_sources") or {})
            result["cache_age_hours"] = round(cache_age, 2)
            logger.debug(f"Returning cached market rates (age: {cache_age:.1f}h)")
            return result

        logger.info("Fetching fresh market rates from FRED")

        # DGS10 = 10-Year, DGS2 = 2-Year, DGS3MO = 3-Month Treasury Constant Maturity Rate
        treasury_10y = cls._fetch_fred_series("DGS10")
        treasury_2y = cls._fetch_fred_series("DGS2")
        treasury_3m = cls._fetch_fred_series("DGS3MO")

        # No made-up defaults and no copying one maturity into another: when FRED
        # timed out we used to return 0.045/0.045/0.045/0.05 labelled "FRED" and
        # cache it for a day. A missing yield is now None, and callers decide.
        rate_fields = {
            "risk_free_rate": treasury_10y,  # 10-year is the standard WACC/DCF risk-free rate
            "treasury_10y": treasury_10y,
            "treasury_2y": treasury_2y,
            "treasury_3m": treasury_3m,
        }
        field_sources: Dict[str, Optional[str]] = {
            name: ("FRED" if value is not None else None) for name, value in rate_fields.items()
        }

        vix, vix_source = cls._get_vix_with_source()
        market_risk_premium = cls.calculate_market_risk_premium(vix)
        field_sources["vix"] = vix_source
        # The premium always has a value; say whether it came from VIX or is the
        # historical-average assumption used when VIX is missing.
        field_sources["market_risk_premium"] = (
            "derived_from_vix" if vix is not None else "historical_average_assumption"
        )

        # The overall label describes the treasury yields, which are what this
        # endpoint advertises as "from FRED".
        fred_count = sum(1 for v in rate_fields.values() if v is not None)
        if fred_count == len(rate_fields):
            source = "FRED"
        elif fred_count > 0:
            source = "partial"
        else:
            source = "unavailable"

        rates = {
            **rate_fields,
            "vix": vix,
            "market_risk_premium": market_risk_premium,
            "last_updated": now.isoformat(),
            "source": source,
            "field_sources": field_sources,
            "cache_age_hours": 0.0,
        }

        cls._cache = {**rates, "field_sources": dict(field_sources)}
        cls._cache_timestamp = now
        cls._cache_ttl = (
            timedelta(hours=cls._CACHE_DURATION_HOURS)
            if source == "FRED"
            else timedelta(minutes=cls._FAILED_CACHE_DURATION_MINUTES)
        )

        if not FRED_API_KEY:
            logger.warning("FRED_API_KEY not configured, market rates unavailable")
        elif source != "FRED":
            logger.warning(
                f"FRED returned {fred_count}/{len(rate_fields)} rate fields; "
                f"caching for {cls._FAILED_CACHE_DURATION_MINUTES} min only"
            )

        return rates

    @classmethod
    def get_risk_free_rate(cls) -> Optional[float]:
        """
        Get current risk-free rate (10-year treasury) from FRED.

        Returns:
            Risk-free rate as decimal (e.g., 0.043 for 4.3%), or None if FRED
            did not return it.
        """
        rates = cls.get_market_rates()
        return rates["risk_free_rate"]

    @classmethod
    def _get_vix_with_source(cls) -> Tuple[Optional[float], Optional[str]]:
        # Primary source is FRED's VIXCLS (prior-day close, same pipeline as the
        # treasury rates); yfinance is the fallback when FRED is down or unkeyed.
        # VIX is an index level, not a percentage rate, so no /100 conversion
        vix = cls._fetch_fred_series("VIXCLS", is_percentage=False)
        if vix is not None:
            return vix, "FRED"
        vix = cls._fetch_vix_from_yfinance()
        if vix is not None:
            return vix, "yfinance"
        return None, None

    @classmethod
    def _fetch_vix_from_yfinance(cls) -> Optional[float]:
        try:
            import yfinance as yf
            from data_layer.vendors.yf_session import close_orphaned_price_history_session, get_yf_session
            vix_ticker = yf.Ticker("^VIX", session=get_yf_session())
            hist = vix_ticker.history(period="1d")
            close_orphaned_price_history_session(vix_ticker)

            if not hist.empty and 'Close' in hist.columns:
                vix_value = float(hist['Close'].iloc[-1])
                logger.info(f"Fetched VIX = {vix_value:.2f} (yfinance fallback)")
                return vix_value
        except Exception as e:
            logger.error(f"Error fetching VIX from yfinance fallback: {e}")

        return None

    @classmethod
    def calculate_market_risk_premium(cls, vix: Optional[float] = None) -> float:
        """
        Calculate market risk premium based on VIX (volatility index).
        
        Uses empirical relationship between VIX and equity risk premium:
        - VIX < 15: Low volatility → 4.5-5.0% premium
        - VIX 15-25: Normal → 5.0-5.5% premium
        - VIX 25-35: Elevated → 5.5-6.5% premium
        - VIX > 35: High stress → 6.5-8.0% premium
        
        Args:
            vix: Current VIX level, or None when it could not be fetched.

        Returns:
            Market risk premium as decimal (e.g., 0.055 for 5.5%)
        """
        # No fetching here: get_market_rates already tried FRED and yfinance, and
        # a second lookup both doubled the slow calls when VIX was down and could
        # price the premium off a VIX the response reports as None.
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

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the market rates cache. Useful for testing or forcing refresh."""
        cls._cache = None
        cls._cache_timestamp = None
        cls._cache_ttl = timedelta(hours=cls._CACHE_DURATION_HOURS)
        logger.info("Market rates cache cleared")

# Made with Bob
