from typing import Literal, List
from pydantic import BaseModel, Field


class RiskManagerOutput(BaseModel):
    """Structured output for risk manager: decision text, recommendation enum, risk score, key takeaways, analyst summaries."""

    final_trade_decision: str = Field(
        description="Final trade decision including detailed reasoning and refined trader plan (narrative)."
    )
    recommendation: Literal["BUY", "SELL", "HOLD"] = Field(
        description="Clear actionable recommendation: BUY, SELL, or HOLD."
    )
    risk_score: int = Field(
        ge=1,
        le=10,
        description="Risk score from 1-10 indicating confidence in the decision. 1-3: Very weak, 4-5: Moderate, 6-7: Strong, 8-10: Very strong.",
    )
    key_takeaways: list[str] = Field(
        max_length=5,
        default_factory=list,
        description="Three to five concise one-sentence takeaways for traders from this decision (or empty if not applicable).",
    )
    risky_summary: List[str] = Field(
        default_factory=list,
        description="3-5 bullet points summarizing the risky analyst's key arguments from the debate",
    )
    safe_summary: List[str] = Field(
        default_factory=list,
        description="3-5 bullet points summarizing the safe/conservative analyst's key arguments from the debate",
    )
    neutral_summary: List[str] = Field(
        default_factory=list,
        description="3-5 bullet points summarizing the neutral analyst's key arguments from the debate",
    )


def create_risk_manager(llm, memory):
    def risk_manager_node(state) -> dict:

        company_name = state["company_of_interest"]

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        sentiment_report = state["sentiment_report"]
        sec_report = state.get("sec_report") or ""
        trader_plan = state["investment_plan"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        if sec_report:
            curr_situation += f"\n\n{sec_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""As the Risk Management Judge and Debate Facilitator, your goal is to evaluate the debate between three risk analysts—Risky, Neutral, and Safe/Conservative—and determine the best course of action for the trader. Your decision must result in a clear recommendation: Buy, Sell, or Hold. Choose Hold only if strongly justified by specific arguments, not as a fallback when all sides seem valid. Strive for clarity and decisiveness.

Guidelines for Decision-Making:
1. **Context**: The situation may include an SEC/regulatory report (management discussion, competition, risk factors from EDGAR). Factor regulatory and disclosure risk into your final decision when that report is present.
2. **Summarize Key Arguments**: Extract the strongest points from each analyst, focusing on relevance to the context.
3. **Provide Rationale**: Support your recommendation with direct quotes and counterarguments from the debate.
4. **Refine the Trader's Plan**: Start with the trader's original plan, **{trader_plan}**, and adjust it based on the analysts' insights.
5. **Learn from Past Mistakes**: Use lessons from **{past_memory_str}** to address prior misjudgments and improve the decision you are making now to make sure you don't make a wrong BUY/SELL/HOLD call that loses money.

Deliverables:
- recommendation: Exactly one of BUY, SELL, or HOLD (use these exact strings in your structured output).
- final_trade_decision: Detailed reasoning and refined plan (narrative text).
- risk_score: An integer 1-10.
- key_takeaways: A list of 3-5 short one-sentence takeaways for traders.

**Formatting:** Structure the final_trade_decision for readability: use clear paragraphs and subparagraphs, Markdown tables where helpful (e.g. summarizing analyst positions or risk factors), and headings (## or ###) to organize sections. Avoid long unbroken blocks of text so the output is well organized and easy to scan.

**CRITICAL: You MUST provide risky_summary, safe_summary, and neutral_summary as lists of 3-5 bullet points each:**
- risky_summary: Summarize the risky analyst's key arguments in a short list (each item one sentence).
- safe_summary: Summarize the safe/conservative analyst's key arguments in a short list (each item one sentence).
- neutral_summary: Summarize the neutral analyst's key arguments in a short list (each item one sentence).

**CRITICAL: You MUST provide recommendation (BUY/SELL/HOLD), risk_score (1-10), and key_takeaways (3-5 items) in your structured output.**
- Scoring guidelines:
  * 1-3: Very weak decision, low confidence, highly uncertain risk assessment, unclear direction
  * 4-5: Moderate decision, some confidence, balanced risk assessment, moderate clarity
  * 6-7: Strong decision, good confidence, clear risk assessment, well-supported decision
  * 8-10: Very strong decision, high confidence, very clear risk assessment, strongly supported decision
- Base your score on: clarity of risk signals, strength of risk arguments, confidence in decision, alignment of risk evidence, and overall conviction in risk management

---

**Analysts Debate History:**  
{history}

---

Focus on actionable insights and continuous improvement. Build on past lessons, critically evaluate all perspectives, and ensure each decision advances better outcomes."""

        # Use structured output for final_trade_decision, recommendation, risk_score, key_takeaways, analyst summaries
        recommendation = None
        key_takeaways = []
        risky_summary = []
        safe_summary = []
        neutral_summary = []
        try:
            structured_llm = llm.with_structured_output(RiskManagerOutput)
            structured_response = structured_llm.invoke(prompt)
            final_trade_decision = structured_response.final_trade_decision
            risk_score = structured_response.risk_score
            recommendation = getattr(structured_response, "recommendation", None)
            key_takeaways = list(getattr(structured_response, "key_takeaways", []) or [])[:5]
            risky_summary = list(getattr(structured_response, "risky_summary", []) or [])
            safe_summary = list(getattr(structured_response, "safe_summary", []) or [])
            neutral_summary = list(getattr(structured_response, "neutral_summary", []) or [])
            class Response:
                def __init__(self, content):
                    self.content = content
            response = Response(final_trade_decision)
        except Exception:
            response = llm.invoke(prompt)
            final_trade_decision = response.content
            risk_score = None

        new_risk_debate_state = {
            "judge_decision": final_trade_decision,
            "history": risk_debate_state["history"],
            "risky_history": risk_debate_state["risky_history"],
            "safe_history": risk_debate_state["safe_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_risky_response": risk_debate_state["current_risky_response"],
            "current_safe_response": risk_debate_state["current_safe_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": final_trade_decision,
            "risk_score": risk_score,
            "recommendation": recommendation,
            "final_report_key_takeaways": key_takeaways,
            "risky_summary": risky_summary,
            "safe_summary": safe_summary,
            "neutral_summary": neutral_summary,
        }

    return risk_manager_node
