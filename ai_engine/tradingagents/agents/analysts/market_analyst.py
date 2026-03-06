import logging

from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from ..utils.agent_utils import (
    get_ticker_data,
    get_ticker_quote,
    get_indicators,
    get_analysts_recommendation,
)
from .helpers import is_tool_result_message, try_structured_response
from .prompts import build_market_analyst_prompt

logger = logging.getLogger(__name__)


class MarketAnalysisOutput(BaseModel):
    """Structured output for market analysis including report and score."""
    report: str = Field(
        description="Comprehensive market analysis report covering technical indicators, trends, and market conditions"
    )
    market_score: int = Field(
        ge=1, le=10,
        description="Market score from 1-10 indicating market performance outlook. 1-3: Very bearish market conditions, 4-5: Neutral/mixed market conditions, 6-7: Moderately bullish market conditions, 8-10: Very bullish market conditions"
    )


def create_market_analyst(llm):

    def market_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        tools = [
            get_ticker_data,
            get_ticker_quote,
            get_indicators,
            get_analysts_recommendation,
        ]

        prompt = build_market_analyst_prompt(
            tool_names=[tool.name for tool in tools],
            current_date=current_date,
            ticker=ticker,
        )
        state_messages = state["messages"]
        structured_chain = prompt | llm.with_structured_output(MarketAnalysisOutput)

        # Check if last message is a tool result (indicating we're ready for final response)
        last_message = state_messages[-1] if state_messages else None
        if is_tool_result_message(last_message):
            report, market_score = try_structured_response(
                structured_chain,
                state_messages,
                 score_field="market_score",
                logger=logger,
                agent_name="Market analyst",
            )
            if report is not None:
                return {
                    "messages": [AIMessage(content=report)],
                    "market_report": report,
                    "market_score": market_score,
                }

            # Fallback: produce a final narrative response without tool calling.
            fallback_result = (prompt | llm).invoke(state_messages)
            fallback_report = (
                fallback_result.content
                if hasattr(fallback_result, "content")
                else str(fallback_result)
            )
            return {
                "messages": [fallback_result],
                "market_report": fallback_report,
                "market_score": None,
            }
        
        # Default: use tools (for initial calls or if structured output failed)
        chain_with_tools = prompt | llm.bind_tools(tools)
        result = chain_with_tools.invoke(state_messages)

        # If no tool calls in result, we might be at final response
        # Try structured output parsing
        if not getattr(result, "tool_calls", []):
            messages_with_result = [*state_messages, result]
            report, market_score = try_structured_response(
                structured_chain,
                messages_with_result,
                score_field="market_score",
                logger=logger,
                agent_name="Market analyst",
            )
            if report is not None:
                return {
                    "messages": [AIMessage(content=report)],
                    "market_report": report,
                    "market_score": market_score,
                }

            report = result.content if hasattr(result, "content") else str(result)
            return {
                "messages": [result],
                "market_report": report,
                "market_score": None,
            }
       
        return {
            "messages": [result],
            "market_report": "",
            "market_score": None,
        }

    return market_analyst_node
