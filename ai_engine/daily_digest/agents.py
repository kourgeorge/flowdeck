"""
User Daily Brief agents: Ticker Interpreter, Market Interpreter, Narrative Writer.

Each agent receives relevant state (DigestContext + prior outputs), uses an LLM with
optional tools, and returns structured updates to the workflow state.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage

from .state import DigestContext, DigestWorkflowState, MarketInterpretation, TickerInterpretation
from . import prompts

logger = logging.getLogger(__name__)


def _format_ticker_context(ctx: DigestContext, ticker: str) -> str:
    """Format the slice of DigestContext for one ticker as text for the prompt."""
    lines = []
    q = (ctx.quotes or {}).get(ticker)
    if q:
        lines.append(f"Quote: {json.dumps(q, default=str)[:800]}")
    r1 = (ctx.returns_1d or {}).get(ticker)
    r5 = (ctx.returns_5d or {}).get(ticker)
    if r1 is not None or r5 is not None:
        lines.append(f"Returns: 1d={r1}%, 5d={r5}%")
    if (ctx.abnormal_signal or {}).get(ticker):
        lines.append("Abnormal move: Yes")
    news = (ctx.news or {}).get(ticker)
    if news:
        lines.append(f"News: {json.dumps(news, default=str)[:1200]}")
    fund = (ctx.fundamentals or {}).get(ticker)
    if fund:
        lines.append(f"Fundamentals: {json.dumps(fund, default=str)[:800]}")
    analyst = (ctx.analyst_rec or {}).get(ticker)
    if analyst:
        lines.append(f"Analyst: {json.dumps(analyst, default=str)[:500]}")
    ins = (ctx.insider or {}).get(ticker)
    if ins:
        lines.append(f"Insider: {json.dumps(ins, default=str)[:500]}")
    ind = (ctx.indicators or {}).get(ticker)
    if ind:
        lines.append(f"Indicators: {json.dumps(ind, default=str)[:500]}")
    reports = (ctx.platform_reports or {}).get(ticker) or {}
    if reports:
        thesis_parts = []
        for k, v in reports.items():
            if isinstance(v, dict):
                c = v.get("content") or v.get("key_takeaways")
                if c:
                    thesis_parts.append(f"{k}: {str(c)[:400]}")
            elif v:
                thesis_parts.append(f"{k}: {str(v)[:400]}")
        if thesis_parts:
            lines.append("Platform reports (thesis/takeaways): " + " | ".join(thesis_parts))
    si = (ctx.sector_industry or {}).get(ticker)
    if si:
        lines.append(f"Sector/industry: {si}")
    peers = (ctx.peer_tickers or {}).get(ticker)
    if peers:
        pq = ctx.peer_quotes or {}
        peer_info = [f"{p}: {pq.get(p)}" for p in peers[:5] if pq.get(p)]
        if peer_info:
            lines.append("Peers: " + "; ".join(peer_info)[:400])
    return "\n".join(lines) if lines else "(no context)"


def _format_market_movers(movers: Dict[str, Any]) -> str:
    if not movers:
        return "(none)"
    lines = []
    for label, key in [("Gainers", "gainers"), ("Losers", "losers")]:
        arr = movers.get(key) or []
        if arr:
            lines.append(f"{label}: {json.dumps(arr[:5], default=str)}")
    return "\n".join(lines) if lines else "(none)"


def run_ticker_interpreter(
    state: DigestWorkflowState,
    llm: Any,
) -> Dict[str, TickerInterpretation]:
    """Run the Ticker Interpreter for each priority ticker; return ticker -> TickerInterpretation."""
    ctx = state.digest_context
    if not ctx or not ctx.priority_tickers:
        return {}

    interpretations: Dict[str, TickerInterpretation] = {}
    for ticker in ctx.priority_tickers:
        try:
            context_text = _format_ticker_context(ctx, ticker)
            prompt_text = prompts.build_ticker_interpreter_prompt(
                ticker=ticker,
                context_text=context_text,
                tool_names=["get_news", "get_platform_reports", "get_fundamentals", "get_analysts_recommendation", "get_insider_transactions", "get_insider_sentiment", "get_indicators", "web_search"],
            )
            message = HumanMessage(content=prompts.TICKER_INTERPRETER_SYSTEM + "\n\n" + prompt_text)
            chain = llm.with_structured_output(TickerInterpretation)
            result = chain.invoke([message])
            if isinstance(result, TickerInterpretation):
                interpretations[ticker] = result
            else:
                interpretations[ticker] = TickerInterpretation(
                    explanation=getattr(result, "explanation", str(result)),
                    driver=getattr(result, "driver", "unclear"),
                    thesis_comparison=getattr(result, "thesis_comparison", ""),
                )
            logger.info("Digest: ticker_interpreter done for %s", ticker)
        except Exception as e:
            logger.warning("Digest: ticker_interpreter failed for %s: %s", ticker, e)
            interpretations[ticker] = TickerInterpretation(
                explanation=f"(Interpretation unavailable: {e})",
                driver="unclear",
                thesis_comparison="",
            )
    return interpretations


def run_market_interpreter(
    state: DigestWorkflowState,
    llm: Any,
) -> Optional[MarketInterpretation]:
    """Run the Market Interpreter; return MarketInterpretation."""
    ctx = state.digest_context
    if not ctx:
        return None

    market_movers_text = _format_market_movers(ctx.market_movers or {})
    global_news_text = ""
    if ctx.global_news is not None:
        global_news_text = json.dumps(ctx.global_news, default=str) if not isinstance(ctx.global_news, str) else ctx.global_news
    one_liners = None
    if state.ticker_interpretations:
        one_liners = {t: interp.explanation[:200] for t, interp in state.ticker_interpretations.items()}

    prompt_text = prompts.build_market_interpreter_prompt(
        market_movers_text=market_movers_text,
        global_news_text=global_news_text,
        web_snippet=ctx.web_search_snippet,
        portfolio_tickers=ctx.tickers or [],
        priority_tickers=ctx.priority_tickers or [],
        ticker_one_liners=one_liners,
        tool_names=["get_global_news", "get_daily_market_movers", "web_search"],
    )
    message = HumanMessage(content=prompts.MARKET_INTERPRETER_SYSTEM + "\n\n" + prompt_text)
    try:
        chain = llm.with_structured_output(MarketInterpretation)
        result = chain.invoke([message])
        if isinstance(result, MarketInterpretation):
            return result
        return MarketInterpretation(
            summary=getattr(result, "summary", str(result)),
            relevance_to_portfolio=getattr(result, "relevance_to_portfolio", ""),
        )
    except Exception as e:
        logger.warning("Digest: market_interpreter failed: %s", e)
        return MarketInterpretation(
            summary=f"(Market summary unavailable: {e})",
            relevance_to_portfolio="",
        )


def run_narrative_writer(
    state: DigestWorkflowState,
    llm: Any,
) -> tuple[str, str]:
    """Run the Narrative Writer; return (digest_narrative, what_to_watch)."""
    ticker_texts = []
    for t, interp in (state.ticker_interpretations or {}).items():
        ticker_texts.append(f"### {t}\n- Explanation: {interp.explanation}\n- Driver: {interp.driver}\n- Thesis comparison: {interp.thesis_comparison}")
    ticker_interpretations_text = "\n\n".join(ticker_texts) if ticker_texts else "(none)"

    mi = state.market_interpretation
    market_interpretation_text = ""
    if mi:
        market_interpretation_text = f"Summary: {mi.summary}\nRelevance to portfolio: {mi.relevance_to_portfolio}"

    prompt_text = prompts.build_narrative_writer_prompt(
        ticker_interpretations_text=ticker_interpretations_text,
        market_interpretation_text=market_interpretation_text,
        tool_names=["get_ticker_quote", "get_platform_reports"],
    )
    message = HumanMessage(content=prompts.NARRATIVE_WRITER_SYSTEM + "\n\n" + prompt_text)

    try:
        from pydantic import BaseModel, Field
        class _NarrativeOut(BaseModel):
            narrative: str = Field(description="Short digest narrative")
            what_to_watch: str = Field(description="What to watch section")
        chain = llm.with_structured_output(_NarrativeOut)
        result = chain.invoke([message])
        narrative = getattr(result, "narrative", "") or ""
        what_to_watch = getattr(result, "what_to_watch", "") or ""
        return narrative, what_to_watch
    except Exception as e:
        logger.warning("Digest: narrative_writer failed: %s", e)
        return (
            f"Digest unavailable: {e}. Ticker summaries: " + ticker_interpretations_text[:500],
            "Check back later for updates.",
        )
