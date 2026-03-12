from pydantic import BaseModel, Field
from ..utils.agent_utils import get_news
from .helpers import _capture_usage
from .prompts import build_social_media_analyst_prompt


class SocialMediaAnalysisOutput(BaseModel):
    """Structured output for social media analysis including report and score."""
    report: str = Field(
        description="Comprehensive social media and sentiment analysis report covering public sentiment, social media discussions, and company news"
    )
    sentiment_score: int = Field(
        ge=1, le=10,
        description="Sentiment score from 1-10 indicating public sentiment and social media outlook. 1-3: Very negative sentiment, 4-5: Neutral/mixed sentiment, 6-7: Moderately positive sentiment, 8-10: Very positive sentiment"
    )


def create_social_media_analyst(llm):
    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        tools = [
            get_news,
        ]

        prompt = build_social_media_analyst_prompt(
            tool_names=[tool.name for tool in tools],
            current_date=current_date,
            ticker=ticker,
        )

        # Check if last message is a tool result (indicating we're ready for final response)
        from langchain_core.messages import ToolMessage
        last_message = state["messages"][-1] if state["messages"] else None
        is_after_tool_call = isinstance(last_message, ToolMessage) or (
            hasattr(last_message, 'content') and 
            isinstance(last_message.content, list) and
            any(isinstance(item, dict) and item.get("type") == "tool" for item in last_message.content)
        )
        
        # If we're after tool calls, use structured output for final response
        if is_after_tool_call:
            try:
                structured_chain = prompt | llm.with_structured_output(SocialMediaAnalysisOutput)
                structured_result = structured_chain.invoke(state["messages"])
                report = structured_result.report
                sentiment_score = structured_result.sentiment_score
                
                # Create a message from the structured result
                from langchain_core.messages import AIMessage
                result = AIMessage(content=report)
                
                return {
                    "messages": [result],
                    "sentiment_report": report,
                    "sentiment_score": sentiment_score,
                }
            except Exception:
                # Fallback to tool-based approach if structured output fails
                pass
        
        # Default: use tools (for initial calls or if structured output failed)
        chain_with_tools = prompt | llm.bind_tools(tools)
        result = chain_with_tools.invoke(state["messages"])

        report = ""
        sentiment_score = None

        # If no tool calls in result, we might be at final response
        # Try structured output parsing
        if len(result.tool_calls) == 0:
            try:
                # Re-invoke with structured output to get parsed result
                structured_chain = prompt | llm.with_structured_output(SocialMediaAnalysisOutput)
                structured_result = structured_chain.invoke(state["messages"])
                report = structured_result.report
                sentiment_score = structured_result.sentiment_score
                # Update result content with the report
                result.content = report
            except Exception:
                # Final fallback: use regular content (no score extraction)
                report = result.content if hasattr(result, 'content') else str(result)
                sentiment_score = None

        usage_meta = _capture_usage(result, llm)
        out = {
            "messages": [result],
            "sentiment_report": report,
            "sentiment_score": sentiment_score,
        }
        if usage_meta:
            out["report_usage"] = {"sentiment_report": usage_meta}
        return out

    return social_media_analyst_node
