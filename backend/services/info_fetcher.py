"""
Info fetcher facade: returns the shared market data source (data layer).

Used by ai_engine modules (daily_digest, watchlist_consulting, portfolio_risk_profiler, etc.).
All market data goes through the data layer (cache + vendors).
"""

from __future__ import annotations

from typing import Any, Optional

_engine: Optional[Any] = None


def get_info_fetcher() -> Any:
    """Get the shared market data source (MarketDataLayer)."""
    global _engine
    if _engine is None:
        from data_layer.market import MarketDataLayer
        _engine = MarketDataLayer()
    return _engine
