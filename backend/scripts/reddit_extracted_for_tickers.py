#!/usr/bin/env python3
"""
Fetch Reddit company social for a list of tickers and print extracted count + content per ticker.
Run from backend: python scripts/reddit_extracted_for_tickers.py
Requires REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET in .env.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
REPO_ROOT = BACKEND.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(BACKEND / ".env")

from data_layer.vendors.reddit_utils import (
    fetch_reddit_posts_online,
    DEFAULT_COMPANY_SOCIAL_SUBREDDITS,
)

TICKERS = [
    "META", "NVDA", "TSLA", "FROG", "UE", "BTC-USD", "ETH-USD",
    "TA35.TA", "V", "ORCL", "MAN", "INTC", "IBM",
]


def search_terms_for_ticker(ticker: str) -> list[str]:
    """Terms for Reddit (script uses ticker only; agent would add company name from get_quote)."""
    return [(ticker or "").strip().upper()]


def main() -> None:
    if not os.getenv("REDDIT_CLIENT_ID") or not os.getenv("REDDIT_CLIENT_SECRET"):
        print("ERROR: Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env")
        sys.exit(1)

    from datetime import datetime, timedelta, timezone
    end_d = datetime.now(timezone.utc)
    start_d = end_d - timedelta(days=60)
    start_date = start_d.strftime("%Y-%m-%d")
    end_date = end_d.strftime("%Y-%m-%d")

    for ticker in TICKERS:
        terms = search_terms_for_ticker(ticker)
        posts = fetch_reddit_posts_online(
            subreddits=DEFAULT_COMPANY_SOCIAL_SUBREDDITS,
            search_terms=terms,
            start_date=start_date,
            end_date=end_date,
            limit=50,
            sort="top",
            time_filter="month",
        )
        n = len(posts)
        print(f"\n{'='*60}")
        print(f"  {ticker}  (search_terms: {terms!r})  →  {n} extracted")
        print("=" * 60)
        if not posts:
            print("  (no posts)")
            continue
        for i, p in enumerate(posts, 1):
            title = (p.get("title") or "")[:80]
            content = (p.get("content") or "").strip()
            snippet = (content[:200] + "…") if len(content) > 200 else content
            sub = p.get("subreddit", "?")
            up = p.get("upvotes", 0)
            date = p.get("posted_date", "")
            print(f"  {i}. [r/{sub}] {up} ↑  {date}")
            print(f"     {title}")
            if snippet:
                print(f"     {snippet}")
            print()
    print("Done.")


if __name__ == "__main__":
    main()
