import logging

from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
from ..utils.agent_utils import get_ticker_data, get_ticker_quote, get_indicators
from ..utils.advanced_technical_tools import (
    detect_divergence,
    detect_regime,
    detect_support_resistance
)
from .helpers import is_tool_result_message, try_structured_response
from .prompts import build_technical_analyst_prompt

logger = logging.getLogger(__name__)


class TechnicalAnalysisOutput(BaseModel):
    """Structured output for technical analysis including report and score."""
    report: str = Field(
        description="Comprehensive technical analysis report covering regime, support/resistance, divergences, and recommendations"
    )
    technical_score: int = Field(
        ge=1, le=10,
        description="Technical score from 1-10 indicating stock performance. 1-3: Strong bearish, 4-5: Neutral/weak bearish, 6-7: Moderate bullish, 8-10: Strong bullish"
    )


def create_technical_analyst(llm):

    def technical_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        tools = [
            get_ticker_data,
            get_ticker_quote,
            get_indicators,
            detect_divergence,
            detect_regime,
            detect_support_resistance,
        ]

        prompt = build_technical_analyst_prompt(
            tool_names=[tool.name for tool in tools],
            current_date=current_date,
            ticker=ticker,
        )
        state_messages = state["messages"]
        structured_chain = prompt | llm.with_structured_output(TechnicalAnalysisOutput)

        # Check if last message is a tool result (indicating we're ready for final response)
        last_message = state_messages[-1] if state_messages else None
        if is_tool_result_message(last_message):
            report, technical_score = try_structured_response(
                structured_chain,
                state_messages,
                score_field="technical_score",
                logger=logger,
                agent_name="Technical analyst",
            )
            if report is not None:
                return {
                    "messages": [AIMessage(content=report)],
                    "technical_report": report,
                    "technical_score": technical_score,
                }

            fallback_result = (prompt | llm).invoke(state_messages)
            fallback_report = (
                fallback_result.content
                if hasattr(fallback_result, "content")
                else str(fallback_result)
            )
            return {
                "messages": [fallback_result],
                "technical_report": fallback_report,
                "technical_score": None,
            }
        
        # Default: use tools (for initial calls or if structured output failed)
        chain_with_tools = prompt | llm.bind_tools(tools)
        result = chain_with_tools.invoke(state_messages)

        # If no tool calls in result, we might be at final response
        # Try structured output parsing
        if not getattr(result, "tool_calls", []):
            messages_with_result = [*state_messages, result]
            report, technical_score = try_structured_response(
                structured_chain,
                messages_with_result,
                score_field="technical_score",
                logger=logger,
                agent_name="Technical analyst",
            )
            if report is not None:
                return {
                    "messages": [AIMessage(content=report)],
                    "technical_report": report,
                    "technical_score": technical_score,
                }

            report = result.content if hasattr(result, "content") else str(result)
            return {
                "messages": [result],
                "technical_report": report,
                "technical_score": None,
            }
       
        return {
            "messages": [result],
            "technical_report": "",
            "technical_score": None,
        }

    return technical_analyst_node
