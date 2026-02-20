# Watchlist consulting

Personalized watchlist report pipeline: payload → stages 1–9 → HTML with Vega-Lite charts. Optional **deep-research** stage (Stage 4) integrates web search with report evidence.

## Pipeline (conductor)

- **Payload** – Watchlist entries, reports, quotes, company info.
- **Stage 1** – User intent (investor style, risk, horizon).
- **Stage 2** – Evidence extraction (thesis, risks, catalysts per ticker).
- **Stage 3** – Theme miner (dominant themes, common risks, exposure).
- **Stage 4** – **Web research** (optional): query generation → SerpAPI search → learnings + follow-up depth → aggregated web context for narrative.
- **Stage 5** – Figure plan + data jobs.
- **Stage 6** – Data builder (figure_data).
- **Stage 7** – Action engine (ranked actions; can use web context).
- **Stage 8** – Narrative composer (report + web learnings, provenance).
- **Stage 9** – Auditor.

## Web research (Stage 4)

When enabled, the pipeline runs a deep-research-style step after themes:

1. **Query generation** – LLM produces search queries from user intent, themes, and tickers/sectors.
2. **Search** – SerpAPI (Google SERP) for each query.
3. **Analysis** – LLM extracts learnings and follow-up questions from results.
4. **Depth** – Optional follow-up searches (configurable).
5. **Aggregation** – Deduped learnings and sources passed to narrative and actions.

### Configuration

- **`SERPAPI_KEY`** – Required for web research. Set in `backend/.env` (see `backend/.env.example`). If unset or `web_breadth=0`, Stage 4 returns empty output and the rest of the pipeline runs unchanged.
- **`web_breadth`** – Number of initial search queries (default `3`). Set to `0` to disable web research.
- **`web_depth`** – Depth level: `1` = no follow-up queries; `2` = up to 2 follow-up searches per initial query (default `2`).

### CLI

```bash
# From repo root; load backend/.env
python ai_engine/watchlist_consulting/build_report.py --email=user@example.com

# Disable web research
python ai_engine/watchlist_consulting/build_report.py --email=user@example.com --web-breadth=0

# Fewer queries, no follow-ups (faster)
python ai_engine/watchlist_consulting/build_report.py --email=user@example.com --web-breadth=2 --web-depth=1
```

### Programmatic

```python
from conductor import run_pipeline

result = run_pipeline(
    email="user@example.com",
    web_breadth=3,
    web_depth=2,
)
# result["report_json"] includes narrative that may cite web learnings; result["payload"] etc.
```

Outputs: `out/pipeline_stages/<user_slug>_<date>/04_web_research_output.json` when Stage 4 runs.
