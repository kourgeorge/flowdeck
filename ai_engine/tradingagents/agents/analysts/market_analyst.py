import logging
from typing import List

from pydantic import BaseModel, Field

from ..utils.agent_utils import (
    get_ticker_data,
    get_ticker_quote,
    get_indicators,
    get_analysts_recommendation,
)
from .self_contained_analyst import create_self_contained_analyst
from .output_schema import analyst_key_takeaways_field
from .prompts import build_market_analyst_prompt

logger = logging.getLogger(__name__)


class MarketAnalysisOutput(BaseModel):
    """Structured output for market analysis including report and score."""
    report: str = Field(
        description="Comprehensive market analysis report covering technical indicators, trends, and market conditions"
    )
    market_score: int = Field(
        ge=1, le=10,
        description="Market score from 1-10 indicating market performance outlook. 1-3: Very bearish market conditions, 4-5: Neutral/mixed market conditions, 6-7: Moderately bullish market conditions, 8-10: Very bullish market conditions"
    )
    key_takeaways: List[str] = analyst_key_takeaways_field()


def create_market_analyst(llm):
    """Create a self-contained market analyst that handles all tool calling internally."""
    return create_self_contained_analyst(
        llm=llm,
        tools=[
            get_ticker_data,
            get_ticker_quote,
            get_indicators,
            get_analysts_recommendation,
        ],
        prompt_builder=build_market_analyst_prompt,
        structured_output_class=MarketAnalysisOutput,
        score_field="market_score",
        report_field="market_report",
        agent_name="Market Analyst",
        max_iterations=5,
    )
