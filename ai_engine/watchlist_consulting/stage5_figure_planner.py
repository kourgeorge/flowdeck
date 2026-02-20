"""
Stage 5: Figure Planner Agent.
Input: evidence_packets, theme_output, user_intent, watchlist_payload.
Output: figure_plan (list of FigurePlanItem), data_jobs.
Importance heuristic for top-N tickers (expected return, bear-bull spread); refs vega_specs as template library.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pipeline_schemas import DataJob, EvidencePacket, FigurePlanItem, ThemeOutput, UserIntent


# Figure IDs aligned with vega_specs and data builder
FIGURE_IDS = [
    "recommendation_dist",
    "daily_change",
    "return_range",
    "risk_return_scatter",
    "sector_exposure",
    "theme_map",
    "price_small_multiples",
    "fundamentals_trajectory",
]


def _importance_rank(evidence_packets: List[EvidencePacket], top_n: int = 5) -> List[str]:
    """Rank tickers by expected-return magnitude and bear-bull spread; return top N."""
    scored: List[tuple[float, str]] = []
    for p in evidence_packets:
        base = p.scenario_range.base_return_pct if p.scenario_range else None
        bear = p.scenario_range.bear_return_pct if p.scenario_range else None
        bull = p.scenario_range.bull_return_pct if p.scenario_range else None
        mag = abs(base) if base is not None else 0.0
        spread = (bull - bear) if (bear is not None and bull is not None) else 0.0
        score = mag * 0.5 + min(abs(spread) / 10.0, 5.0)
        scored.append((score, p.ticker))
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored[:top_n]]


def run_figure_planner(
    evidence_packets: List[EvidencePacket],
    theme_output: ThemeOutput,
    user_intent: UserIntent,
    watchlist_payload: Dict[str, Any],
) -> tuple[List[FigurePlanItem], List[DataJob]]:
    """
    Produce figure_plan and data_jobs. Uses fixed figure set keyed by figure_id;
    top N tickers for small multiples from importance heuristic.
    """
    entries = watchlist_payload.get("entries") or []
    tickers = [e.get("ticker") for e in entries if e.get("ticker")]
    top_tickers = _importance_rank(evidence_packets, top_n=min(5, max(1, len(tickers))))

    figure_plan: List[FigurePlanItem] = [
        FigurePlanItem(
            figure_id="recommendation_dist",
            title="Recommendation distribution",
            why_this_matters="Shows overall tilt of the watchlist (BUY/HOLD/SELL counts).",
            data_requirements={"source": "payload", "fields": ["recommendation"]},
            spec_template="recommendation_bar",
        ),
        FigurePlanItem(
            figure_id="daily_change",
            title="Daily % change by ticker",
            why_this_matters="Short-term market reaction across the watchlist.",
            data_requirements={"source": "payload", "fields": ["quote.daily_change_percent"]},
            spec_template="daily_change_bar",
        ),
        FigurePlanItem(
            figure_id="return_range",
            title="Expected return % (Bear / Base / Bull)",
            why_this_matters="Risk/reward range from analysis per ticker.",
            data_requirements={"source": "payload", "fields": ["expected_return_pct", "bear_case_return_pct", "bull_case_return_pct"]},
            spec_template="return_range",
        ),
        FigurePlanItem(
            figure_id="risk_return_scatter",
            title="Risk vs return (volatility vs expected return)",
            why_this_matters="Context for risk-adjusted view; color by sector.",
            data_requirements={"tickers": tickers, "fields": ["historical", "volatility_or_drawdown", "sector"]},
            spec_template="risk_return_scatter",
        ),
        FigurePlanItem(
            figure_id="sector_exposure",
            title="Sector / industry exposure",
            why_this_matters="Concentration and diversification view.",
            data_requirements={"tickers": tickers, "fields": ["sector", "industry"]},
            spec_template="sector_exposure",
        ),
        FigurePlanItem(
            figure_id="theme_map",
            title="Theme map (tickers × themes)",
            why_this_matters="How themes from the miner map to tickers.",
            data_requirements={"source": "theme_output", "fields": ["dominant_themes"]},
            spec_template="theme_map",
        ),
        FigurePlanItem(
            figure_id="price_small_multiples",
            title="Price trend (top names)",
            why_this_matters="Price context for highest-conviction or widest-range names.",
            data_requirements={"tickers": top_tickers, "fields": ["historical"], "windows": {"period": "6mo"}},
            spec_template="price_series",
        ),
        FigurePlanItem(
            figure_id="fundamentals_trajectory",
            title="Fundamentals trajectory (top names)",
            why_this_matters="Revenue/EPS trend for selected tickers.",
            data_requirements={"tickers": top_tickers, "fields": ["financial_charts"]},
            spec_template="fundamentals_bar",
        ),
    ]

    data_jobs: List[DataJob] = [
        DataJob(job_id="historical_all", tickers=tickers, fields=["historical"], windows={"period": "6mo"}),
        DataJob(job_id="historical_top", tickers=top_tickers, fields=["historical"], windows={"period": "6mo"}),
        DataJob(job_id="financial_charts_top", tickers=top_tickers, fields=["financial_charts"]),
        DataJob(job_id="company_info", tickers=tickers, fields=["sector", "industry"]),
    ]

    return figure_plan, data_jobs
