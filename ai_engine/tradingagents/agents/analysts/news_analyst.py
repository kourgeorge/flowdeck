import logging
from typing import List

from pydantic import BaseModel, Field
from ..utils.agent_utils import (
    get_events,
    get_news,
    get_global_news,
    get_insider_transactions,
)
from .self_contained_analyst import create_self_contained_analyst
from .output_schema import analyst_key_takeaways_field
from .prompts import build_news_analyst_prompt

logger = logging.getLogger(__name__)


class NewsAnalysisOutput(BaseModel):
    """Structured output for news analysis including report and score."""
    report: str = Field(
        description="Comprehensive news analysis report covering recent news, macroeconomic trends, and global events relevant to trading"
    )
    news_score: int = Field(
        ge=1, le=10,
        description="News score from 1-10 indicating news impact outlook. 1-3: Very negative news impact, 4-5: Neutral/mixed news impact, 6-7: Moderately positive news impact, 8-10: Very positive news impact"
    )
    key_takeaways: List[str] = analyst_key_takeaways_field()


def create_news_analyst(llm):
    """Create a self-contained news analyst that handles all tool calling internally."""
    return create_self_contained_analyst(
        llm=llm,
        tools=[
            get_events,
            get_news,
            get_global_news,
            get_insider_transactions,
        ],
        prompt_builder=build_news_analyst_prompt,
        structured_output_class=NewsAnalysisOutput,
        score_field="news_score",
        report_field="news_report",
        agent_name="News Analyst",
        max_iterations=5,
    )
