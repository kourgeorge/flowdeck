import logging

from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
from ..utils.agent_utils import get_news, get_global_news, get_insider_transactions
from .helpers import is_tool_result_message, try_structured_response
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
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        tools = [
            get_news,
            get_global_news,
            get_insider_transactions,
        ]

        prompt = build_news_analyst_prompt(
            tool_names=[tool.name for tool in tools],
            current_date=current_date,
            ticker=ticker,
        )
        state_messages = state["messages"]
        structured_chain = prompt | llm.with_structured_output(NewsAnalysisOutput)

        # Check if last message is a tool result (indicating we're ready for final response)
        last_message = state_messages[-1] if state_messages else None
        if is_tool_result_message(last_message):
            report, news_score = try_structured_response(
                structured_chain,
                state_messages,
                score_field="news_score",
                logger=logger,
                agent_name="News analyst",
            )
            if report is not None:
                return {
                    "messages": [AIMessage(content=report)],
                    "news_report": report,
                    "news_score": news_score,
                }

            fallback_result = (prompt | llm).invoke(state_messages)
            fallback_report = (
                fallback_result.content
                if hasattr(fallback_result, "content")
                else str(fallback_result)
            )
            return {
                "messages": [fallback_result],
                "news_report": fallback_report,
                "news_score": None,
            }
        
        # Default: use tools (for initial calls or if structured output failed)
        chain_with_tools = prompt | llm.bind_tools(tools)
        result = chain_with_tools.invoke(state_messages)

        # If no tool calls in result, we might be at final response
        # Try structured output parsing
        if not getattr(result, "tool_calls", []):
            messages_with_result = [*state_messages, result]
            report, news_score = try_structured_response(
                structured_chain,
                messages_with_result,
                score_field="news_score",
                logger=logger,
                agent_name="News analyst",
            )
            if report is not None:
                return {
                    "messages": [AIMessage(content=report)],
                    "news_report": report,
                    "news_score": news_score,
                }

            report = result.content if hasattr(result, "content") else str(result)
            return {
                "messages": [result],
                "news_report": report,
                "news_score": None,
            }

        return {
            "messages": [result],
            "news_report": "",
            "news_score": None,
        }

    return news_analyst_node
