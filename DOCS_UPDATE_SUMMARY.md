# Docs Update Summary — Graph Engineering Framing

**Date**: 2026-07-25
**Source article**: `.claude/langgraph_graph_engineering_2026-07-22.md` (LangChain blog, Runkle & Chase)

---

## Code/doc mismatches found but NOT fixed (code is unchanged)

1. **`docs/AI_ANALYSIS_FLOW.md` §2 (analyst chain) was stale**: Described an old sequential graph with separate `tools_{analyst}` and `Msg Clear` nodes. The current code (`setup.py`) uses self-contained Agent nodes and parallel `Send` fan-out. Fixed in this update.

2. **`docs/AI_ANALYSIS_FLOW.md` §3 (debate) was stale**: Described a 2-way Bull ↔ Bear debate. The current code has a 3-way Bull ↔ Bear ↔ Neutral debate (`conditional_logic.py`, `researchers/neutral_researcher.py`). Fixed in this update.

3. **`docs/AI_ANALYSIS_FLOW.md` §5 (Risk debate) was stale**: Described Risky/Safe/Neutral Analysts and a Risk Judge node after the Trader. The current compiled graph (`setup.py`) ends at `Trader → END` — these nodes are not present. `AgentState` still declares `risk_debate_state` and related fields (legacy; unpopulated by the current graph). Fixed by adding a "legacy/not in compiled graph" note; the legacy state fields remain in code (not touched).

4. **`docs/AI_ANALYSIS_FLOW.md` §4 (Research Manager) was incomplete**: Did not note that the Research Manager issues a structured `recommendation: BUY/SELL/HOLD` directly. Confirmed from `research_manager.py` (`ResearchManagerOutput`). Fixed in this update.

5. **`docs/AI_ANALYSIS_FLOW.md` §7 (signal extraction) was stale**: Described a second LLM call via `process_signal()`. Current code uses `resolve_trade_signal_from_state()` which reads structured fields directly (`recommendation` → `trader_recommendation`) — no LLM call. Fixed in this update.

6. **Scores described as 1–10 throughout**: Current code uses **1–5** scale (confirmed from `research_manager.py`, `agent_states.py`, analyst output schemas). Fixed in this update.

7. **`docs/graph-flow-social-analyst.md` was stale**: Described a graph with `extract_resources` as a separate graph node and a sequential `START → Social Analyst → tools_social → extract_resources → Social Analyst` loop. The current analyst is self-contained; extraction happens inside the node, not via graph edges. Fixed in this update.

8. **`docs/GRAPH_COMPLEXITY_ANALYSIS.md` was historical**: Described the "problem" of external tool-loop nodes as if they were current. Those issues were resolved before this update. Added a status banner; document retained for history.

---

## Files touched

- **`docs/AI_ANALYSIS_FLOW.md`** — Major update: added "Graph engineering perspective" section at top; rewrote §2 (analyst phase) to describe self-contained Agent nodes and parallel `Send` fan-out; updated §3 to 3-way Bull/Bear/Neutral debate; updated §4 to note Research Manager issues BUY/SELL/HOLD; added §5 noting Risk debate nodes are legacy/not in compiled graph; corrected all scores to 1–5; updated §7 (signal extraction, no LLM call); updated flow diagram (§8); updated key files table (§9).

- **`docs/ARCHITECTURE.md`** — Extended the TradingAgents section (§2) with a "Graph engineering perspective" sub-section: classifies nodes as Agent/Model steps, explains parallel `Send` fan-out, explains the cyclic debate, and adds a cross-reference to AI_ANALYSIS_FLOW.md. Existing Mermaid diagram and other sections unchanged.

- **`docs/graph-flow-social-analyst.md`** — Full rewrite: updated to reflect self-contained Agent node pattern (internal ReAct loop, no external `tools_social`/`extract_resources` nodes), added graph-engineering perspective header, updated topology diagram to show parallel fan-out context, added state fields table with correct 1–5 score range.

- **`docs/GRAPH_COMPLEXITY_ANALYSIS.md`** — Added status banner at top noting the described issues were resolved and pointing to AI_ANALYSIS_FLOW.md. Historical content preserved unchanged.
