# TradingAgents — Exact AI Analysis Flow

This document describes the **exact flow** of the AI analysis in TradingAgents: entry points, graph topology, state, and decision output.

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

## 2. Graph topology (exact node order)

The graph is a **StateGraph(AgentState)**. Edges are fixed and conditional as below.

### 2.1 Analyst chain (sequential)

- **START** → **First analyst** (e.g. `Market Analyst` if `selected_analysts = ["market", "news", "fundamentals"]`).

Analyst types (in selection order): **market**, **social**, **news**, **fundamentals**, **technical**, **sec**.  
Graph default is `["market", "social", "news", "fundamentals"]`; Dashboard API default is `["market", "news", "fundamentals", "sec"]`.

For **each** selected analyst (e.g. `market`, `social`, `news`, `fundamentals`):

1. **`{Analyst} Analyst`** (e.g. `Market Analyst`, `Social Analyst`, `News Analyst`, …)
   - Reads state: `company_of_interest`, `trade_date`, `messages`.
   - Uses LLM + tools (e.g. `get_stock_data`, `get_indicators` for market; social uses `get_insider_sentiment`, `get_insider_transactions`, `get_global_news`) to produce a report and score.
   - Writes: `market_report`, `sentiment_report` (Social), `news_report`, `fundamentals_report`, `sec_report`, `technical_report` and corresponding `*_score`.
   - Conditional edge:
     - If last message has **tool_calls** → **`tools_{analyst}`**
     - Else → **`Msg Clear {Analyst}`**

2. **`tools_{analyst}`**
   - Runs the analyst’s tools (e.g. ToolNode for market: `get_stock_data`, `get_indicators`).
   - Edge: **back to** **`{Analyst} Analyst`** (analyst can call tools again).

3. **`Msg Clear {Analyst}`**
   - Cleans messages for that analyst.
   - Edge:
     - If not last analyst → **next analyst** (e.g. `News Analyst`).
     - If last analyst → **Bull Researcher**.

So the **exact analyst flow** is:

```
START → Analyst_1 ⟷ tools_1 → Msg Clear 1 → Analyst_2 ⟷ tools_2 → … → Msg Clear Last → Bull Researcher
```

(Each analyst can loop with its tool node until it stops calling tools.)

#### Social Analyst

When `"social"` is in `selected_analysts`, the **Social (Media) Analyst** runs in the analyst chain. It produces `sentiment_report` and `sentiment_score` (1–10) using tools such as `get_insider_sentiment`, `get_insider_transactions`, `get_global_news`.

#### Technical Analyst (optional)

When `"technical"` is in `selected_analysts`, the **Technical Analyst** runs with tools including `get_stock_data`, `get_indicators`, and advanced tools (`detect_divergence`, `detect_regime`, `detect_support_resistance`). It produces `technical_report` and `technical_score` (1–10).

#### SEC Analyst (optional)

When `"sec"` is in `selected_analysts`, the **SEC Analyst** runs in the analyst chain. It uses the `get_edgar_filing_content` tool, which calls the backend `GET /api/data/edgar-filing-content/{ticker}`. The backend fetches the filing from SEC EDGAR, converts HTML to text, and uses an LLM to extract structured sections (Risk Factors, MD&A, Competition). The SEC analyst receives that formatted content and produces `sec_report` and `sec_score` (1–10). The risk manager includes `sec_report` in its context and factors regulatory and disclosure risk into the final decision.

---

## 3. Investment debate (Bull vs Bear)

After the last analyst’s “Msg Clear”:

- **Bull Researcher**
  - Inputs: all reports (market, sentiment, news, fundamentals, optional sec, optional technical), `investment_debate_state` (history, current_response, count).
  - Outputs: bull argument; updates `investment_debate_state` (history, bull_history, current_response, count).
  - Conditional edge:
    - If `count >= 2 * max_debate_rounds` → **Research Manager**
    - Else if `current_response` starts with `"Bull"` → **Bear Researcher**
    - Else → **Bull Researcher** (next turn is bull again in practice from setup).

- **Bear Researcher**
  - Same idea: uses reports + debate history; produces bear argument; updates `investment_debate_state`.
  - Conditional edge:
    - If `count >= 2 * max_debate_rounds` → **Research Manager**
    - Else → **Bull Researcher**.

So the loop is: **Bull Researcher ⇄ Bear Researcher** until `count >= 2 * max_debate_rounds`, then → **Research Manager**.

---

## 4. Research Manager → Trader

- **Research Manager**
  - Inputs: all reports (including sec_report when SEC analyst ran), full debate `history`, judge memory.
  - Produces: `investment_plan`, `recommendation_score` (1–10), `expected_return_pct`, `bear_case_return_pct`, `bull_case_return_pct` (optional), and updates `investment_debate_state` (e.g. `judge_decision`).
  - Edge: **Trader** (fixed).

- **Trader**
  - Inputs: investment plan, reports, trader memory.
  - Produces: `trader_investment_plan` (and can set `final_trade_decision` or it’s set later from risk).
  - Edge: **Risky Analyst** (fixed).

---

## 5. Risk debate (Risky / Safe / Neutral) → Risk Judge

- **Risky Analyst**
  - Conditional edge:
    - If `risk_debate_state["count"] >= 3 * max_risk_discuss_rounds` → **Risk Judge**
    - Else if last speaker was Risky → **Safe Analyst**
    - Else → **Risky Analyst** (or Safe/Neutral per logic).

- **Safe Analyst** and **Neutral Analyst**
  - Same pattern: conditional on `count` and `latest_speaker`:
    - Either continue to the next risk debator (Risky / Safe / Neutral),
    - Or go to **Risk Judge** when round limit is reached.

- **Risk Judge**
  - Produces final risk decision, **`final_trade_decision`** (text), and optionally **`recommendation`** (BUY/HOLD/SELL), **`risk_score`**, **`risky_summary`**, **`safe_summary`**, **`neutral_summary`**, **`final_report_key_takeaways`**.
  - Edge: **END**.

So: **Risky Analyst → Safe Analyst → Neutral Analyst → Risky Analyst → …** (round-robin via `should_continue_risk_analysis`) until `count >= 3 * max_risk_discuss_rounds`, then → **Risk Judge** → **END**.

---

## 6. State (AgentState) — what flows through

- **Input / identity**: `company_of_interest`, `trade_date`, `messages`, `sender`.
- **Analyst outputs**: `market_report`, `market_score`; `sentiment_report`, `sentiment_score`; `news_report`, `news_score`; `fundamentals_report`, `fundamentals_score`; `sec_report`, `sec_score`; `technical_report`, `technical_score`.
- **Investment debate**: `investment_debate_state` (`history`, `bull_history`, `bear_history`, `current_response`, `count`, `judge_decision`).
- **Research Manager**: `investment_plan`, `recommendation_score`, `expected_return_pct`, `bear_case_return_pct`, `bull_case_return_pct`, `bull_summary`, `bear_summary`.
- **Trader**: `trader_investment_plan`.
- **Risk debate**: `risk_debate_state` (`risky_history`, `safe_history`, `neutral_history`, `history`, `latest_speaker`, `current_risky_response`, `current_safe_response`, `current_neutral_response`, `count`, `judge_decision`).
- **Risk Judge**: `final_trade_decision`, `recommendation` (BUY/SELL/HOLD), `risk_score`, `risky_summary`, `safe_summary`, `neutral_summary`, `final_report_key_takeaways`.

Each node **reads** from this state and **returns** a dict of keys to **update** (LangGraph merges into the single AgentState).

---

## 7. After the graph finishes

- **TradingAgentsGraph.propagate()** (used from CLI or equivalent):
  - Stores `final_state` in `self.curr_state`.
  - Logs state to `eval_results/{ticker}/TradingAgentsStrategy_logs/full_states_log_{date}.json`.
  - Returns `(final_state, self.process_signal(final_state["final_trade_decision"]))`.

- **SignalProcessor.process_signal(full_signal)**:
  - Takes the **final_trade_decision** text (or equivalent).
  - Uses the quick-thinking LLM to **extract a single token**: **BUY**, **SELL**, or **HOLD**.
  - That is the **final actionable output** of the AI analysis. (The Risk Judge may also set **`recommendation`** directly; the dashboard can use either.)

- **Reflection (optional)**  
  `reflect_and_remember(returns_losses)` updates bull/bear/trader/judge/risk-manager memories based on outcomes.

---

## 8. Flow summary diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ENTRY: create_initial_state(ticker, date) → graph.stream(state, **args)     │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ ANALYST CHAIN (sequential; each can loop with tools)                        │
│ START → [Market] Analyst ⇄ tools_market → Msg Clear →                        │
│         [Social] Analyst ⇄ tools_social → Msg Clear →                        │
│         [News] Analyst ⇄ tools_news → Msg Clear →                            │
│         [Fundamentals] Analyst ⇄ tools_fundamentals → Msg Clear →             │
│         [Technical]/[SEC] … (if selected) → … → Bull Researcher              │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ INVESTMENT DEBATE (until max_debate_rounds)                                  │
│ Bull Researcher ⇄ Bear Researcher → Research Manager                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Research Manager → Trader                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ RISK DEBATE (round-robin until 3 * max_risk_discuss_rounds)                 │
│ Risky Analyst → Safe Analyst → Neutral Analyst → (loop) → Risk Judge → END   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ OUTPUT: final_trade_decision → process_signal() → BUY | SELL | HOLD          │
│         (or recommendation from Risk Judge if set)                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Key files reference

| Concern | File |
|--------|------|
| Graph build, nodes, edges | `tradingagents/graph/setup.py` |
| Initial state, graph args | `tradingagents/graph/propagation.py` |
| Analyst/tool/debate/risk routing | `tradingagents/graph/conditional_logic.py` |
| Orchestrator, LLMs, tools, propagate | `tradingagents/graph/trading_graph.py` |
| Final BUY/SELL/HOLD extraction | `tradingagents/graph/signal_processing.py` |
| State types | `tradingagents/agents/utils/agent_states.py` |
| Research Manager (judge + plan) | `tradingagents/agents/managers/research_manager.py` |
| Analysts | `tradingagents/agents/analysts/*.py` |
| Bull/Bear researchers | `tradingagents/agents/researchers/*.py` |
| Dashboard analysis run | `backend/services/analysis_service.py` |
| API trigger | `backend/main.py` (POST /api/analyses/start) |

This is the **exact flow** of the AI analysis in TradingAgents from request/CLI to final BUY/SELL/HOLD.
