"""
Service to fetch news for the app.

Uses the standalone news fetcher (Yahoo or other provider). Same data is served to
the dashboard UI and to AI agents via the info API. No dependency on tradingagents.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.news_fetcher import get_news_yahoo


class NewsService:
    """Fetches news for the app (UI and info API)."""

    def get_news(
        self,
        ticker: str,
        vendor: Optional[str] = None,
        lookback_days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get news articles for a ticker.

        Args:
            ticker: Ticker symbol
            vendor: Ignored for now; only Yahoo is supported in-app. Kept for API compatibility.
            lookback_days: Number of days to look back (yfinance does not filter by date; used for future providers)

        Returns:
            Dict with ticker, date, articles, count (and optional error).
        """
        # App news API: single provider path. Yahoo only for now; others can be added in news_fetcher.
        return get_news_yahoo(ticker, lookback_days=lookback_days)
