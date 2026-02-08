from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field
from tradingagents.agents.utils.agent_utils import get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement


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

        system_message = (
            "You are a researcher tasked with analyzing fundamental information over the past week about a company. Please write a comprehensive report of the company's fundamental information such as financial documents, company profile, basic company financials, and company financial history to gain a full view of the company's fundamental information to inform traders. Make sure to include as much detail as possible. Do not simply state the trends are mixed, provide detailed and finegrained analysis and insights that may help traders make decisions."
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + " Use the available tools: `get_fundamentals` for comprehensive company analysis, `get_balance_sheet`, `get_cashflow`, and `get_income_statement` for specific financial statements."
            + """ **CRITICAL: You MUST provide a Fundamentals Score between 1-10 as part of your structured output.**
            - Scoring guidelines:
              * 1-3: Very weak fundamentals, poor financial health, declining metrics, significant concerns with balance sheet/cash flow/profitability, weak growth prospects
              * 4-5: Neutral or mixed fundamentals, average financial health, stable but not exceptional metrics, some concerns balanced with positive aspects
              * 6-7: Moderately strong fundamentals, good financial health, positive trends in key metrics, solid balance sheet and cash flow, decent growth prospects
              * 8-10: Very strong fundamentals, excellent financial health, strong and improving metrics across all areas, robust balance sheet and cash flow, exceptional growth prospects
            - Base your score on: balance sheet strength, cash flow quality, profitability trends, revenue growth, debt levels, financial stability, competitive positioning, and overall fundamental health

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
                structured_chain = prompt | llm.with_structured_output(FundamentalsAnalysisOutput)
                structured_result = structured_chain.invoke(state["messages"])
                report = structured_result.report
                fundamentals_score = structured_result.fundamentals_score
                
                # Create a message from the structured result
                from langchain_core.messages import AIMessage
                result = AIMessage(content=report)
                
                return {
                    "messages": [result],
                    "fundamentals_report": report,
                    "fundamentals_score": fundamentals_score,
                }
            except Exception:
                # Fallback to tool-based approach if structured output fails
                pass
        
        # Default: use tools (for initial calls or if structured output failed)
        chain_with_tools = prompt | llm.bind_tools(tools)
        result = chain_with_tools.invoke(state["messages"])

        report = ""
        fundamentals_score = None

        # If no tool calls in result, we might be at final response
        # Try structured output parsing
        if len(result.tool_calls) == 0:
            try:
                # Re-invoke with structured output to get parsed result
                structured_chain = prompt | llm.with_structured_output(FundamentalsAnalysisOutput)
                structured_result = structured_chain.invoke(state["messages"])
                report = structured_result.report
                fundamentals_score = structured_result.fundamentals_score
                # Update result content with the report
                result.content = report
            except Exception:
                # Final fallback: use regular content (no score extraction)
                report = result.content if hasattr(result, 'content') else str(result)
                fundamentals_score = None

        return {
            "messages": [result],
            "fundamentals_report": report,
            "fundamentals_score": fundamentals_score,
        }

    return fundamentals_analyst_node
