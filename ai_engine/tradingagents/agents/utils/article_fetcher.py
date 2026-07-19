"""
Best-effort full-text fetching for news articles.

Scoped intentionally to the News & Sentiment analyst's ``get_news`` tool only
(see ``news_data_tools.get_news``). The shared backend ``/api/data/news``
endpoint is deliberately NOT touched, so the UI, digests and batch paths keep
receiving only headline + summary; the full article body is fetched here, in
the agent process, and attached to each article as a ``content`` field.

Everything here is best-effort: any failure (paywall, bot-block, timeout, non-
HTML, extraction miss) degrades silently to no ``content``, leaving the article
with its original ``title``/``summary`` intact.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:  # pragma: no cover - httpx is a hard dep elsewhere
    httpx = None  # type: ignore

# Preferred extractor; falls back to BeautifulSoup if unavailable.
try:
    import trafilatura  # type: ignore
except ImportError:
    trafilatura = None  # type: ignore

logger = logging.getLogger(__name__)

# --- Tunables (env-overridable, sensible defaults) ---------------------------
# Master switch: set NEWS_FETCH_FULL_TEXT=0 to disable and fall back to summaries only.
_ENABLED = (os.getenv("NEWS_FETCH_FULL_TEXT", "1").strip().lower() not in ("0", "false", "no"))
# Only fetch bodies for the first N articles to bound latency and token cost.
_MAX_ARTICLES = int(os.getenv("NEWS_FETCH_MAX_ARTICLES", "10"))
# Parallel fetches.
_MAX_WORKERS = int(os.getenv("NEWS_FETCH_MAX_WORKERS", "6"))
# Per-request timeout (seconds), connect + read.
_TIMEOUT = float(os.getenv("NEWS_FETCH_TIMEOUT", "6"))
# Truncate extracted text to protect the LLM context / token budget.
_MAX_CHARS = int(os.getenv("NEWS_FETCH_MAX_CHARS", "4000"))

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _extract_text(html: str, url: str) -> Optional[str]:
    """Extract readable article text from raw HTML. Returns None if nothing usable."""
    if trafilatura is not None:
        try:
            text = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=False,
                favor_precision=True,
            )
            if text and text.strip():
                return text.strip()
        except Exception:
            pass  # fall through to bs4

    # Fallback: crude paragraph join via BeautifulSoup.
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
            tag.decompose()
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        text = "\n".join(p for p in paragraphs if len(p) > 40)
        return text.strip() or None
    except Exception:
        return None


def fetch_article_text(
    url: str,
    timeout: float = _TIMEOUT,
    max_chars: int = _MAX_CHARS,
) -> Optional[str]:
    """
    Fetch a single article URL and return its extracted body text (truncated),
    or None on any failure. Never raises.
    """
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        return None
    if httpx is None:
        return None
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=timeout, follow_redirects=True)
        if resp.status_code != 200:
            return None
        ctype = resp.headers.get("Content-Type", "")
        if "html" not in ctype.lower():
            return None
        text = _extract_text(resp.text, url)
        if not text:
            return None
        return text[:max_chars]
    except Exception as e:
        logger.debug("Article fetch failed for %s: %s", url, e)
        return None


def enrich_articles_with_content(
    articles: List[Dict[str, Any]],
    max_articles: int = _MAX_ARTICLES,
    max_workers: int = _MAX_WORKERS,
    timeout: float = _TIMEOUT,
    max_chars: int = _MAX_CHARS,
) -> None:
    """
    Mutate ``articles`` in place, attaching a ``content`` field with best-effort
    full article text for the first ``max_articles`` entries that have a link.
    No-op if disabled via NEWS_FETCH_FULL_TEXT=0 or if httpx is unavailable.
    """
    if not _ENABLED or httpx is None or not articles:
        return

    targets = [a for a in articles[:max_articles] if isinstance(a, dict) and a.get("link")]
    if not targets:
        return

    def _work(article: Dict[str, Any]) -> None:
        body = fetch_article_text(article.get("link", ""), timeout=timeout, max_chars=max_chars)
        if body:
            article["content"] = body

    workers = max(1, min(max_workers, len(targets)))
    try:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(_work, targets))
    except Exception as e:
        logger.debug("Article enrichment pool failed: %s", e)

    fetched = sum(1 for a in targets if a.get("content"))
    logger.info("News full-text: fetched %d/%d article bodies", fetched, len(targets))
