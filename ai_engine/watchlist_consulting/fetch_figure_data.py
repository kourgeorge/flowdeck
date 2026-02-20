"""
Fetch data for report figures using the same sources as Market and Fundamentals analysts.
Uses backend services only (no tradingagents imports): historical OHLCV, fundamentals, financial-charts.
"""

from __future__ import annotations

from typing import Any, Dict, List

try:
    from services.info_fetcher import get_info_fetcher
except ImportError:
    get_info_fetcher = None  # type: ignore


def _get_fetcher():
    if get_info_fetcher is None:
        raise RuntimeError("fetch_figure_data requires backend on sys.path")
    return get_info_fetcher()


def fetch_historical(ticker: str, period: str = "6mo", interval: str = "1d") -> Dict[str, Any]:
    """Fetch OHLCV time series (same data as Market Analyst's get_stock_data / backend historical)."""
    fetcher = _get_fetcher()
    return fetcher.get_historical(ticker.upper(), period=period, interval=interval)


def fetch_fundamentals(ticker: str) -> Dict[str, Any]:
    """Fetch fundamentals (same data as Fundamentals Analyst's get_fundamentals)."""
    fetcher = _get_fetcher()
    return fetcher.get_fundamentals(ticker.upper())


def fetch_financial_charts(ticker: str, freq: str = "annual") -> Dict[str, Any]:
    """Fetch chart-ready fundamental series (revenue, EPS, etc.)."""
    fetcher = _get_fetcher()
    return fetcher.get_financial_charts(ticker.upper(), freq=freq)


def fetch_figure_data_for_tickers(
    tickers: List[str],
    *,
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
    fetcher = _get_fetcher()

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
