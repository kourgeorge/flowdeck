import functools
from typing import Literal
from langchain_core.messages import AIMessage, BaseMessage
from pydantic import BaseModel, Field


class TraderOutput(BaseModel):
    """Structured output for trader: narrative plan + explicit recommendation."""

    trader_investment_plan: str = Field(
        description="Detailed trader decision narrative with rationale and execution considerations."
    )
    recommendation: Literal["BUY", "SELL", "HOLD"] = Field(
        description="Clear actionable recommendation: BUY, SELL, or HOLD."
    )


def create_trader(llm, memory):
    def trader_node(state, name):
        company_name = state["company_of_interest"]
        investment_plan = state["investment_plan"]
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        if past_memories:
            for i, rec in enumerate(past_memories, 1):
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            past_memory_str = "No past memories found."

        context = {
            "role": "user",
            "content": f"Based on a comprehensive analysis by a team of analysts, here is an investment plan tailored for {company_name}. This plan incorporates insights from current technical market trends, macroeconomic indicators, and social media sentiment. Use this plan as a foundation for evaluating your next trading decision.\n\nProposed Investment Plan: {investment_plan}\n\nLeverage these insights to make an informed and strategic decision.",
        }

        messages = [
            {
                "role": "system",
                "content": f"""You are a trading agent analyzing market data to make investment decisions. Based on your analysis, provide a specific recommendation to buy, sell, or hold. In your structured output, provide both:
1) trader_investment_plan: a detailed narrative decision with reasoning and execution notes.
2) recommendation: exactly one of BUY, SELL, or HOLD.
Do not forget to utilize lessons from past decisions to learn from your mistakes. Here is some reflections from similar situatiosn you traded in and the lessons learned: {past_memory_str}""",
            },
            context,
        ]

        recommendation = None
        try:
            structured_llm = llm.with_structured_output(TraderOutput)
            structured_response = structured_llm.invoke(messages)
            trader_investment_plan = structured_response.trader_investment_plan
            recommendation = getattr(structured_response, "recommendation", None)
            result_message = AIMessage(content=trader_investment_plan)
        except Exception:
            raw_result = llm.invoke(messages)
            trader_investment_plan = (
                raw_result.content
                if hasattr(raw_result, "content")
                else str(raw_result)
            )
            result_message = (
                raw_result
                if isinstance(raw_result, BaseMessage)
                else AIMessage(content=trader_investment_plan)
            )

        return {
            "messages": [result_message],
            "trader_investment_plan": trader_investment_plan,
            "trader_recommendation": recommendation,
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")
