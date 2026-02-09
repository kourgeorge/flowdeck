#!/usr/bin/env python3
"""
Standalone analysis runner for Node backend. Invoked as:
  python backend/run_analysis_standalone.py --ticker AAPL --analysis-date 2025-02-08 --analysis-id <uuid> --info-service-url http://127.0.0.1:8002 ...

Streams NDJSON progress to stdout. Writes reports to DB via save_report. Logs go to stderr.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Ensure repo root and backend are on path (script run as python backend/run_analysis_standalone.py)
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
for p in (str(REPO_ROOT), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# Backend services for key_takeaways and content extraction
from services.key_takeaways import extract_key_takeaways
from services.report_service import save_report
from database import init_db

try:
    from tradingagents.agents.utils.insight_extraction import extract_key_takeaways_structured
except ImportError:
    extract_key_takeaways_structured = None


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
    parser.add_argument("--analysis-id", required=True, help="Analysis UUID from Node")
    parser.add_argument("--analysts", default="market,news,fundamentals", help="Comma-separated analysts")
    parser.add_argument("--research-depth", type=int, default=5, help="Max debate rounds")
    parser.add_argument("--llm-provider", default="azure", help="LLM provider")
    parser.add_argument("--results-dir", default="results", help="Results directory (absolute or relative to repo)")
    parser.add_argument("--info-service-url", required=True, help="Node backend URL for /api/data")
    parser.add_argument("--shallow-thinker", default="", help="Azure quick-thinking model (optional)")
    parser.add_argument("--deep-thinker", default="", help="Azure deep-thinking model (optional)")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    analysis_date = args.analysis_date.strip()
    analysts = [a.strip() for a in args.analysts.split(",") if a.strip()]
    if not analysts:
        analysts = ["market", "news", "fundamentals"]

    os.environ["INFO_SERVICE_URL"] = args.info_service_url.strip().rstrip("/")

    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    results_dir = Path(args.results_dir)
    if not results_dir.is_absolute():
        results_dir = REPO_ROOT / results_dir
    # Include time in run id so multiple runs per day don't overwrite
    report_dir = results_dir / ticker / run_id / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    log_file = results_dir / ticker / run_id / "message_tool.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.touch(exist_ok=True)

    config = DEFAULT_CONFIG.copy()
    config["max_debate_rounds"] = args.research_depth
    config["max_risk_discuss_rounds"] = args.research_depth
    config["llm_provider"] = args.llm_provider.lower()
    config["results_dir"] = str(results_dir)
    config["info_service_url"] = args.info_service_url.strip().rstrip("/")

    if args.llm_provider.lower() == "azure":
        if args.shallow_thinker:
            config["quick_think_llm"] = args.shallow_thinker
        else:
            config["quick_think_llm"] = os.getenv("AZURE_QUICK_THINK_MODEL", "gpt-4o-mini-2024-07-18")
        if args.deep_thinker:
            config["deep_think_llm"] = args.deep_thinker
        else:
            config["deep_think_llm"] = os.getenv("AZURE_DEEP_THINK_MODEL", "gpt-4o-2024-08-06")

    init_db()  # Ensure SQLite tables exist
    logger.info(
        "Standalone analysis starting analysis_id=%s ticker=%s date=%s run_id=%s models=%s",
        args.analysis_id, ticker, analysis_date, run_id,
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
        "Social Analyst": "pending",
        "News Analyst": "pending",
        "Fundamentals Analyst": "pending",
        "Bull Researcher": "pending",
        "Bear Researcher": "pending",
        "Research Manager": "pending",
        "Trader": "pending",
        "Risky Analyst": "pending",
        "Neutral Analyst": "pending",
        "Safe Analyst": "pending",
        "Portfolio Manager": "pending",
    }
    if "market" in analysts:
        agent_statuses["Market Analyst"] = "in_progress"
    elif "social" in analysts:
        agent_statuses["Social Analyst"] = "in_progress"
    elif "news" in analysts:
        agent_statuses["News Analyst"] = "in_progress"
    elif "fundamentals" in analysts:
        agent_statuses["Fundamentals Analyst"] = "in_progress"

    reports: dict = {}

    def _takeaways(content):
        if extract_key_takeaways_structured and graph:
            try:
                return extract_key_takeaways_structured(graph.deep_thinking_llm, content)
            except Exception:
                pass
        return extract_key_takeaways(content)

    def _build_report_json(content, score, score_label, key_takeaways_list, **extra):
        meta = {"score_label": score_label or "Score", "analysis_date": analysis_date, "generated_at": generated_at, "models_used": models_used}
        if score is not None:
            meta["score"] = score
        if key_takeaways_list:
            meta["key_takeaways"] = [str(t or "").strip() for t in key_takeaways_list[:5] if t]
        meta.update({k: v for k, v in extra.items() if v is not None})
        return {"metadata": meta, "content": content or ""}

    def _write_report(key, content, score, label, **extra):
        try:
            data = _build_report_json(content, score, label, _takeaways(content), **extra)
            meta = data.get("metadata", {})
            meta.update({k: v for k, v in data.items() if k not in ("metadata", "content")})
            save_report(
                ticker=ticker,
                run_id=run_id,
                report_type=key,
                content=data.get("content", ""),
                metadata=meta,
            )
            logger.info("Report saved ticker=%s run_id=%s report_type=%s", ticker, run_id, key)
        except Exception as e:
            logger.exception("Failed to save report ticker=%s report_type=%s error=%s", ticker, key, e)
            raise

    async def run() -> None:
        try:
            init_agent_state = graph.propagator.create_initial_state(ticker, analysis_date)
            graph_args = graph.propagator.get_graph_args()

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
                    ("sentiment_report", "sentiment_report", "sentiment_score", "Sentiment Score", "Social Analyst"),
                    ("news_report", "news_report", "news_score", "News Score", "News Analyst"),
                    ("fundamentals_report", "fundamentals_report", "fundamentals_score", "Fundamentals Score", "Fundamentals Analyst"),
                ]
                for key, chunk_key, score_key, label, agent in _reports:
                    if chunk_key in chunk and chunk[chunk_key]:
                        c = chunk[chunk_key]
                        reports[key] = c
                        agent_statuses[agent] = "completed"
                        _write_report(key, c, chunk.get(score_key), label)
                        if key == "fundamentals_report":
                            agent_statuses["Bull Researcher"] = "in_progress"
                            agent_statuses["Bear Researcher"] = "in_progress"
                            agent_statuses["Research Manager"] = "in_progress"

                if chunk.get("investment_debate_state") and chunk["investment_debate_state"].get("judge_decision"):
                    agent_statuses["Bull Researcher"] = "completed"
                    agent_statuses["Bear Researcher"] = "completed"
                    agent_statuses["Research Manager"] = "completed"
                    agent_statuses["Trader"] = "in_progress"

                if chunk.get("investment_plan"):
                    bull = chunk.get("bull_summary") or []
                    bear = chunk.get("bear_summary") or []
                    content = chunk["investment_plan"]
                    reports["investment_plan"] = content
                    meta = _build_report_json(
                        content, chunk.get("recommendation_score"), "Recommendation Score", _takeaways(content),
                        expected_return_pct=chunk.get("expected_return_pct"),
                        bear_case_return_pct=chunk.get("bear_case_return_pct"),
                        bull_case_return_pct=chunk.get("bull_case_return_pct"),
                    )
                    save_report(
                        ticker=ticker,
                        run_id=run_id,
                        report_type="investment_plan",
                        content=content,
                        metadata={**meta, "bull_viewpoint": bull, "bear_viewpoint": bear},
                    )

                if chunk.get("trader_investment_plan"):
                    c = chunk["trader_investment_plan"]
                    reports["trader_investment_plan"] = c
                    agent_statuses["Trader"] = "completed"
                    _write_report("trader_investment_plan", c, None, "Trader Plan")
                    agent_statuses["Risky Analyst"] = "in_progress"
                    agent_statuses["Safe Analyst"] = "in_progress"
                    agent_statuses["Neutral Analyst"] = "in_progress"

                if chunk.get("risk_debate_state") and chunk["risk_debate_state"].get("judge_decision"):
                    agent_statuses["Risky Analyst"] = "completed"
                    agent_statuses["Safe Analyst"] = "completed"
                    agent_statuses["Neutral Analyst"] = "completed"
                    agent_statuses["Portfolio Manager"] = "in_progress"

                if chunk.get("final_trade_decision"):
                    agent_statuses["Portfolio Manager"] = "completed"
                    content = chunk["final_trade_decision"]
                    risky = chunk.get("risky_summary") or []
                    safe = chunk.get("safe_summary") or []
                    neutral = chunk.get("neutral_summary") or []
                    reports["final_trade_decision"] = content
                    rscore = chunk.get("risk_score")
                    kt = (chunk.get("final_report_key_takeaways") or [])[:5] or extract_key_takeaways(content)
                    meta = _build_report_json(
                        content, rscore, "Confidence", kt,
                        recommendation=chunk.get("recommendation"),
                        confidence=(rscore / 10.0) if rscore is not None else None,
                    )
                    save_report(
                        ticker=ticker,
                        run_id=run_id,
                        report_type="final_trade_decision",
                        content=content,
                        metadata={**meta, "risky_viewpoint": risky, "safe_viewpoint": safe, "neutral_viewpoint": neutral},
                    )

                emit({
                    "type": "progress",
                    "data": {
                        "agent_statuses": dict(agent_statuses),
                        "current_agent": None,
                        "reports": dict(reports),
                        "status": "running",
                    },
                })

            logger.info("Standalone analysis completed ticker=%s run_id=%s reports=%s", ticker, run_id, list(reports.keys()))
            emit({"type": "completed"})
        except Exception as e:
            logger.exception("Standalone analysis failed ticker=%s run_id=%s error=%s", ticker, run_id, e)
            emit({"type": "error", "error": str(e)})
            raise

    asyncio.run(run())


if __name__ == "__main__":
    main()
