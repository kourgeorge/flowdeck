"""
User Daily Brief agents: Ticker Interpreter, Market Interpreter, Narrative Writer.

Each agent receives relevant state (DigestContext + prior outputs), uses an LLM with
optional tools, and returns structured updates to the workflow state.
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage

from ai_engine.tradingagents.agents.utils.trace_utils import make_agent_step
from backend.processing import build_important_events

from .state import DigestContext, DigestWorkflowState, MarketInterpretation, TickerInterpretation, FocusSelection, ReferenceItem
from . import prompts

logger = logging.getLogger(__name__)


def _append_agent_step(state: DigestWorkflowState, **kwargs: Any) -> None:
    state.agent_steps.append(make_agent_step(**kwargs))


def _invoke_with_timeout(chain: Any, messages: list, timeout_seconds: int = 180) -> Any:
    """
    Invoke a LangChain chain with a timeout using ThreadPoolExecutor.
    
    Args:
        chain: The LangChain chain to invoke
        messages: Messages to pass to the chain
        timeout_seconds: Timeout in seconds (default 180 = 3 minutes)
    
    Returns:
        The chain result
    
    Raises:
        FuturesTimeoutError: If the operation times out
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(chain.invoke, messages)
        try:
            result = future.result(timeout=timeout_seconds)
            return result
        except FuturesTimeoutError:
            logger.error("LLM invocation timed out after %d seconds", timeout_seconds)
            raise


def _format_ticker_context(ctx: DigestContext, ticker: str) -> str:
    """Format the slice of DigestContext for one ticker as text for the prompt."""
    lines = []
    event_summary = (getattr(ctx, "event_summaries", None) or {}).get(ticker)
    if event_summary and getattr(event_summary, "events", None):
        lines.append(f"Deterministic event score: {getattr(event_summary, 'event_score', 0.0)}")
        lines.append("Detected events:")
        for event in event_summary.events:
            meta_parts = []
            if getattr(event, "detected_on", None):
                meta_parts.append(f"date={event.detected_on}")
            if getattr(event, "strength", None):
                meta_parts.append(f"strength={event.strength}")
            if getattr(event, "metric_value", None) is not None:
                meta_parts.append(f"metric={event.metric_value}")
            if getattr(event, "threshold_value", None) is not None:
                meta_parts.append(f"threshold={event.threshold_value}")
            cross = (getattr(event, "metadata", {}) or {}).get("cross")
            if cross:
                meta_parts.append(f"cross={cross}")
            label = f"- {event.event_type}"
            if meta_parts:
                label += f" [{', '.join(meta_parts)}]"
            lines.append(label)
    q = (ctx.quotes or {}).get(ticker)
    if q:
        lines.append(f"Quote: {json.dumps(q, default=str)[:800]}")
    r1 = (ctx.returns_1d or {}).get(ticker)
    r5 = (ctx.returns_5d or {}).get(ticker)
    r_span = (getattr(ctx, "returns_span", None) or {}).get(ticker)
    if r1 is not None or r5 is not None:
        parts = []
        if r1 is not None:
            parts.append(f"1d={r1}%")
        if r5 is not None:
            parts.append(f"5d={r5}%")
        if r_span is not None:
            parts.append(f"span={r_span}%")
        lines.append("Returns: " + ", ".join(parts))
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
                report_recommendation = v.get("recommendation")
                expected_return = v.get("expected_return_pct")
                confidence = v.get("confidence")
                meta_parts = []
                if report_recommendation:
                    meta_parts.append(f"recommendation={report_recommendation}")
                if expected_return is not None:
                    meta_parts.append(f"expected_return_pct={expected_return}")
                if confidence is not None:
                    meta_parts.append(f"confidence={confidence}")
                c = v.get("content") or v.get("key_takeaways")
                if c:
                    prefix = f"{k}"
                    if meta_parts:
                        prefix += f" [{', '.join(meta_parts)}]"
                    thesis_parts.append(f"{prefix}: {str(c)[:400]}")
            elif v:
                thesis_parts.append(f"{k}: {str(v)[:400]}")
        if thesis_parts:
            lines.append("Platform reports (thesis/takeaways): " + " | ".join(thesis_parts))
    share_url = (ctx.share_urls or {}).get(ticker)
    if share_url:
        lines.append(f"Report share URL (viewable without login): {share_url}")
    pm = (getattr(ctx, "polymarket_sentiment", None) or {}).get(ticker)
    if pm and not pm.get("error"):
        trend = pm.get("trend", "neutral")
        overall = pm.get("overall_sentiment")
        confidence = pm.get("confidence")
        market_count = pm.get("market_count", 0)
        pm_parts = [f"trend={trend}"]
        if overall is not None:
            pm_parts.append(f"sentiment_score={overall:.2f}")
        if confidence is not None:
            pm_parts.append(f"confidence={confidence:.2f}")
        if market_count:
            pm_parts.append(f"markets_analysed={market_count}")
        lines.append("Polymarket prediction-market: " + ", ".join(pm_parts))
        top_markets = pm.get("top_markets") or []
        if top_markets:
            market_lines = []
            for m in top_markets[:3]:
                q = m.get("question") or m.get("title") or ""
                prob = m.get("yes_probability") or m.get("probability")
                vol = m.get("volume_usd") or m.get("volume")
                mparts = []
                if prob is not None:
                    mparts.append(f"yes_prob={float(prob):.0%}")
                if vol is not None:
                    try:
                        mparts.append(f"vol=${float(vol):,.0f}")
                    except (TypeError, ValueError):
                        pass
                suffix = f" [{', '.join(mparts)}]" if mparts else ""
                if q:
                    market_lines.append(f"  - {q[:120]}{suffix}")
            if market_lines:
                lines.append("Top prediction markets:")
                lines.extend(market_lines)
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
    for label, key in [("Gainers", "gainers"), ("Losers", "losers"), ("Most active", "most_active")]:
        arr = movers.get(key) or []
        if arr:
            lines.append(f"{label}:")
            for row in arr[:5]:
                if not isinstance(row, dict):
                    lines.append(f"- {row}")
                    continue
                symbol = str(row.get("symbol") or "").strip().upper()
                short_name = str(row.get("shortName") or "").strip()
                name_part = f"{short_name} ({symbol})" if short_name and symbol else (short_name or symbol or "Unknown")
                price = row.get("regularMarketPrice")
                change_pct = row.get("regularMarketChangePercent")
                sector = row.get("sector")
                detail_parts: List[str] = []
                if price is not None:
                    detail_parts.append(f"price={price}")
                if change_pct is not None:
                    detail_parts.append(f"change={change_pct}%")
                if sector:
                    detail_parts.append(f"sector={sector}")
                details = f" [{', '.join(detail_parts)}]" if detail_parts else ""
                lines.append(f"- {name_part}{details}")
    return "\n".join(lines) if lines else "(none)"


def run_focus_selector(
    state: DigestWorkflowState,
    llm: Any,
) -> Optional[List[str]]:
    """Run the Focus Selector agent to determine which tickers to focus on."""
    ctx = state.digest_context
    if not ctx or not ctx.tickers:
        _append_agent_step(
            state,
            agent="Focus Selector",
            phase="selection",
            kind="selection",
            status="skipped",
            summary="Focus selection skipped",
            output_preview="No portfolio tickers were available for digest focus selection.",
        )
        return None

    # If the user explicitly selected focus tickers, honor that (subject to basic validation).
    if state.user_focus_tickers:
        portfolio_set = {t.upper() for t in (ctx.tickers or [])}
        cleaned: List[str] = []
        seen: set[str] = set()
        for t in state.user_focus_tickers:
            if not t:
                continue
            tu = str(t).upper()
            if tu in portfolio_set and tu not in seen:
                cleaned.append(tu)
                seen.add(tu)
            if len(cleaned) >= state.max_priority_tickers:
                break
        if cleaned:
            logger.info("Digest: using user-selected focus tickers: %s", cleaned)
            _append_agent_step(
                state,
                agent="Focus Selector",
                phase="selection",
                kind="selection",
                status="completed",
                summary="Used user-selected focus tickers",
                output_preview={"focus_tickers": cleaned},
                extra={"reason": "user_focus_tickers"},
            )
            return cleaned

    attention_scores = ctx.attention_scores or {}
    if not attention_scores:
        # Fallback: no scores, keep existing priority_tickers
        _append_agent_step(
            state,
            agent="Focus Selector",
            phase="selection",
            kind="selection",
            status="completed",
            summary="Used default priority tickers",
            output_preview={"focus_tickers": list(ctx.priority_tickers or [])},
            extra={"reason": "missing_attention_scores"},
        )
        return list(ctx.priority_tickers or [])

    default_priority = list(ctx.priority_tickers or [])
    if not default_priority:
        # If priority_tickers is empty, use score-based top-N as default
        sorted_tickers = sorted(
            attention_scores.keys(),
            key=lambda t: -float(attention_scores.get(t) or 0.0),
        )
        default_priority = sorted_tickers[: state.max_priority_tickers]

    prompt_text = prompts.build_focus_selector_prompt(
        portfolio_tickers=ctx.tickers or [],
        attention_scores=attention_scores,
        default_priority_tickers=default_priority,
        max_priority_tickers=state.max_priority_tickers,
        user_note=state.user_note,
        user_context_snapshot=ctx.user_context_snapshot,
        period_label=state.period_label,
    )
    message = HumanMessage(content=prompts.FOCUS_SELECTOR_SYSTEM + "\n\n" + prompt_text)

    try:
        chain = llm.with_structured_output(FocusSelection)
        result = chain.invoke([message])
        tickers = list(getattr(result, "focus_tickers", []) or [])
    except Exception as e:
        logger.warning("Digest: focus_selector failed: %s", e)
        _append_agent_step(
            state,
            agent="Focus Selector",
            phase="selection",
            kind="llm_call",
            status="failed",
            summary="Focus Selector failed; using default priority tickers",
            message_preview=message.content,
            output_preview={"focus_tickers": list(default_priority)},
            extra={"error": str(e)},
        )
        return list(default_priority)

    # Sanitize: keep only known portfolio tickers, uppercase, unique, respect max_priority_tickers
    portfolio_set = {t.upper() for t in (ctx.tickers or [])}
    seen: set[str] = set()
    cleaned: List[str] = []
    for t in tickers:
        if not t:
            continue
        tu = str(t).upper()
        if tu in portfolio_set and tu not in seen:
            cleaned.append(tu)
            seen.add(tu)
        if len(cleaned) >= state.max_priority_tickers:
            break

    if not cleaned:
        _append_agent_step(
            state,
            agent="Focus Selector",
            phase="selection",
            kind="llm_call",
            status="completed",
            summary="Focus Selector returned no valid tickers; using defaults",
            message_preview=message.content,
            output_preview={"focus_tickers": list(default_priority)},
            extra={"raw_focus_tickers": tickers},
        )
        return list(default_priority)

    _append_agent_step(
        state,
        agent="Focus Selector",
        phase="selection",
        kind="llm_call",
        status="completed",
        summary="Focus Selector chose digest focus tickers",
        message_preview=message.content,
        output_preview={"focus_tickers": cleaned},
        extra={"raw_focus_tickers": tickers},
    )
    return cleaned


def run_ticker_interpreter(
    state: DigestWorkflowState,
    llm: Any,
) -> Dict[str, TickerInterpretation]:
    """Run the Ticker Interpreter for each priority ticker; return ticker -> TickerInterpretation."""
    ctx = state.digest_context
    if not ctx or not ctx.priority_tickers:
        _append_agent_step(
            state,
            agent="Ticker Interpreter",
            phase="analysis",
            kind="llm_call",
            status="skipped",
            summary="Ticker interpretation skipped",
            output_preview="No priority tickers were available for digest analysis.",
        )
        return {}

    interpretations: Dict[str, TickerInterpretation] = {}
    for ticker in ctx.priority_tickers:
        logger.info("Digest: starting ticker_interpreter for %s", ticker)
        try:
            context_text = _format_ticker_context(ctx, ticker)
            prompt_text = prompts.build_ticker_interpreter_prompt(
                ticker=ticker,
                context_text=context_text,
                tool_names=["get_news", "get_platform_reports", "get_fundamentals", "get_analysts_recommendation", "get_insider_transactions", "get_insider_sentiment", "get_indicators", "web_search"],
                user_context_snapshot=ctx.user_context_snapshot,
                period_label=state.period_label,
            )
            message = HumanMessage(content=prompts.TICKER_INTERPRETER_SYSTEM + "\n\n" + prompt_text)
            logger.info("Digest: invoking LLM for ticker_interpreter %s", ticker)
            chain = llm.with_structured_output(TickerInterpretation)
            try:
                result = _invoke_with_timeout(chain, [message], timeout_seconds=180)
            except FuturesTimeoutError:
                logger.error("Digest: ticker_interpreter timed out for %s after 180 seconds", ticker)
                interpretations[ticker] = TickerInterpretation(
                    explanation=f"(Interpretation timed out after 3 minutes)",
                    driver="unclear",
                    thesis_comparison="",
                    recommendation="HOLD: recommendation unavailable because the interpretation timed out.",
                )
                _append_agent_step(
                    state,
                    agent="Ticker Interpreter",
                    phase="analysis",
                    kind="llm_call",
                    status="failed",
                    summary=f"Ticker Interpreter timed out for {ticker}",
                    message_preview=message.content,
                    output_preview=interpretations[ticker].model_dump(),
                    extra={"ticker": ticker, "timeout_seconds": 180},
                )
                continue
            logger.info("Digest: LLM response received for ticker_interpreter %s", ticker)
            if isinstance(result, TickerInterpretation):
                interpretations[ticker] = result
            else:
                interpretations[ticker] = TickerInterpretation(
                    explanation=getattr(result, "explanation", str(result)),
                    driver=getattr(result, "driver", "unclear"),
                    thesis_comparison=getattr(result, "thesis_comparison", ""),
                    recommendation=getattr(
                        result,
                        "recommendation",
                        "HOLD: recommendation unavailable in the model response.",
                    ),
                )
            _append_agent_step(
                state,
                agent="Ticker Interpreter",
                phase="analysis",
                kind="llm_call",
                status="completed",
                summary=f"Ticker Interpreter analyzed {ticker}",
                message_preview=message.content,
                output_preview=interpretations[ticker].model_dump(),
                extra={"ticker": ticker},
            )
            logger.info("Digest: ticker_interpreter done for %s", ticker)
        except Exception as e:
            logger.exception("Digest: ticker_interpreter failed for %s: %s", ticker, e)
            interpretations[ticker] = TickerInterpretation(
                explanation=f"(Interpretation unavailable: {e})",
                driver="unclear",
                thesis_comparison="",
                recommendation="HOLD: recommendation unavailable because the interpretation failed.",
            )
            _append_agent_step(
                state,
                agent="Ticker Interpreter",
                phase="analysis",
                kind="llm_call",
                status="failed",
                summary=f"Ticker Interpreter failed for {ticker}",
                message_preview=message.content if "message" in locals() else None,
                output_preview=interpretations[ticker].model_dump(),
                extra={"ticker": ticker, "error": str(e)},
            )
    return interpretations


def run_market_interpreter(
    state: DigestWorkflowState,
    llm: Any,
) -> Optional[MarketInterpretation]:
    """Run the Market Interpreter; return MarketInterpretation."""
    ctx = state.digest_context
    if not ctx:
        _append_agent_step(
            state,
            agent="Market Interpreter",
            phase="analysis",
            kind="llm_call",
            status="skipped",
            summary="Market interpretation skipped",
            output_preview="No digest context was available.",
        )
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
        user_context_snapshot=ctx.user_context_snapshot,
        period_label=state.period_label,
    )
    message = HumanMessage(content=prompts.MARKET_INTERPRETER_SYSTEM + "\n\n" + prompt_text)
    try:
        chain = llm.with_structured_output(MarketInterpretation)
        result = chain.invoke([message])
        if isinstance(result, MarketInterpretation):
            interpretation = result
        else:
            interpretation = MarketInterpretation(
                summary=getattr(result, "summary", str(result)),
                relevance_to_portfolio=getattr(result, "relevance_to_portfolio", ""),
            )
        _append_agent_step(
            state,
            agent="Market Interpreter",
            phase="analysis",
            kind="llm_call",
            status="completed",
            summary="Market Interpreter summarized the market backdrop",
            message_preview=message.content,
            output_preview=interpretation.model_dump(),
        )
        return interpretation
    except Exception as e:
        logger.warning("Digest: market_interpreter failed: %s", e)
        interpretation = MarketInterpretation(
            summary=f"(Market summary unavailable: {e})",
            relevance_to_portfolio="",
        )
        _append_agent_step(
            state,
            agent="Market Interpreter",
            phase="analysis",
            kind="llm_call",
            status="failed",
            summary="Market Interpreter failed",
            message_preview=message.content,
            output_preview=interpretation.model_dump(),
            extra={"error": str(e)},
        )
        return interpretation


def run_recent_briefs_summarizer(
    state: DigestWorkflowState,
    llm: Any,
) -> Optional[str]:
    """Summarize already-covered points from the last few stored briefs."""
    recent_briefs = state.recent_digest_briefs or []
    if not recent_briefs:
        _append_agent_step(
            state,
            agent="Recent Briefs Summarizer",
            phase="analysis",
            kind="llm_call",
            status="skipped",
            summary="Recent briefs summarizer skipped",
            output_preview="No prior briefs were available for continuity context.",
        )
        return None

    briefs_lines: List[str] = []
    for idx, brief in enumerate(recent_briefs[:5], start=1):
        briefs_lines.append(f"### Brief {idx}")
        if brief.digest_date:
            briefs_lines.append(f"- Digest date: {brief.digest_date}")
        if brief.created_at:
            briefs_lines.append(f"- Created at (UTC): {brief.created_at}")
        if brief.span_label or brief.span_type:
            briefs_lines.append(f"- Span: {brief.span_label or brief.span_type}")
        if brief.priority_tickers:
            briefs_lines.append(f"- Priority tickers: {', '.join(brief.priority_tickers)}")
        if brief.narrative:
            briefs_lines.append("- Narrative:")
            briefs_lines.append(brief.narrative[:1800])
        if brief.what_to_watch:
            briefs_lines.append("- What to watch:")
            briefs_lines.append(brief.what_to_watch[:800])
        briefs_lines.append("")

    prompt_text = prompts.build_recent_briefs_summary_prompt("\n".join(briefs_lines).strip())
    message = HumanMessage(content=prompts.RECENT_BRIEFS_SUMMARIZER_SYSTEM + "\n\n" + prompt_text)

    try:
        from pydantic import BaseModel, Field

        class _RecentBriefsSummaryOut(BaseModel):
            summary: str = Field(
                description=(
                    "Concise summary of the main points already covered across the recent briefs, "
                    "for use as anti-repetition context."
                )
            )

        chain = llm.with_structured_output(_RecentBriefsSummaryOut)
        result = chain.invoke([message])
        summary = getattr(result, "summary", "") or ""
        clean_summary = summary.strip() or None
        _append_agent_step(
            state,
            agent="Recent Briefs Summarizer",
            phase="analysis",
            kind="llm_call",
            status="completed",
            summary="Summarized prior briefs for continuity",
            message_preview=message.content,
            output_preview=clean_summary,
            extra={"brief_count": len(recent_briefs[:5])},
        )
        return clean_summary
    except Exception as e:
        logger.warning("Digest: recent_briefs_summarizer failed: %s", e)
        _append_agent_step(
            state,
            agent="Recent Briefs Summarizer",
            phase="analysis",
            kind="llm_call",
            status="failed",
            summary="Recent briefs summarizer failed",
            message_preview=message.content,
            output_preview=None,
            extra={"brief_count": len(recent_briefs[:5]), "error": str(e)},
        )
        return None


def run_narrative_writer(
    state: DigestWorkflowState,
    llm: Any,
) -> tuple[str, str]:
    """Run the Narrative Writer; return (digest_narrative, what_to_watch)."""
    ticker_texts = []
    for t, interp in (state.ticker_interpretations or {}).items():
        ticker_texts.append(
            f"### {t}\n"
            f"- Explanation: {interp.explanation}\n"
            f"- Driver: {interp.driver}\n"
            f"- Thesis comparison: {interp.thesis_comparison}\n"
            f"- Recommendation: {interp.recommendation}"
        )
    ticker_interpretations_text = "\n\n".join(ticker_texts) if ticker_texts else "(none)"

    mi = state.market_interpretation
    market_interpretation_text = ""
    if mi:
        market_interpretation_text = f"Summary: {mi.summary}\nRelevance to portfolio: {mi.relevance_to_portfolio}"

    # Build a best-effort resources section from the digest context for grounding.
    resources_lines: List[str] = []
    ctx = state.digest_context
    if ctx:
        # Per-ticker news articles
        news_map = ctx.news or {}
        for ticker in (ctx.priority_tickers or []):
            raw = news_map.get(ticker)
            items: List[str] = []
            if isinstance(raw, dict):
                articles = raw.get("articles") or raw.get("news") or []
            elif isinstance(raw, list):
                articles = raw
            else:
                articles = []
            for a in list(articles)[:3]:
                if not isinstance(a, dict):
                    continue
                title = str(a.get("title") or "")[:200]
                if not title:
                    continue
                publisher = a.get("publisher") or a.get("source") or ""
                link = a.get("link") or a.get("url") or ""
                meta_parts: List[str] = []
                if publisher:
                    meta_parts.append(str(publisher))
                if link:
                    meta_parts.append(str(link))
                meta = f" ({'; '.join(meta_parts)})" if meta_parts else ""
                items.append(f"- {title}{meta}")
            if items:
                resources_lines.append(f"### {ticker} news")
                resources_lines.extend(items)
        # Global / macro sources (best-effort)
        if ctx.global_news is not None:
            resources_lines.append("### Global / macro news feed")
            resources_lines.append(str(ctx.global_news)[:400])
        if ctx.web_search_snippet:
            resources_lines.append("### Web search snippet")
            resources_lines.append(str(ctx.web_search_snippet)[:400])

    resources_text = "\n".join(resources_lines) if resources_lines else ""
    important_events_text = ""
    if ctx:
        important_events = build_important_events(
            getattr(ctx, "event_summaries", {}) or {},
            ticker_order=ctx.priority_tickers,
        )
        important_event_lines: List[str] = []
        for item in important_events:
            event = item.event
            details: List[str] = [f"importance={item.importance_score}", f"strength={event.strength}"]
            if event.detected_on:
                details.append(f"date={event.detected_on}")
            if event.metric_value is not None:
                details.append(f"metric={event.metric_value}")
            if event.threshold_value is not None:
                details.append(f"threshold={event.threshold_value}")
            important_event_lines.append(
                f"- {item.ticker}: {event.event_type} ({'; '.join(details)}) — {event.description}"
            )
        important_events_text = "\n".join(important_event_lines)

    prompt_text = prompts.build_narrative_writer_prompt(
        ticker_interpretations_text=ticker_interpretations_text,
        market_interpretation_text=market_interpretation_text,
        tool_names=["get_ticker_quote", "get_platform_reports"],
        important_events_text=important_events_text or None,
        user_context_snapshot=ctx.user_context_snapshot if ctx else None,
        user_note=state.user_note,
        narrative_style=state.narrative_style,
        recent_briefs_summary=state.recent_briefs_summary,
        resources_text=resources_text or None,
        period_label=state.period_label,
    )
    message = HumanMessage(content=prompts.NARRATIVE_WRITER_SYSTEM + "\n\n" + prompt_text)
    use_structured = prompts.style_uses_structured_output(state.narrative_style)

    try:
        from pydantic import BaseModel, Field

        if use_structured:
            class _NarrativeOutStructured(BaseModel):
                market_highlights: str = Field(
                    description="Market Highlights: what happened (key price moves, headlines, market action)."
                )
                key_signals: str = Field(
                    description="Key Signals: what it means (drivers, themes, implications for the portfolio)."
                )
                what_to_watch: str = Field(
                    description="What to Watch: coming catalysts (earnings, data, events, levels to monitor)."
                )
                risks_opportunities: str = Field(
                    description="Risks & Opportunities: trading implications (risks, opportunities, positioning)."
                )
                references: Optional[List[ReferenceItem]] = Field(
                    default=None,
                    description=(
                        "Structured list of source items used for this brief "
                        "(news articles, global feeds, web snippets, etc.)."
                    ),
                )

            chain = llm.with_structured_output(_NarrativeOutStructured)
            result = chain.invoke([message])
            market_highlights = getattr(result, "market_highlights", "") or ""
            key_signals = getattr(result, "key_signals", "") or ""
            what_to_watch = getattr(result, "what_to_watch", "") or ""
            risks_opportunities = getattr(result, "risks_opportunities", "") or ""
            # Special tokens allow parsing/formatting by section (market_highlights, key_signals, risks_opportunities).
            # Note: what_to_watch is excluded from narrative as it's displayed separately in the email template.
            sections = [
                ("Market Highlights", "market_highlights", market_highlights),
                ("Key Signals", "key_signals", key_signals),
                ("Risks & Opportunities", "risks_opportunities", risks_opportunities),
            ]
            narrative = "\n\n".join(
                f"## {title}\n{token}\n{body.strip()}" for title, token, body in sections if body.strip()
            ).strip()
            if not narrative:
                narrative = market_highlights or key_signals or "Brief unavailable."
            state.references = list(getattr(result, "references", None) or [])
        else:
            class _NarrativeOutBasic(BaseModel):
                narrative: str = Field(
                    description="Short digest narrative (portfolio-centered, a few paragraphs)."
                )
                what_to_watch: str = Field(
                    description="What to watch section (2–4 sentences)."
                )
                references: Optional[List[ReferenceItem]] = Field(
                    default=None,
                    description=(
                        "Structured list of source items used for this brief "
                        "(news articles, global feeds, web snippets, etc.)."
                    ),
                )

            chain = llm.with_structured_output(_NarrativeOutBasic)
            result = chain.invoke([message])
            narrative = getattr(result, "narrative", "") or ""
            what_to_watch = getattr(result, "what_to_watch", "") or ""
            state.references = list(getattr(result, "references", None) or [])

        if not state.references and resources_text:
            fallback_items: List[ReferenceItem] = []
            for line in resources_text.splitlines():
                line = line.strip()
                if not line or line.startswith("###"):
                    continue
                if line.startswith("- "):
                    line = line[2:].strip()
                if not line:
                    continue
                fallback_items.append(ReferenceItem(label=line))
            state.references = fallback_items

        _append_agent_step(
            state,
            agent="Narrative Writer",
            phase="synthesis",
            kind="llm_call",
            status="completed",
            summary="Narrative Writer produced the final digest",
            message_preview=message.content,
            output_preview={
                "narrative": narrative,
                "what_to_watch": what_to_watch,
                "references": [ref.model_dump() for ref in (state.references or [])],
            },
            extra={"structured_output": use_structured},
        )
        return narrative, what_to_watch
    except Exception as e:
        logger.warning("Digest: narrative_writer failed: %s", e)
        fallback = (
            f"Digest unavailable: {e}. Ticker summaries: " + ticker_interpretations_text[:500],
            "Check back later for updates.",
        )
        _append_agent_step(
            state,
            agent="Narrative Writer",
            phase="synthesis",
            kind="llm_call",
            status="failed",
            summary="Narrative Writer failed",
            message_preview=message.content,
            output_preview={
                "narrative": fallback[0],
                "what_to_watch": fallback[1],
            },
            extra={"structured_output": use_structured, "error": str(e)},
        )
        return fallback
