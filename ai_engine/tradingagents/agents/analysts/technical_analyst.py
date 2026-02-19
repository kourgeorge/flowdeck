from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field
from ..utils.agent_utils import get_stock_data, get_indicators
from ..utils.advanced_technical_tools import (
    detect_divergence,
    detect_regime,
    detect_support_resistance
)


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
            get_stock_data,
            get_indicators,
            detect_divergence,
            detect_regime,
            detect_support_resistance,
        ]

        system_message = (
            """You are an advanced technical analyst specializing in quantitative pattern recognition and market regime analysis. 
            Your role is to perform deep technical analysis using three critical approaches:

            1. **Divergence Detection**: Identify bullish and bearish divergences between price and momentum indicators (RSI, MACD).
               - Bullish divergence: Price makes lower lows but indicator makes higher lows (potential reversal up)
               - Bearish divergence: Price makes higher highs but indicator makes lower highs (potential reversal down)
               - Divergences often signal trend reversals before price confirms them

            2. **Regime Detection**: Classify the current market regime to adapt trading strategies.
               - Trending vs Ranging markets
               - High vs Low volatility environments
               - Provide adaptive recommendations based on regime

            3. **Support/Resistance Analysis**: Identify key price levels using multiple methods.
               - Price clustering (where price frequently reverses)
               - Volume profile (price levels with highest trading activity)
               - Recent highs and lows
               - Moving averages as dynamic support/resistance

            **Your Analysis Process:**
            1. First, call get_stock_data to retrieve price history
            2. Call detect_regime to understand the current market environment
            3. Call detect_support_resistance to identify key price levels
            4. Call detect_divergence with different indicators (rsi, macd, macdh) to find reversal signals
            5. Synthesize all findings into a comprehensive technical analysis report

            **Key Principles:**
            - Regime detection should inform how to interpret other signals
            - Support/resistance levels provide precise entry/exit targets
            - Divergences are early warning signals but need confirmation
            - Always consider multiple timeframes and indicators together
            - Provide actionable trading recommendations with specific price levels

            Write a very detailed and nuanced report that:
            - Clearly identifies the current market regime and its implications
            - Lists all detected support and resistance levels with strength ratings
            - Reports any divergences found and their trading significance
            - Provides specific price targets and stop-loss levels
            - Explains how the regime affects indicator interpretation
            - Gives clear BUY/HOLD/SELL recommendations with reasoning

            **CRITICAL: You MUST provide a Technical Score between 1-10 as part of your structured output.**
            - Scoring guidelines:
              * 1-3: Strong bearish signals, multiple negative indicators, poor technical setup
              * 4-5: Weak bearish or neutral signals, mixed indicators, uncertain outlook
              * 6-7: Weak bullish or neutral signals, some positive indicators, moderate setup
              * 8-10: Strong bullish signals, multiple positive indicators, excellent technical setup
            - Base your score on: trend strength, momentum indicators, support/resistance positioning, divergence signals, and overall technical health

            Make sure to append a Markdown table at the end summarizing key findings.

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
                    "For your reference, the current date is {current_date}. The company we want to look at is {ticker}",
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
                structured_chain = prompt | llm.with_structured_output(TechnicalAnalysisOutput)
                structured_result = structured_chain.invoke(state["messages"])
                report = structured_result.report
                technical_score = structured_result.technical_score
                
                # Create a message from the structured result
                from langchain_core.messages import AIMessage
                result = AIMessage(content=report)
                
                return {
                    "messages": [result],
                    "technical_report": report,
                    "technical_score": technical_score,
                }
            except Exception:
                # Fallback to tool-based approach if structured output fails
                # This can happen if the LLM doesn't support structured output well
                pass
        
        # Default: use tools (for initial calls or if structured output failed)
        chain_with_tools = prompt | llm.bind_tools(tools)
        result = chain_with_tools.invoke(state["messages"])

        report = ""
        technical_score = None

        # If no tool calls in result, we might be at final response
        # Try structured output parsing
        if len(result.tool_calls) == 0:
            try:
                # Re-invoke with structured output to get parsed result
                structured_chain = prompt | llm.with_structured_output(TechnicalAnalysisOutput)
                structured_result = structured_chain.invoke(state["messages"])
                report = structured_result.report
                technical_score = structured_result.technical_score
                # Update result content with the report
                result.content = report
            except Exception:
                # Final fallback: use regular content (no score extraction)
                report = result.content if hasattr(result, 'content') else str(result)
                technical_score = None
       
        return {
            "messages": [result],
            "technical_report": report,
            "technical_score": technical_score,
        }

    return technical_analyst_node

