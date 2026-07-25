# Graph flow: Social / News & Sentiment Analyst

> **Graph engineering perspective**: The Social (News & Sentiment) Analyst is an **Agent step** — a self-contained graph node that runs a full internal ReAct loop. All tool calls and retries happen *inside the node*. There is no separate `tools_social` or `extract_resources` node in the compiled graph; the LangGraph routing never leaves this node until the analyst has finished its report.

## Node type

**Agent step** — the node calls tools, inspects results, and iterates internally until it produces a structured `SocialMediaAnalysisOutput`. The graph sees only one node invocation; multiple LLM + tool turns are hidden inside.

## Internal ReAct flow (inside the node)

1. **First turn** → the LLM is given the ticker and current date. It calls `get_ticker_quote` and `get_reddit_company_social` (search_terms = [ticker]). Tool results are appended to the internal message context.

2. **After first tool results** (quote + Reddit data) → the LLM may:
   - **Call the tool again** with different `search_terms` (e.g. company name, sector) if the first results were insufficient — up to a configured retry limit.
   - **Stop calling tools** and proceed to produce the structured report.

3. **Report generation** → the node invokes `with_structured_output(SocialMediaAnalysisOutput)` against the accumulated conversation and returns the report.

The node returns to the graph once, writing `sentiment_report` and `sentiment_score` (1–5) into `AgentState`.

## Graph topology (social analyst in context)

```
START
  │  (parallel fan-out via Send when parallel_analysts=True)
  ▼
Social Analyst  ←─── [internal: LLM ↔ tools, 1–N turns, fully inside node]
  │
  ▼  (barrier after all analysts complete)
Bull Researcher → ...
```

When running social-only (sequential, single analyst), the chain is:

```
START → Social Analyst → Bull Researcher → ...
```

## State written

| Field | Type | Description |
|-------|------|-------------|
| `sentiment_report` | `str` | Full analysis narrative (news/catalysts + crowd sentiment) |
| `sentiment_score` | `int` (1–5) | Combined news & sentiment score |
| `sentiment_key_takeaways` | `List[str]` | Structured key points from the report |
| `report_resources_by_report["sentiment_report"]` | `List[dict]` | Evidence sources (news items, Reddit threads, etc.) |
| `report_steps_by_report["sentiment_report"]` | `List[dict]` | Agent step trace for debugging/visualization |
| `report_usage["sentiment_report"]` | `dict` | Token and cost metadata |

## Tools used

- `get_ticker_quote` — live price quote (anchors the report to the current market context)
- `get_reddit_company_social` — Reddit posts/comments for company-related search terms
- `get_insider_sentiment`, `get_insider_transactions` — insider activity signals
- `get_global_news` — broad news feed for the ticker

## Key files

| Concern | File |
|---------|------|
| Node implementation | `tradingagents/agents/analysts/social_media_analyst.py` |
| Self-contained ReAct base | `tradingagents/agents/analysts/self_contained_analyst.py` |
| Graph wiring | `tradingagents/graph/setup.py` |
