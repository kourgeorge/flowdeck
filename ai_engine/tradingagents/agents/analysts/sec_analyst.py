"""SEC/Regulatory analyst: analyzes EDGAR filing content (risk factors, MD&A, competition) for trading context."""

from typing import List

from pydantic import BaseModel, Field

from ..utils.edgar_tools import get_edgar_filing_content
from .self_contained_analyst import create_self_contained_analyst
from .output_schema import analyst_key_takeaways_field
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
    key_takeaways: List[str] = analyst_key_takeaways_field()


def create_sec_analyst(llm):
    """Create a self-contained SEC analyst that handles all tool calling internally."""
    return create_self_contained_analyst(
        llm=llm,
        tools=[get_edgar_filing_content],
        prompt_builder=build_sec_analyst_prompt,
        structured_output_class=SecAnalysisOutput,
        score_field="sec_score",
        report_field="sec_report",
        agent_name="SEC Analyst",
        max_iterations=5,
    )
