"""SEC/Regulatory analyst: analyzes EDGAR filing content with file exploration capabilities."""

from typing import List

from pydantic import BaseModel, Field

from ..utils.edgar_tools import get_edgar_filing_content
from ..utils.sec_explorer_tools import (
    grep_sec_filing,
    read_sec_section,
    get_sec_toc,
    get_sec_stats,
    read_sec_lines,
)
from .self_contained_analyst import create_self_contained_analyst
from .output_schema import analyst_key_takeaways_field
from .prompts import build_sec_analyst_prompt


class SecAnalysisOutput(BaseModel):
    """Structured output for SEC/regulatory analysis: report and score."""
    report: str = Field(
        description="Comprehensive SEC/regulatory analysis report with targeted insights from filing exploration."
    )
    sec_score: int = Field(
        ge=1, le=10,
        description="SEC/regulatory score 1-10. 1-3: higher regulatory/filing risk or disclosure concerns; 8-10: lower concern, cleaner disclosures."
    )
    key_takeaways: List[str] = analyst_key_takeaways_field()


def create_sec_analyst(llm):
    """Create SEC analyst with file exploration tools (like a coding agent exploring files)."""
    return create_self_contained_analyst(
        llm=llm,
        tools=[
            get_edgar_filing_content, # Primary: LLM extraction (original tool)
            get_sec_toc,              # Optional: see structure (like ls)
            get_sec_stats,            # Optional: overview (like wc)
            grep_sec_filing,          # Optional: search (like grep)
            read_sec_section,         # Optional: read section (like cat function)
            read_sec_lines,           # Optional: read lines (like sed -n 'X,Yp')
        ],
        prompt_builder=build_sec_analyst_prompt,
        structured_output_class=SecAnalysisOutput,
        score_field="sec_score",
        report_field="sec_report",
        agent_name="SEC Analyst",
        max_iterations=8,  # Increased for exploration
    )
