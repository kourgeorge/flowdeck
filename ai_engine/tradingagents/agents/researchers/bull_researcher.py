from langchain_core.messages import AIMessage
import time
import json

from ..analysts.helpers import _capture_usage
from ..utils.trace_utils import make_agent_step


def create_bull_researcher(llm, memory):
    def bull_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")

        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        technical_report = state.get("technical_report", "")
        events_report = state.get("events_report", "")

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        if technical_report:
            curr_situation += f"\n\n{technical_report}"
        if events_report:
            curr_situation += f"\n\n{events_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""You are a Bull Analyst advocating for investing in the stock. Your task is to build a strong, evidence-based case emphasizing growth potential, competitive advantages, and positive market indicators. Leverage the provided research and data to address concerns and counter bearish arguments effectively.

Key points to focus on:
- Growth Potential: Highlight the company's market opportunities, revenue projections, and scalability.
- Competitive Advantages: Emphasize factors like unique products, strong branding, or dominant market positioning.
- Positive Indicators: Use financial health, industry trends, and recent positive news as evidence.
- Bear Counterpoints: Critically analyze the bear argument with specific data and sound reasoning, addressing concerns thoroughly and showing why the bull perspective holds stronger merit.
- Engagement: Present your argument in a conversational style, engaging directly with the bear analyst's points and debating effectively rather than just listing data.

Resources available:
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
Company fundamentals report: {fundamentals_report}
{f"Advanced technical analysis report: {technical_report}" if technical_report else ""}
{f"Deterministic event summary: {events_report}" if events_report else ""}
Conversation history of the debate: {history}
Last bear argument: {current_response}
Reflections from similar situations and lessons learned: {past_memory_str}
Use this information to deliver a compelling bull argument, refute the bear's concerns, and engage in a dynamic debate that demonstrates the strengths of the bull position. You must also address reflections and learn from lessons and mistakes you made in the past.
"""

        response = llm.invoke(prompt)
        
        # Track LLM usage
        usage_meta = _capture_usage(response, llm)

        argument = f"Bull Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": bull_history + "\n" + argument,
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        out = {"investment_debate_state": new_investment_debate_state}
        if usage_meta:
            out["report_usage"] = {"bull_researcher": usage_meta}
        out["report_steps_by_report"] = {
            "investment_plan": [
                make_agent_step(
                    agent="Bull Researcher",
                    phase="investment_debate",
                    kind="debate_turn",
                    report_key="investment_plan",
                    round_number=investment_debate_state["count"] + 1,
                    status="completed",
                    summary="Bull Researcher added a debate turn",
                    message_preview=prompt,
                    output_preview=argument,
                    usage=usage_meta,
                )
            ]
        }
        return out

    return bull_node
