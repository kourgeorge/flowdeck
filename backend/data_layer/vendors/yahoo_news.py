"""Yahoo Finance news search shared by app feeds and research workflows.

Ticker.news uses Yahoo's NCP endpoint, which returns 404. Call Finance Search with
our browser session; yfinance.Search's process-wide response cache has no news TTL.
Search provides recent results, not a historical news archive.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from .yf_session import get_yf_session

SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
CACHE_VERSION = "yahoo-search-v1"
SEARCH_TIMEOUT_SECONDS = 15


class YahooNewsError(RuntimeError):
    """The provider failed; distinct from a successful search with no articles."""


def parse_article(raw: Any) -> dict | None:
    """Normalize Search's flat items and the older nested Yahoo article format."""
    if not isinstance(raw, dict):
        return None
    nested = isinstance(raw.get("content"), dict)
    item = raw["content"] if nested else raw
    title = item.get("title")
    link = item.get("link")
    if nested:
        for field in ("canonicalUrl", "clickThroughUrl"):
            url = item.get(field)
            if isinstance(url, dict) and url.get("url"):
                link = url["url"]
                break
    if not isinstance(title, str) or not title.strip() or not isinstance(link, str) or not link:
        return None

    timestamp = 0
    try:
        if nested and item.get("pubDate"):
            dt = datetime.fromisoformat(item["pubDate"].replace("Z", "+00:00"))
            timestamp = int(dt.replace(tzinfo=dt.tzinfo or timezone.utc).timestamp())
        else:
            timestamp = int(item.get("providerPublishTime") or 0)
        published = datetime.fromtimestamp(timestamp, timezone.utc).isoformat() if timestamp else None
    except (ValueError, TypeError, OverflowError, OSError):
        timestamp, published = 0, None

    thumb = item.get("thumbnail")
    thumbnail = None
    if isinstance(thumb, dict):
        thumbnail = thumb.get("originalUrl")
        resolutions = thumb.get("resolutions")
        if not thumbnail and isinstance(resolutions, list) and resolutions:
            first = resolutions[0]
            thumbnail = first.get("url") if isinstance(first, dict) else None
    provider = item.get("provider")
    publisher = provider.get("displayName") if isinstance(provider, dict) else item.get("publisher")
    summary = item.get("summary") or item.get("description") or ""
    identity = raw.get("uuid") or raw.get("id") or item.get("id")
    return {
        "uuid": str(identity or hashlib.sha256(link.encode()).hexdigest()),
        "title": title.strip(),
        "summary": summary if isinstance(summary, str) else "",
        "publisher": publisher if isinstance(publisher, str) else "",
        "link": link,
        "published_time": published,
        "published_timestamp": timestamp,
        "type": item.get("contentType" if nested else "type") or "STORY",
        "thumbnail": thumbnail if isinstance(thumbnail, str) else None,
    }


def search_news(query: str, limit: int = 20) -> list[dict]:
    """Fetch fresh news. Transport/schema failures must never be cached as empty."""
    query = query.strip()
    if not query:
        raise ValueError("A news search query is required")
    try:
        response = get_yf_session().get(
            SEARCH_URL,
            params={"q": query, "newsCount": min(max(limit, 1), 50), "quotesCount": 0},
            timeout=SEARCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise YahooNewsError("Yahoo Finance news search is temporarily unavailable") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("news"), list):
        raise YahooNewsError("Yahoo Finance returned an invalid news search response")

    articles = {}
    for raw in payload["news"]:
        article = parse_article(raw)
        if article:
            articles.setdefault(article["uuid"], article)
    if payload["news"] and not articles:
        raise YahooNewsError("Yahoo Finance returned unrecognized news articles")
    return sorted(articles.values(), key=lambda a: a["published_timestamp"], reverse=True)[:limit]


def get_ticker_news(
    ticker: str, lookback_days: int = 7, *, start_date: str | None = None, end_date: str | None = None
) -> dict:
    ticker = ticker.strip().upper()
    now = datetime.now(timezone.utc)
    end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1) if end_date else now
    start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) if start_date else end - timedelta(days=lookback_days)
    if start >= end:
        raise ValueError("The news date range must have a start before its end")
    articles = [a for a in search_news(ticker) if start.timestamp() <= a["published_timestamp"] < end.timestamp()]
    return {
        "ticker": ticker, "date": now.date().isoformat(), "articles": articles, "count": len(articles),
        "source": "yahoo_finance_search", "coverage": "recent_news_only",
    }


def get_global_news_yahoo(curr_date: str, look_back_days: int = 7, limit: int = 10, query: str | None = None) -> str:
    """Search recent macro/market headlines using the same provider as ticker news."""
    end = datetime.strptime(curr_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
    start = end - timedelta(days=look_back_days)
    search_query = (query or "").strip() or "stock market"
    articles = [
        a for a in search_news(search_query, limit=max(limit, 20))
        if start.timestamp() <= a["published_timestamp"] < end.timestamp()
    ][:limit]
    lines = [f"## Global News (Yahoo Finance Search), through {curr_date}",
             "Recent search results only; historical coverage is not guaranteed.", ""]
    for article in articles:
        lines.extend([
            f"### {article['title']} ({article['publisher']}, {article['published_time']})",
            article["summary"], f"Source: {article['link']}", "",
        ])
    if not articles:
        lines.append("No recent articles matched this query and date range.")
    return "\n".join(lines)
