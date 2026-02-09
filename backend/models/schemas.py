"""Pydantic models for API schemas."""

from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


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


class StockQuote(BaseModel):
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


class Recommendation(BaseModel):
    """Stock recommendation data."""
    recommendation: str  # "BUY", "SELL", "HOLD"
    confidence: Optional[float] = None
    source: str  # "final_trade_decision" or "trader_investment_plan"
    date: str


class ReportScoreSummary(BaseModel):
    """AI analysis score summary for a single report (for list view)."""
    score: Optional[int] = None
    score_label: Optional[str] = None


class StockWidget(BaseModel):
    """Widget data for homepage."""
    ticker: str
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


class WidgetsResponse(BaseModel):
    """Response containing multiple stock widgets."""
    widgets: List[StockWidget]


class HistoricalAnalysis(BaseModel):
    """Historical analysis data."""
    date: str
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


class StockPageData(BaseModel):
    """Complete stock page data."""
    ticker: str
    quote: Optional[StockQuote] = None
    recommendation: Optional[Recommendation] = None
    report_date: Optional[str] = None
    report_days_ago: Optional[int] = None  # staleness: days since report for "Report from X days ago"
    reports: Dict[str, Optional[str]] = {}
    reports_with_scores: Dict[str, ReportData] = {}  # ReportData includes insights (takeaways, dates)
    historical_analyses: List[HistoricalAnalysis] = []
    has_reports: bool = False
    is_generating: bool = False
    generation_analysis_id: Optional[str] = None
    # Agent return expectations (from Research Manager / investment_plan)
    expected_return_pct: Optional[float] = None
    bear_case_return_pct: Optional[float] = None
    bull_case_return_pct: Optional[float] = None

