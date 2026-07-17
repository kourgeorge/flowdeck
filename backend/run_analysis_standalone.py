#!/usr/bin/env python3
"""
Standalone analysis runner for Node backend. Invoked as:
  python backend/run_analysis_standalone.py --ticker AAPL --analysis-date 2025-02-08 --info-service-url http://127.0.0.1:8002 ...

Creates an Execution (execution_id) via token_service.record_analysis_run, uses that id for the results directory and reports.
Streams NDJSON progress to stdout. Writes reports to DB via save_report. Logs go to stderr.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

HEARTBEAT_INTERVAL_SEC = 5

logger = logging.getLogger(__name__)

# Ensure repo root and backend are on path (script run as python backend/run_analysis_standalone.py)
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
for p in (str(REPO_ROOT), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from ai_engine.llm_provider import get_config_from_env
from ai_engine.tradingagents.graph.trading_graph import TradingAgentsGraph
from ai_engine.tradingagents.default_config import DEFAULT_CONFIG
from ai_engine.tradingagents.agents.utils.trace_utils import sort_agent_steps

# Backend services for report saving, and email notifications
from services.report_service import save_report
from services.email_service import notify_subscribers_new_report
from database import init_db

def _normalize_takeaway_list(val) -> list:
    if not val:
        return []
    if not isinstance(val, (list, tuple)):
        return []
    return [str(x).strip() for x in val if x and str(x).strip()][:5]


_REPORT_TO_STATE_TAKEAWAYS_KEY = {
    "market_report": "market_key_takeaways",
    "sentiment_report": "sentiment_key_takeaways",
    "fundamentals_report": "fundamentals_key_takeaways",
    "technical_report": "technical_key_takeaways",
    "sec_report": "sec_key_takeaways",
    "valuation_report": "valuation_key_takeaways",
    "investment_plan": "investment_plan_key_takeaways",
    "trader_investment_plan": "trader_key_takeaways",
    "final_trade_decision": "final_report_key_takeaways",
}


def _progress_log(msg: str) -> None:
    """Print a progress line to stderr with timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Progress]:\t {ts} - {msg}", file=sys.stderr, flush=True)


def extract_content_string(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif item.get("type") == "tool_use":
                    text_parts.append(f"[Tool: {item.get('name', 'unknown')}]")
            else:
                text_parts.append(str(item))
        return " ".join(text_parts)
    return str(content)


def emit(line: dict) -> None:
    print(json.dumps(line), flush=True)


def main() -> None:
    # Configure logging to stderr (stdout is used for NDJSON progress)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )

    parser = argparse.ArgumentParser(description="Run TradingAgents analysis (standalone for Node backend)")
    parser.add_argument("--ticker", required=True, help="Ticker symbol")
    parser.add_argument("--analysis-date", required=True, help="Analysis date YYYY-MM-DD")
    parser.add_argument("--analysts", default="market,social,news,fundamentals,technical", help="Comma-separated analysts (social = sentiment/social media)")
    parser.add_argument("--research-depth", type=int, default=2, help="Max debate rounds")
    parser.add_argument("--llm-provider", default="azure", help="LLM provider")
    parser.add_argument("--results-dir", default="results", help="Results directory (absolute or relative to repo)")
    parser.add_argument("--info-service-url", required=True, help="Node backend URL for /api/data")
    parser.add_argument("--shallow-thinker", default="", help="Override quick-thinking model for this run (optional)")
    parser.add_argument("--deep-thinker", default="", help="Override deep-thinking model for this run (optional)")
    parser.add_argument("--initiator-email", default="", help="Email of user who started the analysis (notified when done)")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    analysis_date = args.analysis_date.strip()
    analysts = [a.strip() for a in args.analysts.split(",") if a.strip()]
    if not analysts:
        analysts = ["market", "social", "fundamentals", "technical", "sec", "valuation"]

    os.environ["INFO_SERVICE_URL"] = args.info_service_url.strip().rstrip("/")

    init_db()  # Ensure SQLite tables exist
    from services import token_service
    from database import SessionLocal
    db = SessionLocal()
    try:
        creator_id = token_service.get_system_user_id(db)
        analysis_run_id = token_service.record_analysis_run(creator_id, ticker, db)
    finally:
        db.close()

    results_dir = Path(args.results_dir)
    if not results_dir.is_absolute():
        results_dir = REPO_ROOT / results_dir
    run_dir_name = str(analysis_run_id)
    log_file = results_dir / ticker / run_dir_name / "message_tool.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.touch(exist_ok=True)

    config = DEFAULT_CONFIG.copy()
    config["max_debate_rounds"] = args.research_depth
    config["max_risk_discuss_rounds"] = args.research_depth
    config["results_dir"] = str(results_dir)
    config["info_service_url"] = args.info_service_url.strip().rstrip("/")
    env_cfg = get_config_from_env(overrides={"llm_provider": args.llm_provider.lower()})
    config.update(env_cfg)
    if args.shallow_thinker:
        config["quick_think_llm"] = args.shallow_thinker
    if args.deep_thinker:
        config["deep_think_llm"] = args.deep_thinker

    logger.info(
        "Standalone analysis starting analysis_run_id=%s ticker=%s date=%s models=%s",
        analysis_run_id, ticker, analysis_date,
        {"deep": config.get("deep_think_llm"), "quick": config.get("quick_think_llm")},
    )
    graph = TradingAgentsGraph(selected_analysts=analysts, config=config, debug=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    models_used = {
        "provider": config.get("llm_provider"),
        "deep_think": config.get("deep_think_llm"),
        "quick_think": config.get("quick_think_llm"),
    }

    agent_statuses = {
        "Market Analyst": "pending",
        "News & Sentiment Analyst": "pending",
        "Fundamentals Analyst": "pending",
        "Technical Analyst": "pending",
        "SEC Analyst": "pending",
        "Bull Researcher": "pending",
        "Bear Researcher": "pending",
        "Research Manager": "pending",
        "Trader": "pending",
        "Risky Analyst": "pending",
        "Neutral Analyst": "pending",
        "Safe Analyst": "pending",
        "Portfolio Manager": "pending",
    }
    analyst_status_map = {
        "market": "Market Analyst",
        "social": "News & Sentiment Analyst",
        "fundamentals": "Fundamentals Analyst",
        "technical": "Technical Analyst",
        "sec": "SEC Analyst",
    }
    first_selected = next((a for a in analysts if a in analyst_status_map), None)
    if first_selected:
        agent_statuses[analyst_status_map[first_selected]] = "in_progress"

    reports: dict = {}
    final_recommendation = None
    final_confidence = None
    initiator_email = (args.initiator_email or "").strip() or None

    # Store extracted takeaways to avoid re-extraction
    _report_takeaways = {}

    def _get_or_extract_takeaways(report_key, content, chunk=None):
        """Use graph structured takeaways only."""
        if report_key in _report_takeaways:
            logger.info(
                "Key takeaways skipped (cached) analysis_run_id=%s report_type=%s",
                analysis_run_id, report_key,
            )
            return _report_takeaways[report_key]
        state_key = _REPORT_TO_STATE_TAKEAWAYS_KEY.get(report_key)
        if chunk is not None and state_key:
            preferred = _normalize_takeaway_list(chunk.get(state_key))
            if preferred:
                _report_takeaways[report_key] = preferred
                return preferred
        takeaways: list = []
        _report_takeaways[report_key] = takeaways
        return takeaways

    def _build_report_json(content, score, score_label, key_takeaways_list, **extra):
        meta = {"score_label": score_label or "Score", "analysis_date": analysis_date, "generated_at": generated_at, "models_used": models_used}
        if score is not None:
            meta["score"] = score
        if key_takeaways_list:
            meta["key_takeaways"] = [str(t or "").strip() for t in key_takeaways_list[:5] if t]
        meta.update({k: v for k, v in extra.items() if v is not None})
        return {"metadata": meta, "content": content or ""}

    def _get_analysis_quote_meta() -> dict[str, object]:
        try:
            from data_layer import get_data_gateway
            quote = get_data_gateway().get_quote(ticker)
        except Exception:
            return {}
        if not isinstance(quote, dict):
            return {}
        current_price = quote.get("current_price")
        currency = quote.get("currency")
        meta: dict[str, object] = {}
        if isinstance(current_price, (int, float)):
            meta["current_price"] = float(current_price)
        if isinstance(currency, str) and currency.strip():
            meta["currency"] = currency.strip().upper()
        return meta

    analysis_quote_meta = _get_analysis_quote_meta()

    def _write_report(key, content, score, label, llm_usage=None, resources=None, chunk=None, **extra):
        try:
            takeaways = _get_or_extract_takeaways(key, content, chunk)
            data = _build_report_json(content, score, label, takeaways, **extra)
            meta = data.get("metadata", {})
            meta.update({k: v for k, v in data.items() if k not in ("metadata", "content")})
            if llm_usage:
                meta["input_tokens"] = llm_usage.get("input_tokens")
                meta["output_tokens"] = llm_usage.get("output_tokens")
                meta["total_tokens"] = llm_usage.get("total_tokens")
                meta["cost_usd"] = llm_usage.get("cost_usd")
            if resources is not None:
                meta["resources"] = resources
            meta["agent_steps"] = _get_report_agent_steps(chunk, key)
            save_report(
                analysis_run_id,
                key,
                content=data.get("content", ""),
                metadata=meta,
            )
            logger.info("Report saved ticker=%s analysis_run_id=%s report_type=%s", ticker, analysis_run_id, key)
        except Exception as e:
            logger.exception("Failed to save report ticker=%s report_type=%s error=%s", ticker, key, e)
            raise

    def _get_report_resources(
        chunk: Optional[Dict[str, Any]],
        report_key: str,
    ) -> List[Dict[str, Any]]:
        if not isinstance(chunk, dict):
            return []
        by_report = chunk.get("report_resources_by_report")
        if isinstance(by_report, dict):
            specific = by_report.get(report_key)
            if isinstance(specific, list):
                return specific
        resources = chunk.get("report_resources")
        return resources if isinstance(resources, list) else []

    def _get_report_agent_steps(chunk: dict | None, report_key: str) -> list[dict]:
        if not isinstance(chunk, dict):
            return []
        by_report = chunk.get("report_steps_by_report")
        if isinstance(by_report, dict):
            specific = by_report.get(report_key)
            if isinstance(specific, list):
                return sort_agent_steps(specific)
        return []

    async def run() -> None:
        stop_heartbeat = threading.Event()
        heartbeat_thread = None

        def heartbeat_loop() -> None:
            while not stop_heartbeat.wait(timeout=HEARTBEAT_INTERVAL_SEC):
                emit({
                    "type": "progress",
                    "data": {
                        "agent_statuses": dict(agent_statuses),
                        "current_agent": None,
                        "reports": dict(reports),
                        "status": "running",
                        "heartbeat": True,
                    },
                })

        try:
            init_agent_state = graph.propagator.create_initial_state(ticker, analysis_date)
            graph_args = graph.propagator.get_graph_args()
            _progress_log(f"Analysis started ticker={ticker} analysis_run_id={analysis_run_id} analysts={analysts}")
            analyst_to_report_key = {
                "market": "market_report",
                "social": "sentiment_report",
                "fundamentals": "fundamentals_report",
                "technical": "technical_report",
                "sec": "sec_report",
                "valuation": "valuation_report",
            }
            last_analyst_report_key = None
            for analyst in reversed(analysts):
                report_key = analyst_to_report_key.get(analyst)
                if report_key:
                    last_analyst_report_key = report_key
                    break

            heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
            heartbeat_thread.start()

            # Track which reports have been written to avoid duplicate processing
            _written_reports = set()

            for chunk in graph.graph.stream(init_agent_state, **graph_args):
                if chunk.get("messages"):
                    last_message = chunk["messages"][-1]
                    content = extract_content_string(getattr(last_message, "content", last_message))
                    msg_type = "Reasoning" if hasattr(last_message, "content") else "System"
                    ts = datetime.now().strftime("%H:%M:%S")
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write(f"{ts} [{msg_type}] {content.replace(chr(10), ' ')}\n")

                _reports = [
                    ("market_report", "market_report", "market_score", "Market Score", "Market Analyst"),
                    ("sentiment_report", "sentiment_report", "sentiment_score", "Sentiment Score", "News & Sentiment Analyst"),
                    ("fundamentals_report", "fundamentals_report", "fundamentals_score", "Fundamentals Score", "Fundamentals Analyst"),
                    ("technical_report", "technical_report", "technical_score", "Technical Score", "Technical Analyst"),
                    ("sec_report", "sec_report", "sec_score", "SEC Score", "SEC Analyst"),
                    ("valuation_report", "valuation_report", "valuation_score", "Valuation Score", "Valuation Analyst"),
                ]
                for key, chunk_key, score_key, label, agent in _reports:
                    if chunk_key in chunk and chunk[chunk_key] and key not in _written_reports:
                        c = chunk[chunk_key]
                        reports[key] = c
                        agent_statuses[agent] = "completed"
                        report_usage = chunk.get("report_usage") or {}
                        _write_report(
                            key,
                            c,
                            chunk.get(score_key),
                            label,
                            llm_usage=report_usage.get(key),
                            resources=_get_report_resources(chunk, key),
                            chunk=chunk,
                            fair_value_bear=chunk.get("fair_value_bear") if key == "valuation_report" else None,
                            fair_value_base=chunk.get("fair_value_base") if key == "valuation_report" else None,
                            fair_value_bull=chunk.get("fair_value_bull") if key == "valuation_report" else None,
                            current_discount_pct=chunk.get("current_discount_pct") if key == "valuation_report" else None,
                            valuation_conviction=chunk.get("valuation_conviction") if key == "valuation_report" else None,
                            valuation_key_assumptions=chunk.get("valuation_key_assumptions") if key == "valuation_report" else None,
                            valuation_summary=chunk.get("valuation_summary") if key == "valuation_report" else None,
                            valuation_bridge=chunk.get("valuation_bridge") if key == "valuation_report" else None,
                            valuation_sensitivity=chunk.get("valuation_sensitivity") if key == "valuation_report" else None,
                            dcf=chunk.get("dcf") if key == "valuation_report" else None,
                            pe_comps=chunk.get("pe_comps") if key == "valuation_report" else None,
                            ev_ebitda=chunk.get("ev_ebitda") if key == "valuation_report" else None,
                        )
                        _written_reports.add(key)
                        _progress_log(f"{agent} completed → {key} saved")
                        if last_analyst_report_key and key == last_analyst_report_key:
                            agent_statuses["Bull Researcher"] = "in_progress"
                            agent_statuses["Bear Researcher"] = "in_progress"
                            agent_statuses["Research Manager"] = "in_progress"
                            _progress_log("Bull/Bear researchers & Research Manager started")

                if chunk.get("investment_debate_state") and chunk["investment_debate_state"].get("judge_decision"):
                    agent_statuses["Bull Researcher"] = "completed"
                    agent_statuses["Bear Researcher"] = "completed"
                    agent_statuses["Research Manager"] = "completed"
                    agent_statuses["Trader"] = "in_progress"
                    _progress_log("Bull/Bear/Research Manager completed → Trader started")

                if chunk.get("investment_plan") and "investment_plan" not in _written_reports:
                    bull = chunk.get("bull_summary") or []
                    bear = chunk.get("bear_summary") or []
                    content = chunk["investment_plan"]
                    reports["investment_plan"] = content
                    inv_takeaways = _get_or_extract_takeaways("investment_plan", content, chunk)
                    meta = _build_report_json(
                        content, chunk.get("recommendation_score"), "Conviction Score", inv_takeaways,
                        expected_return_pct=chunk.get("expected_return_pct"),
                        bear_case_return_pct=chunk.get("bear_case_return_pct"),
                        bull_case_return_pct=chunk.get("bull_case_return_pct"),
                        current_price=analysis_quote_meta.get("current_price"),
                        currency=analysis_quote_meta.get("currency"),
                    )
                    usage = (chunk.get("report_usage") or {}).get("investment_plan")
                    if usage:
                        meta["input_tokens"] = usage.get("input_tokens")
                        meta["output_tokens"] = usage.get("output_tokens")
                        meta["total_tokens"] = usage.get("total_tokens")
                        meta["cost_usd"] = usage.get("cost_usd")
                    meta["agent_steps"] = _get_report_agent_steps(chunk, "investment_plan")
                    _written_reports.add("investment_plan")
                    save_report(
                        analysis_run_id,
                        "investment_plan",
                        content=content,
                        metadata={**meta, "bull_viewpoint": bull, "bear_viewpoint": bear, "resources": _get_report_resources(chunk, "investment_plan")},
                    )
                    _progress_log("Investment plan ready → saved")

                if chunk.get("trader_investment_plan"):
                    c = chunk["trader_investment_plan"]
                    reports["trader_investment_plan"] = c
                    agent_statuses["Trader"] = "completed"
                    report_usage = chunk.get("report_usage") or {}
                    _write_report(
                        "trader_investment_plan",
                        c,
                        None,
                        "Trader Plan",
                        llm_usage=report_usage.get("trader_investment_plan"),
                        recommendation=chunk.get("trader_recommendation"),
                        resources=_get_report_resources(chunk, "trader_investment_plan"),
                        chunk=chunk,
                    )
                    agent_statuses["Risky Analyst"] = "in_progress"
                    agent_statuses["Safe Analyst"] = "in_progress"
                    agent_statuses["Neutral Analyst"] = "in_progress"
                    _progress_log("Trader completed → Risk debate (Risky/Safe/Neutral) started")

                if chunk.get("risk_debate_state") and chunk["risk_debate_state"].get("judge_decision"):
                    agent_statuses["Risky Analyst"] = "completed"
                    agent_statuses["Safe Analyst"] = "completed"
                    agent_statuses["Neutral Analyst"] = "completed"
                    agent_statuses["Portfolio Manager"] = "in_progress"
                    _progress_log("Risk analysts completed → Portfolio Manager started")

                if chunk.get("final_trade_decision"):
                    agent_statuses["Portfolio Manager"] = "completed"
                    content = chunk["final_trade_decision"]
                    risky = chunk.get("risky_summary") or []
                    safe = chunk.get("safe_summary") or []
                    neutral = chunk.get("neutral_summary") or []
                    reports["final_trade_decision"] = content
                    rscore = chunk.get("risk_score")
                    final_recommendation = chunk.get("recommendation") or chunk.get("trader_recommendation")
                    final_confidence = (rscore / 10.0) if rscore is not None else None
                    kt = _get_or_extract_takeaways("final_trade_decision", content, chunk)
                    meta = _build_report_json(
                        content, rscore, "Confidence", kt,
                        recommendation=chunk.get("recommendation"),
                        confidence=(rscore / 10.0) if rscore is not None else None,
                    )
                    usage = (chunk.get("report_usage") or {}).get("final_trade_decision")
                    if usage:
                        meta["input_tokens"] = usage.get("input_tokens")
                        meta["output_tokens"] = usage.get("output_tokens")
                        meta["total_tokens"] = usage.get("total_tokens")
                        meta["cost_usd"] = usage.get("cost_usd")
                    meta["agent_steps"] = _get_report_agent_steps(chunk, "final_trade_decision")
                    save_report(
                        analysis_run_id,
                        "final_trade_decision",
                        content=content,
                        metadata={**meta, "risky_viewpoint": risky, "safe_viewpoint": safe, "neutral_viewpoint": neutral, "resources": _get_report_resources(chunk, "final_trade_decision")},
                    )
                    rec = final_recommendation or ""
                    _progress_log(f"Final trade decision ready → {rec}")

                emit({
                    "type": "progress",
                    "data": {
                        "agent_statuses": dict(agent_statuses),
                        "current_agent": None,
                        "reports": dict(reports),
                        "status": "running",
                    },
                })

            logger.info("Standalone analysis completed ticker=%s analysis_run_id=%s reports=%s", ticker, analysis_run_id, list(reports.keys()))
            print(f"[ANALYSIS COMPLETED] ticker={ticker} analysis_run_id={analysis_run_id} reports={list(reports.keys())}", file=sys.stderr, flush=True)
            try:
                notify_subscribers_new_report(
                    ticker=ticker,
                    execution_id=analysis_run_id,
                    recommendation=final_recommendation,
                    confidence=final_confidence,
                    initiator_email=initiator_email,
                )
            except Exception as e:
                logger.warning("Failed to send report notification emails: %s", e)
            emit({"type": "completed"})
        except Exception as e:
            print(f"\n[ANALYSIS STOPPED - EXCEPTION] ticker={ticker} analysis_run_id={analysis_run_id}\n  {type(e).__name__}: {e}\n", file=sys.stderr, flush=True)
            logger.exception("Standalone analysis failed ticker=%s analysis_run_id=%s error=%s", ticker, analysis_run_id, e)
            emit({"type": "error", "error": str(e)})
            raise
        finally:
            stop_heartbeat.set()
            if heartbeat_thread is not None:
                heartbeat_thread.join(timeout=HEARTBEAT_INTERVAL_SEC + 1)

    asyncio.run(run())


if __name__ == "__main__":
    main()
