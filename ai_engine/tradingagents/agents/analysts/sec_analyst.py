"""SEC/Regulatory analyst: analyzes EDGAR filing content (risk factors, MD&A, competition) for trading context."""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field

from ..utils.edgar_tools import get_edgar_filing_content


class SecAnalysisOutput(BaseModel):
    """Structured output for SEC/regulatory analysis: report and score."""
    report: str = Field(
        description="Concise SEC/regulatory analysis report focused on management (MD&A), competition, and risk from EDGAR, with implications for traders."
    )
    sec_score: int = Field(
        ge=1, le=10,
        description="SEC/regulatory score 1-10. 1-3: higher regulatory/filing risk or disclosure concerns; 8-10: lower concern, cleaner disclosures."
    )


def create_sec_analyst(llm):
    def sec_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        tools = [get_edgar_filing_content]

        system_message = (
            "You are an SEC/regulatory analyst. Use the get_edgar_filing_content tool to retrieve SEC EDGAR content for the company. "
            "The content is already structured into: Risk Factors, Management's Discussion and Analysis (MD&A), and Competition. "
            "Write a concise report focused on **management (MD&A), competition, and risk** and their implications for traders. "
            "Do not simply state trends are mixed; provide specific insights from the filing. "
            "Append a short Markdown table summarizing key points. "
            "**CRITICAL: You MUST provide a sec_score between 1-10 in your structured output.** "
            "Scoring: 1-3 = higher regulatory/filing risk or material disclosure concerns; 4-5 = neutral; 6-7 = moderate; 8-10 = lower concern, clearer disclosures. "
            "Formatting: Use clear paragraphs, headings (## or ###), and avoid long unbroken blocks of text."
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants. Use the provided tools to progress. "
                    "You have access to: {tool_names}.\n{system_message} "
                    "Current date: {current_date}. Company: {ticker}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([t.name for t in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)

        from langchain_core.messages import ToolMessage
        last_message = state["messages"][-1] if state["messages"] else None
        is_after_tool_call = isinstance(last_message, ToolMessage) or (
            hasattr(last_message, "content")
            and isinstance(last_message.content, list)
            and any(isinstance(item, dict) and item.get("type") == "tool" for item in last_message.content)
        )

        if is_after_tool_call:
            try:
                structured_chain = prompt | llm.with_structured_output(SecAnalysisOutput)
                structured_result = structured_chain.invoke(state["messages"])
                report = structured_result.report
                sec_score = structured_result.sec_score
                from langchain_core.messages import AIMessage
                result = AIMessage(content=report)
                return {
                    "messages": [result],
                    "sec_report": report,
                    "sec_score": sec_score,
                }
            except Exception:
                pass

        chain_with_tools = prompt | llm.bind_tools(tools)
        result = chain_with_tools.invoke(state["messages"])

        report = ""
        sec_score = None

        if len(result.tool_calls) == 0:
            try:
                structured_chain = prompt | llm.with_structured_output(SecAnalysisOutput)
                structured_result = structured_chain.invoke(state["messages"])
                report = structured_result.report
                sec_score = structured_result.sec_score
                result.content = report
            except Exception:
                report = result.content if hasattr(result, "content") else str(result)
                sec_score = None

        return {
            "messages": [result],
            "sec_report": report,
            "sec_score": sec_score,
        }

    return sec_analyst_node
