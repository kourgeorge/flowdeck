import logging
from typing import List

from pydantic import BaseModel, Field
from ..utils.agent_utils import get_events, get_ticker_data, get_ticker_quote, get_indicators
from ..utils.advanced_technical_tools import (
    detect_divergence,
    detect_regime,
    detect_support_resistance
)
from .self_contained_analyst import create_self_contained_analyst
from .output_schema import analyst_key_takeaways_field
from .prompts import build_technical_analyst_prompt

logger = logging.getLogger(__name__)


class TechnicalAnalysisOutput(BaseModel):
    """Structured output for technical analysis including report and score."""
    report: str = Field(
        description="Comprehensive technical analysis report covering regime, support/resistance, divergences, and recommendations"
    )
    technical_score: int = Field(
        ge=1, le=5,
        description="Technical score from 1-5 indicating stock performance. 1: Strong bearish, 2: Weak bearish, 3: Neutral, 4: Moderate bullish, 5: Strong bullish"
    )
    key_takeaways: List[str] = analyst_key_takeaways_field()


def create_technical_analyst(llm):
    """Create a self-contained technical analyst that handles all tool calling internally."""
    return create_self_contained_analyst(
        llm=llm,
        tools=[
            get_events,
            get_ticker_data,
            get_ticker_quote,
            get_indicators,
            detect_divergence,
            detect_regime,
            detect_support_resistance,
        ],
        prompt_builder=build_technical_analyst_prompt,
        structured_output_class=TechnicalAnalysisOutput,
        score_field="technical_score",
        report_field="technical_report",
        agent_name="Technical Analyst",
        max_iterations=5,
    )
