from typing import Annotated, Any, Dict, List, Sequence
import json
from datetime import date, timedelta, datetime
from typing_extensions import TypedDict, Optional
from langchain_core.messages import AnyMessage
from langchain_openai import ChatOpenAI
from .. import *  # agents package
from langgraph.prebuilt import ToolNode
from langgraph.graph import END, StateGraph, START, MessagesState, add_messages
from .trace_utils import sort_agent_steps


def _merge_report_usage(current: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Reducer: merge report_usage dicts so each node adds its report key."""
    base = dict(current) if current else {}
    upd = dict(update) if update else {}
    base.update(upd)
    return base


def _merge_report_resources_by_report(
    current: Dict[str, List[Dict[str, Any]]],
    update: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Reducer: merge per-report resource lists using the same list dedupe logic."""
    base = dict(current) if current else {}
    upd = dict(update) if update else {}
    for report_key, resources in upd.items():
        base[report_key] = _merge_report_resources(base.get(report_key, []), resources or [])
    return base


def _merge_report_steps_by_report(
    current: Dict[str, List[Dict[str, Any]]],
    update: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Reducer: append persisted agent step traces for each report key."""
    base = dict(current) if current else {}
    upd = dict(update) if update else {}
    for report_key, steps in upd.items():
        existing = list(base.get(report_key, []))
        new_steps = [step for step in (steps or []) if isinstance(step, dict)]
        existing.extend(new_steps)
        base[report_key] = sort_agent_steps(existing)
    return base


def _merge_report_resources(
    current: List[Dict[str, Any]], update: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Reducer: append new resource entries and dedupe by (type, url) or (type, title/description/ticker)."""
    combined = list(current) if current else []
    new_entries = update if isinstance(update, list) else []
    seen: set[tuple] = set()

    def _dedupe_key(resource: Dict[str, Any]) -> tuple:
        resource_type = resource.get("type") or ""
        if resource.get("url"):
            return (resource_type, "url", resource.get("url"))
        if resource.get("tool_name") or resource.get("tool") or resource.get("tool_input") or resource.get("args"):
            tool_name = resource.get("tool_name") or resource.get("tool") or ""
            tool_input = resource.get("tool_input")
            if tool_input is None:
                tool_input = resource.get("args")
            try:
                tool_input_key = json.dumps(tool_input, sort_keys=True, default=str)
            except Exception:
                tool_input_key = str(tool_input)
            return (resource_type, "tool", tool_name, tool_input_key)
        return (
            resource_type,
            "meta",
            resource.get("title") or resource.get("description") or resource.get("ticker") or "",
        )

    for r in combined:
        seen.add(_dedupe_key(r))
    for r in new_entries:
        if not isinstance(r, dict):
            continue
        key = _dedupe_key(r)
        if key not in seen:
            seen.add(key)
            combined.append(r)
    return combined


# Researcher team state
class InvestDebateState(TypedDict):
    bull_history: Annotated[
        str, "Bullish Conversation history"
    ]  # Bullish Conversation history
    bear_history: Annotated[
        str, "Bearish Conversation history"
    ]  # Bullish Conversation history
    history: Annotated[str, "Conversation history"]  # Conversation history
    current_response: Annotated[str, "Latest response"]  # Last response
    judge_decision: Annotated[str, "Final judge decision"]  # Last response
    count: Annotated[int, "Length of the current conversation"]  # Conversation length


# Risk management team state
class RiskDebateState(TypedDict):
    risky_history: Annotated[
        str, "Risky Agent's Conversation history"
    ]  # Conversation history
    safe_history: Annotated[
        str, "Safe Agent's Conversation history"
    ]  # Conversation history
    neutral_history: Annotated[
        str, "Neutral Agent's Conversation history"
    ]  # Conversation history
    history: Annotated[str, "Conversation history"]  # Conversation history
    latest_speaker: Annotated[str, "Analyst that spoke last"]
    current_risky_response: Annotated[
        str, "Latest response by the risky analyst"
    ]  # Last response
    current_safe_response: Annotated[
        str, "Latest response by the safe analyst"
    ]  # Last response
    current_neutral_response: Annotated[
        str, "Latest response by the neutral analyst"
    ]  # Last response
    judge_decision: Annotated[str, "Judge's decision"]
    count: Annotated[int, "Length of the current conversation"]  # Conversation length


class AgentState(TypedDict):
    company_of_interest: Annotated[str, "Company that we are interested in trading"]
    trade_date: Annotated[str, "What date we are trading at"]
    events_report: Annotated[str, "Deterministic event summary for the ticker"]

    sender: Annotated[str, "Agent that sent this message"]

    # Temporary isolated message contexts for analysts (not shared between analysts)
    _market_context: Annotated[Optional[List[Any]], "Isolated message context for market analyst"]
    _social_context: Annotated[Optional[List[Any]], "Isolated message context for social media analyst"]
    _news_context: Annotated[Optional[List[Any]], "Isolated message context for news analyst"]
    _fundamentals_context: Annotated[Optional[List[Any]], "Isolated message context for fundamentals analyst"]
    _technical_context: Annotated[Optional[List[Any]], "Isolated message context for technical analyst"]
    _sec_context: Annotated[Optional[List[Any]], "Isolated message context for SEC analyst"]

    # research step
    market_report: Annotated[str, "Report from the Market Analyst"]
    market_score: Annotated[Optional[int], "Market analysis score from 1-10 indicating market performance outlook"]
    market_key_takeaways: Annotated[Optional[List[str]], "Structured key takeaways from market analyst (no post-hoc LLM extraction)"]
    sentiment_report: Annotated[str, "Report from the News & Sentiment Analyst (news/catalysts + crowd sentiment)"]
    sentiment_score: Annotated[Optional[int], "Combined news & sentiment score from 1-10"]
    sentiment_key_takeaways: Annotated[Optional[List[str]], "Structured key takeaways from the News & Sentiment analyst"]
    fundamentals_report: Annotated[str, "Report from the Fundamentals Researcher"]
    fundamentals_score: Annotated[Optional[int], "Fundamentals score from 1-10 indicating company financial health and fundamental strength"]
    fundamentals_key_takeaways: Annotated[Optional[List[str]], "Structured key takeaways from fundamentals analyst"]
    sec_report: Annotated[str, "Report from the SEC/Regulatory Analyst"]
    sec_score: Annotated[Optional[int], "SEC/regulatory score from 1-10"]
    sec_key_takeaways: Annotated[Optional[List[str]], "Structured key takeaways from SEC analyst"]
    technical_report: Annotated[str, "Report from the Technical Analyst with advanced pattern recognition"]
    technical_score: Annotated[Optional[int], "Technical analysis score from 1-10 indicating stock performance"]
    technical_key_takeaways: Annotated[Optional[List[str]], "Structured key takeaways from technical analyst"]
    valuation_report: Annotated[str, "Report from the Valuation Analyst with multi-method fair value analysis"]
    valuation_score: Annotated[Optional[int], "Valuation score from 1-10 based on upside/downside to fair value"]
    valuation_key_takeaways: Annotated[Optional[List[str]], "Structured key takeaways from valuation analyst"]
    fair_value_bear: Annotated[Optional[float], "Conservative fair value estimate (bear case)"]
    fair_value_base: Annotated[Optional[float], "Base case fair value estimate (most likely)"]
    fair_value_bull: Annotated[Optional[float], "Optimistic fair value estimate (bull case)"]
    current_discount_pct: Annotated[Optional[float], "Percentage discount/premium vs base fair value (positive=discount, negative=premium)"]
    valuation_conviction: Annotated[Optional[str], "Valuation conviction level: high, medium, or low"]
    valuation_key_assumptions: Annotated[Optional[List[str]], "Top 3-5 critical assumptions driving the valuation"]

    # researcher team discussion step
    investment_debate_state: Annotated[
        InvestDebateState, "Current state of the debate on if to invest or not"
    ]
    investment_plan: Annotated[str, "Plan generated by the Analyst"]
    investment_plan_key_takeaways: Annotated[Optional[List[str]], "Structured key takeaways from research manager investment plan"]
    bull_summary: Annotated[Optional[List[str]], "Research Manager summary of bull analyst key arguments"]
    bear_summary: Annotated[Optional[List[str]], "Research Manager summary of bear analyst key arguments"]
    recommendation_score: Annotated[Optional[int], "Recommendation score from 1-10 indicating confidence and strength of the investment recommendation"]
    expected_return_pct: Annotated[Optional[float], "Expected percentage return from current price (base case)"]
    bear_case_return_pct: Annotated[Optional[float], "Bear-case percentage return from current price (downside scenario)"]
    bull_case_return_pct: Annotated[Optional[float], "Bull-case percentage return from current price (upside scenario)"]

    trader_investment_plan: Annotated[str, "Plan generated by the Trader"]
    trader_key_takeaways: Annotated[Optional[List[str]], "Structured key takeaways from trader narrative"]
    trader_recommendation: Annotated[Optional[str], "Structured recommendation from trader: BUY, SELL, or HOLD"]
    trader_tps_plan: Annotated[Optional[str], "Structured TPS-YAML v0.1 trading plan emitted by the Trader"]

    # risk management team discussion step
    risk_debate_state: Annotated[
        RiskDebateState, "Current state of the debate on evaluating risk"
    ]
    final_trade_decision: Annotated[str, "Final decision made by the Risk Analysts"]
    recommendation: Annotated[
        Optional[str],
        "Final BUY/SELL/HOLD from Risk Manager structured output (overrides trader when set)",
    ]
    risky_summary: Annotated[Optional[List[str]], "Risk Manager summary of risky analyst key arguments"]
    safe_summary: Annotated[Optional[List[str]], "Risk Manager summary of safe analyst key arguments"]
    neutral_summary: Annotated[Optional[List[str]], "Risk Manager summary of neutral analyst key arguments"]
    risk_score: Annotated[Optional[int], "Risk score from 1-10 indicating confidence and strength of the risk assessment and final decision"]
    final_report_key_takeaways: Annotated[Optional[List[str]], "Structured key takeaways from the final trade decision report"]

    # LLM usage per report (input_tokens, output_tokens, cost_usd) for DB metadata; merged by report key
    report_usage: Annotated[Dict[str, Any], _merge_report_usage]
    # Resources used in this run: news, SEC filings, Reddit, etc. (type, url?, title?, ticker?, description?)
    report_resources: Annotated[List[Dict[str, Any]], _merge_report_resources]
    # Resources used per saved report key so each report can render only its own evidence.
    report_resources_by_report: Annotated[Dict[str, List[Dict[str, Any]]], _merge_report_resources_by_report]
    # Agent step traces per saved report key for future visualization/debugging.
    report_steps_by_report: Annotated[Dict[str, List[Dict[str, Any]]], _merge_report_steps_by_report]
