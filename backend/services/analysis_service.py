"""Service to trigger TradingAgents analysis."""

import asyncio
import logging
import os
import sys
import datetime
import threading
from typing import Dict, Optional, Callable, Any
from pathlib import Path
from dotenv import load_dotenv
import re

logger = logging.getLogger(__name__)

from services.data_cache import (
    clear_stop_requested,
    delete_analysis_status,
    get_analysis_status as get_analysis_status_from_cache,
    get_stop_requested,
    set_analysis_status,
)
from services.key_takeaways import extract_key_takeaways
from services.report_service import save_report
from services.email_service import notify_subscribers_new_report

try:
    from ai_engine.tradingagents.agents.utils.insight_extraction import extract_key_takeaways_structured
except ImportError:
    extract_key_takeaways_structured = None

# Load environment variables from .env file (backend or repo root)
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)
# Also load from repo root when running from backend
load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / '.env')

from ai_engine.tradingagents.graph.trading_graph import TradingAgentsGraph
from ai_engine.tradingagents.default_config import DEFAULT_CONFIG
from ai_engine.llm_provider import get_config_from_env


def _has_sec_data(ticker: str) -> bool:
    """Return True only if the ticker has SEC EDGAR data (10-K/10-Q filings). Run SEC analyst only then."""
    try:
        from data_layer import get_data_gateway
        result = get_data_gateway().get_edgar_filings(ticker)
        if result.get("error"):
            return False
        filings = result.get("filings") or []
        return len(filings) > 0
    except Exception:
        return False


# Keys that indicate real company fundamental data (from get_fundamentals_core / yfinance info)
_FUNDAMENTALS_MEANINGFUL_KEYS = frozenset({
    "MarketCapitalization", "TrailingPE", "ForwardPE", "RevenueTTM", "Sector",
    "EnterpriseValue", "PriceToBookRatio", "EBITDA", "ProfitMargin", "BookValue",
})


def _has_fundamental_data(ticker: str) -> bool:
    """Return True only if the ticker has fetchable company fundamental data (run fundamentals analyst only then)."""
    try:
        from data_layer import get_data_gateway
        result = get_data_gateway().get_fundamentals(ticker)
        fundamentals = result.get("fundamentals") or {}
        if not isinstance(fundamentals, dict) or not fundamentals:
            return False
        return bool(_FUNDAMENTALS_MEANINGFUL_KEYS & set(fundamentals.keys()))
    except Exception:
        return False


def _progress_log(msg: str) -> None:
    """Print a progress line to stderr with timestamp."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Progress]:\t {ts} - {msg}", file=sys.stderr, flush=True)


def extract_content_string(content):
    """Extract string content from various message formats."""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get('type') == 'text':
                    text_parts.append(item.get('text', ''))
                elif item.get('type') == 'tool_use':
                    text_parts.append(f"[Tool: {item.get('name', 'unknown')}]")
            else:
                text_parts.append(str(item))
        return ' '.join(text_parts)
    else:
        return str(content)


class AnalysisService:
    """Service for running TradingAgents analyses."""
    
    def __init__(self, results_dir: str = "results"):
        self.results_dir = Path(results_dir)
        if not self.results_dir.is_absolute():
            backend_dir = Path(__file__).parent.parent
            self.results_dir = backend_dir.parent / self.results_dir  # repo root
        # Keep minimal in-memory state for active analysis context (callbacks, graph objects)
        # Status queries read from filesystem only. Key = analysis_run_id (AnalysisRun.id).
        self.running_analyses: Dict[int, Dict] = {}
        self._lock = threading.Lock()  # Lock to prevent race conditions
    
    def _persist_analysis_status(self, analysis_run_id: int) -> None:
        """Write current status to shared cache DB (visible to all workers)."""
        analysis_info = self.running_analyses.get(analysis_run_id)
        if not analysis_info:
            return
        status_data = {
            "analysis_run_id": analysis_run_id,
            "ticker": analysis_info["ticker"],
            "date": analysis_info["date"],
            "status": analysis_info["status"],
            "agent_statuses": analysis_info.get("agent_statuses", {}),
            "current_agent": analysis_info.get("current_agent"),
            "updated_at": datetime.datetime.utcnow().isoformat(),
        }
        set_analysis_status("ticker", analysis_run_id, status_data)

    def get_running_analysis_run_id(self, ticker: str, analysis_date: str) -> Optional[int]:
        """Return analysis_run_id if an analysis is already running for this (ticker, date)."""
        ticker_upper = ticker.upper()
        for run_id, info in self.running_analyses.items():
            if info.get("status") == "running" and info.get("ticker") == ticker_upper and info.get("date") == analysis_date:
                return run_id
        return None
    
    def start_analysis(
        self,
        ticker: str,
        analysis_date: str,
        analysis_run_id: int,
        analysts: list = None,
        research_depth: int = 5,
        llm_provider: str = "azure",
        backend_url: Optional[str] = None,
        shallow_thinker: Optional[str] = None,
        deep_thinker: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        initiator_email: Optional[str] = None,
    ) -> tuple[int, bool]:
        """Start a new analysis and return (analysis_run_id, existing). existing=True if already running for (ticker, date)."""
        ticker = ticker.upper()
        
        # Use lock to prevent race condition when checking and starting analysis
        with self._lock:
            existing_run_id = self.get_running_analysis_run_id(ticker, analysis_date)
            if existing_run_id is not None:
                logger.info(
                    "Analysis already running analysis_run_id=%s ticker=%s date=%s",
                    existing_run_id, ticker, analysis_date,
                )
                return (existing_run_id, True)
            
            logger.info(
                "Starting analysis analysis_run_id=%s ticker=%s date=%s analysts=%s",
                analysis_run_id, ticker, analysis_date, analysts,
            )

            # Default analysts if not provided (social = sentiment/social media analyst)
            if analysts is None:
                analysts = ["market", "social", "news", "fundamentals", "technical", "sec"]
            # Exclude SEC analyst when no SEC EDGAR data exists for this ticker
            if "sec" in analysts and not _has_sec_data(ticker):
                analysts = [a for a in analysts if a != "sec"]
                logger.info("SEC analyst excluded (no SEC EDGAR data) ticker=%s", ticker)

            # Exclude fundamentals analyst when no fundamental data exists for this ticker
            if "fundamentals" in analysts and not _has_fundamental_data(ticker):
                analysts = [a for a in analysts if a != "fundamentals"]
                logger.info("Fundamentals analyst excluded (no fundamental data) ticker=%s", ticker)

            # Create config
            config = DEFAULT_CONFIG.copy()
            config["max_debate_rounds"] = research_depth
            config["max_risk_discuss_rounds"] = research_depth
            
            # Resolve provider + model defaults from env (with request overrides).
            llm_overrides: Dict[str, Any] = {"llm_provider": llm_provider.lower()}
            if shallow_thinker:
                llm_overrides["quick_think_llm"] = shallow_thinker
            if deep_thinker:
                llm_overrides["deep_think_llm"] = deep_thinker
            if backend_url:
                llm_overrides["backend_url"] = backend_url
            config.update(get_config_from_env(llm_overrides))
            
            config["results_dir"] = str(self.results_dir)
            
            # Use the app's data API for news, fundamentals, stock data, etc. (same as dashboard UI).
            # Agents will call back to this backend via /api/data/* so analysis uses the same infrastructure.
            from config import BACKEND_URL
            info_url = os.getenv("INFO_SERVICE_URL", "").strip() or os.getenv("BACKEND_URL", "").strip() or BACKEND_URL
            config["info_service_url"] = info_url.rstrip("/")
            
            # Initialize graph
            graph = TradingAgentsGraph(
                selected_analysts=analysts,
                config=config,
                debug=True
            )
            
            results_dir = self.results_dir / ticker.upper() / str(analysis_run_id)
            results_dir.mkdir(parents=True, exist_ok=True)
            report_dir = results_dir / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            log_file = results_dir / "message_tool.log"
            log_file.touch(exist_ok=True)
            
            # Initialize agent statuses
            agent_statuses = {
                "Market Analyst": "pending",
                "Social Analyst": "pending",
                "News Analyst": "pending",
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
            
            # Set first selected analyst to in_progress
            analyst_status_map = {
                "market": "Market Analyst",
                "social": "Social Analyst",
                "news": "News Analyst",
                "fundamentals": "Fundamentals Analyst",
                "technical": "Technical Analyst",
                "sec": "SEC Analyst",
            }
            first_selected = next((a for a in analysts if a in analyst_status_map), None)
            current_agent = analyst_status_map[first_selected] if first_selected else None
            if first_selected:
                agent_statuses[analyst_status_map[first_selected]] = "in_progress"

            # Store analysis info immediately to prevent race condition
            # This must be done within the lock before starting the background thread
            self.running_analyses[analysis_run_id] = {
                "ticker": ticker.upper(),
                "date": analysis_date,
                "analysis_run_id": analysis_run_id,
                "status": "running",
                "graph": graph,
                "results_dir": results_dir,
                "report_dir": report_dir,
                "log_file": log_file,
                "progress_callback": progress_callback,
                "agent_statuses": agent_statuses,
                "current_agent": current_agent,
                "reports": {},
                "analysts": analysts,
                "messages": [],
                "tool_calls": [],
                "initiator_email": initiator_email,
            }
            
            # Write initial status to file
            self._persist_analysis_status(analysis_run_id)
        
        # Start analysis in background
        # Create a new event loop in a thread to run the async analysis
        def run_async_analysis():
            """Run the async analysis in a new event loop."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._run_analysis(analysis_run_id, graph, ticker, analysis_date, analysts))
            except Exception as e:
                import traceback
                logger.exception(
                    "Analysis failed analysis_run_id=%s ticker=%s date=%s error=%s",
                    analysis_run_id, ticker, analysis_date, e,
                )
                analysis_info = self.running_analyses.get(analysis_run_id)
                if analysis_info:
                    analysis_info["status"] = "error"
                    analysis_info["error"] = str(e)
            finally:
                loop.close()
        
        # Start the analysis in a background thread
        thread = threading.Thread(target=run_async_analysis, daemon=True)
        thread.start()
        
        return (analysis_run_id, False)
    
    async def _run_analysis(self, analysis_run_id: int, graph: TradingAgentsGraph, ticker: str, analysis_date: str, analysts: list):
        """Run the analysis and update status."""
        analysis_info = self.running_analyses.get(analysis_run_id)
        if not analysis_info:
            logger.warning("Analysis info not found for analysis_run_id=%s", analysis_run_id)
            return

        log_file = analysis_info["log_file"]
        ar_id = analysis_info["analysis_run_id"]
        logger.info(
            "Analysis run started analysis_run_id=%s ticker=%s models=%s",
            ar_id, ticker,
            {"deep": graph.config.get("deep_think_llm"), "quick": graph.config.get("quick_think_llm")},
        )

        try:
            # Check if AI reports should be written to the results folder
            from config import WRITE_AI_REPORTS_TO_RESULTS
            write_reports_to_results = WRITE_AI_REPORTS_TO_RESULTS

            # Initialize state
            init_agent_state = graph.propagator.create_initial_state(ticker, analysis_date)
            args = graph.propagator.get_graph_args()
            generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            models_used = {
                "provider": graph.config.get("llm_provider"),
                "deep_think": graph.config.get("deep_think_llm"),
                "quick_think": graph.config.get("quick_think_llm"),
            }

            def _build_report_json(content, score, score_label, key_takeaways_list, **extra):
                meta = {"score_label": score_label or "Score", "analysis_date": analysis_date, "generated_at": generated_at, "models_used": models_used}
                if score is not None:
                    meta["score"] = score
                if key_takeaways_list:
                    meta["key_takeaways"] = [str(t or "").strip() for t in key_takeaways_list[:5] if t]
                meta.update({k: v for k, v in extra.items() if v is not None})
                return {"metadata": meta, "content": content or ""}

            def _write_report_to_filesystem(key, content, report_dir: Path):
                """Write report content as a markdown file in the results folder."""
                try:
                    safe_key = re.sub(r"[^\w\-]", "_", key)
                    report_file = report_dir / f"{safe_key}.md"
                    report_file.write_text(content or "", encoding="utf-8")
                    logger.debug(
                        "Report written to filesystem analysis_run_id=%s report_type=%s path=%s",
                        analysis_run_id, key, report_file,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to write report to filesystem analysis_run_id=%s report_type=%s error=%s",
                        analysis_run_id, key, e,
                    )

            def _write_report(key, content, score, label, llm_usage=None, **extra):
                try:
                    data = _build_report_json(content, score, label, _takeaways(content), **extra)
                    meta = data.get("metadata", {})
                    meta.update({k: v for k, v in data.items() if k not in ("metadata", "content")})
                    if llm_usage:
                        meta["input_tokens"] = llm_usage.get("input_tokens")
                        meta["output_tokens"] = llm_usage.get("output_tokens")
                        meta["total_tokens"] = llm_usage.get("total_tokens")
                        meta["cost_usd"] = llm_usage.get("cost_usd")
                    save_report(
                        analysis_info["analysis_run_id"],
                        key,
                        content=data.get("content", ""),
                        metadata=meta,
                    )
                    logger.info(
                        "Report saved analysis_run_id=%s ticker=%s report_type=%s",
                        analysis_run_id, analysis_info["ticker"], key,
                    )
                    if write_reports_to_results:
                        _write_report_to_filesystem(key, data.get("content", ""), analysis_info["report_dir"])
                except Exception as e:
                    logger.exception(
                        "Failed to save report analysis_run_id=%s report_type=%s error=%s",
                        analysis_run_id, key, e,
                    )
                    raise

            # Determine when analyst phase is complete (last selected analyst report saved).
            analyst_to_report_key = {
                "market": "market_report",
                "social": "sentiment_report",
                "news": "news_report",
                "fundamentals": "fundamentals_report",
                "technical": "technical_report",
                "sec": "sec_report",
            }
            report_key_to_analyst = {
                "market_report": "market",
                "sentiment_report": "social",
                "news_report": "news",
                "fundamentals_report": "fundamentals",
                "technical_report": "technical",
                "sec_report": "sec",
            }
            analyst_status_map_run = {
                "market": "Market Analyst",
                "social": "Social Analyst",
                "news": "News Analyst",
                "fundamentals": "Fundamentals Analyst",
                "technical": "Technical Analyst",
                "sec": "SEC Analyst",
            }
            last_analyst_report_key = None
            for analyst in reversed(analysts):
                report_key = analyst_to_report_key.get(analyst)
                if report_key:
                    last_analyst_report_key = report_key
                    break

            # Stream the analysis
            _progress_log(f"Analysis started analysis_run_id={ar_id} ticker={ticker}")
            last_chunk = None
            for chunk in graph.graph.stream(init_agent_state, **args):
                if get_stop_requested(analysis_run_id):
                    logger.info(
                        "Analysis stop requested analysis_run_id=%s ticker=%s",
                        analysis_run_id, ticker,
                    )
                    analysis_info["status"] = "cancelled"
                    self._persist_analysis_status(analysis_run_id)
                    delete_analysis_status("ticker", analysis_run_id)
                    clear_stop_requested(analysis_run_id)
                    break
                last_chunk = chunk
                # Process messages
                if len(chunk.get("messages", [])) > 0:
                    last_message = chunk["messages"][-1]
                    
                    # Extract message content and type
                    if hasattr(last_message, "content"):
                        content = extract_content_string(last_message.content)
                        msg_type = "Reasoning"
                    else:
                        content = str(last_message)
                        msg_type = "System"
                    
                    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                    analysis_info["messages"].append({
                        "timestamp": timestamp,
                        "type": msg_type,
                        "content": content
                    })
                    
                    # Log to file
                    with open(log_file, "a", encoding='utf-8') as f:
                        f.write(f"{timestamp} [{msg_type}] {content.replace(chr(10), ' ')}\n")
                
                def _takeaways(content):
                    if extract_key_takeaways_structured and analysis_info.get("graph"):
                        try:
                            return extract_key_takeaways_structured(analysis_info["graph"].deep_thinking_llm, content)
                        except Exception:
                            pass
                    return extract_key_takeaways(content)

                # Update reports and agent status
                _reports = [
                    ("market_report", "market_report", "market_score", "Market Score", "Market Analyst"),
                    ("sentiment_report", "sentiment_report", "sentiment_score", "Sentiment Score", "Social Analyst"),
                    ("news_report", "news_report", "news_score", "News Score", "News Analyst"),
                    ("fundamentals_report", "fundamentals_report", "fundamentals_score", "Fundamentals Score", "Fundamentals Analyst"),
                    ("technical_report", "technical_report", "technical_score", "Technical Score", "Technical Analyst"),
                    ("sec_report", "sec_report", "sec_score", "SEC Score", "SEC Analyst"),
                ]
                for key, chunk_key, score_key, label, agent in _reports:
                    if chunk_key in chunk and chunk[chunk_key]:
                        c = chunk[chunk_key]
                        analysis_info["reports"][key] = c
                        analysis_info["agent_statuses"][agent] = "completed"
                        analyst_key = report_key_to_analyst.get(key)
                        if analyst_key is not None and analysts:
                            try:
                                idx = analysts.index(analyst_key)
                                if idx + 1 < len(analysts):
                                    next_key = analysts[idx + 1]
                                    next_agent = analyst_status_map_run.get(next_key)
                                    if next_agent:
                                        analysis_info["agent_statuses"][next_agent] = "in_progress"
                                        analysis_info["current_agent"] = next_agent
                                elif last_analyst_report_key and key == last_analyst_report_key:
                                    analysis_info["current_agent"] = "Research Manager"
                            except ValueError:
                                pass
                        self._persist_analysis_status(analysis_run_id)
                        report_usage = chunk.get("report_usage") or {}
                        _write_report(key, c, chunk.get(score_key), label, llm_usage=report_usage.get(key))
                        _progress_log(f"{agent} completed → {key} saved")
                        if last_analyst_report_key and key == last_analyst_report_key:
                            analysis_info["agent_statuses"]["Bull Researcher"] = "in_progress"
                            analysis_info["agent_statuses"]["Bear Researcher"] = "in_progress"
                            analysis_info["agent_statuses"]["Research Manager"] = "in_progress"
                            analysis_info["current_agent"] = "Research Manager"
                            self._persist_analysis_status(analysis_run_id)
                            _progress_log("Bull/Bear researchers & Research Manager started")

                if "investment_debate_state" in chunk and chunk["investment_debate_state"]:
                    debate_state = chunk["investment_debate_state"]
                    analysis_info["investment_debate_state"] = debate_state
                    
                    if "judge_decision" in debate_state and debate_state["judge_decision"]:
                        analysis_info["agent_statuses"]["Bull Researcher"] = "completed"
                        analysis_info["agent_statuses"]["Bear Researcher"] = "completed"
                        analysis_info["agent_statuses"]["Research Manager"] = "completed"
                        analysis_info["agent_statuses"]["Trader"] = "in_progress"
                        analysis_info["current_agent"] = "Trader"
                        self._persist_analysis_status(analysis_run_id)
                        _progress_log("Bull/Bear/Research Manager completed → Trader started")
                
                if "investment_plan" in chunk and chunk["investment_plan"]:
                    bull = chunk.get("bull_summary") or []
                    bear = chunk.get("bear_summary") or []
                    content = chunk["investment_plan"]
                    analysis_info["reports"]["investment_plan"] = content
                    meta = _build_report_json(content, chunk.get("recommendation_score"), "Conviction Score", _takeaways(content),
                        expected_return_pct=chunk.get("expected_return_pct"),
                        bear_case_return_pct=chunk.get("bear_case_return_pct"),
                        bull_case_return_pct=chunk.get("bull_case_return_pct"))
                    data = {**meta, "bull_viewpoint": bull, "bear_viewpoint": bear}
                    inner = meta.get("metadata", meta)
                    usage = (chunk.get("report_usage") or {}).get("investment_plan")
                    if usage:
                        inner["input_tokens"] = usage.get("input_tokens")
                        inner["output_tokens"] = usage.get("output_tokens")
                        inner["total_tokens"] = usage.get("total_tokens")
                        inner["cost_usd"] = usage.get("cost_usd")
                    save_report(
                        analysis_info["analysis_run_id"],
                        "investment_plan",
                        content=content,
                        metadata={**inner, "bull_viewpoint": bull, "bear_viewpoint": bear},
                    )
                    if write_reports_to_results:
                        _write_report_to_filesystem("investment_plan", content, analysis_info["report_dir"])
                    _progress_log("Investment plan ready → saved")

                if "trader_investment_plan" in chunk and chunk["trader_investment_plan"]:
                    c = chunk["trader_investment_plan"]
                    tps = chunk.get("trader_tps_plan") or ""
                    analysis_info["reports"]["trader_investment_plan"] = c
                    if tps:
                        analysis_info["reports"]["trader_tps_plan"] = tps
                    analysis_info["agent_statuses"]["Trader"] = "completed"
                    report_usage = chunk.get("report_usage") or {}
                    _write_report(
                        "trader_investment_plan",
                        c,
                        None,
                        "Trader Plan",
                        llm_usage=report_usage.get("trader_investment_plan"),
                        recommendation=chunk.get("trader_recommendation"),
                        tps_plan=tps or None,
                    )
                    analysis_info["agent_statuses"]["Risky Analyst"] = "in_progress"
                    analysis_info["agent_statuses"]["Safe Analyst"] = "in_progress"
                    analysis_info["agent_statuses"]["Neutral Analyst"] = "in_progress"
                    analysis_info["current_agent"] = "Risk Analyst"
                    self._persist_analysis_status(analysis_run_id)
                    _progress_log("Trader completed → Risk debate (Risky/Safe/Neutral) started")
                
                if "risk_debate_state" in chunk and chunk["risk_debate_state"]:
                    risk_state = chunk["risk_debate_state"]
                    analysis_info["risk_debate_state"] = risk_state
                    
                    if "judge_decision" in risk_state and risk_state["judge_decision"]:
                        analysis_info["agent_statuses"]["Risky Analyst"] = "completed"
                        analysis_info["agent_statuses"]["Safe Analyst"] = "completed"
                        analysis_info["agent_statuses"]["Neutral Analyst"] = "completed"
                        analysis_info["agent_statuses"]["Portfolio Manager"] = "in_progress"
                        analysis_info["current_agent"] = "Portfolio Manager"
                        self._persist_analysis_status(analysis_run_id)
                        _progress_log("Risk analysts completed → Portfolio Manager started")
                
                if "final_trade_decision" in chunk and chunk["final_trade_decision"]:
                    analysis_info["agent_statuses"]["Portfolio Manager"] = "completed"
                    analysis_info["current_agent"] = None
                    self._persist_analysis_status(analysis_run_id)
                    content = chunk["final_trade_decision"]
                    risky = chunk.get("risky_summary") or []
                    safe = chunk.get("safe_summary") or []
                    neutral = chunk.get("neutral_summary") or []
                    # Risk Manager now outputs the final recommendation (with fallback to trader if not provided)
                    final_rec = chunk.get("recommendation") or chunk.get("trader_recommendation") or "HOLD"
                    analysis_info["reports"]["final_trade_decision"] = content
                    analysis_info["recommendation"] = final_rec
                    rscore = chunk.get("risk_score")
                    kt = (chunk.get("final_report_key_takeaways") or [])[:5] or extract_key_takeaways(content)
                    meta = _build_report_json(content, rscore, "Confidence", kt,
                        recommendation=final_rec,
                        confidence=(rscore / 10.0) if rscore is not None else None)
                    data = {**meta, "risky_viewpoint": risky, "safe_viewpoint": safe, "neutral_viewpoint": neutral}
                    inner = meta.get("metadata", meta)
                    usage = (chunk.get("report_usage") or {}).get("final_trade_decision")
                    if usage:
                        inner["input_tokens"] = usage.get("input_tokens")
                        inner["output_tokens"] = usage.get("output_tokens")
                        inner["total_tokens"] = usage.get("total_tokens")
                        inner["cost_usd"] = usage.get("cost_usd")
                    save_report(
                        analysis_info["analysis_run_id"],
                        "final_trade_decision",
                        content=content,
                        metadata={**inner, "risky_viewpoint": risky, "safe_viewpoint": safe, "neutral_viewpoint": neutral},
                    )
                    if write_reports_to_results:
                        _write_report_to_filesystem("final_trade_decision", content, analysis_info["report_dir"])
                    analysis_info["recommendation"] = final_rec
                    analysis_info["confidence"] = (chunk.get("risk_score") / 10.0) if chunk.get("risk_score") is not None else None
                    rec = final_rec or ""
                    _progress_log(f"Final trade decision ready → {rec}")

                # Call progress callback if provided
                if analysis_info["progress_callback"]:
                    try:
                        analysis_info["progress_callback"](chunk, analysis_info)
                    except Exception:
                        pass

            # If we broke due to stop request, skip completion (already persisted and deleted).
            if analysis_info.get("status") == "cancelled":
                return

            # Fallback: ensure optional analyst reports are saved if missed in stream chunks.
            if last_chunk:
                fallback_reports = [
                    ("technical", "technical_report", "technical_score", "Technical Score", "Technical Analyst"),
                    ("sec", "sec_report", "sec_score", "SEC Score", "SEC Analyst"),
                ]
                for analyst_key, report_key, score_key, label, agent in fallback_reports:
                    if analyst_key not in analysts or report_key in analysis_info.get("reports", {}):
                        continue
                    content = last_chunk.get(report_key)
                    if not content:
                        continue
                    try:
                        report_usage = last_chunk.get("report_usage") or {}
                        _write_report(report_key, content, last_chunk.get(score_key), label, llm_usage=report_usage.get(report_key))
                        analysis_info["reports"][report_key] = content
                        analysis_info["agent_statuses"][agent] = "completed"
                        _progress_log(f"{agent} report saved (from final state)")
                    except Exception as e:
                        logger.warning("Failed to save %s from final state: %s", report_key, e)
            
            # Mark as completed
            analysis_info["status"] = "completed"
            self._persist_analysis_status(analysis_run_id)
            logger.info(
                "Analysis completed analysis_run_id=%s ticker=%s reports=%s",
                ar_id, ticker, list(analysis_info.get("reports", {}).keys()),
            )
            print(
                f"[ANALYSIS COMPLETED] analysis_run_id={ar_id} ticker={ticker} reports={list(analysis_info.get('reports', {}).keys())}",
                file=sys.stderr,
                flush=True,
            )
            
            # Delete status file after completion (analysis is done)
            delete_analysis_status("ticker", analysis_run_id)

            # Notify subscribed users and initiator by email (best-effort; do not fail analysis)
            try:
                notify_subscribers_new_report(
                    ticker=analysis_info["ticker"],
                    execution_id=analysis_info["analysis_run_id"],
                    recommendation=analysis_info.get("recommendation"),
                    confidence=analysis_info.get("confidence"),
                    initiator_email=analysis_info.get("initiator_email"),
                )
            except Exception:
                pass

            # Final callback
            if analysis_info["progress_callback"]:
                try:
                    analysis_info["progress_callback"]({"type": "completed"}, analysis_info)
                except Exception:
                    pass

        except Exception as e:
            ar_id_safe = analysis_info.get("analysis_run_id", "?") if analysis_info else "?"
            print(
                f"\n[ANALYSIS STOPPED - EXCEPTION] analysis_run_id={ar_id_safe} ticker={ticker}\n  {type(e).__name__}: {e}\n",
                file=sys.stderr,
                flush=True,
            )
            logger.exception(
                "Analysis error analysis_run_id=%s ticker=%s error=%s",
                ar_id_safe, ticker, e,
            )
            analysis_info = self.running_analyses.get(analysis_run_id)
            if analysis_info:
                analysis_info["status"] = "error"
                analysis_info["error"] = str(e)
                self._persist_analysis_status(analysis_run_id)
                if analysis_info["progress_callback"]:
                    try:
                        analysis_info["progress_callback"]({"type": "error", "error": str(e)}, analysis_info)
                    except Exception:
                        pass
                # Delete status file after error (analysis is done)
                delete_analysis_status("ticker", analysis_run_id)
    
    def get_analysis_status(self, analysis_run_id: int) -> Optional[Dict]:
        """Get current status of a running analysis from shared cache (works across workers)."""
        return get_analysis_status_from_cache("ticker", analysis_run_id)
