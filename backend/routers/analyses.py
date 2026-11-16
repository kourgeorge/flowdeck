"""Analysis start, status, WebSocket progress, and major-stocks sync."""

import asyncio
import json
import re
from datetime import datetime
from typing import Any, Dict, Optional, Union

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

import app_services
from api_docs import ERR_402, ERR_404_TICKER
from auth import get_current_user, get_current_admin_user, decode_token
from database import get_db, SessionLocal
from models.db_models import User as UserModel
from services.analysis_service import AnalysisService
from services.analysis_executor import AnalysisQueueFull
from services import token_service
from data_layer import get_data_gateway
from ai_engine.llm_provider import configured_provider
from config import ALL_ANALYSTS
from sync_major_stocks import get_missing_and_skipped, run_analyses_for_tickers

# The endpoint validates JSON explicitly, preserving 400 for a missing ticker
# and using 422 for invalid values or attempts to override server AI policy.
# Keep this documentation schema aligned with that validation.
START_ANALYSIS_REQUEST_BODY = {
    "required": True,
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["ticker"],
                "properties": {
                    "ticker": {"type": "string", "description": "Ticker symbol. Required."},
                    "analysis_date": {
                        "type": "string",
                        "format": "date",
                        "description": "YYYY-MM-DD. Defaults to today.",
                    },
                    "analysts": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(ALL_ANALYSTS)},
                        "description": (
                            "Analysts to run. Defaults to all six. Each maps to one report "
                            "key -- note `social` produces `sentiment_report`, not `news_report`."
                        ),
                    },
                    "research_depth": {
                        "type": "integer",
                        "default": 2,
                        "minimum": 1,
                        "maximum": 5,
                        "description": "Debate/tool-call depth per analyst, from 1 to 5.",
                    },
                    "llm_provider": {
                        "type": "string",
                        "description": "Server-configured provider. If supplied, must match LLM_PROVIDER (default azure).",
                    },
                },
            },
            "examples": {
                "minimal": {"summary": "Minimal request", "value": {"ticker": "AAPL"}},
                "full": {
                    "summary": "All fields set",
                    "value": {
                        "ticker": "AAPL",
                        "analysis_date": "2026-08-28",
                        "analysts": list(ALL_ANALYSTS),
                        "research_depth": 2,
                    },
                },
            },
        }
    },
}

START_ANALYSIS_RESPONSES: Dict[Union[int, str], Dict[str, Any]] = {
    200: {
        "description": (
            "A run was started, or an already-running run for the same ticker/date was "
            "reused (`existing: true`, and the 200 tokens already spent on it are refunded)."
        ),
        "content": {
            "application/json": {
                "examples": {
                    "fresh_run": {
                        "summary": "New run accepted",
                        "value": {
                            "analysis_run_id": 1234,
                            "ticker": "AAPL",
                            "date": "2026-08-28",
                            "existing": False,
                        },
                    },
                    "existing_run": {
                        "summary": "Merged into an already-running run",
                        "value": {
                            "analysis_run_id": 1234,
                            "ticker": "AAPL",
                            "date": "2026-08-28",
                            "existing": True,
                        },
                    },
                }
            }
        },
    },
    400: {"content": {"application/json": {"example": {"detail": "Ticker is required"}}}},
    402: {"content": {"application/json": {"example": ERR_402}}},
    404: {"content": {"application/json": {"example": ERR_404_TICKER}}},
    503: {
        "description": "Analysis capacity is full. Retry after the Retry-After interval.",
        "content": {"application/json": {"example": {"detail": "Analysis queue is full. Please try again later."}}},
    },
    500: {
        "content": {
            "application/json": {
                "example": {"detail": "Failed to start analysis: <error message>"}
            }
        }
    },
}

router = APIRouter(prefix="/api", tags=["Analyses"])
# WebSocket at /ws/... (no /api prefix); included separately in main
ws_router = APIRouter(tags=["Analyses"])

# Every viewer of a run gets its own socket. Runs are shared (a second start for the
# same ticker/date returns `existing: True`) and every signed-in visitor of a
# generating ticker page subscribes, so one socket per run would let viewer B's
# connect silently cut viewer A off, and A's disconnect leave B with nothing.
active_connections: dict[str, set[WebSocket]] = {}
_send_locks: dict[str, asyncio.Lock] = {}

# The loop that owns the sockets. Progress callbacks fire from analysis worker
# threads (services/analysis_executor.py thread pool), where there is no loop; a
# socket can only be written from the loop that accepted it, so sends are handed
# here with run_coroutine_threadsafe instead of spinning up throwaway loops.
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def remember_main_loop() -> None:
    """Record the running loop. Call from async code on the server loop."""
    global _main_loop
    try:
        _main_loop = asyncio.get_running_loop()
    except RuntimeError:
        pass


def add_connection(run_id_key: str, websocket: WebSocket) -> None:
    active_connections.setdefault(run_id_key, set()).add(websocket)


def remove_connection(run_id_key: str, websocket: WebSocket) -> None:
    sockets = active_connections.get(run_id_key)
    if not sockets:
        return
    sockets.discard(websocket)
    if not sockets:
        active_connections.pop(run_id_key, None)
        _send_locks.pop(run_id_key, None)


async def _send_to_viewers(run_id_key: str, messages: list[dict]) -> None:
    # The lock keeps frames in callback order: each send awaits the transport, so
    # without it a later progress frame could overtake an earlier one or land
    # after `completed`.
    lock = _send_locks.setdefault(run_id_key, asyncio.Lock())
    async with lock:
        for websocket in list(active_connections.get(run_id_key, ())):
            for message in messages:
                try:
                    await websocket.send_json(message)
                except Exception:
                    # A closed tab often surfaces here before the receive loop notices.
                    remove_connection(run_id_key, websocket)
                    break


def broadcast_to_run(run_id_key: str, messages: list[dict]) -> None:
    """Send frames to every viewer of a run. Safe to call from any thread."""
    loop = _main_loop
    if loop is None or loop.is_closed() or not active_connections.get(run_id_key):
        return
    asyncio.run_coroutine_threadsafe(_send_to_viewers(run_id_key, messages), loop)


def build_progress_frames(chunk: Any, analysis_info: dict) -> list[dict]:
    """The `progress` frame (shape kept for older clients) plus a top-level
    `completed`/`failed` frame when the service signals the end of the run.

    The service ends a run by calling back with `{"type": "completed"}` or
    `{"type": "error", "error": ...}` as the chunk; before this, that only showed up
    stringified inside `data.chunk`, so clients listening for `completed` never fired.
    """
    status = analysis_info.get("status", "running")
    frames: list[dict] = [{
        "type": "progress",
        "data": {
            "chunk": str(chunk),
            "agent_statuses": analysis_info.get("agent_statuses", {}),
            "current_agent": analysis_info.get("current_agent"),
            "current_agents": analysis_info.get("current_agents", []),
            "live_activities": analysis_info.get("live_activities", []),
            "live_trace": analysis_info.get("live_trace", []),
            "reports": analysis_info.get("reports", {}),
            "status": status,
        },
    }]
    end_type = chunk.get("type") if isinstance(chunk, dict) else None
    base = {
        "analysis_run_id": analysis_info.get("analysis_run_id"),
        "ticker": analysis_info.get("ticker"),
        "date": analysis_info.get("date"),
    }
    if end_type == "completed":
        frames.append({"type": "completed", "data": {**base, "status": "completed"}})
    elif end_type == "error":
        # Named `failed`, not `error`: the browser client already emits its own
        # `error` event for transport errors, and `error` frames here mean
        # "run not found" in reply to get_status.
        frames.append({"type": "failed", "data": {
            **base,
            "status": "cancelled" if status == "cancelled" else "failed",
            "error": chunk.get("error"),
        }})
    return frames


def progress_callback(chunk: Any, analysis_info: dict) -> None:
    run_id = analysis_info.get("analysis_run_id")
    if run_id is None:
        return
    try:
        broadcast_to_run(str(run_id), build_progress_frames(chunk, analysis_info))
    except Exception as e:
        print(f"Error sending WebSocket message: {e}")


def run_sync_major_tickers_background(analysis_date: str, analysis_service: AnalysisService) -> None:
    """Background task: run analyses for major tickers missing a report for the given date."""
    triggered, skipped = get_missing_and_skipped(analysis_date)
    if not triggered:
        return
    db = SessionLocal()
    try:
        run_analyses_for_tickers(
            tickers=triggered,
            analysis_date=analysis_date,
            analysis_service=analysis_service,
            db=db,
            creator_id=None,
            analysts=list(ALL_ANALYSTS),
            research_depth=5,
            llm_provider=configured_provider(),
            wait_for_completion=True,
            poll_interval_seconds=10.0,
            completion_timeout_seconds=3600.0,
        )
    finally:
        db.close()


@router.post(
    "/analyses/start",
    summary="Start an analysis",
    response_description="The analysis run id to poll or subscribe to.",
    openapi_extra={"requestBody": START_ANALYSIS_REQUEST_BODY},
    responses=START_ANALYSIS_RESPONSES,
)
async def start_analysis(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Queue a new analysis. Requires signed-in user; initiator is notified by email when the report is done. Costs 200 tokens.

    Runs wait with status `queued` until capacity is available. There is no default
    queue-length cap. If an optional configured cap is full, return HTTP 503 and
    refund the rejected run's charge.

    Each analyst maps to one report key -- `social` produces `sentiment_report`, not
    `news_report`. Each run builds on the ticker's prior report and ends with a
    `## What changed since {date}` section rather than starting from scratch.
    """
    analysis_service = app_services.get_analysis_service()
    analysis_run_id = None
    try:
        try:
            body = await request.json()
        except ValueError as exc:
            # Starlette surfaces unparseable bodies as JSONDecodeError (a ValueError);
            # the API docs promise 400 for that case, while 422 stays for valid JSON
            # that isn't an object.
            raise HTTPException(status_code=400, detail="Invalid JSON in request body") from exc
        if not isinstance(body, dict) or not isinstance(body.get("ticker", ""), str):
            raise HTTPException(422, "Request body must contain a ticker string")
        ticker = body.get("ticker", "").strip().upper()
        if not ticker:
            raise HTTPException(status_code=400, detail="Ticker is required")
        if not re.fullmatch(r"[A-Z0-9.^=-]{1,32}", ticker):
            raise HTTPException(422, "Invalid ticker symbol")

        analysis_date = body.get("analysis_date") or datetime.now().strftime("%Y-%m-%d")
        try:
            if not isinstance(analysis_date, str) or datetime.strptime(analysis_date, "%Y-%m-%d").strftime("%Y-%m-%d") != analysis_date:
                raise ValueError
        except ValueError as exc:
            raise HTTPException(422, "analysis_date must be YYYY-MM-DD") from exc
        analysts = body.get("analysts", list(ALL_ANALYSTS))
        research_depth = body.get("research_depth", 2)
        if type(research_depth) is not int or not 1 <= research_depth <= 5:
            raise HTTPException(422, "research_depth must be an integer between 1 and 5")
        if not isinstance(analysts, list) or not analysts or any(a not in ALL_ANALYSTS for a in analysts):
            raise HTTPException(422, "Select at least one supported analyst")
        analysts = list(dict.fromkeys(analysts))
        llm_provider = configured_provider()
        if any(body.get(key) for key in ("backend_url", "shallow_thinker", "deep_thinker")):
            raise HTTPException(422, "Provider endpoints and models are configured by the server")
        if body.get("llm_provider") and body["llm_provider"] != llm_provider:
            raise HTTPException(422, "Provider is configured by the server")
        backend_url = shallow_thinker = deep_thinker = None
        initiator_email = (current_user.email or "").strip() or None

        # Validate policy before any vendor access, charge, or background work.
        quote = await asyncio.to_thread(get_data_gateway().get_quote, ticker)
        if quote is None:
            raise HTTPException(
                status_code=404,
                detail=f"Ticker '{ticker}' not found. Check the symbol and try again.",
            )

        existing_run_id = analysis_service.get_running_analysis_run_id(ticker, analysis_date)
        if existing_run_id is not None:
            return {"analysis_run_id": existing_run_id, "ticker": ticker, "date": analysis_date, "existing": True}

        deduct_ok, analysis_run_id = token_service.deduct_for_analysis(current_user.id, ticker, db)
        if not deduct_ok:
            raise HTTPException(
                status_code=402,
                detail="Insufficient token balance. Need 200 tokens to create a report.",
            )

        remember_main_loop()

        returned_run_id, existing = analysis_service.start_analysis(
            ticker=ticker,
            analysis_date=analysis_date,
            analysts=analysts,
            research_depth=research_depth,
            llm_provider=llm_provider,
            backend_url=backend_url,
            shallow_thinker=shallow_thinker,
            deep_thinker=deep_thinker,
            progress_callback=progress_callback,
            initiator_email=initiator_email,
            analysis_run_id=analysis_run_id,
        )
        if existing:
            token_service.refund_for_execution(current_user.id, analysis_run_id, db)

        return {"analysis_run_id": returned_run_id, "ticker": ticker, "date": analysis_date, "existing": existing}
    except AnalysisQueueFull as e:
        raise HTTPException(status_code=503, detail=str(e), headers={"Retry-After": "60"})
    except HTTPException:
        raise
    except Exception as e:
        if analysis_run_id is not None:
            analysis_service._fail_analysis(analysis_run_id, "Unable to start analysis")
        print(f"Error starting analysis: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")


@router.get("/analyses/{analysis_run_id}/status")
async def get_analysis_status(
    analysis_run_id: int,
    _current_user=Depends(get_current_user),
):
    """Get status of a running analysis. Requires authentication."""
    analysis_service = app_services.get_analysis_service()
    status = analysis_service.get_analysis_status(analysis_run_id)
    if not status:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return status


@ws_router.websocket("/ws/analyses/{analysis_run_id}")
async def websocket_endpoint(websocket: WebSocket, analysis_run_id: str, token: Optional[str] = Query(None)):
    """WebSocket endpoint for real-time analysis updates. Requires a valid Bearer token via ?token= query param."""
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    sub = decode_token(token)
    if not sub:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.auth_subject == sub).first()
        if not user:
            await websocket.close(code=4001, reason="User not found")
            return
    finally:
        db.close()

    await websocket.accept()
    remember_main_loop()
    add_connection(analysis_run_id, websocket)

    analysis_service = app_services.get_analysis_service()
    try:
        run_id_int = int(analysis_run_id)
        status = analysis_service.get_analysis_status(run_id_int)
        if status:
            await websocket.send_json({
                "type": "status",
                "data": {
                    "status": status["status"],
                    "ticker": status["ticker"],
                    "date": status["date"],
                    "agent_statuses": status.get("agent_statuses", {}),
                    "current_agent": status.get("current_agent"),
                    "current_agents": status.get("current_agents", []),
                    "live_activities": status.get("live_activities", []),
                    "live_trace": status.get("live_trace", []),
                }
            })

        while True:
            try:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
                elif data == "get_status":
                    status = analysis_service.get_analysis_status(run_id_int)
                    if status:
                        await websocket.send_json({
                            "type": "status",
                            "data": {
                                "status": status.get("status"),
                                "ticker": status.get("ticker"),
                                "date": status.get("date"),
                                "agent_statuses": status.get("agent_statuses", {}),
                                "current_agent": status.get("current_agent"),
                                "current_agents": status.get("current_agents", []),
                                "live_activities": status.get("live_activities", []),
                                "live_trace": status.get("live_trace", []),
                            }
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Analysis not found or completed"
                        })
            except WebSocketDisconnect:
                break
    except Exception:
        pass
    finally:
        remove_connection(analysis_run_id, websocket)


@router.post("/sync/major-stocks")
async def sync_major_tickers(
    request: Request,
    background_tasks: BackgroundTasks,
    _user=Depends(get_current_admin_user),
):
    """
    Ensure each major ticker has a report for today (or the given date). Admin only.
    Returns immediately with which tickers were triggered vs skipped; analyses run in background.
    """
    body = {}
    try:
        raw = await request.body()
        if raw:
            body = json.loads(raw)
    except Exception:
        pass
    analysis_date = body.get("analysis_date") or datetime.now().strftime("%Y-%m-%d")
    triggered, skipped = get_missing_and_skipped(analysis_date)
    analysis_service = app_services.get_analysis_service()
    background_tasks.add_task(run_sync_major_tickers_background, analysis_date, analysis_service)
    return {"date": analysis_date, "triggered": triggered, "skipped": skipped}
