from datetime import datetime, timedelta, timezone

from langchain_core.messages import AIMessage, ToolMessage
from pydantic import BaseModel, Field

from ..utils.agent_utils import get_reddit_company_social, get_ticker_quote
from .helpers import _capture_usage
from .prompts import build_social_media_analyst_prompt


class SocialMediaAnalysisOutput(BaseModel):
    """Structured output for social media analysis including report and score."""
    report: str = Field(
        description="Comprehensive social media and sentiment analysis report based on Reddit discussions and public sentiment"
    )
    sentiment_score: int = Field(
        ge=1, le=10,
        description="Sentiment score from 1-10 indicating public sentiment and social media outlook. 1-3: Very negative sentiment, 4-5: Neutral/mixed sentiment, 6-7: Moderately positive sentiment, 8-10: Very positive sentiment"
    )


def create_social_media_analyst(llm):
    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        # Use isolated local context
        local_messages = state.get("_social_context", [])

        # Check if we have tool results in local context
        last_message = local_messages[-1] if local_messages else None
        is_after_tool_call = isinstance(last_message, ToolMessage)
        tool_message_count = sum(1 for m in local_messages if isinstance(m, ToolMessage))

        if is_after_tool_call:
            prompt = build_social_media_analyst_prompt(
                tool_names=["get_ticker_quote", "get_reddit_company_social"],
                current_date=current_date,
                ticker=ticker,
            )
            # Allow one retry: if we have only 2 tool results (quote + reddit), LLM may call Reddit again with different search_terms.
            can_retry_reddit = tool_message_count == 2
            if can_retry_reddit:
                chain = prompt | llm.bind_tools([get_reddit_company_social])
                result = chain.invoke(local_messages)
                if getattr(result, "tool_calls", None):
                    usage_meta = _capture_usage(result, llm)
                    local_messages.append(result)
                    out = {"_social_context": local_messages, "sentiment_report": "", "sentiment_score": None}
                    if usage_meta:
                        out["report_usage"] = {"sentiment_report": usage_meta}
                    return out
                # No tool_calls → LLM is done; get structured report from current messages (include this response for context).
                messages_plus = list(local_messages) + [result]
                try:
                    chain_structured = prompt | llm.with_structured_output(SocialMediaAnalysisOutput)
                    structured_result = chain_structured.invoke(messages_plus)
                    report = structured_result.report
                    sentiment_score = structured_result.sentiment_score
                except Exception:
                    report = result.content or ""
                    sentiment_score = None
                result = AIMessage(content=report)
            else:
                try:
                    chain = prompt | llm.with_structured_output(SocialMediaAnalysisOutput)
                    structured_result = chain.invoke(local_messages)
                    report = structured_result.report
                    sentiment_score = structured_result.sentiment_score
                except Exception:
                    report = ""
                    sentiment_score = None
                result = AIMessage(content=report)
            usage_meta = _capture_usage(result, llm)
            out = {
                "_social_context": None,  # Clear temp state
                "sentiment_report": report,
                "sentiment_score": sentiment_score,
            }
            if usage_meta:
                out["report_usage"] = {"sentiment_report": usage_meta}
            return out

        # No tool results yet → emit tool_calls so the graph runs quote + Reddit, then loops back.
        trade_dt = datetime.strptime(current_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        start_date = (trade_dt - timedelta(days=7)).strftime("%Y-%m-%d")
        result = AIMessage(
            content="",
            tool_calls=[
                {"id": "call_quote", "name": "get_ticker_quote", "args": {"symbol": ticker}},
                {
                    "id": "call_reddit",
                    "name": "get_reddit_company_social",
                    "args": {
                        "ticker": ticker,
                        "start_date": start_date,
                        "end_date": current_date,
                        "search_terms": [ticker],
                    },
                },
            ],
        )
        local_messages.append(result)
        return {"_social_context": local_messages, "sentiment_report": "", "sentiment_score": None}

    return social_media_analyst_node
