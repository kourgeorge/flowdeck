"""
Stage 7: Recommendation & Action Engine.
Input: user_intent, evidence_packets, theme_output.
Output: actions_ranked (P0/P1/P2: deep-dive, wait for catalyst, set alerts, avoid), watchlist_cleanup_suggestions.
Rule-based policy aligned with user_profile (horizon, risk_budget, report_style).
"""

from __future__ import annotations

from typing import List, Optional

from pipeline_schemas import ActionItem, ActionsOutput, EvidencePacket, ThemeOutput, UserIntent, WebResearchOutput


def run_action_engine(
    user_intent: UserIntent,
    evidence_packets: List[EvidencePacket],
    theme_output: ThemeOutput,
    web_research_output: Optional[WebResearchOutput] = None,
) -> ActionsOutput:
    """
    Produce ranked actions and watchlist cleanup suggestions from evidence and theme.
    Personalization: long-term -> fundamentals/valuation; short-term -> catalysts/volatility.
    When web_research_output is provided, adds a P2 action summarizing recent web context where relevant.
    """
    actions: List[ActionItem] = []
    cleanup: List[str] = []

    # Deep-dive next: BUY with catalyst or widest scenario spread
    buy_tickers = []
    for p in evidence_packets:
        ac = p.action_candidate
        if ac and ac.action.lower() == "buy":
            spread = 0.0
            if p.scenario_range and p.scenario_range.bull_return_pct is not None and p.scenario_range.bear_return_pct is not None:
                spread = abs(p.scenario_range.bull_return_pct - p.scenario_range.bear_return_pct)
            has_catalyst = bool(p.catalysts)
            buy_tickers.append((p.ticker, spread, has_catalyst))
    buy_tickers.sort(key=lambda x: (-x[2], -x[1]))  # catalyst first, then spread
    if buy_tickers:
        top_buys = [t[0] for t in buy_tickers[:3]]
        actions.append(ActionItem(
            priority="P0",
            category="deep_dive",
            tickers=top_buys,
            description="Deep-dive next: strongest conviction or catalyst-driven names.",
            rationale="BUY recommendations with catalysts or wide scenario range.",
        ))

    # Wait for catalyst: tickers with explicit catalysts
    catalyst_tickers = [p.ticker for p in evidence_packets if p.catalysts and (p.action_candidate and p.action_candidate.action.lower() in ("hold", "watch"))]
    if catalyst_tickers:
        actions.append(ActionItem(
            priority="P1",
            category="wait_catalyst",
            tickers=catalyst_tickers[:5],
            description="Wait for catalyst (earnings, product, macro) before adding.",
            rationale="Near-term catalysts noted; hold or watch until clarity.",
        ))

    # Set alerts: divergent views or high volatility names
    divergent = [d.get("ticker") for d in (theme_output.divergent_views or []) if d.get("ticker")]
    if divergent:
        actions.append(ActionItem(
            priority="P2",
            category="set_alert",
            tickers=divergent[:5],
            description="Set alerts: views differ from watchlist majority.",
            rationale="Divergent recommendation vs rest of watchlist.",
        ))

    # Avoid / de-prioritize: SELL or thesis broken
    sell_tickers = [p.ticker for p in evidence_packets if p.action_candidate and p.action_candidate.action.lower() == "sell"]
    if sell_tickers:
        actions.append(ActionItem(
            priority="P0",
            category="avoid",
            tickers=sell_tickers,
            description="Avoid or reduce: thesis broken or downgraded.",
            rationale="Sell recommendation from analysis.",
        ))

    # Cleanup: duplicates (same sector/industry heavy concentration), outdated thesis
    if theme_output.exposure_snapshot:
        sector_counts = theme_output.exposure_snapshot.sector_counts or {}
        for sector, count in sector_counts.items():
            if sector != "N/A" and count > 3 and len(evidence_packets) <= 8:
                cleanup.append(f"High concentration in {sector} ({count} names); consider diversifying.")

    # Web research context: add one action when web learnings are available
    if web_research_output and web_research_output.learnings:
        top_learnings = [wl.text[:120] for wl in web_research_output.learnings[:3] if wl.text.strip()]
        if top_learnings:
            rationale = "Recent web context: " + " ".join(top_learnings)[:300] + ("..." if len(" ".join(top_learnings)) > 300 else "")
            actions.append(ActionItem(
                priority="P2",
                category="set_alert",
                tickers=[],
                description="Consider recent web and macro context when reviewing the watchlist.",
                rationale=rationale,
            ))

    return ActionsOutput(actions_ranked=actions, watchlist_cleanup_suggestions=cleanup)
