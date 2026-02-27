"""FastAPI application for stock dashboard backend."""

import logging
import os
from contextlib import asynccontextmanager

# Ensure backend loggers have sensible defaults (uvicorn configures root; our loggers propagate)
logging.getLogger("services.analysis_service").setLevel(logging.INFO)
logging.getLogger("services.report_service").setLevel(logging.INFO)
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Request, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

from models.schemas import (
    StockQuote,
    StockWidget,
    WidgetsResponse,
    StockPageData,
    Recommendation,
    HistoricalAnalysis,
    ReportScoreSummary,
)
from services.market_data_service import MarketDataService
from services.report_service import ReportService
from services.analysis_service import AnalysisService
from services.news_service import NewsService
from services.info_fetcher import get_info_fetcher
from config import MAJOR_STOCKS, CORS_ORIGINS
from routers.data_api import router as data_router
from routers.users import router as users_router
from routers.subscriptions import router as subscriptions_router
from routers.admin import router as admin_router
from routers.contact import router as contact_router
from routers.payments import router as payments_router
from sync_major_stocks import get_missing_and_skipped, run_analyses_for_tickers
from database import init_db, get_db
from models.db_models import User
from auth import get_current_user, get_current_user_optional, get_current_admin_user, hash_password, verify_password
from sqlalchemy.orm import Session
from services import token_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB and start optional daily sync scheduler."""
    init_db()
    scheduler = None
    if os.environ.get("ENABLE_DAILY_SYNC", "true").lower() in ("true", "1", "yes"):
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            sync_time = os.environ.get("SYNC_SCHEDULE_TIME", "06:00").strip()
            parts = sync_time.split(":")
            hour = int(parts[0]) if parts else 6
            minute = int(parts[1]) if len(parts) > 1 else 0

            def _scheduled_sync_job():
                from datetime import datetime
                analysis_date = datetime.now().strftime("%Y-%m-%d")
                _run_sync_major_stocks_background(analysis_date)

            scheduler = BackgroundScheduler()
            scheduler.add_job(_scheduled_sync_job, "cron", hour=hour, minute=minute)
            scheduler.start()
        except Exception as e:
            print(f"Failed to start daily sync scheduler: {e}")
    yield
    if scheduler is not None:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass


app = FastAPI(title="Stock Dashboard API", lifespan=lifespan)

# CORS middleware - must be added before routes (origins from CORS_ORIGINS env or config)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Initialize services
market_data_service = MarketDataService()
report_service = ReportService()
analysis_service = AnalysisService()
news_service = NewsService()
# Information Fetcher Engine: single entry point for all data (used by /api/data)
get_info_fetcher(market_data_service=market_data_service, news_service=news_service)
# Data API: canonical raw market data for UI and programmatic access
app.include_router(data_router, prefix="/api/data")
app.include_router(users_router)
app.include_router(subscriptions_router)
app.include_router(admin_router)
app.include_router(contact_router)
app.include_router(payments_router)

# WebSocket connections
active_connections: dict[str, WebSocket] = {}


def _normalize_confidence(value: object) -> Optional[float]:
    """Return normalized confidence only when it is a valid 0-1 numeric value."""
    if not isinstance(value, (int, float)):
        return None
    confidence = float(value)
    if 0.0 <= confidence <= 1.0:
        return confidence
    return None


def _normalize_score_confidence(value: object) -> Optional[float]:
    """Convert a 0-10 score to normalized confidence (0-1)."""
    if not isinstance(value, (int, float)):
        return None
    score = float(value)
    if 0.0 <= score <= 10.0:
        return score / 10.0
    return None


def _extract_confidence(*metas: object) -> Optional[float]:
    """Pick first available confidence from metadata, with score/10 fallback."""
    for meta in metas:
        if not isinstance(meta, dict):
            continue
        confidence = _normalize_confidence(meta.get("confidence"))
        if confidence is not None:
            return confidence
        confidence_from_score = _normalize_score_confidence(meta.get("score"))
        if confidence_from_score is not None:
            return confidence_from_score
    return None


def _get_stock_widgets_sync(
    tickers: Optional[str],
    date: Optional[str],
    only_date: bool = False,
    limit: Optional[int] = None,
    offset: int = 0,
    recent_days: Optional[int] = None,
) -> WidgetsResponse:
    """Sync implementation of widget data (runs in thread pool to avoid blocking event loop).
    When only_date=True and tickers is None, returns only tickers that have reports for the given date (no major-stocks list).
    When only_date=True and recent_days>1, returns tickers with reports in that trailing window.
    When only_date=True and limit is set, uses pagination and returns total count."""
    use_major_split = False
    major_set: set[str] = set()
    total_count: Optional[int] = None
    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
    else:
        report_date = date or datetime.now().strftime("%Y-%m-%d")
        recent_window_days = recent_days if recent_days and recent_days > 1 else None
        if only_date and limit is not None:
            if recent_window_days:
                ticker_list, total_count = report_service.get_tickers_with_reports_for_recent_days_paginated(
                    report_date, recent_window_days, limit, offset
                )
            else:
                ticker_list, total_count = report_service.get_tickers_with_reports_for_date_paginated(
                    report_date, limit, offset
                )
        else:
            if only_date:
                if recent_window_days:
                    tickers_for_date = report_service.get_tickers_with_reports_for_recent_days(
                        report_date, recent_window_days
                    )
                else:
                    tickers_for_date = report_service.get_tickers_with_reports_for_date(report_date)
                ticker_list = [t.upper() for t in tickers_for_date]
            else:
                # Home page: only fetch major stocks (UI shows at most 10); avoid loading all tickers with reports for date
                major_set = {t.upper() for t in MAJOR_STOCKS}
                ticker_list = list(MAJOR_STOCKS)
                use_major_split = True

    widgets = []
    cached_fetcher = get_info_fetcher()
    quotes_dict = {}
    try:
        quotes_dict = cached_fetcher.get_quotes_batch(ticker_list)
    except Exception as e:
        print(f"Warning: Failed to fetch market quotes: {e}")

    for ticker in ticker_list:
        quote_data = quotes_dict.get(ticker) if quotes_dict else None
        quote = None
        if quote_data and isinstance(quote_data, dict):
            try:
                quote = StockQuote(**quote_data)
            except Exception:
                quote = None
        # Fallback: batch may return partial data; try single-ticker fetch for missing quotes
        if quote is None:
            try:
                quote_data = cached_fetcher.get_quote(ticker)
                if quote_data and isinstance(quote_data, dict):
                    quote = StockQuote(**quote_data)
            except Exception:
                pass

        latest_date = None
        recommendation = None
        confidence = None
        report_scores = None

        try:
            latest_date = report_service.get_latest_report_date(ticker)

            if latest_date:
                scores_raw = report_service.get_reports_with_scores(ticker, latest_date)
                if scores_raw:
                    report_scores = {
                        k: ReportScoreSummary(score=v.get("score"), score_label=v.get("score_label"))
                        for k, v in scores_raw.items()
                        if v.get("score") is not None or v.get("score_label")
                    }
                    if not report_scores:
                        report_scores = None
                    tip = scores_raw.get("trader_investment_plan") or {}
                    ftd = scores_raw.get("final_trade_decision") or {}
                    if tip.get("recommendation"):
                        recommendation = tip["recommendation"]
                    elif ftd.get("recommendation"):
                        # Legacy fallback for older runs that predate structured trader recommendation.
                        recommendation = ftd.get("recommendation")
                    confidence = _extract_confidence(tip, ftd)
        except Exception as e:
            print(f"Warning: Failed to get reports for {ticker}: {e}")

        is_major = (ticker.upper() in major_set) if use_major_split else None
        if quote:
            widget = StockWidget(
                ticker=ticker,
                current_price=quote.current_price,
                daily_change=quote.daily_change,
                daily_change_percent=quote.daily_change_percent,
                recommendation=recommendation if latest_date else None,
                confidence=confidence,
                report_date=latest_date,
                has_report=latest_date is not None,
                market_status=quote.market_status,
                report_scores=report_scores,
                is_major=is_major,
            )
        else:
            widget = StockWidget(
                ticker=ticker,
                current_price=0.0,
                daily_change=0.0,
                daily_change_percent=0.0,
                recommendation=recommendation if latest_date else None,
                confidence=confidence,
                report_date=latest_date,
                has_report=latest_date is not None,
                market_status="UNKNOWN",
                report_scores=report_scores,
                is_major=is_major,
            )

        widgets.append(widget)

    return WidgetsResponse(widgets=widgets, total=total_count)


def _get_stock_page_sync(ticker: str) -> StockPageData:
    """Sync implementation of stock page data (runs in thread pool to avoid blocking event loop)."""
    from models.schemas import ReportData

    quote = market_data_service.get_current_quote(ticker)
    if quote is None:
        raise HTTPException(
            status_code=404,
            detail=f"Ticker '{ticker}' not found. Check the symbol and try again.",
        )

    # When analysis is generating, use the in-progress run_id so reports count increments 1→2→…→7
    # instead of switching from the previous run (e.g. 5 reports) to the new run (1 report).
    is_generating = False
    generation_analysis_id = None
    generating_run_id = None
    for aid, info in analysis_service.running_analyses.items():
        if info["ticker"] == ticker and info["status"] == "running":
            is_generating = True
            generation_analysis_id = aid
            generating_run_id = info.get("run_id")
            break

    latest_date = generating_run_id if is_generating and generating_run_id else report_service.get_latest_report_date(ticker)
    latest_reports = {}
    latest_reports_with_scores = {}
    latest_reports_with_scores_raw = {}
    latest_recommendation = None

    report_days_ago = None
    if latest_date:
        latest_reports = report_service.get_reports_for_date(ticker, latest_date)
        latest_reports_with_scores_raw = report_service.get_reports_with_scores(ticker, latest_date)

        latest_reports_with_scores = {
            k: ReportData(
                content=v.get('content'),
                score=v.get('score'),
                score_label=v.get('score_label'),
                key_takeaways=v.get('key_takeaways') or [],
                analysis_date=v.get('analysis_date'),
                generated_at=v.get('generated_at'),
                days_ago=v.get('days_ago'),
                models_used=v.get('models_used'),
                bull_viewpoint=v.get('bull_viewpoint'),
                bear_viewpoint=v.get('bear_viewpoint'),
                risky_viewpoint=v.get('risky_viewpoint'),
                safe_viewpoint=v.get('safe_viewpoint'),
                neutral_viewpoint=v.get('neutral_viewpoint')
            )
            for k, v in latest_reports_with_scores_raw.items()
        }
        first_report = next(iter(latest_reports_with_scores_raw.values()), {})
        report_days_ago = first_report.get('days_ago')

        tip_meta = latest_reports_with_scores_raw.get("trader_investment_plan") or {}
        final_meta = latest_reports_with_scores_raw.get("final_trade_decision") or {}
        confidence = _extract_confidence(tip_meta, final_meta)
        if tip_meta.get("recommendation"):
            latest_recommendation = Recommendation(
                recommendation=tip_meta["recommendation"],
                confidence=confidence,
                source="trader_investment_plan",
                date=latest_date
            )
        elif final_meta.get("recommendation"):
            # Legacy fallback for older runs that predate structured trader recommendation.
            latest_recommendation = Recommendation(
                recommendation=final_meta["recommendation"],
                confidence=confidence,
                source="final_trade_decision",
                date=latest_date
            )

    historical = report_service.get_historical_analyses(ticker)
    historical_analyses = []
    for h in historical:
        reports_with_scores = report_service.get_reports_with_scores(ticker, h["date"])
        rec = None
        if (reports_with_scores.get("trader_investment_plan") or {}).get("recommendation"):
            rec = reports_with_scores["trader_investment_plan"]["recommendation"]
        elif (reports_with_scores.get("final_trade_decision") or {}).get("recommendation"):
            # Legacy fallback for older runs that predate structured trader recommendation.
            rec = reports_with_scores["final_trade_decision"]["recommendation"]

        historical_analyses.append(HistoricalAnalysis(
            date=h["date"],
            available_reports=h["available_reports"],
            recommendation=rec
        ))

    investment_plan_meta = latest_reports_with_scores_raw.get("investment_plan") or {}
    expected_return_pct = investment_plan_meta.get("expected_return_pct")
    bear_case_return_pct = investment_plan_meta.get("bear_case_return_pct")
    bull_case_return_pct = investment_plan_meta.get("bull_case_return_pct")

    return StockPageData(
        ticker=ticker,
        quote=quote,
        recommendation=latest_recommendation,
        report_date=latest_date,
        report_days_ago=report_days_ago,
        reports=latest_reports,
        reports_with_scores=latest_reports_with_scores,
        historical_analyses=historical_analyses,
        has_reports=latest_date is not None,
        is_generating=is_generating,
        generation_analysis_id=generation_analysis_id,
        expected_return_pct=expected_return_pct,
        bear_case_return_pct=bear_case_return_pct,
        bull_case_return_pct=bull_case_return_pct,
    )


@app.get("/")
async def root():
    return {"message": "Stock Dashboard API", "status": "running"}

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "tradingagents-api"}


class PublicStatsResponse(BaseModel):
    total_analyses: int
    total_reports: int
    unique_tickers_analyzed: int


@app.get("/api/stats", response_model=PublicStatsResponse)
async def get_public_stats(db: Session = Depends(get_db)):
    """Public stats about analyses and reports (no auth required)."""
    from sqlalchemy import func as sqla_func
    from models.db_models import AnalysisRun, Report
    
    total_analyses = db.query(sqla_func.count(AnalysisRun.id)).scalar() or 0
    total_reports = db.query(sqla_func.count(Report.id)).scalar() or 0
    unique_tickers = db.query(sqla_func.count(sqla_func.distinct(AnalysisRun.ticker))).scalar() or 0
    
    return PublicStatsResponse(
        total_analyses=int(total_analyses),
        total_reports=int(total_reports),
        unique_tickers_analyzed=int(unique_tickers),
    )


class MeResponse(BaseModel):
    user_id: int
    email: str
    name: Optional[str] = None
    token_balance: int
    is_admin: bool = False


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


class TopUpRequest(BaseModel):
    amount: int


@app.get("/api/me", response_model=MeResponse)
async def get_me(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Return current user profile and token balance."""
    balance = token_service.get_balance(current_user.id, db)
    return MeResponse(
        user_id=current_user.id,
        email=current_user.email,
        name=getattr(current_user, "name", None) or None,
        token_balance=balance,
        is_admin=getattr(current_user, "is_admin", False),
    )


@app.patch("/api/me", response_model=MeResponse)
async def update_me(
    body: UpdateProfileRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update name and/or password. If new_password is provided, current_password is required."""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.new_password is not None:
        if not body.current_password:
            raise HTTPException(status_code=400, detail="Current password is required to set a new password")
        if not verify_password(body.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        if len(body.new_password) < 6:
            raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
        user.hashed_password = hash_password(body.new_password)
    if body.name is not None:
        user.name = (body.name or "").strip() or None
    db.commit()
    db.refresh(user)
    balance = token_service.get_balance(user.id, db)
    return MeResponse(
        user_id=user.id,
        email=user.email,
        name=getattr(user, "name", None) or None,
        token_balance=balance,
        is_admin=getattr(user, "is_admin", False),
    )


@app.post("/api/tokens/top-up")
async def top_up_tokens(
    body: TopUpRequest,
    current_user=Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Add tokens to a user's balance (admin only). Use positive amount for credit."""
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    token_service.top_up(current_user.id, body.amount, db)
    return {"token_balance": token_service.get_balance(current_user.id, db)}


@app.get("/api/stocks/widgets", response_model=WidgetsResponse)
async def get_stock_widgets(
    tickers: Optional[str] = Query(None, description="Comma-separated list of tickers"),
    date: Optional[str] = Query(None, description="Date (YYYY-MM-DD) for report filter; default today"),
    only_date: bool = Query(False, description="When set with no tickers: return only tickers with reports for the given date (no major-stocks list)"),
    recent_days: Optional[int] = Query(None, ge=1, le=30, description="When only_date: include reports from the last N days ending at date"),
    limit: Optional[int] = Query(None, description="When only_date: max number of widgets to return (paginated)"),
    offset: int = Query(0, description="When only_date and limit: pagination offset"),
):
    """Get widget data for stocks. Uses cached batch quote fetch for speed. Runs in thread pool (non-blocking)."""
    try:
        return await asyncio.to_thread(_get_stock_widgets_sync, tickers, date, only_date, limit, offset, recent_days)
    except Exception as e:
        print(f"Error in get_stock_widgets: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load widget data: {str(e)}")


@app.get("/api/stocks/{ticker}", response_model=StockPageData)
async def get_stock_page(
    ticker: str,
    current_user=Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Get complete stock page data. Runs in thread pool (non-blocking). Authenticated views are recorded for creator rewards."""
    ticker = ticker.upper()
    try:
        result = await asyncio.to_thread(_get_stock_page_sync, ticker)
        if current_user and result.report_date:
            try:
                token_service.record_view(ticker, result.report_date, current_user.id, db)
            except Exception:
                pass  # Don't fail the response if view recording fails
        if result.report_date:
            try:
                result = result.model_copy(
                    update={
                        "report_view_count": token_service.get_view_count(ticker, result.report_date, db),
                        "report_earned_tokens": token_service.get_run_earned_tokens(ticker, result.report_date, db),
                    }
                )
            except Exception:
                pass
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_stock_page: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load stock page: {str(e)}")


@app.post("/api/analyses/start")
async def start_analysis(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a new analysis. Requires signed-in user; initiator is notified by email when the report is done. Costs 200 tokens."""
    try:
        body = await request.json()
        ticker = body.get("ticker", "").upper()
        if not ticker:
            raise HTTPException(status_code=400, detail="Ticker is required")
        
        analysis_date = body.get("analysis_date") or datetime.now().strftime("%Y-%m-%d")
        analysts = body.get("analysts", ["market", "news", "fundamentals", "technical", "sec"])
        research_depth = body.get("research_depth", 2)
        llm_provider = body.get("llm_provider", "azure")  # Default to Azure
        backend_url = body.get("backend_url")
        shallow_thinker = body.get("shallow_thinker")
        deep_thinker = body.get("deep_thinker")
        initiator_email = (current_user.email or "").strip() or None

        existing_id = analysis_service.get_running_analysis_id(ticker, analysis_date)
        if existing_id is not None:
            return {"analysis_id": existing_id, "ticker": ticker, "date": analysis_date, "existing": True}

        run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        if not token_service.deduct_for_analysis(current_user.id, ticker, run_id, db):
            raise HTTPException(
                status_code=402,
                detail="Insufficient token balance. Need 200 tokens to create a report.",
            )
        
        def progress_callback(chunk, analysis_info):
            """Send progress updates via WebSocket."""
            analysis_id = None
            for aid, info in analysis_service.running_analyses.items():
                if info is analysis_info:
                    analysis_id = aid
                    break
            
            if analysis_id and analysis_id in active_connections:
                ws = active_connections[analysis_id]
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
                    # Schedule the coroutine in the event loop
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(ws.send_json(message))
                    except RuntimeError:
                        # If no event loop, create a new one for this call
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        new_loop.run_until_complete(ws.send_json(message))
                        new_loop.close()
                except Exception as e:
                    print(f"Error sending WebSocket message: {e}")
        
        analysis_id, existing = analysis_service.start_analysis(
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
            run_id=run_id,
        )
        if existing:
            token_service.refund_for_analysis(current_user.id, ticker, run_id, db)
        
        return {"analysis_id": analysis_id, "ticker": ticker, "date": analysis_date, "existing": existing}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except Exception as e:
        print(f"Error starting analysis: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")


@app.get("/api/analyses/{analysis_id}/status")
async def get_analysis_status(analysis_id: str):
    """Get status of a running analysis."""
    status = analysis_service.get_analysis_status(analysis_id)
    if not status:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return status


@app.websocket("/ws/analyses/{analysis_id}")
async def websocket_endpoint(websocket: WebSocket, analysis_id: str):
    """WebSocket endpoint for real-time analysis updates."""
    await websocket.accept()
    active_connections[analysis_id] = websocket
    
    try:
        # Send initial status
        status = analysis_service.get_analysis_status(analysis_id)
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
        
        # Keep connection alive
        while True:
            try:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                break
    except Exception:
        pass
    finally:
        if analysis_id in active_connections:
            del active_connections[analysis_id]


def _run_sync_major_stocks_background(analysis_date: str) -> None:
    """Background task: run analyses for major stocks missing a report for the given date."""
    triggered, skipped = get_missing_and_skipped(analysis_date)
    if not triggered:
        return
    run_analyses_for_tickers(
        tickers=triggered,
        analysis_date=analysis_date,
        analysis_service=analysis_service,
        analysts=["market", "news", "fundamentals", "technical", "sec"],
        research_depth=5,
        llm_provider="azure",
        wait_for_completion=True,
        poll_interval_seconds=10.0,
        completion_timeout_seconds=3600.0,
    )


@app.post("/api/sync/major-stocks")
async def sync_major_stocks(
    request: Request,
    background_tasks: BackgroundTasks,
    _user=Depends(get_current_admin_user),
):
    """
    Ensure each major stock has a report for today (or the given date). Admin only.
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
    background_tasks.add_task(_run_sync_major_stocks_background, analysis_date)
    return {"date": analysis_date, "triggered": triggered, "skipped": skipped}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_config=str(Path(__file__).with_name("uvicorn_logging.json")),
    )
