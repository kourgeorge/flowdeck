import logging
from typing import List

from pydantic import BaseModel, Field
from ..utils.agent_utils import get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement
from .self_contained_analyst import create_self_contained_analyst
from .output_schema import analyst_key_takeaways_field
from .prompts import build_fundamentals_analyst_prompt

logger = logging.getLogger(__name__)


class FundamentalsAnalysisOutput(BaseModel):
    """Structured output for fundamentals analysis including report and score."""
    report: str = Field(
        description="Comprehensive fundamentals analysis report covering financial statements, company profile, financial health, and company fundamentals"
    )
    fundamentals_score: int = Field(
        ge=1, le=10,
        description="Fundamentals score from 1-10 indicating company financial health and fundamental strength. 1-3: Very weak fundamentals, 4-5: Neutral/mixed fundamentals, 6-7: Moderately strong fundamentals, 8-10: Very strong fundamentals"
    )
    key_takeaways: List[str] = analyst_key_takeaways_field()


def create_fundamentals_analyst(llm):
    """Create a self-contained fundamentals analyst that handles all tool calling internally."""
    return create_self_contained_analyst(
        llm=llm,
        tools=[
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        ],
        prompt_builder=build_fundamentals_analyst_prompt,
        structured_output_class=FundamentalsAnalysisOutput,
        score_field="fundamentals_score",
        report_field="fundamentals_report",
        agent_name="Fundamentals Analyst",
        max_iterations=5,
    )
