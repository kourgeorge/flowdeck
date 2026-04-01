"""SEC/Regulatory analyst: analyzes EDGAR filing content (risk factors, MD&A, competition) for trading context."""

from pydantic import BaseModel, Field

from ..utils.edgar_tools import get_edgar_filing_content
from .isolated_context import run_analyst_with_isolated_context
from .prompts import build_sec_analyst_prompt


class SecAnalysisOutput(BaseModel):
    """Structured output for SEC/regulatory analysis: report and score."""
    report: str = Field(
        description="Concise SEC/regulatory analysis report focused on management (MD&A), competition, and risk from EDGAR, with implications for traders."
    )
    sec_score: int = Field(
        ge=1, le=10,
        description="SEC/regulatory score 1-10. 1-3: higher regulatory/filing risk or disclosure concerns; 8-10: lower concern, cleaner disclosures."
    )


def create_sec_analyst(llm):
    def sec_analyst_node(state):
        tools = [get_edgar_filing_content]
        
        return run_analyst_with_isolated_context(
            state=state,
            llm=llm,
            tools=tools,
            prompt_builder=build_sec_analyst_prompt,
            structured_output_class=SecAnalysisOutput,
            score_field="sec_score",
            report_field="sec_report",
            agent_name="SEC Analyst",
            temp_state_key="_sec_context",
        )

    return sec_analyst_node
