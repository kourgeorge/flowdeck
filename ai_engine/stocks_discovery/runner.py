"""
Standalone Stocks Discovery workflow: digest context build (shared) + deterministic ranking + LLM report.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from ai_engine.briefing_agent.context_builder import build_digest_context
from ai_engine.briefing_agent.state import DigestContext, DigestWorkflowState
from ai_engine.llm_provider import get_config_from_env, get_llm
from ai_engine.tradingagents.agents.utils.trace_utils import make_agent_step
from backend.processing import build_important_events

from .deterministic import run_deterministic_discovery
from .markdown import stocks_discovery_payload_to_markdown
from . import prompts
from .serialize import serialize_event_summaries
from .span import SpanType, digest_lookback_days, resolve_span

logger = logging.getLogger(__name__)


def _ensure_backend_import_path() -> None:
    try:
        import backend  # noqa: F401
        return
    except Exception:
        pass
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    backend_dir = os.path.join(repo_root, "backend")
    for path in (repo_root, backend_dir):
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)


class StocksDiscoveryRunResult(BaseModel):
    """Return value for API persistence and DigestResponse mapping."""

    digest_context: DigestContext
    narrative_markdown: str
    agent_steps: List[Dict[str, Any]] = Field(default_factory=list)
    interest_cluster: Dict[str, Any] = Field(default_factory=dict)
    discovered_tickers: List[str] = Field(default_factory=list)
    discovered_ticker_events_json: Dict[str, Any] = Field(default_factory=dict)
    discovered_ticker_info: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None


def _evidence_markdown_for_llm(
    discovered_tickers: List[str],
    discovered_ticker_events: Dict[str, Any],
    discovered_ticker_info: Dict[str, Dict[str, Any]],
) -> str:
    if not discovered_tickers:
        return "_No tickers exceeded the deterministic event-activity threshold._"

    lines: List[str] = []
    discovered_events = build_important_events(
        discovered_ticker_events,
        ticker_order=discovered_tickers,
        max_events=15,
    )
    for item in discovered_events[:12]:
        ticker = item.ticker
        event = item.event
        info = discovered_ticker_info.get(ticker) or {}
        sector = info.get("sector", "N/A")
        industry = info.get("industry", "N/A")
        details = [
            f"sector={sector}",
            f"industry={industry}",
            f"importance={item.importance_score}",
            f"strength={event.strength}",
        ]
        if event.detected_on:
            details.append(f"date={event.detected_on}")
        lines.append(f"- **{ticker}**: {event.event_type} ({'; '.join(details)}) — {event.description}")

    ev_json = serialize_event_summaries(discovered_ticker_events)
    for t in discovered_tickers:
        if t not in {item.ticker for item in discovered_events[:12]}:
            summ = ev_json.get(t) or {}
            score = summ.get("event_score")
            lines.append(f"- **{t}**: event_score={score} (see structured summary in metadata)")

    return "\n".join(lines) if lines else "_No event detail._"


def _run_llm_writer(
    *,
    span_label: str,
    digest_date: str,
    portfolio_tickers: List[str],
    interest_cluster: Dict[str, Any],
    evidence_markdown: str,
    config: Dict[str, Any],
    agent_steps: List[Dict[str, Any]],
) -> tuple[str, Optional[int], Optional[int], Optional[int], Optional[float]]:
    cfg = config or get_config_from_env()
    llm = get_llm("quick", cfg)

    class _Out(BaseModel):
        markdown_report: str = Field(
            description="Complete markdown report for the user (title, sections, tickers)."
        )

    user_msg = prompts.build_stocks_discovery_writer_prompt(
        span_label=span_label,
        digest_date=digest_date,
        portfolio_tickers=portfolio_tickers,
        interest_cluster=interest_cluster,
        evidence_markdown=evidence_markdown,
    )
    message = HumanMessage(content=prompts.STOCKS_DISCOVERY_WRITER_SYSTEM + "\n\n" + user_msg)

    input_tokens = output_tokens = total_tokens = None
    cost_usd = None

    try:
        from langchain_community.callbacks import get_openai_callback  # type: ignore[import]
    except Exception:
        get_openai_callback = None  # type: ignore[assignment]

    text = ""
    if get_openai_callback is not None:
        with get_openai_callback() as cb:  # type: ignore[misc]
            chain = llm.with_structured_output(_Out)
            result = chain.invoke([message])
            text = (getattr(result, "markdown_report", None) or "").strip()
            input_tokens = getattr(cb, "prompt_tokens", None)
            output_tokens = getattr(cb, "completion_tokens", None)
            total_tokens = getattr(cb, "total_tokens", None)
            cost_usd = getattr(cb, "total_cost", None)
    else:
        chain = llm.with_structured_output(_Out)
        result = chain.invoke([message])
        text = (getattr(result, "markdown_report", None) or "").strip()

    agent_steps.append(
        make_agent_step(
            agent="Stocks Discovery Writer",
            phase="synthesis",
            kind="llm_call",
            status="completed" if text else "failed",
            summary="LLM wrote stocks discovery markdown report",
            message_preview=message.content[:8000],
            output_preview={"narrative_chars": len(text)},
        )
    )
    return text, input_tokens, output_tokens, total_tokens, cost_usd


def run_stocks_discovery(
    user_id: int,
    digest_date: str,
    db: Any,
    *,
    max_priority_tickers: int = 5,
    fetcher: Optional[Any] = None,
    span_type: SpanType = "daily",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> StocksDiscoveryRunResult:
    """
    Build digest context (algorithmic), rank discovery candidates, run LLM writer, return persist-ready payload.
    """
    span_type, start_date, end_date, span_trading_days = resolve_span(
        digest_date, span_type, start_date, end_date
    )
    span_label = "Weekly" if span_type == "weekly" else "Daily"
    lb = digest_lookback_days(span_trading_days)

    if fetcher is None:
        _ensure_backend_import_path()
        from services.info_fetcher import get_info_fetcher  # type: ignore[import-not-found]

        fetcher = get_info_fetcher()

    state = DigestWorkflowState(
        user_id=user_id,
        digest_date=digest_date,
        span_type=span_type,
        start_date=start_date,
        end_date=end_date,
        period_label="today" if span_type == "daily" else "this week",
        max_priority_tickers=max_priority_tickers,
        db=db,
        config=config or {},
    )

    agent_steps: List[Dict[str, Any]] = []

    ctx = build_digest_context(
        user_id=user_id,
        digest_date=digest_date,
        max_priority_tickers=max_priority_tickers,
        db=db,
        fetcher=fetcher,
        start_date=start_date,
        end_date=end_date,
        span_trading_days=span_trading_days,
    )
    state.digest_context = ctx

    agent_steps.append(
        make_agent_step(
            agent="Digest Context Builder",
            phase="data_collection",
            kind="context",
            status="completed",
            summary="Built digest context",
            output_preview={
                "portfolio_tickers": ctx.tickers,
                "priority_tickers": ctx.priority_tickers,
                "attention_scores": ctx.attention_scores,
            },
        )
    )

    interest_cluster, discovered_tickers, discovered_ticker_events, discovered_ticker_info, det_steps = (
        run_deterministic_discovery(ctx, fetcher, digest_date, lookback_days=lb)
    )
    agent_steps.extend(det_steps)

    events_json = serialize_event_summaries(discovered_ticker_events)

    evidence_md = _evidence_markdown_for_llm(
        discovered_tickers,
        discovered_ticker_events,
        discovered_ticker_info,
    )

    narrative = ""
    in_tok = out_tok = tot_tok = None
    cost = None
    try:
        narrative, in_tok, out_tok, tot_tok, cost = _run_llm_writer(
            span_label=span_label,
            digest_date=digest_date,
            portfolio_tickers=list(ctx.tickers or []),
            interest_cluster=dict(interest_cluster or {}),
            evidence_markdown=evidence_md,
            config=config or {},
            agent_steps=agent_steps,
        )
    except Exception as e:
        logger.warning("Stocks discovery LLM writer failed, using fallback markdown: %s", e)
        agent_steps.append(
            make_agent_step(
                agent="Stocks Discovery Writer",
                phase="synthesis",
                kind="llm_call",
                status="failed",
                summary="LLM writer failed; fallback markdown used",
                output_preview={"error": str(e)},
            )
        )

    if not narrative.strip():
        narrative = stocks_discovery_payload_to_markdown(
            digest_date=digest_date,
            span_type=str(span_type),
            interest_cluster=interest_cluster,
            discovered_tickers=discovered_tickers,
            discovered_ticker_events=events_json,
            discovered_ticker_info=discovered_ticker_info,
        )

    return StocksDiscoveryRunResult(
        digest_context=ctx,
        narrative_markdown=narrative,
        agent_steps=agent_steps,
        interest_cluster=dict(interest_cluster or {}),
        discovered_tickers=list(discovered_tickers),
        discovered_ticker_events_json=events_json,
        discovered_ticker_info=dict(discovered_ticker_info or {}),
        input_tokens=in_tok,
        output_tokens=out_tok,
        total_tokens=tot_tok,
        cost_usd=cost,
    )
