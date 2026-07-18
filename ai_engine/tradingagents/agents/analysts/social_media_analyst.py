from typing import List

from pydantic import BaseModel, Field

from ..utils.agent_utils import (
    get_reddit_company_social,
    get_ticker_quote,
    get_polymarket_sentiment,
    get_events,
    get_news,
    get_global_news,
    get_insider_transactions,
)
from .self_contained_analyst import create_self_contained_analyst
from .output_schema import analyst_key_takeaways_field
from .prompts import build_social_media_analyst_prompt


class SocialMediaAnalysisOutput(BaseModel):
    """Structured output for the combined news & sentiment analysis (report + score)."""
    report: str = Field(
        description="Comprehensive News & Sentiment report integrating recent news, catalysts, macroeconomic trends, and insider activity with crowd sentiment from Reddit discussions and Polymarket prediction markets"
    )
    sentiment_score: int = Field(
        ge=1, le=5,
        description="Combined news & sentiment score from 1-5. 1: Very negative news/sentiment, 2: Mildly negative, 3: Neutral/mixed, 4: Moderately positive, 5: Very positive"
    )
    key_takeaways: List[str] = analyst_key_takeaways_field()


def create_social_media_analyst(llm):
    """Create the self-contained News & Sentiment analyst.

    Combines the former News and Social/Sentiment analysts into a single node that
    gathers both the news/catalyst narrative and crowd-sentiment signals, then
    produces one integrated ``sentiment_report`` and ``sentiment_score``.
    """
    return create_self_contained_analyst(
        llm=llm,
        tools=[
            get_ticker_quote,
            # News layer
            get_events,
            get_news,
            get_global_news,
            get_insider_transactions,
            # Sentiment layer
            get_reddit_company_social,
            get_polymarket_sentiment,
        ],
        prompt_builder=build_social_media_analyst_prompt,
        structured_output_class=SocialMediaAnalysisOutput,
        score_field="sentiment_score",
        report_field="sentiment_report",
        agent_name="News & Sentiment Analyst",
        max_iterations=8,
    )
