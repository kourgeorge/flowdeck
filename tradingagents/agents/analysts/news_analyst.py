from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field
from tradingagents.agents.utils.agent_utils import get_news, get_global_news


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
        ]

        system_message = (
            "You are a news researcher tasked with analyzing recent news and trends over the past week. Please write a comprehensive report of the current state of the world that is relevant for trading and macroeconomics. Use the available tools: get_news(query, start_date, end_date) for company-specific or targeted news searches, and get_global_news(curr_date, look_back_days, limit) for broader macroeconomic news. Do not simply state the trends are mixed, provide detailed and finegrained analysis and insights that may help traders make decisions."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + """ **CRITICAL: You MUST provide a News Score between 1-10 as part of your structured output.**
            - Scoring guidelines:
              * 1-3: Very negative news impact, significant negative developments, concerning macroeconomic trends, adverse global events
              * 4-5: Neutral or mixed news impact, balanced developments, no clear positive or negative trend
              * 6-7: Moderately positive news impact, generally favorable developments, some positive trends
              * 8-10: Very positive news impact, significant positive developments, strong macroeconomic trends, favorable global events
            - Base your score on: news sentiment, macroeconomic indicators, global events, market-moving developments, and overall news impact

            **Formatting:** Structure your report for readability: use clear paragraphs and subparagraphs, Markdown tables for key data or comparisons, and headings (## or ###) to organize sections. Avoid long unbroken blocks of text so the output is easy to scan and use."""
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. We are looking at the company {ticker}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)

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
                structured_chain = prompt | llm.with_structured_output(NewsAnalysisOutput)
                structured_result = structured_chain.invoke(state["messages"])
                report = structured_result.report
                news_score = structured_result.news_score
                
                # Create a message from the structured result
                from langchain_core.messages import AIMessage
                result = AIMessage(content=report)
                
                return {
                    "messages": [result],
                    "news_report": report,
                    "news_score": news_score,
                }
            except Exception:
                # Fallback to tool-based approach if structured output fails
                pass
        
        # Default: use tools (for initial calls or if structured output failed)
        chain_with_tools = prompt | llm.bind_tools(tools)
        result = chain_with_tools.invoke(state["messages"])

        report = ""
        news_score = None

        # If no tool calls in result, we might be at final response
        # Try structured output parsing
        if len(result.tool_calls) == 0:
            try:
                # Re-invoke with structured output to get parsed result
                structured_chain = prompt | llm.with_structured_output(NewsAnalysisOutput)
                structured_result = structured_chain.invoke(state["messages"])
                report = structured_result.report
                news_score = structured_result.news_score
                # Update result content with the report
                result.content = report
            except Exception:
                # Final fallback: use regular content (no score extraction)
                report = result.content if hasattr(result, 'content') else str(result)
                news_score = None

        return {
            "messages": [result],
            "news_report": report,
            "news_score": news_score,
        }

    return news_analyst_node
