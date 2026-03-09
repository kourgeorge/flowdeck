"""
Standalone news fetcher for the app.

Used by both the dashboard UI and the /api/data/news endpoint. AI agents get news
via the info service client calling this same app API. No dependency on tradingagents.

Provider: Yahoo Finance (yfinance). Other providers can be added here later.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

import yfinance as yf

logger = logging.getLogger(__name__)


def _parse_yf_article(raw: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    Parse one yfinance news item into our API shape.
    Supports current format (id + content) and legacy flat format (uuid, title, link, ...).
    """
    # Current yfinance format: { "id": "...", "content": { "title", "pubDate", "provider", ... } }
    content = raw.get("content")
    if isinstance(content, dict):
        uuid = raw.get("id") or content.get("id", "")
        title = content.get("title", "")
        link = ""
        for key in ("canonicalUrl", "clickThroughUrl"):
            u = content.get(key)
            if isinstance(u, dict) and u.get("url"):
                link = u["url"]
                break
        provider = content.get("provider")
        publisher = provider.get("displayName", "") if isinstance(provider, dict) else ""
        pub_date_str = content.get("pubDate") or ""
        published_time = pub_date_str[:19].replace("T", " ") if pub_date_str else None
        published_timestamp = 0
        if pub_date_str:
            try:
                # Parse ISO format e.g. 2026-02-05T18:30:00Z
                s = pub_date_str.replace("Z", "+00:00")
                dt = datetime.fromisoformat(s[:26])  # ignore fractional seconds
                published_timestamp = int(dt.timestamp())
            except Exception:
                pass
        thumb = content.get("thumbnail")
        thumb_url = None
        if isinstance(thumb, dict):
            thumb_url = thumb.get("originalUrl")
            if not thumb_url:
                resolutions = thumb.get("resolutions") or []
                first = resolutions[0] if resolutions else None
                if isinstance(first, dict):
                    thumb_url = first.get("url")
        summary = content.get("summary") or content.get("description") or ""
        return {
            "uuid": str(uuid),
            "title": title or "",
            "summary": summary if isinstance(summary, str) else "",
            "publisher": publisher or "",
            "link": link or "",
            "published_time": published_time,
            "published_timestamp": published_timestamp,
            "type": content.get("contentType", ""),
            "thumbnail": thumb_url,
        }
    # Legacy flat format
    pub_time = raw.get("providerPublishTime", 0)
    pub_date = (
        datetime.fromtimestamp(pub_time).strftime("%Y-%m-%d %H:%M:%S")
        if pub_time
        else None
    )
    thumb = raw.get("thumbnail")
    thumb_url = None
    if thumb and isinstance(thumb, dict):
        resolutions = thumb.get("resolutions") or []
        first = resolutions[0] if resolutions else None
        if isinstance(first, dict):
            thumb_url = first.get("url")
        elif isinstance(first, str):
            thumb_url = first
    summary = raw.get("summary") or raw.get("description") or ""
    return {
        "uuid": raw.get("uuid", raw.get("id", "")),
        "title": raw.get("title", ""),
        "summary": summary if isinstance(summary, str) else "",
        "publisher": raw.get("publisher", ""),
        "link": raw.get("link", ""),
        "published_time": pub_date,
        "published_timestamp": pub_time,
        "type": raw.get("type", ""),
        "thumbnail": thumb_url,
    }


def get_news_yahoo(ticker: str, lookback_days: int = 7) -> Dict[str, Any]:
    """
    Fetch news for a ticker from Yahoo Finance.

    Returns the same shape expected by the UI and info API:
    { "ticker", "date", "articles": [...], "count" }.
    Each article has: uuid, title, publisher, link, published_time, published_timestamp, type, thumbnail.
    """
    ticker = ticker.upper()
    curr_date = datetime.now().strftime("%Y-%m-%d")
    try:
        ticker_obj = yf.Ticker(ticker)
        news = ticker_obj.news
    except Exception as e:
        logger.warning("Unable to fetch news for %s: %s", ticker, e, exc_info=True)
        return {
            "ticker": ticker,
            "date": curr_date,
            "articles": [],
            "count": 0,
            "error": str(e),
        }

    if not news:
        logger.info("No news returned for %s (Yahoo returned empty list)", ticker)
        return {
            "ticker": ticker,
            "date": curr_date,
            "articles": [],
            "count": 0,
        }

    articles: List[Dict[str, Any]] = []
    for raw in news:
        item = _parse_yf_article(raw)
        if item:
            articles.append(item)

    return {
        "ticker": ticker,
        "date": curr_date,
        "articles": articles,
        "count": len(articles),
    }
