import requests
import time
import json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from contextlib import contextmanager
from typing import Annotated, Optional, List, Dict
import os
import re

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False

ticker_to_company = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOGL": "Google",
    "AMZN": "Amazon",
    "TSLA": "Tesla",
    "NVDA": "Nvidia",
    "TSM": "Taiwan Semiconductor Manufacturing Company OR TSMC",
    "JPM": "JPMorgan Chase OR JP Morgan",
    "JNJ": "Johnson & Johnson OR JNJ",
    "V": "Visa",
    "WMT": "Walmart",
    "META": "Meta OR Facebook",
    "AMD": "AMD",
    "INTC": "Intel",
    "QCOM": "Qualcomm",
    "BABA": "Alibaba",
    "ADBE": "Adobe",
    "NFLX": "Netflix",
    "CRM": "Salesforce",
    "PYPL": "PayPal",
    "PLTR": "Palantir",
    "MU": "Micron",
    "SQ": "Block OR Square",
    "ZM": "Zoom",
    "CSCO": "Cisco",
    "SHOP": "Shopify",
    "ORCL": "Oracle",
    "X": "Twitter OR X",
    "SPOT": "Spotify",
    "AVGO": "Broadcom",
    "ASML": "ASML ",
    "TWLO": "Twilio",
    "SNAP": "Snap Inc.",
    "TEAM": "Atlassian",
    "SQSP": "Squarespace",
    "UBER": "Uber",
    "ROKU": "Roku",
    "PINS": "Pinterest",
}

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

# Default subreddits for company news
DEFAULT_COMPANY_NEWS_SUBREDDITS = [
    "stocks",
    "investing",
    "StockMarket",
    "wallstreetbets",
    "SecurityAnalysis",
    "ValueInvesting",
    "Stock_Picks",
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
    query: Optional[str] = None,
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
        query: Optional search query (searches in title and selftext)
        start_date: Start date in YYYY-MM-DD format (filters posts by creation date)
        end_date: End date in YYYY-MM-DD format (filters posts by creation date)
        limit: Maximum number of posts to fetch per subreddit
        sort: Sort method ('hot', 'new', 'top', 'rising')
        time_filter: Time filter for 'top' sort ('hour', 'day', 'week', 'month', 'year', 'all')
    
    Returns:
        List of post dictionaries with keys: title, content, url, upvotes, posted_date
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
                
                # Filter by query if specified
                if query:
                    search_terms = query.lower().split()
                    title_lower = post.title.lower()
                    selftext_lower = (post.selftext or "").lower()
                    
                    # Check if any search term appears in title or content
                    if not any(term in title_lower or term in selftext_lower for term in search_terms):
                        continue
                
                post_dict = {
                    "title": post.title,
                    "content": post.selftext or "",
                    "url": f"https://reddit.com{post.permalink}",
                    "upvotes": post.score,
                    "posted_date": post_date_str,
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


def get_reddit_company_news_online(
    query: Annotated[str, "Search query or ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Retrieve company-specific reddit news from online Reddit API."""
    try:
        search_query = query
        if query in ticker_to_company:
            company_name = ticker_to_company[query]
            search_query = company_name.split(" OR ")[0] if "OR" in company_name else company_name
            search_query = f"{search_query} {query}"
        posts = fetch_reddit_posts_online(
            subreddits=DEFAULT_COMPANY_NEWS_SUBREDDITS,
            query=search_query,
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
        return f"## {query} News Reddit (Online), from {start_date} to {end_date}:\n\n{news_str}"
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

                # if is company_news, check that the title or the content has the company's name (query) mentioned
                if "company" in category and query:
                    search_terms = []
                    if "OR" in ticker_to_company[query]:
                        search_terms = ticker_to_company[query].split(" OR ")
                    else:
                        search_terms = [ticker_to_company[query]]

                    search_terms.append(query)

                    found = False
                    for term in search_terms:
                        if re.search(
                            term, parsed_line["title"], re.IGNORECASE
                        ) or re.search(term, parsed_line["selftext"], re.IGNORECASE):
                            found = True
                            break

                    if not found:
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
