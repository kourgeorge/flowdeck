#!/usr/bin/env python3
"""
Standalone analysis runner for Node backend. Invoked as:
  python backend/run_analysis_standalone.py --ticker AAPL --analysis-date 2025-02-08 --info-service-url http://127.0.0.1:8002 ...

Creates an Execution (execution_id) via token_service.record_analysis_run, uses that id for the results directory and reports.
Streams NDJSON progress to stdout. Writes reports to DB via save_report. Logs go to stderr.
"""

import argparse
import asyncio
import functools
import json
import logging
import os
import sys
import threading
from pathlib import Path
from datetime import datetime, timezone

HEARTBEAT_INTERVAL_SEC = 5

logger = logging.getLogger(__name__)

# Ensure repo root and backend are on path (script run as python backend/run_analysis_standalone.py)
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
for p in (str(REPO_ROOT), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from ai_engine.llm_provider import configured_provider, get_config_from_env
from ai_engine.tradingagents.graph.trading_graph import TradingAgentsGraph
from ai_engine.tradingagents.default_config import DEFAULT_CONFIG

# Backend services for report saving, and email notifications
from services.report_service import save_report
from services.email_service import notify_subscribers_new_report
from database import init_db
from services import analysis_report_helpers as report_helpers


def _ensure_data_gateway() -> None:
    """Set up the shared data gateway, which only backend/main.py does on import.

    Without it every get_data_gateway() call raises, so the quote and event-signal lookups
    quietly come back empty. An empty event signal means trader_investment_plan is saved
    without event_score, and the event monitor then skips this ticker for lack of a baseline.
    """
    from data_layer import get_data_gateway, init_data_gateway
    try:
        get_data_gateway()
        return
    except RuntimeError:
        pass
    try:
        from data_layer.market import MarketDataLayer
        from services.edgar_service import get_edgar_service
        from services.report_service import ReportService
        init_data_gateway(market=MarketDataLayer(), reports=ReportService(), edgar=get_edgar_service())
    except Exception as e:
        logger.warning("Could not initialize data gateway; quote and event signal will be missing: %s", e)


_progress_log = report_helpers.progress_log
extract_content_string = report_helpers.extract_content_string


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
    parser.add_argument("--llm-provider", default="", help="LLM provider (default: LLM_PROVIDER from the environment)")
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
    _ensure_data_gateway()
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
    env_cfg = get_config_from_env(overrides={"llm_provider": args.llm_provider.strip().lower() or configured_provider()})
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
        "Neutral Researcher": "pending",
        "Research Manager": "pending",
        "Trader": "pending",
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

    _get_or_extract_takeaways = functools.partial(
        report_helpers.get_or_extract_takeaways,
        _report_takeaways,
        analysis_run_id=analysis_run_id,
    )
    _build_report_json = functools.partial(
        report_helpers.build_report_json,
        analysis_date=analysis_date,
        generated_at=generated_at,
        models_used=models_used,
    )
    _get_report_resources = report_helpers.get_report_resources
    _get_report_agent_steps = report_helpers.get_report_agent_steps

    analysis_quote_meta = report_helpers.get_analysis_quote_meta(ticker)
    analysis_event_meta = report_helpers.get_analysis_event_meta(ticker, analysis_date)

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

    async def run() -> None:
        # Assigned when the investment_plan chunk arrives; without this they would be
        # locals of run() and the trader log line and email step would raise
        # UnboundLocalError on a run that never produced an investment plan.
        nonlocal final_recommendation, final_confidence
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
                    agent_statuses["Neutral Researcher"] = "completed"
                    agent_statuses["Research Manager"] = "completed"
                    agent_statuses["Trader"] = "in_progress"
                    _progress_log("Bull/Bear/Neutral/Research Manager completed → Trader started")

                if chunk.get("investment_plan") and "investment_plan" not in _written_reports:
                    bull = chunk.get("bull_summary") or []
                    bear = chunk.get("bear_summary") or []
                    neutral = chunk.get("neutral_summary") or []
                    content = chunk["investment_plan"]
                    reports["investment_plan"] = content
                    inv_takeaways = _get_or_extract_takeaways("investment_plan", content, chunk)
                    # Research Manager now emits the authoritative BUY/SELL/HOLD; conviction drives confidence.
                    rec_score = chunk.get("recommendation_score")
                    final_recommendation = chunk.get("recommendation") or chunk.get("trader_recommendation")
                    final_confidence = (rec_score / 5.0) if rec_score is not None else None
                    # build_report_json returns {"metadata": ..., "content": ...}; save only the
                    # inner metadata, as analysis_service does, or every field lands under
                    # metadata.metadata and the frontend finds no score/recommendation.
                    meta = _build_report_json(
                        content, rec_score, "Conviction Score", inv_takeaways,
                        recommendation=final_recommendation,
                        confidence=final_confidence,
                        expected_return_pct=chunk.get("expected_return_pct"),
                        bear_case_return_pct=chunk.get("bear_case_return_pct"),
                        bull_case_return_pct=chunk.get("bull_case_return_pct"),
                        current_price=analysis_quote_meta.get("current_price"),
                        currency=analysis_quote_meta.get("currency"),
                    )["metadata"]
                    usage = (chunk.get("report_usage") or {}).get("investment_plan")
                    if usage:
                        meta["input_tokens"] = usage.get("input_tokens")
                        meta["output_tokens"] = usage.get("output_tokens")
                        meta["total_tokens"] = usage.get("total_tokens")
                        meta["cost_usd"] = usage.get("cost_usd")
                        meta["per_call"] = usage.get("per_call", [])
                    meta["resources"] = _get_report_resources(chunk, "investment_plan")
                    meta["agent_steps"] = _get_report_agent_steps(chunk, "investment_plan")
                    _written_reports.add("investment_plan")
                    save_report(
                        analysis_run_id,
                        "investment_plan",
                        content=content,
                        metadata={**meta, "bull_viewpoint": bull, "bear_viewpoint": bear, "neutral_viewpoint": neutral},
                    )
                    _progress_log(f"Investment plan ready → {final_recommendation or ''} → saved")

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
                        # Same fields analysis_service stores: the event monitor reads event_score
                        # from this report as its baseline and skips tickers that lack it.
                        event_score=analysis_event_meta.get("event_score"),
                        dominant_events=analysis_event_meta.get("dominant_events"),
                    )
                    # Trader is the terminal node; the run ends here.
                    _progress_log(f"Trader completed → {final_recommendation or ''} → analysis finished")

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
