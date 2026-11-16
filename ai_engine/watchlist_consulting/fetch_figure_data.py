"""
Fetch data for report figures using the same sources as Market and Fundamentals analysts.
No tradingagents imports: historical OHLCV, fundamentals, financial-charts.

The data source (the backend's info fetcher) is passed in by the caller. ai_engine may
not import backend services (backend -> ai_engine only); see
backend/services/watchlist_report_service.py, which builds and passes it.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _require(fetcher: Any) -> Any:
    if fetcher is None:
        raise RuntimeError("fetch_figure_data needs a fetcher (pass get_info_fetcher() from the backend)")
    return fetcher


def fetch_figure_data_for_tickers(
    tickers: List[str],
    *,
    fetcher: Any,
    include_historical: bool = True,
    include_fundamentals: bool = True,
    include_financial_charts: bool = True,
    historical_period: str = "6mo",
    financial_charts_freq: str = "annual",
) -> Dict[str, Dict[str, Any]]:
    """
    For each ticker, fetch historical, fundamentals, and/or financial-charts.
    Returns dict: ticker -> { "historical": {...}, "fundamentals": {...}, "financial_charts": {...} }.
    Missing or failed fetches are omitted or have an "error" key.
    """
    result: Dict[str, Dict[str, Any]] = {}
    fetcher = _require(fetcher)

    for ticker in tickers:
        t = ticker.upper()
        result[t] = {}

        if include_historical:
            try:
                result[t]["historical"] = fetcher.get_historical(t, period=historical_period, interval="1d")
            except Exception as e:
                result[t]["historical"] = {"ticker": t, "data": [], "count": 0, "error": str(e)}

        if include_fundamentals:
            try:
                result[t]["fundamentals"] = fetcher.get_fundamentals(t)
            except Exception as e:
                result[t]["fundamentals"] = {"ticker": t, "fundamentals": {}, "error": str(e)}

        if include_financial_charts:
            try:
                result[t]["financial_charts"] = fetcher.get_financial_charts(t, freq=financial_charts_freq)
            except Exception as e:
                result[t]["financial_charts"] = {"ticker": t, "error": str(e)}

    return result
