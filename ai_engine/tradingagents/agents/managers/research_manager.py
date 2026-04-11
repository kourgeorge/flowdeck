from typing import Optional, List
from pydantic import BaseModel, Field

from ..analysts.helpers import _UsageCaptureCallback, _capture_usage
from ..utils.trace_utils import make_agent_step


class ResearchManagerOutput(BaseModel):
    """Structured output for research manager: strategy narrative, directional score, and return expectations."""
    investment_plan: str = Field(
        description="Comprehensive investment plan with directional thesis, rationale, and strategic actions for the Trader"
    )
    recommendation_score: int = Field(
        ge=1, le=10,
        description="Directional conviction score from 1-10. 1-3: Very weak/low conviction, 4-5: Moderate conviction, 6-7: Strong conviction, 8-10: Very strong conviction"
    )
    bull_summary: List[str] = Field(
        default_factory=list,
        description="3-5 bullet points summarizing the bull analyst's key arguments from the debate"
    )
    bear_summary: List[str] = Field(
        default_factory=list,
        description="3-5 bullet points summarizing the bear analyst's key arguments from the debate"
    )
    expected_return_pct: Optional[float] = Field(
        default=None,
        description="Expected percentage return from current price over the investment horizon (e.g. 0.64 for +0.64%). Base case."
    )
    bear_case_return_pct: Optional[float] = Field(
        default=None,
        description="Bear-case percentage return from current price (e.g. -12.87 for -12.87%). Downside scenario."
    )
    bull_case_return_pct: Optional[float] = Field(
        default=None,
        description="Bull-case percentage return from current price (e.g. 9.41 for +9.41%). Upside scenario."
    )
    key_takeaways: List[str] = Field(
        default_factory=list,
        description="3-5 one-sentence takeaways for traders from this investment plan and debate resolution.",
    )


def create_research_manager(llm, memory):
    def research_manager_node(state) -> dict:
        history = state["investment_debate_state"].get("history", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        sec_report = state.get("sec_report", "")
        technical_report = state.get("technical_report", "")
        valuation_report = state.get("valuation_report", "")
        events_report = state.get("events_report", "")

        investment_debate_state = state["investment_debate_state"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        if sec_report:
            curr_situation += f"\n\n{sec_report}"
        if technical_report:
            curr_situation += f"\n\n{technical_report}"
        if valuation_report:
            curr_situation += f"\n\n{valuation_report}"
        if events_report:
            curr_situation += f"\n\n{events_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""As the portfolio manager and debate facilitator, your role is to critically evaluate this round of debate and make an honest directional call: align with the bear analyst (bearish/sell), the bull analyst (bullish/buy), or recommend a hold stance when the evidence is genuinely mixed, uncertain, or when the risk/reward does not clearly favor action.

Summarize the key points from both sides concisely, focusing on the most compelling evidence or reasoning. Your directional stance must be clear and actionable for the Trader. Avoid defaulting to hold-bias simply because both sides have valid points; commit to a stance grounded in the debate's strongest arguments. That said, a HOLD is the right call when signals are genuinely conflicting, conviction is low, or the risk/reward does not clearly favor entering or exiting a position.

Additionally, develop a detailed investment plan for the trader. This should include:

Directional Stance: A clear thesis (bullish, bearish, or hold/neutral) supported by the most convincing arguments.
Rationale: An explanation of why these arguments lead to your conclusion.
Strategic Actions: Concrete steps the Trader can use to implement the plan (including waiting/monitoring if the stance is hold).
Take into account your past mistakes on similar situations. Use these insights to refine your decision-making and ensure you are learning and improving. Present your analysis conversationally, as if speaking naturally.

**Formatting:** Structure the investment plan for readability: use clear paragraphs and subparagraphs, Markdown tables for key data or comparisons (e.g. bull vs bear points, return scenarios), and headings (## or ###) to organize sections. Avoid long unbroken blocks of text so the output is well organized and easy to scan. 

**CRITICAL: You MUST provide a Conviction Score between 1-10 as part of your structured output. This score measures how strongly and clearly the directional thesis (bullish, bearish, or hold) is supported by the debate — it is NOT a quality rating of the recommendation, but a measure of directional conviction.**
- Scoring guidelines:
  * 1-3: Very weak directional conviction, highly mixed signals, unclear direction
  * 4-5: Moderate directional conviction, balanced arguments, moderate clarity
  * 6-7: Strong directional conviction, clear signals, well-supported thesis
  * 8-10: Very strong directional conviction, very clear signals, strongly supported thesis
- Base your score on: clarity of signals, strength of arguments, confidence in directional stance, alignment of evidence, and overall conviction

**CRITICAL: You MUST provide bull_summary and bear_summary as lists of 3-5 bullet points each:**
- bull_summary: Summarize the bull analyst's key arguments in a short list (each item one sentence).
- bear_summary: Summarize the bear analyst's key arguments in a short list (each item one sentence).

**CRITICAL: You MUST provide numerical return expectations as percentages from current price (e.g. over a 12-month horizon):**
- expected_return_pct: Base-case expected percentage return (e.g. 0.64 for +0.64%).
- bear_case_return_pct: Downside scenario percentage return (e.g. -12.87 for -12.87%).
- bull_case_return_pct: Upside scenario percentage return (e.g. 9.41 for +9.41%).
Use the debate, analyst reports (especially the Valuation Analyst's fair value scenarios if available), and your view to estimate these three numbers. They must be numeric (can be negative for bear). If the Valuation Analyst has provided bear/base/bull fair values, use those as the foundation for calculating return percentages.

**CRITICAL: You MUST provide key_takeaways as a list of 3-5 one-sentence trader-facing takeaways summarizing the plan and thesis.**

Here are your past reflections on mistakes:
\"{past_memory_str}\"

Deterministic event context:
{events_report if events_report else "No deterministic event summary available."}

Here is the debate:
Debate History:
{history}"""
        
        # Use structured output to get both investment plan, score, and return expectations
        expected_return_pct = None
        bear_case_return_pct = None
        bull_case_return_pct = None
        usage_meta = None
        usage_cb = _UsageCaptureCallback()
        try:
            structured_llm = llm.with_structured_output(ResearchManagerOutput)
            structured_response = structured_llm.invoke(
                prompt, config={"callbacks": [usage_cb]}
            )
            investment_plan = structured_response.investment_plan
            if usage_cb.last_message is not None:
                usage_meta = _capture_usage(usage_cb.last_message, llm)
            recommendation_score = structured_response.recommendation_score
            bull_summary = getattr(structured_response, "bull_summary", None) or []
            bear_summary = getattr(structured_response, "bear_summary", None) or []
            expected_return_pct = getattr(structured_response, "expected_return_pct", None)
            bear_case_return_pct = getattr(structured_response, "bear_case_return_pct", None)
            bull_case_return_pct = getattr(structured_response, "bull_case_return_pct", None)
            plan_key_takeaways = list(
                getattr(structured_response, "key_takeaways", None) or []
            )[:5]
            plan_key_takeaways = [str(t).strip() for t in plan_key_takeaways if str(t).strip()]

            # Create a regular response object for compatibility
            class Response:
                def __init__(self, content):
                    self.content = content
            response = Response(investment_plan)
        except Exception:
            response = llm.invoke(prompt)
            investment_plan = response.content
            usage_meta = _capture_usage(response, llm)
            recommendation_score = None
            bull_summary = []
            bear_summary = []
            plan_key_takeaways = []

        new_investment_debate_state = {
            "judge_decision": investment_plan,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": investment_plan,
            "count": investment_debate_state["count"],
        }

        out = {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": investment_plan,
            "investment_plan_key_takeaways": plan_key_takeaways,
            "recommendation_score": recommendation_score,
            "bull_summary": bull_summary,
            "bear_summary": bear_summary,
            "expected_return_pct": expected_return_pct,
            "bear_case_return_pct": bear_case_return_pct,
            "bull_case_return_pct": bull_case_return_pct,
            "report_steps_by_report": {
                "investment_plan": [
                    make_agent_step(
                        agent="Research Manager",
                        phase="investment_decision",
                        kind="report_synthesis",
                        report_key="investment_plan",
                        status="completed" if recommendation_score is not None else "fallback",
                        summary="Research Manager synthesized the analyst debate into the investment plan",
                        output_preview=investment_plan,
                        usage=usage_meta,
                        extra={
                            "recommendation_score": recommendation_score,
                            "bull_summary": bull_summary,
                            "bear_summary": bear_summary,
                            "key_takeaways": plan_key_takeaways,
                            "expected_return_pct": expected_return_pct,
                            "bear_case_return_pct": bear_case_return_pct,
                            "bull_case_return_pct": bull_case_return_pct,
                        },
                    )
                ]
            },
        }
        if usage_meta:
            out["report_usage"] = {"investment_plan": usage_meta}
        return out

    return research_manager_node
