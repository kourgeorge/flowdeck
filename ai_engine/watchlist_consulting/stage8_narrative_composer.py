"""
Stage 8: Narrative Composer.
Input: user_intent, evidence_packets, theme_output, figure_plan, figure_data, actions_ranked, watchlist_payload.
Output: NarrativeOutput (title, watchlist_summary, figure_explanations, ticker_cards, actions_section, provenance).
Follows outline; references every figure_id; no invented numbers — only evidence and figure_data; emits provenance.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pipeline_schemas import (
    ActionsOutput,
    EvidencePacket,
    FigurePlanItem,
    NarrativeOutput,
    TickerCard,
    ThemeOutput,
    UserIntent,
    WebResearchOutput,
)

try:
    from report_agent import _get_llm
except ImportError:
    _get_llm = None


def _evidence_summary(packets: List[EvidencePacket]) -> str:
    """Condense evidence for prompt."""
    lines = []
    for p in packets:
        lines.append(f"[{p.ticker}] Thesis: " + " | ".join(p.thesis_bullets[:3]))
        if p.key_risks:
            lines.append(f"  Risks: " + " | ".join(p.key_risks[:2]))
        if p.scenario_range:
            sr = p.scenario_range
            lines.append(f"  Scenario: bear={sr.bear_return_pct}% base={sr.base_return_pct}% bull={sr.bull_return_pct}%")
        if p.action_candidate:
            lines.append(f"  Action: {p.action_candidate.action} — {p.action_candidate.rationale[:100]}")
    return "\n".join(lines)[:8000]


def _figure_plan_summary(figure_plan: List[FigurePlanItem]) -> str:
    """List figure_id and title so narrative must reference each."""
    return "\n".join(f"- {fp.figure_id}: {fp.title}" for fp in figure_plan)


def _actions_summary(actions: ActionsOutput) -> str:
    """Text summary of actions for prompt."""
    lines = []
    for a in actions.actions_ranked:
        lines.append(f"[{a.priority}] {a.category}: {', '.join(a.tickers)} — {a.description}")
    return "\n".join(lines) or "No actions."


def _web_research_summary(web: Optional[WebResearchOutput]) -> str:
    """Condensed web learnings and numbered sources for prompt; empty if no web research."""
    if not web or not web.learnings:
        return ""
    bullets = "\n".join(f"- {wl.text}" for wl in web.learnings[:15])
    sources = web.sources or []
    ref_list = "\n".join(f"  [{i}] {u}" for i, u in enumerate(sources[:25], start=1))
    return (
        f"Web research learnings (use to reinforce or contrast with report evidence):\n{bullets}\n\n"
        f"Numbered references (cite these in the text with [1], [2], etc.):\n{ref_list}\n\n"
        "When you use information from the web learnings above in watchlist_summary or narrative, "
        "add a citation at the end of the sentence, e.g. [1] or [2], matching the reference number."
    )


def _append_web_provenance(
    narrative_output: NarrativeOutput,
    web: Optional[WebResearchOutput],
) -> NarrativeOutput:
    """Append provenance entries for web learnings so report cites web sources."""
    if not web or not web.learnings or not web.sources:
        return narrative_output
    prov = list(narrative_output.provenance or [])
    for i, wl in enumerate(web.learnings[:20]):
        prov.append({
            "claim_or_figure_id": f"web_learning_{i+1}",
            "source": "web",
            "urls": wl.source_urls or web.sources[:3],
        })
    return NarrativeOutput(
        title=narrative_output.title,
        watchlist_summary=narrative_output.watchlist_summary,
        narrative=narrative_output.narrative,
        figure_explanations=narrative_output.figure_explanations,
        ticker_cards=narrative_output.ticker_cards,
        actions_section=narrative_output.actions_section,
        provenance=prov,
    )


def run_narrative_composer(
    user_intent: UserIntent,
    evidence_packets: List[EvidencePacket],
    theme_output: ThemeOutput,
    figure_plan: List[FigurePlanItem],
    figure_data: Dict[str, Any],
    actions_ranked: ActionsOutput,
    watchlist_payload: Dict[str, Any],
    use_llm: bool = True,
    web_research_output: Optional[WebResearchOutput] = None,
) -> NarrativeOutput:
    """
    Produce narrative following outline; reference every figure_id; emit provenance.
    """
    entries = watchlist_payload.get("entries") or []
    figure_ids = [fp.figure_id for fp in figure_plan]

    if not use_llm or not _get_llm:
        return _fallback_narrative(
            entries, evidence_packets, theme_output, figure_plan, actions_ranked, figure_ids,
            web_research_output=web_research_output,
        )

    from langchain_core.messages import HumanMessage

    evidence_text = _evidence_summary(evidence_packets)
    figure_plan_text = _figure_plan_summary(figure_plan)
    actions_text = _actions_summary(actions_ranked)
    web_section = _web_research_summary(web_research_output)

    prompt = (
        "You are writing a **consultation report** for the client: a clear, evidence-based explanation of their portfolio. "
        "Explain the companies in the watchlist, their risks, opportunities, and volatility. Every claim must be supported by the evidence or by a specific figure (e.g. 'as shown in Figure 1', 'see Figure 3'). Do not invent numbers.\n\n"
        "OUTLINE (follow this order):\n"
        "1. Executive summary (watchlist_summary): Write 3-5 paragraphs as a consultation overview. Explain what the portfolio holds, sector exposure, recommendation mix (BUY/HOLD/SELL), main risks and opportunities, and any divergent views. Tie each point to evidence or to a figure where relevant (e.g. 'Figure 1 shows the current tilt').\n"
        "2. Discussion (narrative): Write 2-4 paragraphs that explain how the figures support the story. Cover: recommendation distribution (Figure 1), daily moves and volatility (Figure 2), return ranges and uncertainty (Figure 3), and price/fundamental trends. Explicitly reference Figure 1, 2, 3 and supporting charts so the client sees where each claim is documented.\n"
        "3. Figure explanations (figure_explanations): For EACH figure below write 2-4 sentences: what the chart shows, how to read it, and what to look for. You MUST reference every figure_id. Be specific.\n"
        "Figure plan (reference each by figure_id):\n" + figure_plan_text + "\n\n"
        "4. Action plan (actions_section): Summarize the ranked actions in clear bullets with brief rationale.\n"
        "5. Ticker cards: For each ticker provide a short consultation-style summary: thesis, key risks, opportunities, and volatility or scenario (1-3 sentences); top 3 get is_expanded=true and optional details.\n\n"
    )
    if web_section:
        prompt += (
            "WEB RESEARCH (integrate where relevant; add inline citations [1], [2], etc.):\n"
            "Use the following web learnings to reinforce or contrast with report evidence. Weave them into watchlist_summary or narrative where they add value. "
            "Whenever you use a web learning, cite its source with the corresponding reference number in square brackets, e.g. [1] or [2], at the end of the sentence. "
            "Do not invent numbers; only cite insights that are clearly stated below. In provenance, include entries for web-backed claims.\n\n"
            + web_section + "\n\n"
        )
    prompt += (
        "RULES: Do not invent numbers. Only use numbers from the evidence and scenario ranges given (or from web learnings when stated). "
        "Support every claim with a figure or evidence. Use a consultation tone: explain risks, opportunities, and volatility for the client. "
        "Produce: title (e.g. 'Portfolio consultation report'), watchlist_summary, narrative, figure_explanations, ticker_cards, actions_section, provenance (include figure_ids and web_learning entries when you use web content)."
    )

    try:
        llm = _get_llm()
        structured = llm.with_structured_output(NarrativeOutput)
        out = structured.invoke([HumanMessage(content=prompt)])
        if isinstance(out, NarrativeOutput):
            return _append_web_provenance(out, web_research_output)
        if isinstance(out, dict):
            narr_out = NarrativeOutput(
                title=out.get("title") or "Watchlist Report",
                watchlist_summary=out.get("watchlist_summary") or "",
                narrative=out.get("narrative") or "",
                figure_explanations=out.get("figure_explanations") or "",
                ticker_cards=[TickerCard(**c) if isinstance(c, dict) else c for c in out.get("ticker_cards", [])],
                actions_section=out.get("actions_section") or "",
                provenance=out.get("provenance") or [],
            )
            return _append_web_provenance(narr_out, web_research_output)
    except Exception:
        pass

    return _fallback_narrative(
        entries, evidence_packets, theme_output, figure_plan, actions_ranked, figure_ids,
        web_research_output=web_research_output,
    )


def _fallback_narrative(
    entries: List[Dict[str, Any]],
    evidence_packets: List[EvidencePacket],
    theme_output: ThemeOutput,
    figure_plan: List[FigurePlanItem],
    actions_ranked: ActionsOutput,
    figure_ids: List[str],
    web_research_output: Optional[WebResearchOutput] = None,
) -> NarrativeOutput:
    """No-LLM narrative: substantial summary, discussion, and figure explanations from evidence and theme."""
    rec_counts = {"BUY": 0, "HOLD": 0, "SELL": 0}
    for p in evidence_packets:
        a = p.action_candidate.action.upper() if p.action_candidate else "HOLD"
        if a == "BUY" or a == "SELL":
            rec_counts[a] = rec_counts.get(a, 0) + 1
        else:
            rec_counts["HOLD"] = rec_counts.get("HOLD", 0) + 1
    n_buy, n_hold, n_sell = rec_counts.get("BUY", 0), rec_counts.get("HOLD", 0), rec_counts.get("SELL", 0)

    exp = theme_output.exposure_snapshot
    sector_counts = (exp.sector_counts or {}) if exp else {}
    sector_line = ", ".join(f"{s}: {c}" for s, c in sorted(sector_counts.items(), key=lambda x: -x[1])[:5]) if sector_counts else "Not available."
    risks = theme_output.common_risks or []
    risks_line = "; ".join(risks[:5]) if risks else "General market and sector risks apply."
    divergent = theme_output.divergent_views or []
    regime = theme_output.regime_fit or "Mixed exposure across sectors."

    watchlist_summary = (
        f"This consultation report covers your watchlist of {len(entries)} names. "
        f"The current mix of views is tilted bullish: {n_buy} BUY, {n_hold} HOLD, and {n_sell} SELL (see Figure 1). "
        f"Sector exposure is {sector_line}. {regime}\n\n"
        f"Risks that appear across multiple names include: {risks_line}. "
        "Figure 2 shows same-day volatility and price moves; Figure 3 shows expected return ranges (bear, base, bull) for each name. "
        "Supporting figures show six-month price and fundamental trends. Use the action plan and per-ticker highlights to decide next steps.\n\n"
    )
    if divergent:
        watchlist_summary += (
            f"One name stands out from the majority: {', '.join(d.get('ticker', '') for d in divergent)} "
            f"is rated {divergent[0].get('action', '')} while the rest of the watchlist is mostly {divergent[0].get('majority', '')}. "
            "Worth reviewing separately for conviction or timing."
        )
    else:
        watchlist_summary += "Recommendations are broadly aligned across the watchlist; the main differentiator is magnitude of expected return and risk."

    narrative = (
        "Figure 1 documents the distribution of BUY, HOLD, and SELL recommendations across your watchlist—use it to assess overall tilt and conviction. "
        "Figure 2 shows same-day price change and short-term volatility for each ticker. "
        "Figure 3 plots the expected return range (bear, base, bull) for each name; wider spreads indicate higher uncertainty and risk. "
        "Supporting figures show six-month price and revenue (or EPS) trends so you can see how analyst views align with recent price and fundamental trajectory."
    )

    figure_explanations = (
        "**Recommendation distribution (Figure 1).** This bar chart shows how many watchlist names are rated BUY, HOLD, or SELL. "
        "It summarizes analyst tilt at a glance: a majority of BUYs suggests a constructive stance; a mix of HOLDs and SELLs suggests caution or selectivity.\n\n"
        "**Daily % change by ticker (Figure 2).** Each bar is the same-day price change for one ticker. "
        "Use it to see which names moved most on the report date and whether moves are in line with or against recent recommendations.\n\n"
        "**Expected return % — Bear / Base / Bull (Figure 3).** For each ticker, points show the low (bear), base (expected), and high (bull) return from the latest analysis. "
        "Larger gaps between bear and bull imply more uncertainty; similar ranges across names allow comparison of risk/reward.\n\n"
        "**Price series (Supporting figures).** Line charts of closing price over the last six months. "
        "They provide trend context and help relate current recommendations to recent price action.\n\n"
        "**Revenue / fundamentals (Supporting figures).** Bar charts of revenue or earnings per share over recent periods. "
        "They show fundamental trajectory and growth or pressure, complementing the return ranges and recommendations."
    )

    ticker_cards = []
    for e in entries:
        t = e.get("ticker") or ""
        name = e.get("name", t)
        p = next((x for x in evidence_packets if x.ticker == t), None)
        if p:
            thesis = " | ".join(p.thesis_bullets[:2]) if p.thesis_bullets else ""
            risks = " Key risks: " + " | ".join(p.key_risks[:2]) if p.key_risks else ""
            scenario = ""
            if p.scenario_range and p.scenario_range.base_return_pct is not None:
                scenario = f" Base case return: {p.scenario_range.base_return_pct}%."
            summary = (p.action_candidate.action if p.action_candidate else "—") + ": " + (thesis or name) + risks + scenario
            details = None
            if len(ticker_cards) < 3 and (p.thesis_bullets or p.key_risks):
                details = "\n".join(("- " + b for b in p.thesis_bullets[:3])) + ("\nRisks: " + " | ".join(p.key_risks[:3]) if p.key_risks else "")
        else:
            summary = f"{e.get('recommendation') or '—'} — {name}"
            details = None
        ticker_cards.append(TickerCard(ticker=t, is_expanded=len(ticker_cards) < 3, summary=summary, details=details))
    actions_section = "\n".join(
        f"- [{a.priority}] {a.category}: {', '.join(a.tickers)} — {a.description} {a.rationale or ''}"
        for a in actions_ranked.actions_ranked
    ) or "No actions."
    provenance = [{"claim_or_figure_id": fid, "source_figure_id": fid} for fid in figure_ids]
    if web_research_output and web_research_output.learnings:
        for i, wl in enumerate(web_research_output.learnings[:20]):
            provenance.append({
                "claim_or_figure_id": f"web_learning_{i+1}",
                "source": "web",
                "urls": wl.source_urls or (web_research_output.sources or [])[:3],
            })
        watchlist_summary += "\n\nWeb context: " + " ".join(wl.text[:150] for wl in web_research_output.learnings[:3]) + "."
    out = NarrativeOutput(
        title="Portfolio consultation report",
        watchlist_summary=watchlist_summary.strip(),
        narrative=narrative,
        figure_explanations=figure_explanations,
        ticker_cards=ticker_cards,
        actions_section=actions_section,
        provenance=provenance,
    )
    return out
