"""
Shared Pydantic schemas for the personalized report pipeline.
All stage inputs/outputs and final report types for conductor and auditor.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ----- Stage 1: User Intent -----
class UserIntent(BaseModel):
    investor_style: str = Field(description="e.g. long-term, swing, learning, income, speculation")
    risk_budget: str = Field(description="low, med, high")
    time_horizon: str = Field(description="days, weeks, months, years")
    constraints: List[str] = Field(default_factory=list, description="sector exclusions, ESG, no derivatives, etc.")
    report_style: str = Field(description="concise vs deep-dive; technical vs plain")
    assumptions_stated: bool = Field(default=False, description="true when profile was missing and we inferred")
    inferred_preferences_explanation: Optional[str] = Field(default=None)


# ----- Stage 2: Evidence Extractor -----
class ScenarioRange(BaseModel):
    bear_return_pct: Optional[float] = None
    base_return_pct: Optional[float] = None
    bull_return_pct: Optional[float] = None
    confidence: Optional[float] = None


class ActionCandidate(BaseModel):
    action: str = Field(description="buy, hold, sell, watch")
    rationale: str = Field(default="")


class EvidencePacket(BaseModel):
    ticker: str
    thesis_bullets: List[str] = Field(default_factory=list)
    key_risks: List[str] = Field(default_factory=list)
    catalysts: List[str] = Field(default_factory=list)
    valuation_signal: Optional[str] = None
    quality_signal: Optional[str] = None
    momentum_signal: Optional[str] = None
    news_drivers: List[str] = Field(default_factory=list)
    scenario_range: Optional[ScenarioRange] = None
    numbers_used: List[str] = Field(default_factory=list)
    action_candidate: Optional[ActionCandidate] = None


# ----- Stage 3: Theme Miner -----
class ThemeWithTickers(BaseModel):
    theme: str
    supporting_tickers: List[str] = Field(default_factory=list)
    rank: Optional[int] = None


class ExposureSnapshot(BaseModel):
    sector_counts: Dict[str, int] = Field(default_factory=dict)
    industry_counts: Dict[str, int] = Field(default_factory=dict)


class ThemeOutput(BaseModel):
    dominant_themes: List[ThemeWithTickers] = Field(default_factory=list)
    common_risks: List[str] = Field(default_factory=list)
    divergent_views: List[Dict[str, Any]] = Field(default_factory=list)
    exposure_snapshot: Optional[ExposureSnapshot] = None
    regime_fit: Optional[str] = None


# ----- Stage 4: Web Research -----
class WebSearchResult(BaseModel):
    """One SERP item from SerpAPI (title, snippet, url, domain)."""
    title: str = Field(default="")
    snippet: str = Field(default="")
    url: str = Field(default="")
    domain: str = Field(default="")


class WebLearning(BaseModel):
    """One extracted learning from web search results."""
    text: str = Field(description="Short bullet or insight")
    query_used: str = Field(default="", description="Search query that produced this learning")
    source_urls: List[str] = Field(default_factory=list, description="URLs this learning is derived from")
    theme_or_ticker: Optional[str] = Field(default=None, description="Optional attribution to theme or ticker")


class WebResearchOutput(BaseModel):
    """Result of the web research stage: learnings, sources, queries, stats."""
    learnings: List[WebLearning] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list, description="Deduped list of source URLs")
    queries_used: List[str] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(
        default_factory=lambda: {
            "total_learnings": 0,
            "total_sources": 0,
            "follow_ups_used": 0,
        },
        description="e.g. total_learnings, total_sources, follow_ups_used",
    )


# ----- Stage 5: Figure Planner -----
class FigurePlanItem(BaseModel):
    figure_id: str
    title: str
    why_this_matters: str = Field(default="")
    data_requirements: Dict[str, Any] = Field(default_factory=dict)
    spec_template: Optional[str] = None


class DataJob(BaseModel):
    job_id: str
    tickers: List[str] = Field(default_factory=list)
    fields: List[str] = Field(default_factory=list)
    windows: Optional[Dict[str, Any]] = None


# ----- Stage 6: Data Builder output is figure_data dict + data_quality_notes -----
# figure_data: Dict[str, Any]  # figure_id -> chart-ready dataset
# data_quality_notes: List[str]

# ----- Stage 7: Action Engine -----
class ActionItem(BaseModel):
    priority: str = Field(description="P0, P1, P2")
    category: str = Field(description="deep_dive, wait_catalyst, set_alert, avoid")
    tickers: List[str] = Field(default_factory=list)
    description: str = Field(default="")
    rationale: str = Field(default="")


class ActionsOutput(BaseModel):
    actions_ranked: List[ActionItem] = Field(default_factory=list)
    watchlist_cleanup_suggestions: List[str] = Field(default_factory=list)


# ----- Stage 8: Narrative Composer -----
class TickerCard(BaseModel):
    ticker: str
    is_expanded: bool = True
    summary: str = Field(default="")
    details: Optional[str] = None


class NarrativeOutput(BaseModel):
    title: str = Field(default="Watchlist Report")
    watchlist_summary: str = Field(default="")
    narrative: str = Field(default="", description="Discussion: how the figures connect to the story")
    figure_explanations: str = Field(default="")
    ticker_cards: List[TickerCard] = Field(default_factory=list)
    actions_section: str = Field(default="")
    provenance: List[Dict[str, Any]] = Field(default_factory=list)


# ----- Stage 9: Auditor -----
class AuditIssue(BaseModel):
    severity: str = Field(description="error, warning, info")
    message: str
    fix_suggestion: Optional[str] = None


class AuditOutput(BaseModel):
    issues_found: List[AuditIssue] = Field(default_factory=list)
    auto_fix_instructions: Optional[str] = None


# ----- Final report (conductor output) -----
class ProvenanceEntry(BaseModel):
    claim_or_figure_id: str
    source_field: Optional[str] = None
    source_ticker: Optional[str] = None
    source_figure_id: Optional[str] = None


class ResearchQAItem(BaseModel):
    """One research question and the answers/learnings from deep research."""
    question: str = Field(description="Search/research question asked")
    answers: List[str] = Field(default_factory=list, description="Key learnings or answers from search results")


class ReportJson(BaseModel):
    title: str = Field(default="")
    watchlist_summary: str = Field(default="")
    narrative: str = Field(default="")
    figure_explanations: str = Field(default="")
    ticker_cards: List[Dict[str, Any]] = Field(default_factory=list)
    actions_section: str = Field(default="")
    data_freshness: Optional[str] = None
    audit_notes: Optional[str] = None
    provenance: List[Dict[str, Any]] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list, description="URLs and sources cited (web research)")
    research_qa: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Questions explored during deep research and their answers (question, answers)",
    )
