from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field
from tradingagents.agents.utils.agent_utils import get_news


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

        system_message = (
            "You are a social media and company specific news researcher/analyst tasked with analyzing social media posts, recent company news, and public sentiment for a specific company over the past week. You will be given a company's name your objective is to write a comprehensive long report detailing your analysis, insights, and implications for traders and investors on this company's current state after looking at social media and what people are saying about that company, analyzing sentiment data of what people feel each day about the company, and looking at recent company news. Use the get_news(query, start_date, end_date) tool to search for company-specific news and social media discussions. Try to look at all sources possible from social media to sentiment to news. Do not simply state the trends are mixed, provide detailed and finegrained analysis and insights that may help traders make decisions."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + """ **CRITICAL: You MUST provide a Sentiment Score between 1-10 as part of your structured output.**
            - Scoring guidelines:
              * 1-3: Very negative sentiment, widespread criticism, negative social media buzz, poor public perception
              * 4-5: Neutral or mixed sentiment, balanced discussions, no clear positive or negative trend
              * 6-7: Moderately positive sentiment, generally favorable discussions, some positive buzz
              * 8-10: Very positive sentiment, strong positive buzz, widespread praise, excellent public perception
            - Base your score on: overall sentiment trends, social media discussions, public perception, news sentiment, and community engagement

            **Formatting:** Structure your report for readability: use clear paragraphs and subparagraphs, Markdown tables for key data or comparisons, and headings (## or ###) to organize sections. Avoid long unbroken blocks of text so the output is easy to scan and use.""",
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
                    "For your reference, the current date is {current_date}. The current company we want to analyze is {ticker}",
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

        return {
            "messages": [result],
            "sentiment_report": report,
            "sentiment_score": sentiment_score,
        }

    return social_media_analyst_node
