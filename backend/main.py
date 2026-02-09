"""FastAPI application for stock dashboard backend."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime
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
from services.recommendation_parser import RecommendationParser
from services.analysis_service import AnalysisService
from services.news_service import NewsService
from services.info_fetcher import get_info_fetcher
from config import MAJOR_STOCKS, CORS_ORIGINS
from routers.data_api import router as data_router
from routers.users import router as users_router
from routers.subscriptions import router as subscriptions_router
from sync_major_stocks import get_missing_and_skipped, run_analyses_for_tickers
from database import init_db


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
recommendation_parser = RecommendationParser()
analysis_service = AnalysisService()
news_service = NewsService()
# Information Fetcher Engine: single entry point for all data (used by /api/data)
get_info_fetcher(market_data_service=market_data_service, news_service=news_service)
# Data API: canonical raw market data for UI and programmatic access
app.include_router(data_router, prefix="/api/data")
app.include_router(users_router)
app.include_router(subscriptions_router)

# WebSocket connections
active_connections: dict[str, WebSocket] = {}


def _get_stock_widgets_sync(
    tickers: Optional[str],
    date: Optional[str],
) -> WidgetsResponse:
    """Sync implementation of widget data (runs in thread pool to avoid blocking event loop)."""
    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
    else:
        report_date = date or datetime.now().strftime("%Y-%m-%d")
        tickers_for_date = report_service.get_tickers_with_reports_for_date(report_date)
        major_set = {t.upper() for t in MAJOR_STOCKS}
        ticker_list = list(MAJOR_STOCKS) + [t for t in tickers_for_date if t.upper() not in major_set]

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
                    ftd = scores_raw.get("final_trade_decision") or {}
                    if ftd.get("recommendation"):
                        recommendation = ftd["recommendation"]
                        confidence = ftd.get("confidence")
                    if recommendation is None:
                        tip = scores_raw.get("trader_investment_plan") or {}
                        if tip.get("recommendation"):
                            recommendation = tip["recommendation"]
                            confidence = tip.get("confidence")
                if recommendation is None:
                    reports = report_service.get_reports_for_date(ticker, latest_date)
                    if "final_trade_decision" in reports and reports["final_trade_decision"]:
                        rec_data = recommendation_parser.parse_recommendation(reports["final_trade_decision"])
                        if rec_data:
                            recommendation = rec_data.recommendation
                            confidence = rec_data.confidence
                    if recommendation is None and "trader_investment_plan" in reports and reports["trader_investment_plan"]:
                        rec_data = recommendation_parser.parse_recommendation(reports["trader_investment_plan"])
                        if rec_data:
                            recommendation = rec_data.recommendation
                            confidence = rec_data.confidence
        except Exception as e:
            print(f"Warning: Failed to get reports for {ticker}: {e}")

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
            )

        widgets.append(widget)

    return WidgetsResponse(widgets=widgets)


def _get_stock_page_sync(ticker: str) -> StockPageData:
    """Sync implementation of stock page data (runs in thread pool to avoid blocking event loop)."""
    from models.schemas import ReportData

    quote = market_data_service.get_current_quote(ticker)
    if quote is None:
        raise HTTPException(
            status_code=404,
            detail=f"Ticker '{ticker}' not found. Check the symbol and try again.",
        )

    latest_date = report_service.get_latest_report_date(ticker)
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

        final_meta = latest_reports_with_scores_raw.get("final_trade_decision") or {}
        if final_meta.get("recommendation"):
            confidence = final_meta.get("confidence")
            if confidence is None or not (0 <= confidence <= 1):
                confidence = 1.0
            latest_recommendation = Recommendation(
                recommendation=final_meta["recommendation"],
                confidence=confidence,
                source="structured_output",
                date=latest_date
            )
        elif "final_trade_decision" in latest_reports and latest_reports["final_trade_decision"]:
            rec_data = recommendation_parser.parse_recommendation(latest_reports["final_trade_decision"])
            if rec_data:
                latest_recommendation = Recommendation(
                    recommendation=rec_data.recommendation,
                    confidence=rec_data.confidence,
                    source=rec_data.source,
                    date=latest_date
                )
        if latest_recommendation is None and "trader_investment_plan" in latest_reports and latest_reports["trader_investment_plan"]:
            rec_data = recommendation_parser.parse_recommendation(latest_reports["trader_investment_plan"])
            if rec_data:
                latest_recommendation = Recommendation(
                    recommendation=rec_data.recommendation,
                    confidence=rec_data.confidence,
                    source=rec_data.source,
                    date=latest_date
                )

    historical = report_service.get_historical_analyses(ticker)
    historical_analyses = []
    for h in historical:
        reports = report_service.get_reports_for_date(ticker, h["date"])
        rec = None
        if "final_trade_decision" in reports and reports["final_trade_decision"]:
            rec_data = recommendation_parser.parse_recommendation(reports["final_trade_decision"])
            if rec_data:
                rec = rec_data.recommendation
        elif "trader_investment_plan" in reports and reports["trader_investment_plan"]:
            rec_data = recommendation_parser.parse_recommendation(reports["trader_investment_plan"])
            if rec_data:
                rec = rec_data.recommendation

        historical_analyses.append(HistoricalAnalysis(
            date=h["date"],
            available_reports=h["available_reports"],
            recommendation=rec
        ))

    is_generating = False
    generation_analysis_id = None
    for aid, info in analysis_service.running_analyses.items():
        if info["ticker"] == ticker and info["status"] == "running":
            is_generating = True
            generation_analysis_id = aid
            break

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


@app.get("/api/stocks/widgets", response_model=WidgetsResponse)
async def get_stock_widgets(
    tickers: Optional[str] = Query(None, description="Comma-separated list of tickers"),
    date: Optional[str] = Query(None, description="Date (YYYY-MM-DD) for report filter; default today"),
):
    """Get widget data for stocks. Uses cached batch quote fetch for speed. Runs in thread pool (non-blocking)."""
    try:
        return await asyncio.to_thread(_get_stock_widgets_sync, tickers, date)
    except Exception as e:
        print(f"Error in get_stock_widgets: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load widget data: {str(e)}")


@app.get("/api/stocks/{ticker}", response_model=StockPageData)
async def get_stock_page(ticker: str):
    """Get complete stock page data. Runs in thread pool (non-blocking)."""
    ticker = ticker.upper()
    try:
        return await asyncio.to_thread(_get_stock_page_sync, ticker)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_stock_page: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load stock page: {str(e)}")


@app.post("/api/analyses/start")
async def start_analysis(request: Request, background_tasks: BackgroundTasks):
    """Start a new analysis."""
    try:
        body = await request.json()
        ticker = body.get("ticker", "").upper()
        if not ticker:
            raise HTTPException(status_code=400, detail="Ticker is required")
        
        analysis_date = body.get("analysis_date") or datetime.now().strftime("%Y-%m-%d")
        analysts = body.get("analysts", ["market", "news", "fundamentals"])
        research_depth = body.get("research_depth", 5)
        llm_provider = body.get("llm_provider", "azure")  # Default to Azure
        
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
            progress_callback=progress_callback
        )
        
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
        analysts=["market", "news", "fundamentals"],
        research_depth=5,
        llm_provider="azure",
        wait_for_completion=True,
        poll_interval_seconds=10.0,
        completion_timeout_seconds=3600.0,
    )


@app.post("/api/sync/major-stocks")
async def sync_major_stocks(request: Request, background_tasks: BackgroundTasks):
    """
    Ensure each major stock has a report for today (or the given date).
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
    uvicorn.run(app, host="0.0.0.0", port=8002, reload=True)

