import logging

from pydantic import BaseModel, Field
from ..utils.agent_utils import get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement
from .isolated_context import run_analyst_with_isolated_context
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


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        ]
        
        return run_analyst_with_isolated_context(
            state=state,
            llm=llm,
            tools=tools,
            prompt_builder=build_fundamentals_analyst_prompt,
            structured_output_class=FundamentalsAnalysisOutput,
            score_field="fundamentals_score",
            report_field="fundamentals_report",
            agent_name="Fundamentals Analyst",
            temp_state_key="_fundamentals_context",
        )

    return fundamentals_analyst_node
