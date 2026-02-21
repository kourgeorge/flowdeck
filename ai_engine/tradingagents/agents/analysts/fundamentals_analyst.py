import logging

from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
from ..utils.agent_utils import get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement
from .helpers import is_tool_result_message, try_structured_response
from .prompts import build_fundamentals_analyst_prompt

logger = logging.getLogger(__name__)


class FundamentalsAnalysisOutput(BaseModel):
    """Structured output for fundamentals analysis including report and score."""
    report: str = Field(
        description="Comprehensive fundamentals analysis report covering financial statements, company profile, financial health, and company fundamentals"
    )
    fundamentals_score: int = Field(
        ge=1, le=10,
        description="Fundamentals score from 1-10 indicating company financial health and fundamental strength. 1-3: Very weak fundamentals, 4-5: Neutral/mixed fundamentals, 6-7: Moderately strong fundamentals, 8-10: Very strong fundamentals"
    )


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        ]

        prompt = build_fundamentals_analyst_prompt(
            tool_names=[tool.name for tool in tools],
            current_date=current_date,
            ticker=ticker,
        )
        state_messages = state["messages"]
        structured_chain = prompt | llm.with_structured_output(
            FundamentalsAnalysisOutput
        )

        # Check if last message is a tool result (indicating we're ready for final response)
        last_message = state_messages[-1] if state_messages else None
        if is_tool_result_message(last_message):
            report, fundamentals_score = try_structured_response(
                structured_chain,
                state_messages,
                score_field="fundamentals_score",
                logger=logger,
                agent_name="Fundamentals analyst",
            )
            if report is not None:
                return {
                    "messages": [AIMessage(content=report)],
                    "fundamentals_report": report,
                    "fundamentals_score": fundamentals_score,
                }

            fallback_result = (prompt | llm).invoke(state_messages)
            fallback_report = (
                fallback_result.content
                if hasattr(fallback_result, "content")
                else str(fallback_result)
            )
            return {
                "messages": [fallback_result],
                "fundamentals_report": fallback_report,
                "fundamentals_score": None,
            }
        
        # Default: use tools (for initial calls or if structured output failed)
        chain_with_tools = prompt | llm.bind_tools(tools)
        result = chain_with_tools.invoke(state_messages)

        # If no tool calls in result, we might be at final response
        # Try structured output parsing
        if not getattr(result, "tool_calls", []):
            messages_with_result = [*state_messages, result]
            report, fundamentals_score = try_structured_response(
                structured_chain,
                messages_with_result,
                score_field="fundamentals_score",
                logger=logger,
                agent_name="Fundamentals analyst",
            )
            if report is not None:
                return {
                    "messages": [AIMessage(content=report)],
                    "fundamentals_report": report,
                    "fundamentals_score": fundamentals_score,
                }

            report = result.content if hasattr(result, "content") else str(result)
            return {
                "messages": [result],
                "fundamentals_report": report,
                "fundamentals_score": None,
            }

        return {
            "messages": [result],
            "fundamentals_report": "",
            "fundamentals_score": None,
        }

    return fundamentals_analyst_node
