---
name: stock-deep-dive
description: Run a comprehensive multi-step analysis of a single stock. Use when the user asks for a deep dive, full analysis, complete report, or everything about a specific company or ticker. Fetches current quote, AI platform reports, recent news, technical indicators, and fundamental metrics, then synthesizes them into one structured report.
allowed-tools: get_ticker_quote get_platform_reports get_news get_indicators get_fundamentals
---

# Stock Deep Dive

## When to use this skill
Use this skill when the user asks for an in-depth, comprehensive, or complete analysis of a single stock or company. Trigger phrases include:
- "deep dive", "deep-dive", "deep analysis"
- "full analysis", "comprehensive analysis", "complete analysis"
- "full report", "everything about", "tell me everything about"
- "give me a complete picture of X"

A single ticker must be identifiable from the user's message.

## Steps
1. Extract the ticker symbol from the user's message
2. Call `get_ticker_quote` — current price, daily change, volume
3. Call `get_platform_reports` — FlowDeck AI recommendation and return scenarios
4. Call `get_news` — recent company news (last 7 days)
5. Call `get_indicators` — RSI, MACD, Bollinger Bands
6. Call `get_fundamentals` — P/E ratio, market cap, EPS, margins
7. Synthesize all results into a structured deep-dive report

## Output format
Present results as:
- Header: "📊 Deep Dive: {TICKER}"
- Current Quote section
- FlowDeck AI Analysis section (recommendation + scenarios)
- Fundamentals section (valuation metrics)
- Technical Indicators section (momentum signals)
- Recent News section (headlines + sentiment)
- A brief synthesis paragraph with key takeaways

## Notes
- If one data source fails, continue with the others and note the gap
- Never estimate or simulate data — only use what the tools return
- Keep each section concise; the LLM will synthesize into a final narrative
