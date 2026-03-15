"""
Info fetcher facade: returns the shared market data source (data layer).

Used by ai_engine modules (daily_digest, watchlist_consulting, portfolio_risk_profiler, etc.).
All market data goes through the data layer (cache + vendors).
"""

from __future__ import annotations

from typing import Any, Optional

_engine: Optional[Any] = None


def get_info_fetcher(
    market_data_service: Optional[Any] = None,
    news_service: Optional[Any] = None,
) -> Any:
    """Get the shared market data source (CachedMarketSource wrapping MarketDataLayer).
    market_data_service and news_service args are ignored; kept for backward compatibility."""
    global _engine
    if _engine is None:
        from data_layer.market import MarketDataLayer
        from data_layer.sources.market import CachedMarketSource
        _engine = CachedMarketSource(MarketDataLayer())
    return _engine
