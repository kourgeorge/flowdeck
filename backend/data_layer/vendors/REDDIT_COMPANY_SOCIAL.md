# Reddit company social – subreddits and returned data

## Subreddits used (company social)

Used by `get_reddit_company_social_online` (and the `/api/data/reddit-company-social/{ticker}` API). Chosen for **stock sentiment and discussion** (retail hype, company-specific sentiment, risk appetite, momentum).

### Core (high volume, widely tracked by sentiment tools)

| Subreddit         | Focus |
|-------------------|--------|
| r/wallstreetbets  | Meme stocks, options, YOLO trades; retail hype, early meme momentum |
| r/stocks          | Company discussions, earnings, fundamentals, trading ideas |
| r/investing       | Long-term investing, macro, portfolio construction |
| r/StockMarket     | Market-wide discussion, daily threads, intraday sentiment |

### Advanced (stronger signals for risk/momentum/quality)

| Subreddit         | Focus |
|-------------------|--------|
| r/options         | Options strategies, volatility sentiment, risk appetite per ticker |
| r/Daytrading      | Short-term trading, technicals, momentum |
| r/ValueInvesting  | Fundamental analysis, valuation, longer-term sentiment |
| r/thetagang       | Options premium selling, risk/positioning |
| r/SecurityAnalysis| Fundamental analysis, quality discussions |

r/Stock_Picks is excluded (often 403 / private).

---

## Query when trading agents run

There are **no heuristics or regex** in the backend. The **search terms are provided by the agent**.

1. **Agent flow:** The Social Media Analyst gets the company name (e.g. via `get_quote(ticker)` or `get_news`), then calls `get_reddit_company_social(ticker, start_date, end_date, search_terms)` with **search_terms** set to the list of terms to look for (e.g. `["Apple", "AAPL"]`).
2. **Backend:** The API and vendor use only these terms. A post is kept if **at least one** of the provided terms appears in the title or body (case-insensitive substring). No regex, no word-boundary logic, no preset ticker list.
3. **API:** `GET /api/data/reddit-company-social/{ticker}?start_date=...&end_date=...&search_terms=Apple,AAPL` — **search_terms** is required (comma-separated).

### Future: weighted sentiment

For a sentiment score you could weight by subreddit, e.g.  
`WSB * 0.4 + stocks * 0.3 + investing * 0.2 + StockMarket * 0.1`, and add options/Daytrading for risk appetite. Right now we return raw markdown; the Social Media Analyst consumes it and outputs a 1–10 score.

---

## What the API returns

- **HTTP:** `GET /api/data/reddit-company-social/{ticker}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&search_terms=Apple,AAPL`
- **search_terms** (required): comma-separated terms the agent wants to match (e.g. company name and ticker from Yahoo/quote).
- **Response body:** JSON `{ "ticker": "AAPL", "data": "<markdown string>" }`.

The `data` value is a **single markdown string** (social/discussion content), not a list of objects. It is built from posts where at least one of the provided search terms appears in title or body, within the date range.

---

## Internal per-post data (before formatting)

Each Reddit post is fetched and filtered by date and query; then it is turned into a dict with these keys (see `fetch_reddit_posts_online` in `reddit_utils.py`):

| Field         | Type   | Description |
|---------------|--------|-------------|
| `title`       | str    | Post title  |
| `content`     | str    | Post body (selftext); can be empty for link posts |
| `url`         | str    | Full Reddit URL (e.g. `https://reddit.com/r/stocks/...`) |
| `upvotes`     | int    | Post score  |
| `posted_date` | str    | Date string `YYYY-MM-DD` (UTC) |
| `subreddit`   | str    | Subreddit name (e.g. `stocks`) |

These dicts are **not** returned by the API; they are used internally to build the markdown string.

---

## Example: AAPL response shape

For AAPL the backend builds a string like:

```
## AAPL Reddit (social), from 2025-02-01 to 2025-03-15:

### Apple stock discussion - Q1 results

Discussion about AAPL earnings and iPhone...

### Is AAPL still a buy?

Current sentiment and price targets...
```

So the **returned data points** you get from the API for AAPL are:

1. **`ticker`** (string): `"AAPL"`.
2. **`data`** (string): One markdown document containing:
   - A header line: `## {ticker} Reddit (social), from {start_date} to {end_date}:`
   - For each post, a block:
     - `### {title}`
     - `{content}` (if non-empty)
     - Blank line between posts.

There are no separate “data points” (e.g. JSON array of posts) in the response; the agent and any downstream code see only this single markdown string.
