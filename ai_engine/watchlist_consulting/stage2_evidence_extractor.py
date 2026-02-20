"""
Stage 2: Per-Ticker Evidence Extractor.
Input: watchlist_payload.entries.
Output: List of EvidencePacket per ticker (thesis, risks, catalysts, signals, scenario_range, numbers_used, action_candidate).
Uses LLM structured extraction; fallback to heuristic when LLM unavailable.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pipeline_schemas import ActionCandidate, EvidencePacket, ScenarioRange

try:
    from report_agent import _get_llm
except ImportError:
    _get_llm = None


def _entry_to_text(entry: Dict[str, Any]) -> str:
    """Condense one payload entry for the LLM."""
    lines = [
        f"Ticker: {entry.get('ticker')}",
        f"Name: {entry.get('name', entry.get('ticker'))}",
        f"Recommendation: {entry.get('recommendation') or '—'}",
        f"Confidence: {entry.get('confidence')}",
        f"Report date: {entry.get('report_date')}",
        f"Expected return %: {entry.get('expected_return_pct')}",
        f"Bear/Base/Bull return %: {entry.get('bear_case_return_pct')} / {entry.get('expected_return_pct')} / {entry.get('bull_case_return_pct')}",
    ]
    qt = entry.get("quote") or {}
    if qt:
        lines.append(f"Quote: price={qt.get('current_price')}, daily_change%={qt.get('daily_change_percent')}")
    for key in ("key_takeaways", "bull_viewpoint", "bear_viewpoint"):
        val = entry.get(key)
        if val:
            if isinstance(val, list):
                val = " | ".join(str(v)[:200] for v in val[:5])
            else:
                val = str(val)[:500]
            lines.append(f"{key}: {val}")
    scores = entry.get("report_scores") or {}
    if scores:
        lines.append("Scores: " + ", ".join(f"{k}={v.get('score_label') or v.get('score')}" for k, v in list(scores.items())[:6]))
    return "\n".join(lines)


def _extract_one_llm(llm: Any, entry: Dict[str, Any]) -> EvidencePacket:
    """Single-ticker LLM extraction -> EvidencePacket."""
    from langchain_core.messages import HumanMessage

    text = _entry_to_text(entry)
    ticker = (entry.get("ticker") or "").upper()

    structured_llm = llm.with_structured_output(EvidencePacket)
    prompt = (
        "You are an analyst extracting structured evidence from a single stock's report summary. "
        "Output only the requested structure. Use the ticker from the input. "
        "thesis_bullets: 2-5 short bullets summarizing the investment thesis. "
        "key_risks: 2-4 main risks. catalysts: near-term catalysts (earnings, product, macro). "
        "valuation_signal, quality_signal, momentum_signal: one short phrase each if evident from the text, else empty. "
        "news_drivers: top 3 if mentioned; else leave empty. "
        "scenario_range: fill bear_return_pct, base_return_pct, bull_return_pct, confidence from the numbers given. "
        "numbers_used: list of field names you used (e.g. expected_return_pct, bear_case_return_pct). "
        "action_candidate: one of buy/hold/sell/watch and a brief rationale.\n\n"
        "Report summary for this ticker:\n" + text
    )
    out = structured_llm.invoke([HumanMessage(content=prompt)])
    if isinstance(out, EvidencePacket):
        return out
    if isinstance(out, dict):
        return EvidencePacket(ticker=ticker, **{k: v for k, v in out.items() if k != "ticker"})
    return EvidencePacket(ticker=ticker)


def _extract_one_heuristic(entry: Dict[str, Any]) -> EvidencePacket:
    """Build EvidencePacket from entry without LLM."""
    ticker = (entry.get("ticker") or "").upper()
    takeaways = entry.get("key_takeaways") or []
    thesis_bullets = [str(t)[:300] for t in takeaways[:5]]
    bull = entry.get("bull_viewpoint")
    bear = entry.get("bear_viewpoint")
    if bull:
        pts = bull if isinstance(bull, list) else [str(bull)]
        thesis_bullets.extend([str(p)[:200] for p in pts[:2]])
    key_risks: List[str] = []
    if bear:
        pts = bear if isinstance(bear, list) else [str(bear)]
        key_risks = [str(p)[:200] for p in pts[:3]]

    rec = (entry.get("recommendation") or "HOLD").upper()
    if rec not in ("BUY", "SELL", "HOLD"):
        rec = "HOLD"
    action = "buy" if rec == "BUY" else ("sell" if rec == "SELL" else "hold")
    numbers_used = []
    for f in ("expected_return_pct", "bear_case_return_pct", "bull_case_return_pct"):
        if entry.get(f) is not None:
            numbers_used.append(f)

    scenario = None
    if any(entry.get(f) is not None for f in ("expected_return_pct", "bear_case_return_pct", "bull_case_return_pct")):
        scenario = ScenarioRange(
            bear_return_pct=entry.get("bear_case_return_pct"),
            base_return_pct=entry.get("expected_return_pct"),
            bull_return_pct=entry.get("bull_case_return_pct"),
            confidence=entry.get("confidence"),
        )

    return EvidencePacket(
        ticker=ticker,
        thesis_bullets=thesis_bullets[:5],
        key_risks=key_risks[:4],
        catalysts=[],
        valuation_signal=None,
        quality_signal=None,
        momentum_signal=None,
        news_drivers=[],
        scenario_range=scenario,
        numbers_used=numbers_used,
        action_candidate=ActionCandidate(action=action, rationale=f"Recommendation: {rec}"),
    )


def run_evidence_extractor(entries: List[Dict[str, Any]], use_llm: bool = True) -> List[EvidencePacket]:
    """
    Run evidence extraction on watchlist_payload.entries.
    Returns one EvidencePacket per entry; uses LLM when available and use_llm=True.
    """
    if not entries:
        return []

    llm = None
    if use_llm and _get_llm:
        try:
            llm = _get_llm()
        except (ValueError, ImportError):
            pass

    out: List[EvidencePacket] = []
    for entry in entries:
        if not entry.get("ticker"):
            continue
        if llm:
            try:
                out.append(_extract_one_llm(llm, entry))
            except Exception:
                out.append(_extract_one_heuristic(entry))
        else:
            out.append(_extract_one_heuristic(entry))
    return out
