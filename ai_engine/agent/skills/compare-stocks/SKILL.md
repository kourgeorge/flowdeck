---
name: compare-stocks
description: Compare two or more stocks, market indices, or country markets side-by-side — including over a time period (e.g. "last month", "this year", "last week"). Use when the user asks to compare markets, countries, sectors, or specific tickers. Handles natural-language market names such as "usa market", "israeli market", "s&p 500", "nasdaq", "ta-35", "dow jones". Resolves country/index names to ticker symbols automatically. When a period is specified, fetches real historical price data and computes % returns with a chart.
allowed-tools: get_stock_quote get_fundamentals get_multi_historical_prices
---

# Compare Stocks / Markets / Indices

## When to use this skill
Use this skill whenever the user wants to compare two or more of the following:
- Specific stock tickers (e.g. AAPL vs MSFT)
- Market indices (e.g. S&P 500 vs Nasdaq, TA-35 vs S&P 500)
- Country markets (e.g. "usa market vs israeli market", "compare US and Israel")
- Sectors or ETFs (e.g. QQQ vs SPY)
- Over a time period (e.g. "compare usa and israeli market in the last month")

Trigger phrases include: "compare", "vs", "versus", "side by side", "which is better",
"how does X compare to Y", "X or Y", "compare X and Y over the last month".

## Arguments
- `tickers`: list of resolved ticker symbols (minimum 2, maximum 6)
- `period` (optional): time period for historical comparison
  - `"month"` or `"last month"` — previous calendar month
  - `"this month"` — current month so far
  - `"week"` or `"last week"` — previous Mon–Fri week
  - `"this week"` — current week so far
  - `"ytd"` — year to date
  - `"1y"` — past 365 days
  - `"3m"` — past 90 days
  - `"6m"` — past 180 days
  - `"YYYY-MM-DD:YYYY-MM-DD"` — explicit date range
  - Omit if the user wants a current snapshot (no time period mentioned)

## Market name → ticker resolution
Before fetching data, resolve natural-language names to ticker symbols:

| User says | Ticker |
|---|---|
| usa, us market, s&p, s&p 500, american market | ^GSPC |
| nasdaq, nasdaq 100 | ^IXIC |
| dow, dow jones, djia | ^DJI |
| israel, israeli market, ta-35, ta35, tel aviv | TA35.TA |
| ftse, uk market | ^FTSE |
| dax, german market | ^GDAXI |
| nikkei, japan market | ^N225 |
| hang seng, hong kong | ^HSI |

## Steps — Historical mode (period specified)
1. Resolve market names to ticker symbols
2. Call `get_multi_historical_prices` with all tickers, start_date, end_date
3. Compute % return for each ticker: (end_price - start_price) / start_price × 100
4. Rank by return (best to worst)
5. Present a markdown table with start price, end price, % return
6. Include a bar chart (CHART_JSON) of returns
7. Highlight best and worst performer

## Steps — Snapshot mode (no period)
1. Resolve market names to ticker symbols
2. For each ticker: call `get_stock_quote` and `get_fundamentals`
3. Present side-by-side current price, daily change, and key fundamentals

## Output format — Historical
- Header: "⚖️ Market Comparison: X vs Y"
- Period and date range
- Markdown table: Ticker | Start Price | End Price | Return %
- Best/worst performer callouts
- CHART_JSON bar chart

## Output format — Snapshot
- Header: "⚖️ Market Comparison: X vs Y"
- Current Quotes section
- Fundamentals section

## Notes
- Always use real data — never estimate or simulate
- Index tickers (^GSPC, ^IXIC, etc.) may not have fundamentals — skip gracefully
- Preserve ticker case exactly as resolved (e.g. `^GSPC`, `TA35.TA`)