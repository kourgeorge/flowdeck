"""
Stage 3: Cross-Ticker Theme Miner.
Input: evidence_packets, watchlist_payload (for sector/industry via get_company_info).
Output: ThemeOutput (dominant_themes, common_risks, divergent_views, exposure_snapshot, regime_fit).
Sector/industry counts from company info; LLM summarizes themes; divergent_views = tickers that differ from majority.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from pipeline_schemas import EvidencePacket, ExposureSnapshot, ThemeOutput, ThemeWithTickers

try:
    from report_agent import _get_llm
except ImportError:
    _get_llm = None


def _get_info_fetcher():
    from services.info_fetcher import get_info_fetcher
    return get_info_fetcher()


def _build_exposure_snapshot(tickers: List[str]) -> ExposureSnapshot:
    """Sector/industry counts from company info."""
    sector_counts: Dict[str, int] = {}
    industry_counts: Dict[str, int] = {}
    try:
        fetcher = _get_info_fetcher()
        for t in tickers:
            try:
                info = fetcher.get_company_info(t.upper())
                s = (info.get("sector") or "N/A").strip() or "N/A"
                i = (info.get("industry") or "N/A").strip() or "N/A"
                sector_counts[s] = sector_counts.get(s, 0) + 1
                industry_counts[i] = industry_counts.get(i, 0) + 1
            except Exception:
                sector_counts["N/A"] = sector_counts.get("N/A", 0) + 1
    except ImportError:
        pass
    return ExposureSnapshot(sector_counts=sector_counts, industry_counts=industry_counts)


def _divergent_views(evidence_packets: List[EvidencePacket]) -> List[Dict[str, Any]]:
    """Tickers whose action_candidate differs from majority (e.g. only SELL when rest are BUY/HOLD)."""
    if len(evidence_packets) < 2:
        return []
    actions = []
    for p in evidence_packets:
        ac = p.action_candidate
        a = (ac.action.lower() if ac else "hold").strip()
        if a not in ("buy", "hold", "sell", "watch"):
            a = "hold"
        actions.append((p.ticker, a))
    counter = Counter(a for _, a in actions)
    majority_action = counter.most_common(1)[0][0] if counter else "hold"
    out = []
    for ticker, action in actions:
        if action != majority_action and counter[action] <= max(1, len(actions) // 4):
            out.append({"ticker": ticker, "action": action, "majority": majority_action})
    return out


def _themes_and_risks_llm(evidence_packets: List[EvidencePacket]) -> tuple[List[ThemeWithTickers], List[str]]:
    """Use LLM to summarize dominant themes and common risks from thesis_bullets and key_risks."""
    from langchain_core.messages import HumanMessage

    text_parts = []
    for p in evidence_packets:
        block = f"[{p.ticker}]\nThesis: " + " | ".join(p.thesis_bullets[:3]) + "\nRisks: " + " | ".join(p.key_risks[:3])
        text_parts.append(block)
    combined = "\n\n".join(text_parts)[:12000]

    try:
        llm = _get_llm()
        structured = llm.with_structured_output(ThemeOutput)
        prompt = (
            "You are a theme analyst. Given per-ticker thesis bullets and key risks, output:\n"
            "dominant_themes: list of {theme: string, supporting_tickers: list of ticker symbols}. "
            "Rank by how many tickers share the theme (put most shared first). 3-6 themes.\n"
            "common_risks: list of 3-6 short risk phrases that appear across multiple tickers.\n"
            "Leave divergent_views, exposure_snapshot, regime_fit empty (they are computed elsewhere).\n\n"
            "Data:\n" + combined
        )
        out = structured.invoke([HumanMessage(content=prompt)])
        if isinstance(out, ThemeOutput):
            return (out.dominant_themes, out.common_risks)
        if isinstance(out, dict):
            return (
                [ThemeWithTickers(**t) if isinstance(t, dict) else t for t in out.get("dominant_themes", [])],
                out.get("common_risks", []),
            )
    except Exception:
        pass

    # Fallback: no embedding; simple keyword-style themes
    themes: List[ThemeWithTickers] = []
    all_risks: List[str] = []
    for p in evidence_packets:
        all_risks.extend(p.key_risks[:2])
    risk_counter = Counter(all_risks)
    common_risks = [r for r, _ in risk_counter.most_common(5)]
    return themes, common_risks


def run_theme_miner(
    evidence_packets: List[EvidencePacket],
    watchlist_payload: Optional[Dict[str, Any]] = None,
    use_llm: bool = True,
) -> ThemeOutput:
    """
    Run theme mining: exposure snapshot from sector/industry, LLM themes/risks, divergent views.
    """
    tickers = [p.ticker for p in evidence_packets]
    exposure = _build_exposure_snapshot(tickers)
    divergent = _divergent_views(evidence_packets)

    dominant_themes, common_risks = _themes_and_risks_llm(evidence_packets) if use_llm and _get_llm else ([], [])

    # Regime fit: simple heuristic from sector mix (rate-sensitive, commodity-sensitive)
    sector_counts = exposure.sector_counts or {}
    regime_fit = None
    if sector_counts:
        rate_sensitive = sum(sector_counts.get(s, 0) for s in ("Real Estate", "Financial Services", "Financial"))
        if rate_sensitive and len(tickers) > 0 and rate_sensitive / len(tickers) >= 0.3:
            regime_fit = "Rate-sensitive tilt (Real Estate / Financials)"
        else:
            regime_fit = "Mixed sector exposure"

    return ThemeOutput(
        dominant_themes=dominant_themes,
        common_risks=common_risks,
        divergent_views=divergent,
        exposure_snapshot=exposure,
        regime_fit=regime_fit,
    )
