# Watchlist consulting — design and architecture

This document describes the current design of the **watchlist consulting** pipeline: data flow, LLM usage, web search, and how the final report is created.

---

## 1. Overview

**Goal:** Produce a personalized, evidence-based consultation report for a user’s watchlist: summary, narrative, charts (Vega-Lite), and action items. The report must cite only evidence and figures (no invented numbers) and can optionally be enriched with web research.

**High-level flow:**

1. **Payload** — Load user’s watchlist from the backend (subscriptions + latest report + quote per ticker).
2. **Stages 1–9** — A linear DAG run by the conductor: user intent → evidence → themes → optional web research → figure plan → data → actions → narrative → audit.
3. **Report** — Assemble `report_json` (title, summary, narrative, figure explanations, ticker cards, actions, provenance, references) and build HTML with embedded Vega-Lite charts.

**Entry point:** `python ai_engine/watchlist_consulting/build_report.py --email=...` runs the full conductor and writes HTML (and optional stage outputs under `out/pipeline_stages/`).

---

## 2. Data flow (conductor)

The conductor (`conductor.run_pipeline`) runs in a fixed order and passes structured outputs between stages. Optional caching (keyed by `user_id` + `report_date`) can skip recomputing evidence, themes, figure plan, and data jobs for the same day.

| Stage | Input | Output | Cached? |
|-------|--------|--------|--------|
| — | user_id / email | **Payload** (user, tickers, entries with report + quote) | — |
| 1 | user_profile?, payload | **UserIntent** (investor_style, risk_budget, time_horizon, report_style, etc.) | — |
| 2 | entries | **EvidencePacket[]** (per-ticker thesis, risks, catalysts, scenario_range, action_candidate) | Yes |
| 3 | evidence_packets, payload | **ThemeOutput** (dominant_themes, common_risks, divergent_views, exposure_snapshot, regime_fit) | Yes |
| 4 | user_intent, theme_output, payload | **WebResearchOutput** (learnings, sources, queries_used) — optional | No |
| 5 | evidence, theme, intent, payload | **figure_plan**, **data_jobs** | Yes |
| 6 | figure_plan, data_jobs, payload | **figure_data**, data_quality_notes | No |
| 7 | intent, evidence, theme, web_research? | **ActionsOutput** (actions_ranked, watchlist_cleanup_suggestions) | — |
| 8 | intent, evidence, theme, figure_plan, figure_data, actions, payload, web_research? | **NarrativeOutput** (title, watchlist_summary, narrative, figure_explanations, ticker_cards, actions_section, provenance) | — |
| 9 | report_dict, figure_specs, figure_data, evidence, intent, provenance | **AuditOutput** (issues_found, auto_fix_instructions) | No |

After Stage 8, the conductor:

- Builds **report_dict** (adds references and research_qa from web research, and audit_notes if Stage 9 found issues).
- Builds **figure_specs** via `vega_specs.build_all_specs(payload, figure_data["by_ticker"])`.
- Returns **report_json**, **figure_specs**, **figure_data**, **provenance**, **audit_output**, **payload**.

`build_report.py` then adapts `report_json` to the shape expected by `html_report.build_html` (e.g. `portfolio_summary` ← `watchlist_summary`, `per_ticker_highlights` from ticker_cards) and writes the HTML file.

---

## 3. LLM parts

LLM access is centralized in **report_agent._get_llm()**, which delegates to **ai_engine.llm_provider** (quick role). Config comes from **get_config_from_env()**; env vars `DEEP_THINK_MODEL` and `QUICK_THINK_MODEL` set model names for all providers (see `ai_engine/llm_provider.py`). Supported backends: OpenAI, Azure, Ollama, OpenRouter, Anthropic, Google, Perplexity. Temperature 0.3; timeout 120s. No dependency on `tradingagents`.

### 3.1 Stage 1 — User intent

- **LLM:** None.
- **Logic:** If a `user_profile` dict is provided, map it to `UserIntent` (investor_style, risk_budget, time_horizon, constraints, report_style). Otherwise return conservative defaults (long-term, medium risk, concise) and set `assumptions_stated=True` and `inferred_preferences_explanation`.

### 3.2 Stage 2 — Evidence extractor

- **LLM:** Yes (optional).
- **Role:** For each watchlist entry, turn the raw report summary (recommendation, takeaways, bull/bear, scores, scenario numbers) into a structured **EvidencePacket** (thesis_bullets, key_risks, catalysts, valuation/quality/momentum signals, scenario_range, numbers_used, action_candidate).
- **Mechanism:** One LLM call per ticker with `llm.with_structured_output(EvidencePacket)` and a prompt that asks for 2–5 thesis bullets, 2–4 risks, catalysts, scenario numbers, and a single action (buy/hold/sell/watch) with rationale.
- **Fallback:** If LLM is disabled or fails, a heuristic builds EvidencePacket from recommendation, key_takeaways, bull/bear, and scenario fields.

### 3.3 Stage 3 — Theme miner

- **LLM:** Yes (optional).
- **Role:** Summarize cross-ticker **dominant_themes** (theme + supporting_tickers) and **common_risks** from evidence_packets.
- **Mechanism:** One LLM call with `with_structured_output(ThemeOutput)` over a condensed text of all tickers’ thesis bullets and key_risks (capped ~12k chars). Prompt asks for 3–6 themes and 3–6 common risks; divergent_views, exposure_snapshot, regime_fit are left for code.
- **Non-LLM:** Exposure (sector/industry counts) comes from backend `get_company_info`; divergent_views from comparing action_candidate to majority; regime_fit from a simple sector heuristic (e.g. rate-sensitive tilt).

### 3.4 Stage 4 — Web research

- **LLM:** Yes (for query generation and result analysis).
- **Role:** Generate search queries from intent/themes/tickers; run SerpAPI; extract learnings and follow-up questions; optionally run follow-up searches; aggregate into **WebResearchOutput** (learnings, sources, queries_used, stats). See [§4](#4-search-stage-4-web-research) below.

### 3.5 Stage 5 — Figure planner

- **LLM:** None.
- **Logic:** Fixed set of figure IDs (recommendation_dist, daily_change, return_range, risk_return_scatter, sector_exposure, theme_map, price_small_multiples, fundamentals_trajectory). Builds **FigurePlanItem** list and **DataJob** list (historical, financial_charts, company_info). “Top” tickers for small multiples come from an importance heuristic (expected-return magnitude + bear–bull spread).

### 3.6 Stage 6 — Data builder

- **LLM:** None.
- **Logic:** Execute data_jobs via `fetch_figure_data` (historical, financial_charts) and backend company info (sector/industry); compute volatility from historical returns; fill **figure_data** (by_ticker + keys like recommendation_dist, daily_change, return_range, risk_return_scatter, sector_exposure, theme_map, price_small_multiples, fundamentals_trajectory).

### 3.7 Stage 7 — Action engine

- **LLM:** None.
- **Logic:** Rule-based: P0 deep_dive (top BUYs by catalyst/spread), P1 wait_catalyst, P2 set_alert (divergent views), P0 avoid (SELLs), cleanup suggestions (sector concentration). If **web_research_output** has learnings, one extra P2 action summarizes recent web context.

### 3.8 Stage 8 — Narrative composer

- **LLM:** Yes (optional).
- **Role:** Produce the consultation narrative: watchlist_summary, narrative, figure_explanations (must reference every figure_id), ticker_cards, actions_section, and **provenance** (claim/figure → source). Web learnings can be woven in with inline citations [1], [2] and provenance entries.
- **Mechanism:** One structured call `with_structured_output(NarrativeOutput)` with a long prompt that includes evidence summary, figure plan, actions, and (if present) web research learnings + numbered references. Rules: no invented numbers; every claim tied to evidence or a figure; consultation tone.
- **Fallback:** If LLM is off or fails, `_fallback_narrative` builds NarrativeOutput from evidence, theme_output, and fixed prose; it still adds web learnings and provenance.

### 3.9 Stage 9 — Auditor

- **LLM:** No (use_llm=False in conductor).
- **Logic:** Deterministic checks only: ticker consistency (evidence vs report cards), figure_ids mentioned in figure_explanations, data_freshness mentioned, figure_specs count vs figure_data. Emits **AuditIssue** (severity, message, fix_suggestion) and optional auto_fix_instructions. No LLM rubric in current code.

---

## 4. Search (Stage 4 — Web research)

Web research is **optional**: skipped when `web_breadth=0` or `SERPAPI_KEY` is unset. Implemented in **web_research.run_web_research_sync** and invoked by **stage4_web_research.run_web_research**.

### 4.1 Query generation (LLM)

- **Input:** UserIntent, ThemeOutput, payload (tickers, sectors from entries).
- **Prompt:** Asks for `breadth` search queries (default 3) that mix intent-driven, theme-driven, and ticker/sector-driven. One query per line, no numbering.
- **Output:** List of query strings.

### 4.2 Search execution

- **API:** SerpAPI (Google) via `serpapi_search(query, num_results)`.
- **Sync:** Uses `urllib.request` (no aiohttp). Timeout 30s.
- **Result shape:** List of dicts with title, snippet, url, domain.

### 4.3 Analysis (LLM)

- **Input:** One query + its search results (title, snippet, url, domain).
- **Prompt:** Ask for a JSON object with **learnings** (3–5 short bullets) and **follow_up_questions** (2–3).
- **Output:** Parsed learnings and follow_up_questions; on parse failure, fallback to snippet-based learnings only.

### 4.4 Depth (follow-ups)

- If `depth > 1`, for each initial query the code takes up to `max_follow_ups_per_query` follow-up questions and runs **serpapi_search** again (with `num_results_followup`). Each follow-up is analyzed the same way; learnings are appended with `query_used` set to the follow-up question.
- **Config:** breadth (initial queries), depth (1 = no follow-ups, 2 = up to 2 per query), num_results_initial, num_results_followup. Conductor passes `web_breadth` and `web_depth` from CLI/defaults.

### 4.5 Aggregation

- All learnings are wrapped as **WebLearning** (text, query_used, source_urls).
- **Deduplication:** By normalized text (lowercased, first 300 chars); first occurrence kept.
- **Sources:** Deduped list of all URLs from initial and follow-up results.
- **Output:** **WebResearchOutput** (learnings, sources, queries_used, stats: total_learnings, total_sources, follow_ups_used).

### 4.6 Downstream use

- **Stage 7:** Optionally adds one P2 action that summarizes top web learnings.
- **Stage 8:** Narrative composer receives `web_research_output`; prompt includes learnings and numbered references and asks for inline citations [1], [2]. Provenance is extended with entries for web-backed claims.
- **Conductor:** Builds `references` (list of URLs) and `research_qa` (list of {question, answers}) from WebResearchOutput for **report_json**.
- **HTML:** References section and “Research questions explored” (Q&A) are rendered from report_json.

---

## 5. Report creation dynamics

### 5.1 report_json

The conductor builds **report_dict** then wraps it as **ReportJson** (Pydantic). Fields:

- **title**, **watchlist_summary**, **narrative**, **figure_explanations**, **ticker_cards**, **actions_section**, **data_freshness**
- **provenance** — list of { claim_or_figure_id, source_field?, source_ticker?, source_figure_id? } or { claim_or_figure_id, source, urls } for web
- **references** — URLs from web research
- **research_qa** — list of { question, answers } from web research (grouped by query_used)
- **audit_notes** — if Stage 9 found issues, concatenated severity + message

### 5.2 Figure specs (Vega-Lite)

- **build_all_specs(payload, figure_data)** in **vega_specs** builds a list of Vega-Lite v5 spec dicts.
- **Input:** `payload.entries` and `figure_data` (in pipeline, this is `figure_data["by_ticker"]`).
- **Charts produced:**  
  - Recommendation bar (BUY/HOLD/SELL counts from entries)  
  - Daily % change bar (from entries’ quote)  
  - Return range (bear/base/bull from entries)  
  - Per-ticker: price series from `figure_data[ticker]["historical"]`, and optional fundamentals bar from `figure_data[ticker]["financial_charts"]`.
- **Note:** The pipeline’s figure_data also has pre-aggregated keys (e.g. risk_return_scatter, sector_exposure) for potential future specs; current **build_all_specs** only uses entries + by_ticker historical/financial_charts.

### 5.3 HTML report (html_report.build_html)

- **Input:** agent_output (title, portfolio_summary, narrative, figure_explanations, per_ticker_highlights, actions_section, references, research_qa), payload, figure specs, report_date.
- **Layout (paper-style):**
  - Title and meta (user, date)
  - **Summary** — portfolio_summary (prose)
  - **Key metrics** — first three figures with short intros (Fig 1: recommendation dist, Fig 2: daily change, Fig 3: return range)
  - **Discussion** — narrative
  - **Interpretation of figures** — figure_explanations
  - **Action plan** — actions_section
  - **Per-ticker highlights** — list from ticker_cards
  - **Supporting figures** — remaining specs (e.g. price series, fundamentals)
  - **Research questions explored** — research_qa (question + answers)
  - **References** — numbered list; [1], [2] in text are turned into superscript links to #ref-1, #ref-2
- **Charts:** Vega-Lite specs are serialized to JSON and embedded with vega-embed (Vega 5 / Vega-Lite 5 CDN). Each figure has a caption and a container div (chart-0, chart-1, …).
- **Provenance:** Stored in report_json but not rendered as a separate section in the current HTML; narrative and figure_explanations are expected to cite figures and references.

### 5.4 Payload and figure data sources

- **Payload:** **report_payload.build_payload** uses backend DB (User, Subscription) and **ReportService** to get latest report per ticker, plus **info_fetcher** (quotes, company info). Entries include ticker, name, recommendation, confidence, key_takeaways, bull/bear, expected_return_pct, bear/bull case, quote, report_scores.
- **Figure data (pipeline):** **fetch_figure_data** (historical, financial_charts) and backend company info (sector/industry); volatility derived from historical in Stage 6. Same data sources as Market/Fundamentals analysts; no tradingagents imports.

---

## 6. Caching and outputs

- **Cache:** Optional, keyed by `user_{user_id}_{report_date}` under `out/cache/`. Stores evidence_packets, theme_output, figure_plan, data_jobs, actions_output, narrative_output, user_intent. Does **not** store raw figure_data (by_ticker).
- **Stage outputs:** If `write_stage_outputs=True`, conductor writes JSON files under `out/pipeline_stages/<user_slug>_<report_date>/` (00_payload.json through 09_audit_output.json). Useful for debugging and inspecting intermediate results.
- **Final output:** One HTML file (default `out/watchlist_report_<user_slug>_<date>.html`). With `--write-json`, a `.report.json` sidecar is written with the report_json content.

---

## 7. Summary diagram

```
Payload (DB + ReportService + quotes)
    → Stage 1: UserIntent (no LLM)
    → Stage 2: EvidencePacket[] (LLM per ticker, optional)
    → Stage 3: ThemeOutput (LLM themes/risks + code exposure/divergent/regime)
    → Stage 4: WebResearchOutput (LLM queries + SerpAPI + LLM analysis + optional depth)
    → Stage 5: figure_plan, data_jobs (no LLM)
    → Stage 6: figure_data (fetch_figure_data + company info + volatility)
    → Stage 7: ActionsOutput (rules + optional web summary)
    → Stage 8: NarrativeOutput (LLM structured, optional; provenance + web citations)
    → Stage 9: AuditOutput (deterministic checks)
    → report_dict + figure_specs (vega_specs) + figure_data
    → ReportJson + build_html → HTML file
```

This is the current design of watchlist consulting: a staged, evidence-based pipeline with optional LLMs at evidence extraction, theme mining, web research, and narrative composition, and optional web search feeding references and research Q&A into the final report.
