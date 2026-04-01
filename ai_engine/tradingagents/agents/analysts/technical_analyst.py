import logging

from pydantic import BaseModel, Field
from ..utils.agent_utils import get_ticker_data, get_ticker_quote, get_indicators
from ..utils.advanced_technical_tools import (
    detect_divergence,
    detect_regime,
    detect_support_resistance
)
from .isolated_context import run_analyst_with_isolated_context
from .prompts import build_technical_analyst_prompt

logger = logging.getLogger(__name__)


class TechnicalAnalysisOutput(BaseModel):
    """Structured output for technical analysis including report and score."""
    report: str = Field(
        description="Comprehensive technical analysis report covering regime, support/resistance, divergences, and recommendations"
    )
    technical_score: int = Field(
        ge=1, le=10,
        description="Technical score from 1-10 indicating stock performance. 1-3: Strong bearish, 4-5: Neutral/weak bearish, 6-7: Moderate bullish, 8-10: Strong bullish"
    )


def create_technical_analyst(llm):

    def technical_analyst_node(state):
        tools = [
            get_ticker_data,
            get_ticker_quote,
            get_indicators,
            detect_divergence,
            detect_regime,
            detect_support_resistance,
        ]
        
        return run_analyst_with_isolated_context(
            state=state,
            llm=llm,
            tools=tools,
            prompt_builder=build_technical_analyst_prompt,
            structured_output_class=TechnicalAnalysisOutput,
            score_field="technical_score",
            report_field="technical_report",
            agent_name="Technical Analyst",
            temp_state_key="_technical_context",
        )

    return technical_analyst_node
