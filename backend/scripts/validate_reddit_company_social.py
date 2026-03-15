#!/usr/bin/env python3
"""
Validate Reddit company social: fetch for AAPL, MSFT, TSLA and report:
- Whether data was returned
- List of all subreddits that contributed posts (extracted list)
Run from backend: python scripts/validate_reddit_company_social.py
Requires REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET in .env.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# backend on path
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


def search_terms_for_ticker(ticker: str) -> list[str]:
    """Terms to pass to fetch (script uses ticker only; agent would add company name from get_quote)."""
    return [(ticker or "").strip().upper()]


def main() -> None:
    if not os.getenv("REDDIT_CLIENT_ID") or not os.getenv("REDDIT_CLIENT_SECRET"):
        print("ERROR: Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env")
        sys.exit(1)

    # Wide date range so "top" posts fall inside (Reddit returns last month; strict window often yields 0)
    from datetime import datetime, timedelta, timezone
    end_d = datetime.now(timezone.utc)
    start_d = end_d - timedelta(days=60)
    start_date = start_d.strftime("%Y-%m-%d")
    end_date = end_d.strftime("%Y-%m-%d")

    print("Subreddits queried (company social):")
    for s in DEFAULT_COMPANY_SOCIAL_SUBREDDITS:
        print(f"  r/{s}")
    print()

    tickers = ["AAPL", "MSFT", "TSLA"]
    all_subreddits_used: set[str] = set()

    for ticker in tickers:
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
        data_returned = len(posts) > 0
        subreddits = sorted(set(p.get("subreddit") for p in posts if p.get("subreddit")))
        all_subreddits_used.update(subreddits)

        print(f"--- {ticker} (search_terms: {terms!r}) ---")
        print(f"  Data returned: {'Yes' if data_returned else 'No'}")
        print(f"  Posts found:   {len(posts)}")
        print(f"  Subreddits extracted: {subreddits if subreddits else '(none)'}")
        if posts:
            for i, p in enumerate(posts[:5], 1):
                print(f"    {i}. r/{p.get('subreddit', '?')} | {p.get('upvotes', 0)} upvotes | {p.get('title', '')[:60]}...")
            if len(posts) > 5:
                print(f"    ... and {len(posts) - 5} more")
        print()

    print("=== All subreddits we query (company social) ===")
    print([f"r/{s}" for s in DEFAULT_COMPANY_SOCIAL_SUBREDDITS])
    print()
    print("=== All Reddits that returned posts (extracted for AAPL, MSFT, TSLA) ===")
    extracted = sorted(all_subreddits_used)
    print([f"r/{s}" for s in extracted] if extracted else "(none)")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
