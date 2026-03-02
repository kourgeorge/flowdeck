---
name: portfolio-performance
description: Compute real portfolio performance — top gainers, top losers, and % returns — over a specified time period using actual historical price data. Use when the user asks about portfolio performance, top gainers, top losers, best or worst performers, weekly/monthly/yearly returns, or wants to rank their stocks by performance. Never simulates or estimates — always fetches real market data.
allowed-tools: get_user_subscriptions get_multi_historical_prices
---

# Portfolio Performance

## When to use this skill
Use this skill when the user asks about how their portfolio performed over a time period. Trigger phrases include:
- "top gainer", "top loser", "best performer", "worst performer"
- "biggest gainer", "biggest loser", "best stock", "worst stock"
- "portfolio performance", "how did my stocks", "how did my portfolio"
- "weekly performance", "monthly performance", "yearly performance"
- "ytd", "year to date", "last week", "last month", "this month"
- "which stock gained the most", "which stock lost the most"
- "rank my stocks", "show me the top performers"

## Arguments
- `period`: The time period to analyse. Supported values:
  - `"week"` or `"last week"` — previous Mon–Fri trading week
  - `"this week"` — current week so far
  - `"month"` or `"last month"` — previous calendar month
  - `"this month"` — current month so far
  - `"ytd"` or `"year to date"` — January 1 to today
  - `"1y"` — past 365 days
  - `"3m"` — past 90 days
  - `"6m"` — past 180 days
  - `"YYYY-MM-DD:YYYY-MM-DD"` — explicit date range
  - Default: `"week"` if not specified

## Steps
1. Call `get_user_subscriptions` — retrieve the user's subscribed tickers
2. If no subscriptions found, inform the user they have no subscribed stocks
3. Resolve the requested period to a start_date and end_date
4. Call `get_multi_historical_prices` with all tickers, start_date, and end_date
5. Compute % return for each ticker: (end_price - start_price) / start_price × 100
6. Rank tickers from highest to lowest return
7. Present a table with start price, end price, and % return for each ticker
8. Highlight the top gainer and top loser
9. Include a bar chart (CHART_JSON) of returns

## Output format
- Header: "📈 Portfolio Performance — {period}"
- Period and date range
- Markdown table: Ticker | Start Price | End Price | Return %
- Top gainer and top loser callouts
- CHART_JSON bar chart spec

## Notes
- Always use real historical price data — never estimate or simulate
- If price data is unavailable for a ticker, skip it and note the gap
- Sort results descending by return (best performers first)