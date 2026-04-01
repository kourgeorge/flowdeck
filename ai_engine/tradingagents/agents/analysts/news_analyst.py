import logging

from pydantic import BaseModel, Field
from ..utils.agent_utils import get_news, get_global_news, get_insider_transactions
from .isolated_context import run_analyst_with_isolated_context
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


def create_news_analyst(llm):
    def news_analyst_node(state):
        tools = [
            get_news,
            get_global_news,
            get_insider_transactions,
        ]
        
        return run_analyst_with_isolated_context(
            state=state,
            llm=llm,
            tools=tools,
            prompt_builder=build_news_analyst_prompt,
            structured_output_class=NewsAnalysisOutput,
            score_field="news_score",
            report_field="news_report",
            agent_name="News Analyst",
            temp_state_key="_news_context",
        )

    return news_analyst_node
