# TradingAgents — Exact AI Analysis Flow

This document describes the **exact flow** of the AI analysis in TradingAgents: entry points, graph topology, state, and decision output.

---

## Graph engineering perspective

The TradingAgents pipeline is a **LangGraph `StateGraph`** — a state machine where:

- **Nodes do work.** Each node is classified on the deterministic-to-agentic scale:
  - **Fixed step** — deterministic code or a simple API call (no LLM).
  - **Model step** — a single structured LLM call (no tools).
  - **Agent step** — a full internal ReAct loop (the node calls tools, inspects results, and iterates until done — all without graph-level routing).
- **Edges define transitions.** Most post-analyst edges are deterministic. The analyst fan-out and debate routing are conditional/dynamic.
- **Cycles are intentional.** The debate loop (Bull ↔ Bear ↔ Neutral) is a directed cycle; this is expected and correct behavior, not a bug.
- **Dynamic fan-out via `Send`.** When `parallel_analysts=True` (default), a single conditional edge from `START` fans out dynamically to N analyst nodes using LangGraph's `Send` primitive — the number of workers equals the number of `selected_analysts`, which is not known until runtime.

The graph is therefore **not a DAG**: it contains cycles (debate) and dynamic fan-out. This is the normal shape for a production agentic system.

---

## 1. Entry points

Analysis can be started from:

| Entry | Where | What happens |
|-------|--------|----------------|
| **Dashboard API** | `backend/main.py` → `POST /api/analyses/start` | Calls `AnalysisService.start_analysis()` with ticker, analysis_date, analysts (default `["market", "news", "fundamentals", "sec"]`), research_depth, llm_provider, progress_callback, initiator_email; runs analysis in a background thread. |
| **CLI** | `cli/main.py` → `run_analysis()` | Builds config, creates `TradingAgentsGraph`, creates initial state, then `graph.stream(init_agent_state, **args)` (or `invoke` in non-debug). |

In both cases the **core execution** is:

1. **State init**: `graph.propagator.create_initial_state(ticker, trade_date)`
2. **Graph args**: `graph.propagator.get_graph_args()` → `stream_mode="values"`, `config={"recursion_limit": ...}`
3. **Run**: `graph.graph.stream(init_agent_state, **args)` (or `invoke` in non-debug)
   The `graph` is the **compiled LangGraph** built in `GraphSetup.setup_graph(selected_analysts)`.

---

## 2. Graph topology

The graph is a **`StateGraph(AgentState)`**. Edges are fixed and conditional as below.

### 2.1 Analyst phase — parallel Agent nodes (dynamic fan-out)

**Node type: Agent step** — each analyst is a self-contained node with an internal ReAct loop. The node calls its tools, inspects results, and iterates until it has enough context to produce a structured report. There are **no separate tool nodes or message-clear nodes** in the compiled graph; all tool execution happens inside the node.

**Fan-out (parallel, default):**

When `parallel_analysts=True` (default) and more than one analyst is selected, `setup_graph` adds a conditional edge from `START` that returns a `list[Send]` — one `Send` per analyst. LangGraph dispatches all analyst nodes concurrently. After all analyst nodes complete, a barrier edge routes to `Bull Researcher`.

```
START ──conditional_edge(fan_out_analysts)──► Market Analyst    ─┐
                                            ► Social Analyst     ├── (barrier) ──► Bull Researcher
                                            ► Fundamentals Analyst│
                                            ► Technical Analyst  │
                                            ► SEC Analyst        │
                                            ► Valuation Analyst  ─┘
```

**Fan-out (sequential, fallback):**

When `parallel_analysts=False` or only one analyst is selected, analysts run in a deterministic chain: `START → Analyst_1 → Analyst_2 → … → Bull Researcher`.

**Available analyst types** (selection order when sequential):

| Analyst | State fields written | Node type |
|---------|----------------------|-----------|
| `market` | `market_report`, `market_score` (1–5), `market_key_takeaways` | Agent step |
| `social` | `sentiment_report`, `sentiment_score` (1–5), `sentiment_key_takeaways` | Agent step |
| `fundamentals` | `fundamentals_report`, `fundamentals_score` (1–5), `fundamentals_key_takeaways` | Agent step |
| `technical` | `technical_report`, `technical_score` (1–5), `technical_key_takeaways` | Agent step |
| `sec` | `sec_report`, `sec_score` (1–5), `sec_key_takeaways` | Agent step |
| `valuation` | `valuation_report`, `valuation_score` (1–5), `valuation_key_takeaways`, `fair_value_bear/base/bull`, `current_discount_pct`, `valuation_conviction` | Agent step |

Default selections:
- **`setup_graph` default**: `["market", "social", "fundamentals"]`
- **Dashboard API default**: `["market", "news", "fundamentals", "sec"]` (where `"news"` maps to the Social/News & Sentiment analyst)

#### Social (News & Sentiment) Analyst

The `"social"` analyst produces `sentiment_report` and `sentiment_score`. Despite the key name, it covers news/catalysts and crowd sentiment (insider transactions, Reddit sentiment, global news). It is the "News & Sentiment Analyst" in user-facing UI.

#### Technical Analyst

When `"technical"` is in `selected_analysts`, the Technical Analyst uses tools including `get_stock_data`, `get_indicators`, and advanced pattern tools (`detect_divergence`, `detect_regime`, `detect_support_resistance`).

#### SEC Analyst

When `"sec"` is in `selected_analysts`, the SEC Analyst uses `get_edgar_filing_content` to fetch and parse SEC EDGAR filings (10-K/10-Q), extracting Risk Factors, MD&A, and Competition sections.

#### Valuation Analyst

When `"valuation"` is in `selected_analysts`, the Valuation Analyst performs multi-method fair value analysis, producing bear/base/bull fair value estimates and a discount-to-fair-value percentage.

---

## 3. Investment debate (Bull ↔ Bear ↔ Neutral) — cyclic subgraph

**Node type: Model step** — each researcher makes a single LLM call (no tools) using all analyst reports and the accumulated debate history.

After all analyst nodes complete, a barrier routes to `Bull Researcher`. The debate then runs round-robin:

```
Bull Researcher ──should_continue_debate──► Bear Researcher
Bear Researcher ──should_continue_debate──► Neutral Researcher
Neutral Researcher ──should_continue_debate──► Bull Researcher
(any) ──should_continue_debate (when count ≥ 3 × max_debate_rounds)──► Research Manager
```

This is a **directed cycle** — the graph is not a DAG. One round = one turn each for Bull, Bear, and Neutral (count incremented per turn).

**Routing logic** (`ConditionalLogic.should_continue_debate`):
- `count >= 3 * max_debate_rounds` → `Research Manager`
- `latest_speaker` starts with `"Bull"` → `Bear Researcher`
- `latest_speaker` starts with `"Bear"` → `Neutral Researcher`
- otherwise → `Bull Researcher`

State written per turn: `investment_debate_state` (`bull_history`, `bear_history`, `neutral_history`, `history`, `latest_speaker`, `current_response`, `count`).

---

## 4. Research Manager → Trader

**Both are fixed graph edges (deterministic).**

### Research Manager — Model step

- **Inputs**: all analyst reports (`market_report`, `sentiment_report`, `fundamentals_report`, optional `sec_report`, `technical_report`, `valuation_report`, `events_report`), full debate `history`, judge memory.
- **Outputs** (structured `ResearchManagerOutput`):
  - `investment_plan` — comprehensive narrative for the Trader.
  - `recommendation` — **BUY / SELL / HOLD** (issued directly by the Research Manager).
  - `recommendation_score` (1–5) — directional conviction score.
  - `bull_summary`, `bear_summary`, `neutral_summary` — 3–5 bullet summaries of each side's debate arguments.
  - `expected_return_pct`, `bear_case_return_pct`, `bull_case_return_pct` — return scenarios.
  - `key_takeaways` — written to `investment_plan_key_takeaways`.
- **Edge**: deterministic → `Trader`.

### Trader — Model step

- **Inputs**: `investment_plan`, all analyst reports, `recommendation` from Research Manager, `events_report`, trader memory, live quote (fetched inside node).
- **Outputs** (structured `TraderOutput`):
  - `trader_investment_plan` — detailed narrative with execution rationale.
  - `trader_recommendation` — **BUY / SELL / HOLD**.
  - `trader_tps_plan` — structured **TPS-YAML v0.1** trade plan (instrument, timeframe, side, entry, risk.stop, risk.max_loss, take_profit, vol_guard, add_if).
  - `trader_key_takeaways`.
- **Edge**: deterministic → `END`.

---

## 5. Risk debate (legacy — not in compiled graph)

> **Note**: The `AgentState` type still defines `risk_debate_state`, `final_trade_decision`, `risky_summary`, `safe_summary`, `neutral_summary` (risk side), and `risk_score` fields. These originated from an older version of the graph that included Risky / Safe / Neutral Analysts and a Risk Judge after the Trader. **The current compiled graph does not include these nodes** — `setup.py` adds `Trader → END` with no risk debate in between. These state fields are currently unpopulated at the end of a run. Do not rely on them in new code.

---

## 6. State (AgentState) — what flows through

- **Input / identity**: `company_of_interest`, `trade_date`, `events_report`, `prior_reports`, `prior_analysis_date`, `sender`.
- **Analyst outputs**: `market_report`, `market_score` (1–5); `sentiment_report`, `sentiment_score` (1–5); `fundamentals_report`, `fundamentals_score` (1–5); `sec_report`, `sec_score` (1–5); `technical_report`, `technical_score` (1–5); `valuation_report`, `valuation_score` (1–5), `fair_value_bear/base/bull`, `current_discount_pct`, `valuation_conviction`.
- **Key takeaways per analyst**: `market_key_takeaways`, `sentiment_key_takeaways`, `fundamentals_key_takeaways`, `sec_key_takeaways`, `technical_key_takeaways`, `valuation_key_takeaways`.
- **Investment debate**: `investment_debate_state` (`bull_history`, `bear_history`, `neutral_history`, `history`, `latest_speaker`, `current_response`, `count`, `judge_decision`).
- **Research Manager**: `investment_plan`, `recommendation` (BUY/SELL/HOLD), `recommendation_score` (1–5), `bull_summary`, `bear_summary`, `neutral_summary`, `expected_return_pct`, `bear_case_return_pct`, `bull_case_return_pct`, `investment_plan_key_takeaways`.
- **Trader**: `trader_investment_plan`, `trader_recommendation` (BUY/SELL/HOLD), `trader_tps_plan` (TPS-YAML JSON string), `trader_key_takeaways`.
- **LLM usage / tracing**: `report_usage` (tokens, cost per report key), `report_resources`, `report_resources_by_report`, `report_steps_by_report`.
- **Legacy (unpopulated)**: `risk_debate_state`, `final_trade_decision`, `risk_score`, `risky_summary`, `safe_summary` (risk), `neutral_summary` (risk), `final_report_key_takeaways`.

Each node **reads** from this state and **returns** a dict of keys to **update** (LangGraph merges into the single `AgentState`).

---

## 7. After the graph finishes

- **`resolve_trade_signal_from_state(state)`** (`signal_processing.py`):
  - Reads `recommendation` first (from Research Manager), then falls back to `trader_recommendation`.
  - Returns `BUY`, `SELL`, or `HOLD` — no second LLM call.

- **`TradingAgentsGraph.propagate()`** (used from CLI or equivalent):
  - Stores `final_state` in `self.curr_state`.
  - Logs state to `eval_results/{ticker}/TradingAgentsStrategy_logs/full_states_log_{date}.json`.
  - Returns `(final_state, resolve_trade_signal_from_state(final_state))`.

- **Reflection (optional)**
  `reflect_and_remember(returns_losses)` updates bull/bear/neutral/trader/research-manager memories based on outcomes.

---

## 8. Flow summary diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ENTRY: create_initial_state(ticker, date) → graph.stream(state, **args)     │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ ANALYST PHASE — Agent steps (each: full internal ReAct loop + tools)        │
│                                                                             │
│ Parallel (default, via Send):                                               │
│   START ──fan_out──► Market Analyst      ─┐                                 │
│                    ► Social Analyst       ├── barrier ──► Bull Researcher   │
│                    ► Fundamentals Analyst │                                 │
│                    ► [Technical Analyst]  │  (N = len(selected_analysts),   │
│                    ► [SEC Analyst]        │   resolved at runtime)          │
│                    ► [Valuation Analyst] ─┘                                 │
│                                                                             │
│ Sequential (fallback):                                                      │
│   START → Analyst_1 → Analyst_2 → … → Bull Researcher                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ INVESTMENT DEBATE — Model steps (cyclic; not a DAG)                         │
│   Bull Researcher ⇄ Bear Researcher ⇄ Neutral Researcher                   │
│   (round-robin until count ≥ 3 × max_debate_rounds)                        │
│                              │                                              │
│                              ▼                                              │
│                      Research Manager                                       │
│                   (issues investment_plan + recommendation BUY/SELL/HOLD)   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │ (fixed edge)
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TRADER — Model step                                                         │
│   Produces: trader_investment_plan, trader_recommendation, TPS-YAML plan   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │ (fixed edge)
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ END                                                                         │
│ resolve_trade_signal_from_state() → reads recommendation or                 │
│   trader_recommendation → BUY | SELL | HOLD  (no LLM call)                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Key files reference

| Concern | File |
|--------|------|
| Graph build, nodes, edges, parallel Send fan-out | `tradingagents/graph/setup.py` |
| Initial state, graph args | `tradingagents/graph/propagation.py` |
| Debate routing condition | `tradingagents/graph/conditional_logic.py` |
| Orchestrator, LLMs, tools, propagate | `tradingagents/graph/trading_graph.py` |
| BUY/SELL/HOLD extraction (no LLM) | `tradingagents/graph/signal_processing.py` |
| State types (AgentState, InvestDebateState, RiskDebateState) | `tradingagents/agents/utils/agent_states.py` |
| Self-contained analyst base | `tradingagents/agents/analysts/self_contained_analyst.py` |
| Research Manager (judge + plan + recommendation) | `tradingagents/agents/managers/research_manager.py` |
| Trader (narrative + TPS-YAML plan) | `tradingagents/agents/trader/trader.py` |
| Analysts | `tradingagents/agents/analysts/*.py` |
| Bull/Bear/Neutral researchers | `tradingagents/agents/researchers/*.py` |
| Dashboard analysis run | `backend/services/analysis_service.py` |
| API trigger | `backend/main.py` (POST /api/analyses/start) |

This is the **exact flow** of the AI analysis in TradingAgents from request/CLI to final BUY/SELL/HOLD.
