import time
import json

from ..analysts.helpers import _capture_usage
from ..utils.trace_utils import make_agent_step


def create_neutral_debator(llm):
    def neutral_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_risky_response = risk_debate_state.get("current_risky_response", "")
        current_safe_response = risk_debate_state.get("current_safe_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        fundamentals_report = state["fundamentals_report"]
        sec_report = state.get("sec_report", "")
        technical_report = state.get("technical_report", "")
        events_report = state.get("events_report", "")

        trader_decision = state["trader_investment_plan"]

        prompt = f"""As the Neutral Risk Analyst, your role is to provide a balanced perspective, weighing both the potential benefits and risks of the trader's decision or plan. You prioritize a well-rounded approach, evaluating the upsides and downsides while factoring in broader market trends, potential economic shifts, and diversification strategies.Here is the trader's decision:

{trader_decision}

Your task is to challenge both the Risky and Safe Analysts, pointing out where each perspective may be overly optimistic or overly cautious. Use insights from the following data sources to support a moderate, sustainable strategy to adjust the trader's decision:

Market Research Report: {market_research_report}
News & Sentiment Report: {sentiment_report}
Company Fundamentals Report: {fundamentals_report}
SEC / Regulatory Report: {sec_report if sec_report else "Not available"}
Advanced Technical Report: {technical_report if technical_report else "Not available"}
Deterministic Event Summary: {events_report if events_report else "Not available"}
Here is the current conversation history: {history} Here is the last response from the risky analyst: {current_risky_response} Here is the last response from the safe analyst: {current_safe_response}. If there are no responses from the other viewpoints, do not halluncinate and just present your point.

Engage actively by analyzing both sides critically, addressing weaknesses in the risky and conservative arguments to advocate for a more balanced approach. Challenge each of their points to illustrate why a moderate risk strategy might offer the best of both worlds, providing growth potential while safeguarding against extreme volatility. Focus on debating rather than simply presenting data, aiming to show that a balanced view can lead to the most reliable outcomes. Output conversationally as if you are speaking without any special formatting."""

        response = llm.invoke(prompt)
        
        # Track LLM usage
        usage_meta = _capture_usage(response, llm)

        argument = f"Neutral Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "risky_history": risk_debate_state.get("risky_history", ""),
            "safe_history": risk_debate_state.get("safe_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "latest_speaker": "Neutral",
            "current_risky_response": risk_debate_state.get(
                "current_risky_response", ""
            ),
            "current_safe_response": risk_debate_state.get("current_safe_response", ""),
            "current_neutral_response": argument,
            "count": risk_debate_state["count"] + 1,
        }

        out = {"risk_debate_state": new_risk_debate_state}
        if usage_meta:
            out["report_usage"] = {"neutral_debator": usage_meta}
        out["report_steps_by_report"] = {
            "final_trade_decision": [
                make_agent_step(
                    agent="Neutral Analyst",
                    phase="risk_debate",
                    kind="debate_turn",
                    report_key="final_trade_decision",
                    round_number=risk_debate_state["count"] + 1,
                    status="completed",
                    summary="Neutral Analyst added a debate turn",
                    message_preview=prompt,
                    output_preview=argument,
                    usage=usage_meta,
                )
            ]
        }
        return out

    return neutral_node
