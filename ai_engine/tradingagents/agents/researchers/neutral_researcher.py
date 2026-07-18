from langchain_core.messages import AIMessage
import time
import json

from ..analysts.helpers import _capture_usage
from ..utils.trace_utils import make_agent_step


def create_neutral_researcher(llm, memory):
    def neutral_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        neutral_history = investment_debate_state.get("neutral_history", "")

        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        fundamentals_report = state["fundamentals_report"]
        technical_report = state.get("technical_report", "")
        events_report = state.get("events_report", "")

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{fundamentals_report}"
        if technical_report:
            curr_situation += f"\n\n{technical_report}"
        if events_report:
            curr_situation += f"\n\n{events_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""You are a Neutral Analyst providing a balanced, moderate perspective in the debate over investing in the stock. Your role is to weigh both the bull and bear arguments critically, pointing out where each side may be overly optimistic or overly pessimistic, and to advocate for a well-rounded, sustainable view.

Key points to focus on:
- Balance: Weigh the strongest growth arguments against the most credible risks; avoid anchoring to either extreme.
- Critique both sides: Show where the bull case may be over-optimistic and where the bear case may be overly cautious, using specific data.
- Broader context: Factor in market trends, macroeconomic conditions, valuation, and uncertainty when the evidence is genuinely mixed.
- Engagement: Present your argument conversationally, directly engaging with the bull and bear analysts' points rather than just listing data.

Resources available:
Market research report: {market_research_report}
News & sentiment report: {sentiment_report}
Company fundamentals report: {fundamentals_report}
{f"Advanced technical analysis report: {technical_report}" if technical_report else ""}
{f"Deterministic event summary: {events_report}" if events_report else ""}
Conversation history of the debate: {history}
Last argument in the debate: {current_response}
Reflections from similar situations and lessons learned: {past_memory_str}
Use this information to deliver a balanced perspective, challenge the weaknesses in both the bull and bear positions, and argue for the most reliable, moderate reading of the evidence. If there are no responses from the other viewpoints yet, do not hallucinate and just present your balanced point. You must also address reflections and learn from lessons and mistakes you made in the past.
"""

        response = llm.invoke(prompt)

        # Track LLM usage
        usage_meta = _capture_usage(response, llm)

        argument = f"Neutral Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "latest_speaker": "Neutral",
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        out = {"investment_debate_state": new_investment_debate_state}
        if usage_meta:
            out["report_usage"] = {"neutral_researcher": usage_meta}
        out["report_steps_by_report"] = {
            "investment_plan": [
                make_agent_step(
                    agent="Neutral Researcher",
                    phase="investment_debate",
                    kind="debate_turn",
                    report_key="investment_plan",
                    round_number=investment_debate_state["count"] + 1,
                    status="completed",
                    summary="Neutral Researcher added a debate turn",
                    message_preview=prompt,
                    output_preview=argument,
                    usage=usage_meta,
                )
            ]
        }
        return out

    return neutral_node
