"""Compatibility entry point using the same cached Yahoo search as all app feeds."""

from data_layer.vendors.yahoo_news import parse_article as _parse_yf_article


def get_news_yahoo(ticker: str, lookback_days: int = 7) -> dict:
    from data_layer.market import MarketDataLayer

    return MarketDataLayer().get_news(ticker, lookback_days=lookback_days)
