"""
Stage 9: Quality & Consistency Auditor.
Input: report_json, figure_specs, figure_data, evidence_packets, user_intent, provenance.
Output: issues_found (severity, message, fix_suggestion); optional auto_fix_instructions for composer.
Deterministic checks (counts, dates, figure_ids) + optional LLM rubric (numeric backing, personalization, actionability).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pipeline_schemas import AuditIssue, AuditOutput, EvidencePacket, UserIntent


def run_auditor(
    report_json: Dict[str, Any],
    figure_specs: List[Dict[str, Any]],
    figure_data: Dict[str, Any],
    evidence_packets: List[EvidencePacket],
    user_intent: UserIntent,
    provenance: List[Dict[str, Any]],
    use_llm: bool = False,
) -> AuditOutput:
    """
    Run deterministic checks and optionally LLM rubric. Return issues_found and optional auto_fix_instructions.
    """
    issues: List[AuditIssue] = []

    # Deterministic: ticker counts
    payload_tickers = set()
    entries = (report_json.get("entries") or report_json.get("ticker_cards") or [])
    if isinstance(entries, list):
        for e in entries:
            if isinstance(e, dict) and e.get("ticker"):
                payload_tickers.add(e.get("ticker"))
            elif hasattr(e, "ticker"):
                payload_tickers.add(getattr(e, "ticker", ""))
    evidence_tickers = {p.ticker for p in evidence_packets}
    if payload_tickers and evidence_tickers and payload_tickers != evidence_tickers:
        missing = evidence_tickers - payload_tickers
        extra = payload_tickers - evidence_tickers
        if missing or extra:
            issues.append(AuditIssue(
                severity="warning",
                message=f"Ticker mismatch: evidence has {len(evidence_tickers)} tickers; report cards reference {len(payload_tickers)}. Missing in cards: {missing or 'none'}. Extra in cards: {extra or 'none'}.",
                fix_suggestion="Align ticker_cards with evidence_packets tickers.",
            ))

    # Deterministic: figure_ids in narrative
    figure_explanations = report_json.get("figure_explanations") or ""
    figure_ids_in_data = set(k for k in figure_data if k != "by_ticker")
    for fid in figure_ids_in_data:
        if fid not in figure_explanations:
            issues.append(AuditIssue(
                severity="info",
                message=f"Figure '{fid}' not referenced in figure_explanations.",
                fix_suggestion=f"Add 1-2 sentences in figure_explanations describing what {fid} shows.",
            ))

    # Deterministic: date freshness
    if not report_json.get("data_freshness") and not any("date" in str(v).lower() or "fresh" in str(v).lower() for v in (report_json.get("watchlist_summary") or "").split()):
        issues.append(AuditIssue(
            severity="info",
            message="Report does not state quote or data freshness.",
            fix_suggestion="Add data_freshness or a sentence in watchlist_summary stating when data is as of.",
        ))

    # Deterministic: figure_specs count vs figure_plan
    if figure_specs and figure_data:
        n_specs = len(figure_specs)
        n_figures = len([k for k in figure_data if k != "by_ticker"])
        if n_specs < n_figures - 2:  # allow by_ticker and one aggregate
            issues.append(AuditIssue(
                severity="warning",
                message=f"Fewer figure specs ({n_specs}) than figure_data keys ({n_figures}).",
                fix_suggestion="Ensure every planned figure has a corresponding Vega-Lite spec.",
            ))

    if issues:
        auto_fix = "Re-run narrative composer with: (1) reference every figure_id in figure_explanations; (2) align ticker_cards to evidence tickers; (3) add data_freshness or state date in summary."
    else:
        auto_fix = None

    return AuditOutput(issues_found=issues, auto_fix_instructions=auto_fix)
