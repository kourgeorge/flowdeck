from typing import List

from pydantic import BaseModel, Field

from ..utils.agent_utils import (
    get_reddit_company_social,
    get_ticker_quote,
    get_polymarket_sentiment,
)
from .self_contained_analyst import create_self_contained_analyst
from .output_schema import analyst_key_takeaways_field
from .prompts import build_social_media_analyst_prompt


class SocialMediaAnalysisOutput(BaseModel):
    """Structured output for social media analysis including report and score."""
    report: str = Field(
        description="Comprehensive social media and sentiment analysis report based on Reddit discussions, Polymarket prediction markets, and public sentiment"
    )
    sentiment_score: int = Field(
        ge=1, le=10,
        description="Sentiment score from 1-10 indicating public sentiment and social media outlook. 1-3: Very negative sentiment, 4-5: Neutral/mixed sentiment, 6-7: Moderately positive sentiment, 8-10: Very positive sentiment"
    )
    key_takeaways: List[str] = analyst_key_takeaways_field()


def create_social_media_analyst(llm):
    """Create a self-contained social media analyst that handles all tool calling internally."""
    return create_self_contained_analyst(
        llm=llm,
        tools=[
            get_ticker_quote,
            get_reddit_company_social,
            get_polymarket_sentiment,
        ],
        prompt_builder=build_social_media_analyst_prompt,
        structured_output_class=SocialMediaAnalysisOutput,
        score_field="sentiment_score",
        report_field="sentiment_report",
        agent_name="Social Media Analyst",
        max_iterations=5,
    )
