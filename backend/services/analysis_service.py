"""Service to trigger TradingAgents analysis."""

import asyncio
import logging
import os
import sys
import datetime
import threading
from typing import Dict, Optional, Callable, Any, List
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
from ai_engine.tradingagents.agents.utils.trace_utils import make_agent_step, preview_text, sort_agent_steps
from services.report_service import save_report, update_execution_status
from services.email_service import notify_subscribers_new_report

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


def _normalize_takeaway_list(val) -> list:
    """Non-empty strings only, max 5 (from graph structured fields or similar)."""
    if not val:
        return []
    if not isinstance(val, (list, tuple)):
        return []
    return [str(x).strip() for x in val if x and str(x).strip()][:5]


# Saved report type -> AgentState key produced by the graph (avoid a second LLM for takeaways).
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


def _iso_utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _preview_activity_text(value: Any, max_chars: int = 180) -> str:
    text = extract_content_string(value).replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


class AnalysisService:
    """Service for running TradingAgents analyses."""

    _MAX_LIVE_ACTIVITIES = 18
    _MAX_LIVE_TRACE_STEPS = 120
    _MAX_ACTIVITY_FINGERPRINTS = 72
    
    def __init__(self, results_dir: str = "results"):
        self.results_dir = Path(results_dir)
        if not self.results_dir.is_absolute():
            backend_dir = Path(__file__).parent.parent
            self.results_dir = backend_dir.parent / self.results_dir  # repo root
        # Keep minimal in-memory state for active analysis context (callbacks, graph objects)
        # Status queries read from filesystem only. Key = analysis_run_id (AnalysisRun.id).
        self.running_analyses: Dict[int, Dict] = {}
        self._lock = threading.Lock()  # Lock to prevent race conditions

    def _append_live_activity(
        self,
        analysis_info: Dict[str, Any],
        *,
        kind: str,
        summary: str,
        agent: Optional[str] = None,
        tool_name: Optional[str] = None,
        status: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        summary_text = (summary or "").strip()
        if not summary_text:
            return

        fingerprint = "||".join(
            [
                kind.strip(),
                (agent or "").strip(),
                (tool_name or "").strip(),
                (status or "").strip(),
                summary_text,
                (detail or "").strip(),
            ]
        )
        recent_fingerprints = analysis_info.setdefault("activity_fingerprints", [])
        if fingerprint in recent_fingerprints:
            return

        activity_seq = int(analysis_info.get("activity_seq", 0)) + 1
        analysis_info["activity_seq"] = activity_seq

        activity = {
            "id": f"{analysis_info.get('analysis_run_id', 'analysis')}-{activity_seq}",
            "kind": kind,
            "summary": summary_text,
            "captured_at": _iso_utc_now(),
        }
        if agent:
            activity["agent"] = agent
        if tool_name:
            activity["tool_name"] = tool_name
        if status:
            activity["status"] = status
        if detail:
            activity["detail"] = detail

        live_activities = analysis_info.setdefault("live_activities", [])
        live_activities.append(activity)
        if len(live_activities) > self._MAX_LIVE_ACTIVITIES:
            del live_activities[:-self._MAX_LIVE_ACTIVITIES]

        recent_fingerprints.append(fingerprint)
        if len(recent_fingerprints) > self._MAX_ACTIVITY_FINGERPRINTS:
            del recent_fingerprints[:-self._MAX_ACTIVITY_FINGERPRINTS]

    def _append_agent_transition_activity(
        self,
        analysis_info: Dict[str, Any],
        agent: str,
        status: str,
        summary: Optional[str] = None,
    ) -> None:
        status_text = status.replace("_", " ").strip() or "updated"
        self._append_live_activity(
            analysis_info,
            kind="status",
            agent=agent,
            status=status,
            summary=summary or f"{agent} {status_text}",
        )

    def _append_live_trace_step(self, analysis_info: Dict[str, Any], step: Dict[str, Any]) -> None:
        if not isinstance(step, dict):
            return

        fingerprint = "||".join(
            [
                str(step.get("agent") or "").strip(),
                str(step.get("phase") or "").strip(),
                str(step.get("kind") or "").strip(),
                str(step.get("status") or "").strip(),
                str(step.get("summary") or "").strip(),
                str(step.get("tool_name") or "").strip(),
                preview_text(step.get("message_preview") or ""),
                preview_text(step.get("tool_args") or ""),
                preview_text(step.get("observation_preview") or ""),
                preview_text(step.get("output_preview") or ""),
            ]
        )

        recent_fingerprints = analysis_info.setdefault("trace_fingerprints", [])
        if fingerprint in recent_fingerprints:
            return

        live_trace = analysis_info.setdefault("live_trace", [])
        live_trace.append(step)
        if len(live_trace) > self._MAX_LIVE_TRACE_STEPS:
            del live_trace[:-self._MAX_LIVE_TRACE_STEPS]

        recent_fingerprints.append(fingerprint)
        if len(recent_fingerprints) > self._MAX_ACTIVITY_FINGERPRINTS:
            del recent_fingerprints[:-self._MAX_ACTIVITY_FINGERPRINTS]

    def _append_live_trace_steps(self, analysis_info: Dict[str, Any], steps: List[Dict[str, Any]]) -> None:
        for step in sort_agent_steps(steps):
            self._append_live_trace_step(analysis_info, step)

    def _infer_message_agent(self, analysis_info: Dict[str, Any], message: Any) -> Optional[str]:
        name = getattr(message, "name", None)
        if isinstance(name, str) and name.strip():
            return name.strip()

        current_agents = analysis_info.get("current_agents") or []
        if len(current_agents) == 1:
            return current_agents[0]
        return None

    def _record_live_message_activity(self, analysis_info: Dict[str, Any], message: Any) -> None:
        agent = self._infer_message_agent(analysis_info, message)
        trace_agent = agent or "Agent"
        content = getattr(message, "content", None)
        handled_tool_call = False
        message_preview = ""
        trace_tool_calls: List[Dict[str, Any]] = []

        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "tool_use":
                    tool_name = str(item.get("name") or "tool").strip() or "tool"
                    tool_args = item.get("input") or item.get("args") or {}
                    self._append_live_activity(
                        analysis_info,
                        kind="tool_call",
                        agent=agent,
                        tool_name=tool_name,
                        status="started",
                        summary=f"{agent or 'Agent'} calling {tool_name}",
                        detail=_preview_activity_text(tool_args),
                    )
                    self._append_live_trace_step(
                        analysis_info,
                        make_agent_step(
                            agent=trace_agent,
                            phase="analysis",
                            kind="tool_call",
                            status="started",
                            summary=f"{trace_agent} calling {tool_name}",
                            tool_name=tool_name,
                            tool_args=tool_args,
                        ),
                    )
                    trace_tool_calls.append(
                        {
                            "id": item.get("id"),
                            "name": tool_name,
                            "args": tool_args,
                        }
                    )
                    handled_tool_call = True
                elif item.get("type") == "text":
                    text = _preview_activity_text(item.get("text") or "")
                    if text:
                        message_preview = f"{message_preview} {text}".strip()
                        self._append_live_activity(
                            analysis_info,
                            kind="reasoning",
                            agent=agent,
                            status="running",
                            summary=text,
                        )

        tool_calls = getattr(message, "tool_calls", None)
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue
                tool_name = str(tool_call.get("name") or "tool").strip() or "tool"
                tool_args = tool_call.get("args") or {}
                self._append_live_activity(
                    analysis_info,
                    kind="tool_call",
                    agent=agent,
                    tool_name=tool_name,
                    status="started",
                    summary=f"{agent or 'Agent'} calling {tool_name}",
                    detail=_preview_activity_text(tool_args),
                )
                self._append_live_trace_step(
                    analysis_info,
                    make_agent_step(
                        agent=trace_agent,
                        phase="analysis",
                        kind="tool_call",
                        status="started",
                        summary=f"{trace_agent} calling {tool_name}",
                        tool_name=tool_name,
                        tool_args=tool_args,
                    ),
                )
                trace_tool_calls.append(tool_call)
                handled_tool_call = True

        message_name = getattr(message, "name", None)
        tool_call_id = getattr(message, "tool_call_id", None)
        if tool_call_id or (isinstance(message_name, str) and message_name.strip() and not handled_tool_call):
            tool_name = str(message_name or "tool").strip() or "tool"
            result_preview = _preview_activity_text(content)
            self._append_live_activity(
                analysis_info,
                kind="tool_result",
                agent=agent,
                tool_name=tool_name,
                status="completed",
                summary=f"{tool_name} returned data",
                detail=result_preview,
            )
            self._append_live_trace_step(
                analysis_info,
                make_agent_step(
                    agent=trace_agent,
                    phase="analysis",
                    kind="tool_result",
                    status="completed",
                    summary=f"{tool_name} returned data",
                    tool_name=tool_name,
                    observation_preview=content,
                ),
            )
            return

        if trace_tool_calls:
            self._append_live_trace_step(
                analysis_info,
                make_agent_step(
                    agent=trace_agent,
                    phase="analysis",
                    kind="llm_decision",
                    status="tool_calls_requested",
                    summary=f"{trace_agent} requested {len(trace_tool_calls)} tool call(s)",
                    message_preview=message_preview or content,
                    tool_calls=trace_tool_calls,
                ),
            )
            return

        if not handled_tool_call:
            text_preview = _preview_activity_text(content)
            if text_preview:
                self._append_live_activity(
                    analysis_info,
                    kind="reasoning",
                    agent=agent,
                    status="running",
                    summary=text_preview,
                )
                self._append_live_trace_step(
                    analysis_info,
                    make_agent_step(
                        agent=trace_agent,
                        phase="analysis",
                        kind="llm_decision",
                        status="responded",
                        summary=f"{trace_agent} responded",
                        message_preview=content,
                    ),
                )
    
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
            "current_agents": analysis_info.get("current_agents", []),  # Changed to list
            "live_activities": analysis_info.get("live_activities", []),
            "live_trace": analysis_info.get("live_trace", []),
            "created_at": analysis_info.get("created_at"),
            "updated_at": _iso_utc_now(),
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
                analysts = ["market", "social", "fundamentals", "technical", "sec", "valuation"]
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
            
            # Map analyst keys to their display names.
            analyst_status_map = {
                "market": "Market Analyst",
                "social": "News & Sentiment Analyst",
                "fundamentals": "Fundamentals Analyst",
                "technical": "Technical Analyst",
                "sec": "SEC Analyst",
                "valuation": "Valuation Analyst",
            }

            # Initialize agent statuses. Only include analysts actually selected for
            # this ticker (e.g. SEC/fundamentals are excluded for ETFs like QQQ) so the
            # UI shows only relevant agents instead of leaving them as "pending" chips.
            # Downstream agents (research/trading/risk/portfolio) always run.
            agent_statuses = {}
            for analyst_key in analysts:
                agent_name = analyst_status_map.get(analyst_key)
                if agent_name:
                    agent_statuses[agent_name] = "pending"
            for agent_name in (
                "Bull Researcher",
                "Bear Researcher",
                "Neutral Researcher",
                "Research Manager",
                "Trader",
            ):
                agent_statuses[agent_name] = "pending"

            # Check if parallel execution is enabled (default: True)
            parallel_analysts = config.get("parallel_analysts", True)
            
            # Set initial analyst statuses
            if parallel_analysts and len(analysts) > 1:
                # All selected analysts start in parallel
                current_agents = []
                for analyst_key in analysts:
                    if analyst_key in analyst_status_map:
                        agent_name = analyst_status_map[analyst_key]
                        agent_statuses[agent_name] = "in_progress"
                        current_agents.append(agent_name)
            else:
                # Sequential mode: only first analyst is in progress
                first_selected = next((a for a in analysts if a in analyst_status_map), None)
                current_agents = [analyst_status_map[first_selected]] if first_selected else []
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
                "current_agents": current_agents,  # Changed from current_agent to current_agents (list)
                "live_activities": [],
                "live_trace": [],
                "reports": {},
                "analysts": analysts,
                "messages": [],
                "tool_calls": [],
                "initiator_email": initiator_email,
                "parallel_analysts": parallel_analysts,  # Store mode for later reference
                "activity_seq": 0,
                "activity_fingerprints": [],
                "created_at": _iso_utc_now(),
            }

            for agent_name in current_agents:
                self._append_agent_transition_activity(
                    self.running_analyses[analysis_run_id],
                    agent_name,
                    "in_progress",
                    summary=f"{agent_name} started",
                )
            
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

        # Open log file once and keep it open throughout the analysis to prevent file descriptor leaks
        log_file_handle = None
        try:
            log_file_handle = open(log_file, "a", encoding='utf-8')
            # Check if AI reports should be written to the results folder
            from config import WRITE_AI_REPORTS_TO_RESULTS
            write_reports_to_results = WRITE_AI_REPORTS_TO_RESULTS

            # Initialize state
            init_agent_state = graph.propagator.create_initial_state(ticker, analysis_date)
            # Use analysis_run_id as session_id to maintain context across all requests in this execution
            session_id = f"analysis-{analysis_run_id}"
            args = graph.propagator.get_graph_args(session_id=session_id)
            generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            models_used = {
                "provider": graph.config.get("llm_provider", "unknown"),
                "model": graph.config.get("deep_think_llm", "unknown"),  # Primary model used
                "deep_think": graph.config.get("deep_think_llm", "unknown"),
                "quick_think": graph.config.get("quick_think_llm", "unknown"),
            }

            def _build_report_json(content, score, score_label, key_takeaways_list, **extra):
                meta = {"score_label": score_label or "Score", "analysis_date": analysis_date, "generated_at": generated_at, "models_used": models_used}
                if score is not None:
                    meta["score"] = score
                if key_takeaways_list:
                    meta["key_takeaways"] = [str(t or "").strip() for t in key_takeaways_list[:5] if t]
                meta.update({k: v for k, v in extra.items() if v is not None})
                return {"metadata": meta, "content": content or ""}

            def _get_analysis_quote_meta() -> Dict[str, Any]:
                try:
                    from data_layer import get_data_gateway
                    quote = get_data_gateway().get_quote(ticker)
                except Exception:
                    return {}
                if not isinstance(quote, dict):
                    return {}
                current_price = quote.get("current_price")
                currency = quote.get("currency")
                meta: Dict[str, Any] = {}
                if isinstance(current_price, (int, float)):
                    meta["current_price"] = float(current_price)
                if isinstance(currency, str) and currency.strip():
                    meta["currency"] = currency.strip().upper()
                return meta

            analysis_quote_meta = _get_analysis_quote_meta()

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

            def _get_or_extract_takeaways(report_key, content, chunk=None):
                """Use structured takeaways from graph state only; no content scraping or extra LLM."""
                if report_key in _report_takeaways:
                    logger.info(
                        "Key takeaways extraction skipped (cached) analysis_run_id=%s report_type=%s",
                        analysis_run_id, report_key,
                    )
                    return _report_takeaways[report_key]
                state_key = _REPORT_TO_STATE_TAKEAWAYS_KEY.get(report_key)
                if chunk is not None and state_key:
                    preferred = _normalize_takeaway_list(chunk.get(state_key))
                    if preferred:
                        _report_takeaways[report_key] = preferred
                        logger.info(
                            "Key takeaways from graph state analysis_run_id=%s report_type=%s items=%s",
                            analysis_run_id, report_key, len(preferred),
                        )
                        return preferred
                takeaways: list = []
                _report_takeaways[report_key] = takeaways
                return takeaways

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
                    report_agent_steps = _get_report_agent_steps(chunk, key)
                    meta["agent_steps"] = report_agent_steps
                    if report_agent_steps:
                        self._append_live_trace_steps(analysis_info, report_agent_steps)
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

            def _get_report_agent_steps(
                chunk: Optional[Dict[str, Any]],
                report_key: str,
            ) -> List[Dict[str, Any]]:
                if not isinstance(chunk, dict):
                    return []
                by_report = chunk.get("report_steps_by_report")
                if isinstance(by_report, dict):
                    specific = by_report.get(report_key)
                    if isinstance(specific, list):
                        return sort_agent_steps(specific)
                return []

            # Determine when analyst phase is complete (last selected analyst report saved).
            analyst_to_report_key = {
                "market": "market_report",
                "social": "sentiment_report",
                "fundamentals": "fundamentals_report",
                "technical": "technical_report",
                "sec": "sec_report",
                "valuation": "valuation_report",
            }
            report_key_to_analyst = {
                "market_report": "market",
                "sentiment_report": "social",
                "fundamentals_report": "fundamentals",
                "technical_report": "technical",
                "sec_report": "sec",
                "valuation_report": "valuation",
            }
            analyst_status_map_run = {
                "market": "Market Analyst",
                "social": "News & Sentiment Analyst",
                "fundamentals": "Fundamentals Analyst",
                "technical": "Technical Analyst",
                "sec": "SEC Analyst",
                "valuation": "Valuation Analyst",
            }
            last_analyst_report_key = None
            for analyst in reversed(analysts):
                report_key = analyst_to_report_key.get(analyst)
                if report_key:
                    last_analyst_report_key = report_key
                    break

            # Track which reports have been written to avoid duplicate processing across chunks
            _written_reports = set()

            # Store extracted takeaways to avoid re-extraction across chunks
            _report_takeaways = {}

            # Stream the analysis
            _progress_log(f"Analysis started analysis_run_id={ar_id} ticker={ticker}")
            last_chunk = None
            for chunk in graph.graph.stream(init_agent_state, **args):
                activity_seq_before_chunk = int(analysis_info.get("activity_seq", 0))
                if get_stop_requested(analysis_run_id):
                    logger.info(
                        "Analysis stop requested analysis_run_id=%s ticker=%s",
                        analysis_run_id, ticker,
                    )
                    analysis_info["status"] = "cancelled"
                    self._append_live_activity(
                        analysis_info,
                        kind="status",
                        status="cancelled",
                        summary="Analysis cancelled",
                    )
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
                    
                    # Log to file (using persistent file handle to prevent file descriptor leaks)
                    if log_file_handle:
                        try:
                            log_file_handle.write(f"{timestamp} [{msg_type}] {content.replace(chr(10), ' ')}\n")
                            log_file_handle.flush()  # Ensure data is written immediately
                        except Exception as log_err:
                            logger.warning("Failed to write to log file: %s", log_err)

                    self._record_live_message_activity(analysis_info, last_message)

                # Update reports and agent status
                _reports = [
                    ("market_report", "market_report", "market_score", "Market Score", "Market Analyst"),
                    ("sentiment_report", "sentiment_report", "sentiment_score", "Sentiment Score", "News & Sentiment Analyst"),
                    ("fundamentals_report", "fundamentals_report", "fundamentals_score", "Fundamentals Score", "Fundamentals Analyst"),
                    ("technical_report", "technical_report", "technical_score", "Technical Score", "Technical Analyst"),
                    ("sec_report", "sec_report", "sec_score", "SEC Score", "SEC Analyst"),
                    ("valuation_report", "valuation_report", "valuation_score", "Valuation Score", "Valuation Analyst"),
                ]
                for key, chunk_key, score_key, label, agent in _reports:
                    if chunk_key in chunk and chunk[chunk_key]:
                        c = chunk[chunk_key]
                        # Only process if not already written
                        if key not in _written_reports:
                            analysis_info["reports"][key] = c
                            analysis_info["agent_statuses"][agent] = "completed"
                            self._append_live_activity(
                                analysis_info,
                                kind="report_synthesis",
                                agent=agent,
                                status="completed",
                                summary=f"{agent} finished {key.replace('_', ' ')}",
                            )
                            
                            # Update current_agents list
                            current_agents = analysis_info.get("current_agents", [])
                            if agent in current_agents:
                                current_agents.remove(agent)
                            
                            # Handle next agent based on execution mode
                            parallel_analysts = analysis_info.get("parallel_analysts", True)
                            analyst_key = report_key_to_analyst.get(key)
                            
                            if not parallel_analysts and analyst_key is not None and analysts:
                                # Sequential mode: start next analyst
                                try:
                                    idx = analysts.index(analyst_key)
                                    if idx + 1 < len(analysts):
                                        next_key = analysts[idx + 1]
                                        next_agent = analyst_status_map_run.get(next_key)
                                        if next_agent:
                                            analysis_info["agent_statuses"][next_agent] = "in_progress"
                                            current_agents.append(next_agent)
                                            self._append_agent_transition_activity(
                                                analysis_info,
                                                next_agent,
                                                "in_progress",
                                                summary=f"{next_agent} started",
                                            )
                                    elif last_analyst_report_key and key == last_analyst_report_key:
                                        current_agents.append("Research Manager")
                                        self._append_agent_transition_activity(
                                            analysis_info,
                                            "Research Manager",
                                            "in_progress",
                                            summary="Research Manager started synthesizing the analyst reports",
                                        )
                                except ValueError:
                                    pass
                            elif last_analyst_report_key and key == last_analyst_report_key:
                                # Last analyst completed (parallel or sequential)
                                current_agents.append("Research Manager")
                                self._append_agent_transition_activity(
                                    analysis_info,
                                    "Research Manager",
                                    "in_progress",
                                    summary="Research Manager started synthesizing the analyst reports",
                                )
                            
                            analysis_info["current_agents"] = current_agents
                            self._persist_analysis_status(analysis_run_id)
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
                            analysis_info["agent_statuses"]["Bull Researcher"] = "in_progress"
                            analysis_info["agent_statuses"]["Bear Researcher"] = "in_progress"
                            analysis_info["agent_statuses"]["Neutral Researcher"] = "in_progress"
                            analysis_info["agent_statuses"]["Research Manager"] = "in_progress"
                            analysis_info["current_agents"] = ["Bull Researcher", "Bear Researcher", "Neutral Researcher", "Research Manager"]
                            self._append_agent_transition_activity(
                                analysis_info,
                                "Bull Researcher",
                                "in_progress",
                                summary="Bull Researcher started the investment debate",
                            )
                            self._append_agent_transition_activity(
                                analysis_info,
                                "Bear Researcher",
                                "in_progress",
                                summary="Bear Researcher started the investment debate",
                            )
                            self._append_agent_transition_activity(
                                analysis_info,
                                "Neutral Researcher",
                                "in_progress",
                                summary="Neutral Researcher started the investment debate",
                            )
                            self._append_agent_transition_activity(
                                analysis_info,
                                "Research Manager",
                                "in_progress",
                                summary="Research Manager started moderating the investment debate",
                            )
                            self._persist_analysis_status(analysis_run_id)
                            _progress_log("Bull/Bear/Neutral researchers & Research Manager started")

                if "investment_debate_state" in chunk and chunk["investment_debate_state"]:
                    debate_state = chunk["investment_debate_state"]
                    analysis_info["investment_debate_state"] = debate_state
                    
                    if "judge_decision" in debate_state and debate_state["judge_decision"]:
                        analysis_info["agent_statuses"]["Bull Researcher"] = "completed"
                        analysis_info["agent_statuses"]["Bear Researcher"] = "completed"
                        analysis_info["agent_statuses"]["Research Manager"] = "completed"
                        analysis_info["agent_statuses"]["Trader"] = "in_progress"
                        analysis_info["current_agents"] = ["Trader"]
                        self._append_live_activity(
                            analysis_info,
                            kind="report_synthesis",
                            agent="Research Manager",
                            status="completed",
                            summary="Research Manager finalized the investment plan",
                        )
                        self._append_agent_transition_activity(
                            analysis_info,
                            "Trader",
                            "in_progress",
                            summary="Trader started converting the thesis into a trading plan",
                        )
                        self._persist_analysis_status(analysis_run_id)
                        _progress_log("Bull/Bear/Research Manager completed → Trader started")
                
                if "investment_plan" in chunk and chunk["investment_plan"] and "investment_plan" not in _written_reports:
                    bull = chunk.get("bull_summary") or []
                    bear = chunk.get("bear_summary") or []
                    neutral = chunk.get("neutral_summary") or []
                    content = chunk["investment_plan"]
                    analysis_info["reports"]["investment_plan"] = content
                    inv_takeaways = _get_or_extract_takeaways("investment_plan", content, chunk)
                    # Research Manager now emits the authoritative BUY/SELL/HOLD recommendation;
                    # its conviction score (recommendation_score) drives the confidence.
                    rec_score = chunk.get("recommendation_score")
                    final_rec = chunk.get("recommendation") or chunk.get("trader_recommendation") or "HOLD"
                    meta = _build_report_json(content, rec_score, "Conviction Score", inv_takeaways,
                        recommendation=final_rec,
                        confidence=(rec_score / 10.0) if rec_score is not None else None,
                        expected_return_pct=chunk.get("expected_return_pct"),
                        bear_case_return_pct=chunk.get("bear_case_return_pct"),
                        bull_case_return_pct=chunk.get("bull_case_return_pct"),
                        current_price=analysis_quote_meta.get("current_price"),
                        currency=analysis_quote_meta.get("currency"))
                    data = {**meta, "bull_viewpoint": bull, "bear_viewpoint": bear, "neutral_viewpoint": neutral}
                    inner = meta.get("metadata", meta)
                    usage = (chunk.get("report_usage") or {}).get("investment_plan")
                    if usage:
                        inner["input_tokens"] = usage.get("input_tokens")
                        inner["output_tokens"] = usage.get("output_tokens")
                        inner["total_tokens"] = usage.get("total_tokens")
                        inner["cost_usd"] = usage.get("cost_usd")
                    inner["resources"] = _get_report_resources(chunk, "investment_plan")
                    inner["agent_steps"] = _get_report_agent_steps(chunk, "investment_plan")
                    _written_reports.add("investment_plan")
                    analysis_info["recommendation"] = final_rec
                    analysis_info["confidence"] = (rec_score / 10.0) if rec_score is not None else None
                    save_report(
                        analysis_info["analysis_run_id"],
                        "investment_plan",
                        content=content,
                        metadata={**inner, "bull_viewpoint": bull, "bear_viewpoint": bear, "neutral_viewpoint": neutral},
                    )
                    if write_reports_to_results:
                        _write_report_to_filesystem("investment_plan", content, analysis_info["report_dir"])
                    _progress_log(f"Investment plan ready → {final_rec} → saved")

                if "trader_investment_plan" in chunk and chunk["trader_investment_plan"]:
                    c = chunk["trader_investment_plan"]
                    tps = chunk.get("trader_tps_plan") or ""
                    analysis_info["reports"]["trader_investment_plan"] = c
                    if tps:
                        analysis_info["reports"]["trader_tps_plan"] = tps
                    analysis_info["agent_statuses"]["Trader"] = "completed"
                    self._append_live_activity(
                        analysis_info,
                        kind="report_synthesis",
                        agent="Trader",
                        status="completed",
                        summary="Trader produced the execution plan",
                    )
                    report_usage = chunk.get("report_usage") or {}
                    _write_report(
                        "trader_investment_plan",
                        c,
                        None,
                        "Trader Plan",
                        llm_usage=report_usage.get("trader_investment_plan"),
                        recommendation=chunk.get("trader_recommendation"),
                        tps_plan=tps or None,
                        resources=_get_report_resources(chunk, "trader_investment_plan"),
                        chunk=chunk,
                    )
                    # Trader is the terminal node; the run ends here.
                    analysis_info["current_agents"] = []
                    self._persist_analysis_status(analysis_run_id)
                    rec = analysis_info.get("recommendation") or chunk.get("trader_recommendation") or ""
                    _progress_log(f"Trader completed → {rec} → analysis finished")

                # Call progress callback if provided
                if int(analysis_info.get("activity_seq", 0)) != activity_seq_before_chunk:
                    self._persist_analysis_status(analysis_run_id)
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
                    ("valuation", "valuation_report", "valuation_score", "Valuation Score", "Valuation Analyst"),
                ]
                for analyst_key, report_key, score_key, label, agent in fallback_reports:
                    if analyst_key not in analysts or report_key in analysis_info.get("reports", {}):
                        continue
                    content = last_chunk.get(report_key)
                    if not content:
                        continue
                    try:
                        report_usage = last_chunk.get("report_usage") or {}
                        _write_report(
                            report_key,
                            content,
                            last_chunk.get(score_key),
                            label,
                            llm_usage=report_usage.get(report_key),
                            resources=_get_report_resources(last_chunk, report_key),
                            chunk=last_chunk,
                        )
                        analysis_info["reports"][report_key] = content
                        analysis_info["agent_statuses"][agent] = "completed"
                        _progress_log(f"{agent} report saved (from final state)")
                    except Exception as e:
                        logger.warning("Failed to save %s from final state: %s", report_key, e)
            
            # Mark as completed
            analysis_info["status"] = "completed"
            self._append_live_activity(
                analysis_info,
                kind="status",
                status="completed",
                summary="Analysis completed",
            )
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
            
            # Update execution status to completed
            try:
                update_execution_status(analysis_run_id, "completed")
            except Exception as e:
                logger.warning("Failed to update execution status to completed: %s", e)
            
            # Update Usage entry with actual LLM usage from reports
            try:
                from database import SessionLocal
                from services.token_service import update_usage_with_llm_data
                from services.report_service import aggregate_llm_usage_from_reports
                
                db = SessionLocal()
                try:
                    llm_usage = aggregate_llm_usage_from_reports(analysis_run_id, db)
                    if llm_usage["total_tokens"] > 0:
                        update_usage_with_llm_data(
                            execution_id=analysis_run_id,
                            db=db,
                            llm_tokens=llm_usage["total_tokens"],
                            input_tokens=llm_usage["input_tokens"],
                            output_tokens=llm_usage["output_tokens"],
                            cost_usd=llm_usage["cost_usd"],
                            models_used=llm_usage["models_used"],
                        )
                        logger.info(
                            "Updated Usage entry with LLM data: analysis_run_id=%s tokens=%s cost=$%.4f",
                            analysis_run_id, llm_usage["total_tokens"], llm_usage["cost_usd"]
                        )
                finally:
                    db.close()
            except Exception as e:
                logger.warning("Failed to update Usage entry with LLM data: %s", e)
            
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
            
            # Update execution status to failed
            if isinstance(ar_id_safe, int):
                try:
                    update_execution_status(ar_id_safe, "failed", error_message=str(e))
                except Exception as update_err:
                    logger.warning("Failed to update execution status to failed: %s", update_err)
                
                # Refund tokens for failed execution
                try:
                    from database import SessionLocal
                    from services.token_service import refund_for_failed_execution
                    db = SessionLocal()
                    try:
                        refunded = refund_for_failed_execution(ar_id_safe, db)
                        if refunded:
                            logger.info(
                                "Tokens refunded for failed analysis analysis_run_id=%s ticker=%s",
                                ar_id_safe, ticker,
                            )
                        else:
                            logger.warning(
                                "Token refund failed or already processed analysis_run_id=%s ticker=%s",
                                ar_id_safe, ticker,
                            )
                    finally:
                        db.close()
                except Exception as refund_err:
                    logger.exception(
                        "Failed to refund tokens for failed analysis analysis_run_id=%s error=%s",
                        ar_id_safe, refund_err,
                    )
            
            analysis_info = self.running_analyses.get(analysis_run_id)
            if analysis_info:
                analysis_info["status"] = "error"
                analysis_info["error"] = str(e)
                self._append_live_activity(
                    analysis_info,
                    kind="status",
                    status="error",
                    summary="Analysis failed",
                    detail=_preview_activity_text(str(e)),
                )
                self._persist_analysis_status(analysis_run_id)
                if analysis_info["progress_callback"]:
                    try:
                        analysis_info["progress_callback"]({"type": "error", "error": str(e)}, analysis_info)
                    except Exception:
                        pass
                # Delete status file after error (analysis is done)
                delete_analysis_status("ticker", analysis_run_id)
        finally:
            # Always close the log file handle to prevent file descriptor leaks
            if log_file_handle:
                try:
                    log_file_handle.close()
                except Exception as close_err:
                    logger.warning("Failed to close log file: %s", close_err)
    
    # Fixed pipeline order for deriving current_agent when missing (deterministic on refresh).
    _AGENT_PIPELINE_ORDER = (
        "Market Analyst", "News & Sentiment Analyst", "Fundamentals Analyst",
        "Technical Analyst", "SEC Analyst",
        "Bull Researcher", "Bear Researcher", "Neutral Researcher", "Research Manager",
        "Trader",
    )

    def get_analysis_status(self, analysis_run_id: int) -> Optional[Dict]:
        """Get current status of a running analysis from shared cache (works across workers).
        If current_agent is missing but some agent is in_progress, set current_agent to the
        first in pipeline order so the UI shows a deterministic value on refresh.
        """
        status = get_analysis_status_from_cache("ticker", analysis_run_id)
        if not status:
            return None
        if status.get("current_agent"):
            return status
        agent_statuses = status.get("agent_statuses") or {}
        for name in self._AGENT_PIPELINE_ORDER:
            if agent_statuses.get(name) == "in_progress":
                status = dict(status)
                status["current_agent"] = name
                break
        return status
