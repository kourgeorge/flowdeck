import functools
import json
from pathlib import Path
from typing import List, Literal, Optional, Union
from langchain_core.messages import AIMessage, BaseMessage
from pydantic import BaseModel, Field

from ..analysts.helpers import _UsageCaptureCallback, _capture_usage


# ---------------------------------------------------------------------------
# Pydantic models mirroring TPS-YAML v0.1 JSON Schema exactly
# ---------------------------------------------------------------------------

class TpsEntry(BaseModel):
    """entry block — required: near; optional: scale, confirm."""
    near: Union[float, str] = Field(
        description="Entry trigger: a positive price number (e.g. 607.99) or a price-band string (e.g. '607.99 ±1%')."
    )
    scale: Optional[str] = Field(
        default=None,
        description="Tranche allocation as '100' or '40/30/30' (percent-of-intended position per tranche)."
    )
    confirm: Optional[List[str]] = Field(
        default=None,
        description="List of confirmation conditions; all must evaluate true to allow entry."
    )


class TpsRisk(BaseModel):
    """risk block — required: max_loss, stop; optional: max_position, invalidate."""
    max_loss: str = Field(
        description="Maximum allowed portfolio loss for the trade, e.g. '1%' or '2.5%'."
    )
    stop: float = Field(
        description="Hard stop-loss price level. Exit immediately when breached."
    )
    max_position: Optional[str] = Field(
        default=None,
        description="Maximum exposure allowed for this instrument, e.g. '5%'."
    )
    invalidate: Optional[str] = Field(
        default=None,
        description="Persistence-based exit rule, e.g. 'close < 595.83 for 2d -> exit'."
    )


class TpsTakeProfit(BaseModel):
    """take_profit block — all optional."""
    tp1: Optional[str] = Field(
        default=None,
        description="First target and partial reduction rule, e.g. '640.64 sell 50%'."
    )
    trail: Optional[str] = Field(
        default=None,
        description="Trailing stop distance applied to remaining position, e.g. '4%'."
    )


class TpsPlan(BaseModel):
    """
    TPS-YAML v0.1 trade plan instance.
    Mirrors the JSON Schema at backend/TPS/TPS-YAML-v0.1.schema-1.json exactly.
    """
    instrument: str = Field(description="Ticker symbol, e.g. 'META'.")
    timeframe: str = Field(description="Candle resolution, e.g. '1D', '4H', '15m'.")
    side: Literal["long", "short"] = Field(description="Trade direction: 'long' or 'short'.")
    entry: TpsEntry = Field(description="Entry configuration.")
    risk: TpsRisk = Field(description="Risk configuration.")
    take_profit: Optional[TpsTakeProfit] = Field(
        default=None,
        description="Take-profit configuration."
    )
    vol_guard: Optional[str] = Field(
        default=None,
        description="Volatility guard rule, e.g. 'atr20 > 1.5x avg -> reduce 30%'."
    )
    add_if: Optional[str] = Field(
        default=None,
        description="Conditional position increase rule, e.g. 'macd bull & close > ma50 -> max_position 7%'."
    )


# ---------------------------------------------------------------------------
# Outer structured output: narrative + recommendation + TPS plan
# ---------------------------------------------------------------------------

class TraderOutput(BaseModel):
    """Structured output for the Trader agent."""

    trader_investment_plan: str = Field(
        description="Detailed trader decision narrative with rationale and execution considerations."
    )
    recommendation: Literal["BUY", "SELL", "HOLD"] = Field(
        description="Clear actionable recommendation: BUY, SELL, or HOLD."
    )
    tps_plan: TpsPlan = Field(
        description=(
            "Structured TPS-YAML v0.1 trade plan. "
            "instrument: ticker; timeframe: default '1D'; "
            "side: 'long' for BUY/HOLD-long, 'short' for SELL/SHORT; "
            "entry.near: entry price (number) or price-band string; "
            "risk.stop: hard stop price; risk.max_loss: default '1%'. "
            "Omit optional sub-fields you cannot reasonably infer. Never fabricate prices."
        )
    )


def _tps_to_json(plan: TpsPlan) -> str:
    """Serialize a TpsPlan Pydantic model to a compact, clean JSON string."""
    d: dict = {}
    d["instrument"] = plan.instrument
    d["timeframe"] = plan.timeframe
    d["side"] = plan.side

    entry: dict = {"near": plan.entry.near}
    if plan.entry.scale is not None:
        entry["scale"] = plan.entry.scale
    if plan.entry.confirm:
        entry["confirm"] = plan.entry.confirm
    d["entry"] = entry

    risk: dict = {"max_loss": plan.risk.max_loss, "stop": plan.risk.stop}
    if plan.risk.max_position is not None:
        risk["max_position"] = plan.risk.max_position
    if plan.risk.invalidate is not None:
        risk["invalidate"] = plan.risk.invalidate
    d["risk"] = risk

    if plan.take_profit is not None:
        tp: dict = {}
        if plan.take_profit.tp1 is not None:
            tp["tp1"] = plan.take_profit.tp1
        if plan.take_profit.trail is not None:
            tp["trail"] = plan.take_profit.trail
        if tp:
            d["take_profit"] = tp

    if plan.vol_guard is not None:
        d["vol_guard"] = plan.vol_guard
    if plan.add_if is not None:
        d["add_if"] = plan.add_if

    return json.dumps(d, indent=2, ensure_ascii=False)


def create_trader(llm, memory):
    def trader_node(state, name):
        company_name = state["company_of_interest"]
        investment_plan = state["investment_plan"]

        # Build memory similarity key from all available reports (not re-fed to LLM — already synthesized in investment_plan)
        curr_situation = investment_plan
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        if past_memories:
            for i, rec in enumerate(past_memories, 1):
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            past_memory_str = "No past memories found."

        context = {
            "role": "user",
            "content": (
                f"Based on a comprehensive analysis by a team of analysts, here is an investment plan "
                f"tailored for {company_name}. This plan incorporates insights from current technical "
                f"market trends, macroeconomic indicators, and social media sentiment. Use this plan as "
                f"a foundation for evaluating your next trading decision.\n\n"
                f"Proposed Investment Plan: {investment_plan}\n\n"
                f"Leverage these insights to make an informed and strategic decision."
            ),
        }

        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a trading agent analyzing market data to make investment decisions. "
                    f"Based on your analysis, provide a specific recommendation to buy, sell, or hold. "
                    f"In your structured output, provide:\n"
                    f"1) trader_investment_plan: a detailed narrative decision with reasoning and execution notes.\n"
                    f"2) recommendation: exactly one of BUY, SELL, or HOLD.\n"
                    f"3) tps_plan: a structured TPS-YAML v0.1 trade plan object with fields: "
                    f"instrument (ticker), timeframe (default '1D'), side ('long' or 'short'), "
                    f"entry.near (entry price as a number, or price-band string like '123.45 ±1%'), "
                    f"risk.stop (hard stop price as a number), risk.max_loss (default '1%'). "
                    f"Add optional fields only when you can infer them from the analysis. "
                    f"Never fabricate prices.\n\n"
                    f"Do not forget to utilize lessons from past decisions to learn from your mistakes. "
                    f"Here are some reflections from similar situations you traded in and the lessons learned: "
                    f"{past_memory_str}"
                ),
            },
            context,
        ]

        recommendation = None
        tps_plan_yaml = ""
        usage_meta = None
        usage_cb = _UsageCaptureCallback()
        try:
            structured_llm = llm.with_structured_output(TraderOutput)
            structured_response = structured_llm.invoke(
                messages, config={"callbacks": [usage_cb]}
            )
            trader_investment_plan = structured_response.trader_investment_plan
            if usage_cb.last_message is not None:
                usage_meta = _capture_usage(usage_cb.last_message, llm)
            recommendation = getattr(structured_response, "recommendation", None)
            tps_obj = getattr(structured_response, "tps_plan", None)
            if tps_obj is not None:
                tps_plan_yaml = _tps_to_json(tps_obj)
            result_message = AIMessage(content=trader_investment_plan)
        except Exception:
            raw_result = llm.invoke(messages)
            usage_meta = _capture_usage(raw_result, llm)
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
        out = {
            "messages": [result_message],
            "trader_investment_plan": trader_investment_plan,
            "trader_recommendation": recommendation,
            "trader_tps_plan": tps_plan_yaml,
            "sender": name,
        }
        if usage_meta:
            out["report_usage"] = {"trader_investment_plan": usage_meta}
        return out

    return functools.partial(trader_node, name="Trader")


