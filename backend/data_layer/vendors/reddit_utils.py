import requests
import time
import json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from contextlib import contextmanager
from typing import Annotated, Optional, List, Dict
import os

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False


# Default subreddits for global news
DEFAULT_GLOBAL_NEWS_SUBREDDITS = [
    "worldnews",
    "news",
    "business",
    "economics",
    "stocks",
    "investing",
    "StockMarket",
    "wallstreetbets",
    "finance",
]

# Subreddits for company/ticker social/sentiment (core + advanced; r/Stock_Picks excluded: 403/private)
# Core: WSB, stocks, investing, StockMarket (high volume, retail sentiment)
# Advanced: options, Daytrading, ValueInvesting, thetagang (risk/momentum/quality signals)
# See REDDIT_COMPANY_SOCIAL.md for rationale and weighting ideas.
DEFAULT_COMPANY_SOCIAL_SUBREDDITS = [
    "wallstreetbets",
    "stocks",
    "investing",
    "StockMarket",
    "options",
    "Daytrading",
    "ValueInvesting",
    "thetagang",
    "SecurityAnalysis",
]


def get_reddit_client():
    """Initialize and return a PRAW Reddit client using environment variables."""
    if not PRAW_AVAILABLE:
        raise ImportError(
            "PRAW is not installed. Install it with: pip install praw"
        )
    
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "TradingAgents/1.0")
    
    if not client_id or not client_secret:
        raise ValueError(
            "Reddit API credentials not found. Please set REDDIT_CLIENT_ID, "
            "REDDIT_CLIENT_SECRET, and optionally REDDIT_USER_AGENT environment variables. "
            "Get credentials at: https://www.reddit.com/prefs/apps"
        )
    
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
    )


def fetch_reddit_posts_online(
    subreddits: List[str],
    search_terms: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 25,
    sort: str = "top",
    time_filter: str = "week",
) -> List[Dict]:
    """
    Fetch Reddit posts online using PRAW.

    Args:
        subreddits: List of subreddit names to search
        search_terms: Optional list of terms; keep only posts where at least one term
            appears in title or body (case-insensitive substring). No regex.
        start_date: Start date in YYYY-MM-DD format (filters posts by creation date)
        end_date: End date in YYYY-MM-DD format (filters posts by creation date)
        limit: Maximum number of posts to fetch per subreddit
        sort: Sort method ('hot', 'new', 'top', 'rising')
        time_filter: Time filter for 'top' sort ('hour', 'day', 'week', 'month', 'year', 'all')

    Returns:
        List of post dictionaries with keys: title, content, url, upvotes, posted_date, subreddit
    """
    if not PRAW_AVAILABLE:
        raise ImportError("PRAW is not installed. Install it with: pip install praw")
    
    reddit = get_reddit_client()
    all_posts = []
    
    # Parse dates if provided
    start_dt = None
    end_dt = None
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    
    for subreddit_name in subreddits:
        try:
            subreddit = reddit.subreddit(subreddit_name)
            
            # Get posts based on sort method
            if sort == "hot":
                posts = subreddit.hot(limit=limit)
            elif sort == "new":
                posts = subreddit.new(limit=limit)
            elif sort == "top":
                posts = subreddit.top(limit=limit, time_filter=time_filter)
            elif sort == "rising":
                posts = subreddit.rising(limit=limit)
            else:
                posts = subreddit.hot(limit=limit)
            
            for post in posts:
                # Convert post creation time to date
                post_date = datetime.utcfromtimestamp(post.created_utc)
                post_date_str = post_date.strftime("%Y-%m-%d")
                
                # Filter by date if specified
                if start_dt and post_date.date() < start_dt.date():
                    continue
                if end_dt and post_date.date() > end_dt.date():
                    continue
                
                # Filter by search_terms if specified: keep post if any term appears in title or body (substring, no regex)
                if search_terms:
                    title = post.title or ""
                    selftext = post.selftext or ""
                    combined = (title + " " + selftext).lower()
                    terms = [t.strip() for t in search_terms if t and t.strip()]
                    if not terms or not any(t.lower() in combined for t in terms):
                        continue
                
                post_dict = {
                    "title": post.title,
                    "content": post.selftext or "",
                    "url": f"https://reddit.com{post.permalink}",
                    "upvotes": post.score,
                    "posted_date": post_date_str,
                    "subreddit": subreddit_name,
                }
                all_posts.append(post_dict)
                
        except Exception as e:
            print(f"Error fetching from r/{subreddit_name}: {e}")
            continue
    
    # Sort by upvotes (descending)
    all_posts.sort(key=lambda x: x["upvotes"], reverse=True)
    
    return all_posts


def get_reddit_global_news_online(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of articles to return"] = 5,
    query: Annotated[Optional[str], "Optional search focus (unused for Reddit)"] = None,
) -> str:
    """Retrieve the latest top reddit news from online Reddit API."""
    try:
        curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        before = curr_date_dt - relativedelta(days=look_back_days)
        before_str = before.strftime("%Y-%m-%d")
        posts = fetch_reddit_posts_online(
            subreddits=DEFAULT_GLOBAL_NEWS_SUBREDDITS,
            start_date=before_str,
            end_date=curr_date,
            limit=limit * 2,
            sort="top",
            time_filter="week",
        )
        posts = posts[:limit]
        if len(posts) == 0:
            return ""
        news_str = ""
        for post in posts:
            if post["content"] == "":
                news_str += f"### {post['title']}\n\n"
            else:
                news_str += f"### {post['title']}\n\n{post['content']}\n\n"
        return f"## Global News Reddit (Online), from {before_str} to {curr_date}:\n{news_str}"
    except Exception as e:
        raise RuntimeError(
            f"Error fetching Reddit news online: {e}. "
            "Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT."
        ) from e


def get_reddit_company_social_online(
    ticker: Annotated[str, "Ticker symbol for the response header (e.g. AAPL)."],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    search_terms: Annotated[
        List[str],
        "Terms to match in posts (e.g. company name and ticker). Agent should obtain from Yahoo/quote and pass here.",
    ],
) -> str:
    """Retrieve Reddit social/discussion content from finance subreddits. Uses only the provided search_terms; no heuristics or regex."""
    if not search_terms:
        raise ValueError("search_terms is required; agent should provide terms (e.g. company name and ticker from get_quote/get_news).")
    try:
        ticker_upper = (ticker or "").strip().upper()
        terms = [t.strip() for t in search_terms if t and t.strip()]
        if not terms:
            raise ValueError("search_terms must contain at least one non-empty term.")
        posts = fetch_reddit_posts_online(
            subreddits=DEFAULT_COMPANY_SOCIAL_SUBREDDITS,
            search_terms=terms,
            start_date=start_date,
            end_date=end_date,
            limit=50,
            sort="top",
            time_filter="month",
        )
        if len(posts) == 0:
            return ""
        news_str = ""
        for post in posts:
            if post["content"] == "":
                news_str += f"### {post['title']}\n\n"
            else:
                news_str += f"### {post['title']}\n\n{post['content']}\n\n"
        return f"## {ticker_upper} Reddit (social), from {start_date} to {end_date}:\n\n{news_str}"
    except Exception as e:
        raise RuntimeError(
            f"Error fetching Reddit news online: {e}. "
            "Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT."
        ) from e


def fetch_top_from_category(
    category: Annotated[
        str, "Category to fetch top post from. Collection of subreddits."
    ],
    date: Annotated[str, "Date to fetch top posts from."],
    max_limit: Annotated[int, "Maximum number of posts to fetch."],
    query: Annotated[str, "Optional query to search for in the subreddit."] = None,
    data_path: Annotated[
        str,
        "Path to the data folder. Default is 'reddit_data'.",
    ] = "reddit_data",
):
    base_path = data_path

    all_content = []

    if max_limit < len(os.listdir(os.path.join(base_path, category))):
        raise ValueError(
            "REDDIT FETCHING ERROR: max limit is less than the number of files in the category. Will not be able to fetch any posts"
        )

    limit_per_subreddit = max_limit // len(
        os.listdir(os.path.join(base_path, category))
    )

    for data_file in os.listdir(os.path.join(base_path, category)):
        # check if data_file is a .jsonl file
        if not data_file.endswith(".jsonl"):
            continue

        all_content_curr_subreddit = []

        with open(os.path.join(base_path, category, data_file), "rb") as f:
            for i, line in enumerate(f):
                # skip empty lines
                if not line.strip():
                    continue

                parsed_line = json.loads(line)

                # select only lines that are from the date
                post_date = datetime.utcfromtimestamp(
                    parsed_line["created_utc"]
                ).strftime("%Y-%m-%d")
                if post_date != date:
                    continue

                # if is company, keep post if query appears in title or content (substring, no regex)
                if "company" in category and query:
                    title = parsed_line.get("title") or ""
                    selftext = parsed_line.get("selftext") or ""
                    combined = (title + " " + selftext).lower()
                    if query.strip().lower() not in combined:
                        continue

                post = {
                    "title": parsed_line["title"],
                    "content": parsed_line["selftext"],
                    "url": parsed_line["url"],
                    "upvotes": parsed_line["ups"],
                    "posted_date": post_date,
                }

                all_content_curr_subreddit.append(post)

        # sort all_content_curr_subreddit by upvote_ratio in descending order
        all_content_curr_subreddit.sort(key=lambda x: x["upvotes"], reverse=True)

        all_content.extend(all_content_curr_subreddit[:limit_per_subreddit])

    return all_content
