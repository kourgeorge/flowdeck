from langchain_core.messages import AIMessage
import time
import json

from ..analysts.helpers import _capture_usage
from ..utils.trace_utils import make_agent_step


def create_bear_researcher(llm, memory):
    def bear_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bear_history = investment_debate_state.get("bear_history", "")

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

        prompt = f"""You are a Bear Analyst making the case against investing in the stock. Your goal is to present a well-reasoned argument emphasizing risks, challenges, and negative indicators. Leverage the provided research and data to highlight potential downsides and counter bullish arguments effectively.

Key points to focus on:

- Risks and Challenges: Highlight factors like market saturation, financial instability, or macroeconomic threats that could hinder the stock's performance.
- Competitive Weaknesses: Emphasize vulnerabilities such as weaker market positioning, declining innovation, or threats from competitors.
- Negative Indicators: Use evidence from financial data, market trends, or recent adverse news to support your position.
- Bull Counterpoints: Critically analyze the bull argument with specific data and sound reasoning, exposing weaknesses or over-optimistic assumptions.
- Engagement: Present your argument in a conversational style, directly engaging with the bull analyst's points and debating effectively rather than simply listing facts.

Resources available:

Market research report: {market_research_report}
News & sentiment report: {sentiment_report}
Company fundamentals report: {fundamentals_report}
{f"Advanced technical analysis report: {technical_report}" if technical_report else ""}
{f"Deterministic event summary: {events_report}" if events_report else ""}
Conversation history of the debate: {history}
Last bull argument: {current_response}
Reflections from similar situations and lessons learned: {past_memory_str}
Use this information to deliver a compelling bear argument, refute the bull's claims, and engage in a dynamic debate that demonstrates the risks and weaknesses of investing in the stock. You must also address reflections and learn from lessons and mistakes you made in the past.
"""

        response = llm.invoke(prompt)
        
        # Track LLM usage
        usage_meta = _capture_usage(response, llm)

        argument = f"Bear Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bear_history": bear_history + "\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        out = {"investment_debate_state": new_investment_debate_state}
        if usage_meta:
            out["report_usage"] = {"bear_researcher": usage_meta}
        out["report_steps_by_report"] = {
            "investment_plan": [
                make_agent_step(
                    agent="Bear Researcher",
                    phase="investment_debate",
                    kind="debate_turn",
                    report_key="investment_plan",
                    round_number=investment_debate_state["count"] + 1,
                    status="completed",
                    summary="Bear Researcher added a debate turn",
                    message_preview=prompt,
                    output_preview=argument,
                    usage=usage_meta,
                )
            ]
        }
        return out

    return bear_node
