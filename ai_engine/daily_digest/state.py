"""
State models for the User Daily Brief workflow.

DigestContext is the output of the single algorithmic step and the primary input to agents.
Workflow state carries input, DigestContext, and agent outputs through the pipeline.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Interpretation outputs (agent-structured)
# ---------------------------------------------------------------------------

class TickerInterpretation(BaseModel):
    """Per-ticker interpretation from the Ticker Interpreter agent."""
    explanation: str = Field(description="What happened for this ticker and why.")
    driver: Literal["company", "sector", "macro", "unclear"] = Field(
        description="Classification of the main driver of the move."
    )
    thesis_comparison: str = Field(
        description="How today's developments compare to the latest FlowDeck thesis from platform reports."
    )


class MarketInterpretation(BaseModel):
    """Market-level interpretation from the Market Interpreter agent."""
    summary: str = Field(description="Overall market backdrop summary.")
    relevance_to_portfolio: str = Field(description="Why the market context matters for this portfolio.")


class FocusSelection(BaseModel):
    """Output of the Focus Selector agent."""
    focus_tickers: List[str] = Field(
        description="Ordered list of tickers to focus on in today's brief (subset of the user's portfolio)."
    )


class ReferenceItem(BaseModel):
    """Structured reference item used to ground the daily brief."""
    label: str = Field(
        description="Short human-readable label for the source (e.g. article title or feed name)."
    )
    url: Optional[str] = Field(
        default=None,
        description="Optional URL for the source, if available.",
    )
    source: Optional[str] = Field(
        default=None,
        description="Optional publisher/feed/source name.",
    )
    tickers: Optional[List[str]] = Field(
        default=None,
        description="Related tickers, if any (e.g. ['AAPL', 'MSFT']).",
    )


# ---------------------------------------------------------------------------
# DigestContext (output of build_digest_context)
# ---------------------------------------------------------------------------

class DigestContext(BaseModel):
    """Output of the single algorithmic step. Primary input to digest agents."""

    # Portfolio
    tickers: List[str] = Field(default_factory=list, description="All portfolio tickers.")
    user_context_snapshot: Optional[str] = Field(default=None, description="Optional user profile/preferences snapshot.")

    # Priority (top N by attention score)
    priority_tickers: List[str] = Field(default_factory=list, description="Tickers selected for deep analysis.")
    attention_scores: Dict[str, float] = Field(default_factory=dict, description="ticker -> attention score.")

    # Per-ticker data (for priority_tickers; missing key -> agent can use tools)
    quotes: Dict[str, Optional[Dict[str, Any]]] = Field(default_factory=dict)
    returns_1d: Dict[str, Optional[float]] = Field(default_factory=dict)
    returns_5d: Dict[str, Optional[float]] = Field(default_factory=dict)
    abnormal_signal: Dict[str, bool] = Field(default_factory=dict)

    news: Dict[str, Any] = Field(default_factory=dict)  # ticker -> news payload (e.g. list of articles or str)
    fundamentals: Dict[str, Any] = Field(default_factory=dict)
    analyst_rec: Dict[str, Any] = Field(default_factory=dict)
    insider: Dict[str, Any] = Field(default_factory=dict)
    indicators: Dict[str, Any] = Field(default_factory=dict)
    platform_reports: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="ticker -> report_type -> {content, score, key_takeaways, ...}",
    )

    sector_industry: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="ticker -> {sector, industry}.",
    )
    peer_tickers: Dict[str, List[str]] = Field(default_factory=dict, description="ticker -> list of peer tickers.")
    peer_quotes: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="peer ticker -> quote or move summary (for display).",
    )

    # Market-wide
    market_movers: Dict[str, Any] = Field(default_factory=dict, description="Top gainers/losers from get_daily_market_movers.")
    global_news: Any = Field(default=None, description="Global/macro news (list or str).")
    web_search_snippet: Optional[str] = Field(default=None, description="Optional macro/sector snippet from web_search.")

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Workflow state (passed along the pipeline)
# ---------------------------------------------------------------------------

class DigestWorkflowState(BaseModel):
    """State passed through the digest pipeline."""

    user_id: int = Field(description="User ID for portfolio and preferences.")
    digest_date: str = Field(description="Date for the digest (YYYY-MM-DD).")
    max_priority_tickers: int = Field(default=5, ge=1, le=20, description="Max number of tickers to analyze in depth.")
    db: Any = Field(default=None, description="DB session (optional; required for portfolio load).")
    config: Dict[str, Any] = Field(default_factory=dict, description="LLM/config overrides.")
    user_note: Optional[str] = Field(
        default=None,
        description="Optional free-form user input for today's brief (preferences, concerns, focus).",
    )
    user_focus_tickers: Optional[List[str]] = Field(
        default=None,
        description=(
            "Optional explicit list of tickers from the user's portfolio that the brief should focus on. "
            "When provided, this is treated as a strong preference and guides focus selection."
        ),
    )
    narrative_style: Optional[str] = Field(
        default=None,
        description=(
            "Optional style preference for the brief narrative, e.g. "
            "'concise', 'professional', 'technical', 'story-like'. "
            "Used as a soft instruction for the narrative writer."
        ),
    )

    digest_context: Optional[DigestContext] = Field(default=None, description="Set after algorithmic step.")

    ticker_interpretations: Dict[str, TickerInterpretation] = Field(default_factory=dict)
    market_interpretation: Optional[MarketInterpretation] = Field(default=None)
    digest_narrative: str = Field(default="")
    what_to_watch: str = Field(default="")
    references: List[ReferenceItem] = Field(
        default_factory=list,
        description="Structured list of sources used for this brief (news articles, feeds, web snippets, etc.).",
    )

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Result (for API/script return)
# ---------------------------------------------------------------------------

class DigestResult(BaseModel):
    """Final digest result returned by run_digest."""
    narrative: str = Field(description="Short portfolio-centered digest narrative.")
    what_to_watch: str = Field(description="Short 'what to watch' section.")
    digest_date: str = Field(description="Date of the digest.")
    priority_tickers: List[str] = Field(default_factory=list, description="Tickers that were analyzed in depth.")
    references: List[ReferenceItem] = Field(
        default_factory=list,
        description="Structured list of sources used for this brief.",
    )
    # Optional LLM usage metadata (for token accounting / cost analysis)
    input_tokens: Optional[int] = Field(default=None, description="Prompt tokens used by the digest workflow.")
    output_tokens: Optional[int] = Field(default=None, description="Completion tokens used by the digest workflow.")
    total_tokens: Optional[int] = Field(default=None, description="Total tokens used by the digest workflow.")
    cost_usd: Optional[float] = Field(default=None, description="Approximate USD cost of the digest workflow.")
    models_used: Optional[Dict[str, Any]] = Field(default=None, description="LLM provider and model names used.")
