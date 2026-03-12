from typing import List, Literal
from statistics import pstdev
from pydantic import BaseModel, Field

from ..analysts.helpers import _UsageCaptureCallback, _capture_usage


class RiskManagerOutput(BaseModel):
    """Structured output for risk manager: risk analysis text, risk score, recommendation, key takeaways, analyst summaries."""

    final_trade_decision: str = Field(
        description="Final risk analysis including detailed reasoning and refined trader plan (narrative)."
    )
    recommendation: Literal["BUY", "SELL", "HOLD"] = Field(
        description="Final trade recommendation after risk analysis: BUY, SELL, or HOLD. Can agree with or override the trader's initial recommendation based on risk assessment."
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
        trader_recommendation = state.get("trader_recommendation", "HOLD")
        score_candidates = {
            "market_score": state.get("market_score"),
            "sentiment_score": state.get("sentiment_score"),
            "news_score": state.get("news_score"),
            "fundamentals_score": state.get("fundamentals_score"),
            "sec_score": state.get("sec_score"),
            "technical_score": state.get("technical_score"),
            "recommendation_score": state.get("recommendation_score"),
        }
        available_scores = {
            k: float(v)
            for k, v in score_candidates.items()
            if isinstance(v, (int, float))
        }
        score_values = list(available_scores.values())
        avg_score = round(sum(score_values) / len(score_values), 2) if score_values else None
        score_std = (
            round(pstdev(score_values), 2)
            if len(score_values) > 1
            else (0.0 if len(score_values) == 1 else None)
        )
        score_context_lines = (
            "\n".join([f"- {k}: {v:.2f}" for k, v in available_scores.items()])
            if available_scores
            else "- No upstream aspect scores are available for this run."
        )

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        if sec_report:
            curr_situation += f"\n\n{sec_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""As the Risk Management Judge and Debate Facilitator, your goal is to evaluate the debate between three risk analysts—Risky, Neutral, and Safe/Conservative—and produce a clear risk analysis for the trader's plan. Focus on risk quality, vulnerabilities, and practical risk controls.

**Trader's Initial Recommendation:** {trader_recommendation}

Guidelines for Decision-Making:
1. **Context**: The situation may include an SEC/regulatory report (management discussion, competition, risk factors from EDGAR). Factor regulatory and disclosure risk into your final decision when that report is present.
2. **Summarize Key Arguments**: Extract the strongest points from each analyst, focusing on relevance to the context.
3. **Provide Rationale**: Support your analysis with direct quotes and counterarguments from the debate.
4. **Refine the Trader's Plan**: Start with the trader's original plan, **{trader_plan}**, and adjust it based on the analysts' insights.
5. **Learn from Past Mistakes**: Use lessons from **{past_memory_str}** to address prior misjudgments and improve the risk assessment.
6. **Use Quantitative Score Context**: You must incorporate all available upstream report scores and their statistics when deciding the final risk_score.
7. **Output Final Recommendation**: Based on your risk analysis, output a final recommendation (BUY, SELL, or HOLD). You can agree with the trader's recommendation or override it based on risk assessment. For example:
   - If trader says BUY but risk is very high (risk_score < 5), consider downgrading to HOLD
   - If trader says SELL but risk analysis shows opportunity is strong (risk_score > 7), consider upgrading to HOLD or BUY
   - If risk assessment aligns with trader's view, confirm their recommendation

Deliverables:
- final_trade_decision: Detailed risk analysis and refined plan (narrative text).
- recommendation: Final trade recommendation (BUY, SELL, or HOLD) after considering risk analysis.
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
- Quantitative calibration rules:
  * Consider every available score in this run: market, sentiment, news, fundamentals, SEC, technical, and recommendation.
  * Use the average score as your baseline anchor for risk_score.
  * Use score dispersion (standard deviation) as confidence penalty/boost:
    - std <= 1.0: signals are consistent; confidence can be stronger if debate evidence agrees.
    - 1.0 < std <= 2.0: mixed consistency; keep confidence moderate unless evidence is decisive.
    - std > 2.0: conflicting signals; avoid very high confidence unless you clearly justify why one side dominates.
  * Keep risk_score as an integer from 1-10, and align it with both quantitative context and debate quality.

**Quantitative Score Context (precomputed):**
{score_context_lines}
- score_average: {avg_score if avg_score is not None else "N/A"}
- score_std_dev: {score_std if score_std is not None else "N/A"}

---

**Analysts Debate History:**  
{history}

---

Focus on actionable insights and continuous improvement. Build on past lessons, critically evaluate all perspectives, and ensure each decision advances better outcomes."""

        # Use structured output for final_trade_decision, recommendation, risk_score, key_takeaways, analyst summaries
        key_takeaways = []
        risky_summary = []
        safe_summary = []
        neutral_summary = []
        recommendation = None
        usage_meta = None
        usage_cb = _UsageCaptureCallback()
        try:
            structured_llm = llm.with_structured_output(RiskManagerOutput)
            structured_response = structured_llm.invoke(
                prompt, config={"callbacks": [usage_cb]}
            )
            final_trade_decision = structured_response.final_trade_decision
            if usage_cb.last_message is not None:
                usage_meta = _capture_usage(usage_cb.last_message, llm)
            recommendation = structured_response.recommendation
            risk_score = structured_response.risk_score
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
            usage_meta = _capture_usage(response, llm)
            final_trade_decision = response.content
            recommendation = None
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

        out = {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": final_trade_decision,
            "recommendation": recommendation,
            "risk_score": risk_score,
            "final_report_key_takeaways": key_takeaways,
            "risky_summary": risky_summary,
            "safe_summary": safe_summary,
            "neutral_summary": neutral_summary,
        }
        if usage_meta:
            out["report_usage"] = {"final_trade_decision": usage_meta}
        return out

    return risk_manager_node
