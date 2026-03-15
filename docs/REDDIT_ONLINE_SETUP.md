# Reddit Online Data Fetching Setup

This guide explains how to fetch Reddit data online using the Reddit API (PRAW).

## Prerequisites

PRAW is already included in `requirements.txt`. Make sure it's installed:

```bash
pip install praw
```

## Setting Up Reddit API Credentials

To fetch Reddit data online, you need to create a Reddit application and get API credentials:

1. **Create a Reddit Application:**
   - Go to https://www.reddit.com/prefs/apps
   - Click "create another app..." or "create app"
   - Fill in the form:
     - **Name**: TradingAgents (or any name you prefer)
     - **Type**: Select "script"
     - **Description**: Optional
     - **About URL**: Optional
     - **Redirect URI**: `http://localhost:8080` (required but not used for script apps)
   - Click "create app"

2. **Get Your Credentials:**
   - After creating the app, you'll see:
     - **Client ID**: The string under your app name (looks like: `abc123def456`)
     - **Client Secret**: The "secret" field (looks like: `xyz789secret_key`)

3. **Set Environment Variables:**
   ```bash
   export REDDIT_CLIENT_ID="your_client_id_here"
   export REDDIT_CLIENT_SECRET="your_client_secret_here"
   export REDDIT_USER_AGENT="TradingAgents/1.0"  # Optional, defaults to this
   ```

   Or add them to your `.env` file:
   ```
   REDDIT_CLIENT_ID=your_client_id_here
   REDDIT_CLIENT_SECRET=your_client_secret_here
   REDDIT_USER_AGENT=TradingAgents/1.0
   ```

## Using Online Reddit Data

### Option 1: Configure in Default Config

Update `tradingagents/default_config.py` or your custom config:

```python
config["data_vendors"] = {
    "news_data": "reddit_online",  # Use online Reddit instead of alpha_vantage
    "get_global_news": "reddit_online",  # Use online Reddit for global news
}
```

### Option 2: Use Directly in Code

```python
# Vendor implementations live in data_layer; use when backend is on path
from data_layer.vendors.reddit_utils import (
    get_reddit_global_news_online,
    get_reddit_company_news_online,
)

# Get global news
global_news = get_reddit_global_news_online(
    curr_date="2025-12-11",
    look_back_days=7,
    limit=5
)

# Get company-specific news
company_news = get_reddit_company_news_online(
    query="INTC",  # or "Intel"
    start_date="2025-12-01",
    end_date="2025-12-11"
)
```

## Available Functions

### `get_reddit_global_news_online`
Fetches global/macroeconomic news from popular finance and news subreddits.

**Parameters:**
- `curr_date`: Current date in YYYY-MM-DD format
- `look_back_days`: Number of days to look back (default: 7)
- `limit`: Maximum number of articles to return (default: 5)

**Subreddits searched:**
- worldnews, news, business, economics, stocks, investing, StockMarket, wallstreetbets, finance

### `get_reddit_company_news_online`
Fetches company-specific news from finance and investing subreddits.

**Parameters:**
- `query`: Search query or ticker symbol (e.g., "INTC" or "Intel")
- `start_date`: Start date in YYYY-MM-DD format
- `end_date`: End date in YYYY-MM-DD format

**Subreddits searched:**
- stocks, investing, StockMarket, wallstreetbets, SecurityAnalysis, ValueInvesting, Stock_Picks

## Notes

- The Reddit API has rate limits. Be mindful of how many requests you make.
- Free tier Reddit API allows 60 requests per minute.
- Posts are sorted by upvotes (top posts first).
- Date filtering is applied to post creation dates.
- Search queries match against post titles and content.

## Troubleshooting

**Error: "Reddit API credentials not found"**
- Make sure you've set `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` environment variables.

**Error: "PRAW is not installed"**
- Run: `pip install praw`

**No results returned**
- Check that your date range is valid
- Try expanding your search query or date range
- Some subreddits may have limited recent posts

