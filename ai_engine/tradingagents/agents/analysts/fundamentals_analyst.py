import logging
from typing import Any, Dict, List

from pydantic import BaseModel, Field
from ..utils.agent_utils import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
)
from ..utils.fundamental_data_tools import is_etf_or_index
from .self_contained_analyst import create_self_contained_analyst
from .output_schema import analyst_key_takeaways_field
from .prompts import build_fundamentals_analyst_prompt

logger = logging.getLogger(__name__)

_NOT_APPLICABLE_REPORT = (
    "## Fundamentals Analysis — Not Applicable\n\n"
    "This ticker is an ETF, index fund, or similar non-company instrument. "
    "Fundamentals analysis (balance sheet, income statement, cash flow, company profile) "
    "is only meaningful for individual companies and has been skipped."
)


class FundamentalsAnalysisOutput(BaseModel):
    """Structured output for fundamentals analysis including report and score."""
    report: str = Field(
        description="Comprehensive fundamentals analysis report covering financial statements, company profile, financial health, and company fundamentals"
    )
    fundamentals_score: int = Field(
        ge=1, le=5,
        description="Fundamentals score from 1-5 indicating company financial health and fundamental strength. 1: Very weak fundamentals, 2: Weak/below-average fundamentals, 3: Neutral/mixed fundamentals, 4: Moderately strong fundamentals, 5: Very strong fundamentals"
    )
    key_takeaways: List[str] = analyst_key_takeaways_field()


def create_fundamentals_analyst(llm):
    """Create a self-contained fundamentals analyst that handles all tool calling internally."""
    inner = create_self_contained_analyst(
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

    def analyst_node(state: Dict[str, Any]) -> Dict[str, Any]:
        ticker = state.get("company_of_interest", "")
        if is_etf_or_index(ticker):
            logger.info("Fundamentals Analyst: skipping ETF/index %s", ticker)
            return {
                "fundamentals_report": _NOT_APPLICABLE_REPORT,
                "fundamentals_score": None,
                "fundamentals_key_takeaways": [],
                "report_usage": {"fundamentals_report": {}},
                "report_resources": [],
                "report_resources_by_report": {"fundamentals_report": []},
                "report_steps_by_report": {"fundamentals_report": []},
            }
        return inner(state)

    return analyst_node
