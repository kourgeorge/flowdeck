---
name: portfolio-health
description: Run a portfolio health check for the current user. Use when the user asks about their portfolio, watchlist, subscribed stocks, how their stocks are doing, or wants a portfolio overview or summary. Fetches all subscribed tickers, gets live quotes and AI recommendations for each, then synthesizes into a portfolio health summary with overall sentiment.
allowed-tools: get_user_subscriptions get_ticker_quote get_platform_reports
---

# Portfolio Health Check

## When to use this skill
Use this skill when the user asks about their own portfolio or subscribed stocks. Trigger phrases include:
- "portfolio health", "portfolio check", "portfolio overview", "portfolio summary"
- "how is my portfolio", "how are my stocks", "how are my subscriptions"
- "my portfolio", "all my stocks", "watchlist health", "check my stocks"
- "what's in my portfolio", "show me my stocks"

This skill requires no arguments — it automatically fetches the user's subscribed tickers.

## Steps
1. Call `get_user_subscriptions` — retrieve the list of tickers the user is subscribed to
2. If no subscriptions found, inform the user they have no subscribed stocks
3. For each subscribed ticker (up to 10):
   a. Call `get_ticker_quote` — current price and daily change
   b. Call `get_platform_reports` — latest AI recommendation
4. Synthesize all results into a portfolio health summary

## Output format
Present results as:
- Header: "🏥 Portfolio Health Check"
- Count of stocks analysed
- For each ticker: current price, daily change, AI recommendation
- Overall portfolio sentiment (bullish / bearish / mixed) based on the recommendations
- Highlight top mover (biggest gainer and biggest loser of the day)

## Notes
- Cap at 10 tickers to avoid excessive API calls
- If quote or reports fail for a ticker, note it as unavailable and continue
- Never estimate or simulate data — only use what the tools return
- This skill uses the authenticated user's subscriptions — no ticker input needed
