"""Analysis start, status, WebSocket progress, and major-stocks sync."""

import asyncio
import json
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

from auth import get_current_user, get_current_admin_user, decode_token
from database import get_db, SessionLocal
from models.db_models import User as UserModel
from services.analysis_service import AnalysisService
from services.info_fetcher import get_info_fetcher
from services.market_data_service import MarketDataService
from services import token_service
from sync_major_stocks import get_missing_and_skipped, run_analyses_for_tickers

router = APIRouter(tags=["analyses"])

active_connections: dict[str, WebSocket] = {}

_analysis_service: Optional[AnalysisService] = None
_market_data_service: Optional[MarketDataService] = None


def set_analysis_service(service: AnalysisService) -> None:
    """Set the shared analysis service (called from main.py)."""
    global _analysis_service
    _analysis_service = service


def set_market_data_service(service: MarketDataService) -> None:
    """Set the shared market data service (called from main.py)."""
    global _market_data_service
    _market_data_service = service


def _get_analysis_service() -> AnalysisService:
    if _analysis_service is None:
        raise RuntimeError("Analyses router: analysis_service not set")
    return _analysis_service


def _get_market_data_service() -> MarketDataService:
    if _market_data_service is None:
        raise RuntimeError("Analyses router: market_data_service not set")
    return _market_data_service


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
            analysts=["market", "news", "fundamentals", "technical", "sec"],
            research_depth=5,
            llm_provider="azure",
            wait_for_completion=True,
            poll_interval_seconds=10.0,
            completion_timeout_seconds=3600.0,
        )
    finally:
        db.close()


@router.post("/api/analyses/start")
async def start_analysis(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a new analysis. Requires signed-in user; initiator is notified by email when the report is done. Costs 200 tokens."""
    analysis_service = _get_analysis_service()
    try:
        body = await request.json()
        ticker = body.get("ticker", "").upper()
        if not ticker:
            raise HTTPException(status_code=400, detail="Ticker is required")

        # Use cached fetcher so quote check goes through cache (same as data API)
        quote = await asyncio.to_thread(get_info_fetcher().get_quote, ticker)
        if quote is None:
            raise HTTPException(
                status_code=404,
                detail=f"Ticker '{ticker}' not found. Check the symbol and try again.",
            )

        analysis_date = body.get("analysis_date") or datetime.now().strftime("%Y-%m-%d")
        analysts = body.get("analysts", ["market", "news", "fundamentals", "technical", "sec"])
        research_depth = body.get("research_depth", 2)
        llm_provider = (body.get("llm_provider") or os.environ.get("LLM_PROVIDER") or "azure").strip().lower()
        backend_url = body.get("backend_url")
        shallow_thinker = body.get("shallow_thinker")
        deep_thinker = body.get("deep_thinker")
        initiator_email = (current_user.email or "").strip() or None

        existing_run_id = analysis_service.get_running_analysis_run_id(ticker, analysis_date)
        if existing_run_id is not None:
            return {"analysis_run_id": existing_run_id, "ticker": ticker, "date": analysis_date, "existing": True}

        deduct_ok, analysis_run_id = token_service.deduct_for_analysis(current_user.id, ticker, db)
        if not deduct_ok:
            raise HTTPException(
                status_code=402,
                detail="Insufficient token balance. Need 200 tokens to create a report.",
            )

        def progress_callback(chunk, analysis_info):
            run_id = analysis_info.get("analysis_run_id")
            run_id_key = str(run_id) if run_id is not None else None
            if run_id_key and run_id_key in active_connections:
                ws = active_connections[run_id_key]
                try:
                    message = {
                        "type": "progress",
                        "data": {
                            "chunk": str(chunk),
                            "agent_statuses": analysis_info.get("agent_statuses", {}),
                            "current_agent": analysis_info.get("current_agent"),
                            "reports": analysis_info.get("reports", {}),
                            "status": analysis_info.get("status", "running"),
                        }
                    }
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(ws.send_json(message))
                    except RuntimeError:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        new_loop.run_until_complete(ws.send_json(message))
                        new_loop.close()
                except Exception as e:
                    print(f"Error sending WebSocket message: {e}")

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
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except Exception as e:
        print(f"Error starting analysis: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")


@router.get("/api/analyses/{analysis_run_id}/status")
async def get_analysis_status(
    analysis_run_id: int,
    _current_user=Depends(get_current_user),
):
    """Get status of a running analysis. Requires authentication."""
    analysis_service = _get_analysis_service()
    status = analysis_service.get_analysis_status(analysis_run_id)
    if not status:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return status


@router.websocket("/ws/analyses/{analysis_run_id}")
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
        try:
            user_id = int(sub)
        except ValueError:
            await websocket.close(code=4001, reason="Invalid token subject")
            return
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            await websocket.close(code=4001, reason="User not found")
            return
    finally:
        db.close()

    await websocket.accept()
    active_connections[analysis_run_id] = websocket

    analysis_service = _get_analysis_service()
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
        if analysis_run_id in active_connections:
            del active_connections[analysis_run_id]


@router.post("/api/sync/major-stocks")
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
    analysis_service = _get_analysis_service()
    background_tasks.add_task(run_sync_major_tickers_background, analysis_date, analysis_service)
    return {"date": analysis_date, "triggered": triggered, "skipped": skipped}
