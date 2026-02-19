# Stock Deep Research Agent

A **multi-agent deep research system** for producing comprehensive company/equity reports. It is **separate from the trading agent**: it does not output BUY/SELL/HOLD, but instead autonomously searches the web (and optionally SEC EDGAR), gathers information, and writes long-form research reports.

Inspired by [Open Deep Research](https://github.com/langchain-ai/open_deep_research) (LangChain/LangGraph), but specialized for **stock/company research** with:

- **Stock-specific research brief**: from a user question (e.g. “Research Amazon AMZN”), the system expands into topics such as business model, industry & competition, SEC/10-K, market share, legal/regulatory, competitive threats, AI disruption, ESG/energy transition.
- **Web search**: DuckDuckGo (default, no API key) or Tavily (optional).
- **Optional SEC/EDGAR**: when `INFO_SERVICE_URL` points to the Flowdeck backend, researchers can pull Risk Factors, MD&A, Competition, and related sections from 10-K/10-Q.
- **Structured final report**: sections, tables, key takeaways, sources, and data limitations (similar in spirit to the Amazon-style report examples).

## Architecture

- **Entry**: User message (e.g. “Research Amazon” or “Full report on Microsoft”).
- **Write research brief**: LLM turns the message into a structured research brief (company + 4–8 focused topics).
- **Supervisor subgraph**: A lead researcher delegates each topic via `ConductResearch` to **researcher subgraphs** (up to `max_concurrent_research_units` in parallel). Each researcher can use:
  - **Web search** (DuckDuckGo or Tavily),
  - **SEC EDGAR** (if `INFO_SERVICE_URL` is set),
  - **think_tool** for planning.
- **Researcher subgraph**: For each topic: search (and EDGAR) → compress findings into a subsection.
- **Final report**: All compressed findings are passed to an LLM to produce one Markdown report with sections, tables, and sources.

So: **clarify (optional) → research brief → supervisor (delegate) → researchers (search + optional EDGAR) → final report**.

## Requirements

- Python 3.10+
- `langgraph`, `langchain-core`, and a chat model (e.g. `langchain-openai`).
- `duckduckgo-search` for web search (default), or `tavily-python` + `TAVILY_API_KEY` for Tavily.
- Optional: Flowdeck backend running and `INFO_SERVICE_URL` for SEC EDGAR.

## Environment variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | For OpenAI models (default). |
| `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` | If using Anthropic/Google models. |
| `STOCK_RESEARCH_MODEL` | Model for supervisor + researchers (default: `openai:gpt-4o`). |
| `STOCK_COMPRESSION_MODEL` | Model for compressing researcher output (default: `openai:gpt-4o-mini`). |
| `STOCK_FINAL_REPORT_MODEL` | Model for final report (default: `openai:gpt-4o`). |
| `STOCK_SEARCH_API` | `duckduckgo` (default) or `tavily`. |
| `TAVILY_API_KEY` | Required if `STOCK_SEARCH_API=tavily`. |
| `INFO_SERVICE_URL` | Flowdeck backend URL for SEC EDGAR (e.g. `http://localhost:8000`). |
| `STOCK_MAX_ITERATIONS` | Max supervisor loops (default: 15). |
| `STOCK_MAX_CONCURRENT` | Max parallel researcher subgraphs (default: 3). |

## CLI

From the repo root:

```bash
# Default: DuckDuckGo search, OpenAI models
export OPENAI_API_KEY=sk-...
pip install duckduckgo-search langgraph langchain-openai langchain-core

python scripts/run_stock_deep_research.py "Research Amazon (AMZN)"
python scripts/run_stock_deep_research.py "Full report on Microsoft, focus on cloud and competition"
```

With SEC EDGAR (Flowdeck backend must be running):

```bash
export INFO_SERVICE_URL=http://localhost:8000
python scripts/run_stock_deep_research.py "Competitive analysis of Apple"
```

The script prints the report to stdout and saves it to `results/stock_deep_research/latest_report.md`.

## Using the graph in code

```python
from langchain_core.messages import HumanMessage
from ai_engine.stock_deep_research.graph import stock_researcher_graph

config = {
    "configurable": {
        "research_model": "openai:gpt-4o",
        "search_api": "duckduckgo",
        "info_service_url": "http://localhost:8000",
    }
}
result = await stock_researcher_graph.ainvoke(
    {"messages": [HumanMessage(content="Research Amazon AMZN")]},
    config=config,
)
report = result["final_report"]
```

## Difference from the trading agent

| | Trading agent | Stock Deep Research |
|---|--------------|---------------------|
| **Goal** | BUY/SELL/HOLD + investment plan | Comprehensive company report |
| **Flow** | Analysts → Bull/Bear debate → Research Manager → Trader → Risk → signal | Research brief → Supervisor → Researchers (web + optional SEC) → Final report |
| **Output** | Trading signal + reports (market, news, fundamentals, SEC, plan) | Single long-form Markdown report |
| **Web search** | No (uses quote, news, fundamentals, EDGAR APIs) | Yes (DuckDuckGo/Tavily + optional EDGAR) |
| **Trigger** | Dashboard “Run analysis” / API / CLI for a ticker+date | CLI or direct graph invoke with a natural-language question |

## Files

| Path | Purpose |
|------|---------|
| `stock_deep_research/state.py` | State types and structured outputs (e.g. `ConductResearch`, `StockResearchQuestion`). |
| `stock_deep_research/config.py` | `StockDeepResearchConfig`: models, search API, limits, `INFO_SERVICE_URL`. |
| `stock_deep_research/prompts.py` | Stock-specific prompts (brief, supervisor, researcher, compression, final report). |
| `stock_deep_research/tools.py` | Web search (DuckDuckGo/Tavily), optional EDGAR, `think_tool`; `get_all_tools()`. |
| `stock_deep_research/graph.py` | Main graph: write_research_brief → supervisor subgraph → final_report_generation. |
| `scripts/run_stock_deep_research.py` | CLI entry point. |

## Optional: API endpoint

To trigger Stock Deep Research from the Flowdeck backend (e.g. a new endpoint that does not consume the trading token economy), add something like:

- `POST /api/deep-research/start`: body `{"query": "Research Amazon AMZN"}`; run `stock_researcher_graph.ainvoke(...)` in a background task; return `research_id` and optionally stream or store the report and expose it via `GET /api/deep-research/{research_id}`.

This can be implemented in `backend/main.py` and `backend/services/` without changing the trading analysis flow.
