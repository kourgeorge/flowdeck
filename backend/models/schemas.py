"""Pydantic models for API schemas."""

import math
from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


def _sanitize_float(v: Optional[float]) -> Optional[float]:
    """Replace NaN/Inf float values with None to keep JSON serialization valid."""
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


# --- Structured insights layer ---

class ParsedRecommendation(BaseModel):
    """Structured recommendation parsed from a report (replaces raw regex dict)."""
    recommendation: str  # "BUY", "SELL", "HOLD"
    confidence: Optional[float] = None
    source: str  # e.g. "final_trade_decision", "trader_investment_plan", "general_parsing"


class ReportInsight(BaseModel):
    """Structured metadata for a single report: scores, recommendation, takeaways, staleness."""
    content: Optional[str] = None
    score: Optional[int] = None
    score_label: Optional[str] = None
    recommendation: Optional[ParsedRecommendation] = None
    key_takeaways: List[str] = []
    analysis_date: Optional[str] = None  # date the analysis was run (e.g. YYYY-MM-DD)
    generated_at: Optional[str] = None   # ISO datetime when report was generated
    days_ago: Optional[int] = None     # computed: report age in days for staleness display


class TickerQuote(BaseModel):
    """Real-time market quote data."""
    ticker: str
    current_price: float
    daily_change: float
    daily_change_percent: float
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    volume: Optional[int] = None
    previous_close: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    market_status: str  # "OPEN", "CLOSED", "PRE_MARKET", "AFTER_HOURS"
    last_update_time: datetime
    currency: Optional[str] = None  # e.g. "USD", "ILS", "ILA" for display

    @field_validator(
        'bid_price', 'ask_price', 'previous_close',
        'day_high', 'day_low', 'fifty_two_week_high', 'fifty_two_week_low',
        mode='before',
    )
    @classmethod
    def sanitize_optional_floats(cls, v):
        """Replace NaN/Inf with None for optional float fields."""
        return _sanitize_float(v)

    @field_validator('current_price', 'daily_change', 'daily_change_percent', mode='before')
    @classmethod
    def sanitize_required_floats(cls, v):
        """Replace NaN/Inf with 0.0 for required float fields."""
        result = _sanitize_float(v)
        return result if result is not None else 0.0


class Recommendation(BaseModel):
    """Ticker recommendation data."""
    recommendation: str  # "BUY", "SELL", "HOLD"
    confidence: Optional[float] = None
    source: str  # "final_trade_decision" or "trader_investment_plan"
    date: str


class ReportScoreSummary(BaseModel):
    """AI analysis score summary for a single report (for list view)."""
    score: Optional[int] = None
    score_label: Optional[str] = None


class TickerWidget(BaseModel):
    """Widget data for homepage."""
    ticker: str
    name: Optional[str] = None  # Company full name (e.g. "JFrog Ltd.")
    current_price: float
    daily_change: float
    daily_change_percent: float
    recommendation: Optional[str] = None  # "BUY", "SELL", "HOLD"
    confidence: Optional[float] = None  # 0-1 from AI (risk_score/10)
    report_date: Optional[str] = None
    has_report: bool = False
    market_status: str = "UNKNOWN"
    # AI analysis scores by report type (e.g. investment_plan, final_trade_decision) for list view
    report_scores: Optional[Dict[str, ReportScoreSummary]] = None
    # True when ticker is in MAJOR_STOCKS (only set when widgets requested without explicit tickers)
    is_major: Optional[bool] = None
    currency: Optional[str] = None  # e.g. "USD", "ILS" for price display
    dominant_events: Optional[List[str]] = None
    event_count: Optional[int] = None

    @field_validator('confidence', mode='before')
    @classmethod
    def sanitize_optional_floats(cls, v):
        return _sanitize_float(v)

    @field_validator('current_price', 'daily_change', 'daily_change_percent', mode='before')
    @classmethod
    def sanitize_required_floats(cls, v):
        result = _sanitize_float(v)
        return result if result is not None else 0.0


class WidgetsResponse(BaseModel):
    """Response containing multiple ticker widgets. total is set when using only_date with limit (paginated)."""
    widgets: List[TickerWidget]
    total: Optional[int] = None


class TickerEventSummaryLite(BaseModel):
    """Lightweight event summary for list views."""
    dominant_events: Optional[List[str]] = None
    event_count: Optional[int] = None


class TickerEventSummariesResponse(BaseModel):
    """Batch event-summary response keyed by ticker."""
    summaries: Dict[str, TickerEventSummaryLite]


class HistoricalAnalysis(BaseModel):
    """Historical analysis data."""
    analysis_run_id: int
    date: str  # display string (e.g. YYYY-MM-DD HH:MM)
    available_reports: List[str]
    recommendation: Optional[str] = None


class ModelsUsed(BaseModel):
    """AI model names used for this analysis run."""
    provider: Optional[str] = None
    deep_think: Optional[str] = None
    quick_think: Optional[str] = None


class ReportData(BaseModel):
    """Report data with optional score and structured insights."""
    content: Optional[str] = None
    score: Optional[int] = None
    score_label: Optional[str] = None
    key_takeaways: List[str] = []
    analysis_date: Optional[str] = None
    generated_at: Optional[str] = None
    days_ago: Optional[int] = None
    models_used: Optional[ModelsUsed] = None
    bull_viewpoint: Optional[List[str]] = None
    bear_viewpoint: Optional[List[str]] = None
    risky_viewpoint: Optional[List[str]] = None
    safe_viewpoint: Optional[List[str]] = None
    neutral_viewpoint: Optional[List[str]] = None
    tps_plan: Optional[str] = None
    # Sources used for this report (news, SEC, Reddit, etc.)
    resources: Optional[List[Dict[str, Any]]] = None
    # Persisted agent execution trace for this report (tool calls, debate turns, synthesis steps).
    agent_steps: Optional[List[Dict[str, Any]]] = None
    # Return scenarios (typically on investment_plan report; used for historical run header)
    expected_return_pct: Optional[float] = None
    bear_case_return_pct: Optional[float] = None
    bull_case_return_pct: Optional[float] = None
    current_price: Optional[float] = None
    currency: Optional[str] = None
    fair_value_bear: Optional[float] = None
    fair_value_base: Optional[float] = None
    fair_value_bull: Optional[float] = None
    current_discount_pct: Optional[float] = None
    valuation_conviction: Optional[str] = None
    valuation_key_assumptions: Optional[List[str]] = None
    valuation_summary: Optional[Dict[str, Any]] = None
    valuation_bridge: Optional[Dict[str, Any]] = None
    valuation_sensitivity: Optional[Dict[str, Any]] = None
    dcf: Optional[Dict[str, Any]] = None
    pe_comps: Optional[Dict[str, Any]] = None
    ev_ebitda: Optional[Dict[str, Any]] = None

    @field_validator(
        'expected_return_pct', 'bear_case_return_pct', 'bull_case_return_pct', 'current_price',
        'fair_value_bear', 'fair_value_base', 'fair_value_bull', 'current_discount_pct',
        mode='before'
    )
    @classmethod
    def sanitize_return_pcts(cls, v):
        return _sanitize_float(v) if v is not None else None


class TickerPageData(BaseModel):
    """Complete ticker page data."""
    ticker: str
    quote: Optional[TickerQuote] = None
    recommendation: Optional[Recommendation] = None
    report_run_id: Optional[int] = None  # analysis_runs.id for API calls
    report_date: Optional[str] = None  # display string (e.g. YYYY-MM-DD)
    report_days_ago: Optional[int] = None  # staleness: days since report for "Report from X days ago"
    reports: Dict[str, Optional[str]] = {}
    reports_with_scores: Dict[str, ReportData] = {}  # ReportData includes insights (takeaways, dates)
    historical_analyses: List[HistoricalAnalysis] = []
    has_reports: bool = False
    is_generating: bool = False
    generation_analysis_run_id: Optional[int] = None  # AnalysisRun.id for WebSocket/status
    # Agent return expectations (from Research Manager / investment_plan)
    expected_return_pct: Optional[float] = None
    bear_case_return_pct: Optional[float] = None
    bull_case_return_pct: Optional[float] = None
    # Token economy: unique view count and tokens earned for this report run
    report_view_count: Optional[int] = None
    report_earned_tokens: Optional[int] = None
    # Shareable link for this report run (viewable without login)
    share_url: Optional[str] = None

    @field_validator('expected_return_pct', 'bear_case_return_pct', 'bull_case_return_pct', mode='before')
    @classmethod
    def sanitize_return_pcts(cls, v):
        return _sanitize_float(v)
