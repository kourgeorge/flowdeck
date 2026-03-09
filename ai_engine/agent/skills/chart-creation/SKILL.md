---
name: chart-creation
description: Create a chart or graph of stock/index prices over time. Use when the user asks for a chart, graph, plot, or visualization of one or more tickers (e.g. "chart of AAPL", "graph TSLA and NVDA over the last year", "plot the S&P 500 this month"). Fetches real historical price data and outputs a line chart (or bar for single-period comparisons). Supports indices and markets (e.g. ^GSPC, TA35.TA).
allowed-tools: get_multi_historical_prices
---

# Chart Creation

## When to use this skill
Use this skill when the user explicitly wants a **chart**, **graph**, or **plot**:
- "Show me a chart of AAPL"
- "Graph TSLA over the last year"
- "Plot NVDA and MSFT"
- "Visualize the S&P 500 this month"
- "Chart comparing USA and Israeli market"

Trigger phrases: "chart", "graph", "plot", "visualize", "visualization", "draw a graph".

Do **not** use this skill when the user wants a comparison table or analysis without asking for a chart — use **compare_stocks** or the ReAct agent instead.

## Arguments
- `tickers`: list of ticker symbols (1–6). For indices use ^GSPC, ^IXIC, TA35.TA, etc.
- `period` (optional): time range — "1y", "6m", "3m", "month", "this month", "ytd", or "YYYY-MM-DD:YYYY-MM-DD". Default "1y".

## Steps
1. Resolve period to start_date and end_date.
2. Call `get_multi_historical_prices` with tickers and date range.
3. Parse the returned CSV data per ticker and build a unified time series (date → close prices).
4. Build a line chart spec: xKey=date, yKeys=[ticker1, ticker2, ...], data=[{date, ticker1, ticker2, ...}].
5. Output a short summary and a single CHART_JSON line so the UI renders the chart.

## Output format
- One or two sentences describing the chart (e.g. "Line chart of AAPL and MSFT over the past year.")
- A blank line, then exactly one line: CHART_JSON:{...}
- Chart type: "line" for time series. Set yAxisConfig min/max from the data range (not 0 for prices).

## Notes
- Always use real data from get_multi_historical_prices — never simulate.
- Preserve ticker symbols as returned (e.g. ^GSPC, TA35.TA).
- For a single ticker, the chart has one line; for multiple tickers, one line per ticker with distinct colors.
