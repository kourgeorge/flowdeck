"""
Data layer vendor implementations: yfinance, Alpha Vantage, reddit_online, etc.

Public API: get_ticker_data, get_indicators, get_global_news, get_insider_sentiment.
Vendor selection and fallback are implementation details.
"""

from .interface import (
    get_global_news,
    get_indicators,
    get_insider_sentiment,
    get_ticker_data,
)

__all__ = [
    "get_global_news",
    "get_indicators",
    "get_insider_sentiment",
    "get_ticker_data",
]
