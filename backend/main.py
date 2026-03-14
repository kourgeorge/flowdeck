"""FastAPI application for ticker dashboard backend."""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure backend loggers have sensible defaults (uvicorn configures root; our loggers propagate)
logging.getLogger("services.analysis_service").setLevel(logging.INFO)
logging.getLogger("services.report_service").setLevel(logging.INFO)

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

import app_services
from config import CORS_ORIGINS
from database import init_db
from routers.analyses import run_sync_major_tickers_background, router as analyses_router, ws_router as analyses_ws_router
from routers.data_api import router as data_router
from routers.users import router as users_router
from routers.subscriptions import router as subscriptions_router
from routers.admin import router as admin_router
from routers.contact import router as contact_router
from routers.payments import router as payments_router
from routers.chat import router as chat_router
from routers.api_keys import router as api_keys_router
from routers.tickers import router as tickers_router
from routers.me import router as me_router
from routers.digest import router as digest_router
from routers.public import router as public_router
from routers.share import router as share_router
from data_layer import init_data_gateway
from data_layer.sources.market import CachedMarketSource
from data_layer.sources.reports import ReportDataSource
from data_layer.sources.user import UserPortfolioSource
from data_layer.sources.edgar import EdgarDataSource
from services.analysis_service import AnalysisService
from services.market_data_service import MarketDataService
from services.news_service import NewsService
from services.report_service import ReportService
from services.info_fetcher import get_info_fetcher
from services.edgar_service import get_edgar_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB and start optional daily sync and market overview cache refresh."""
    init_db()
    from services.data_cache import ensure_data_cache
    ensure_data_cache()
    scheduler = None
    if os.environ.get("ENABLE_DAILY_SYNC", "true").lower() in ("true", "1", "yes"):
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            sync_time = os.environ.get("SYNC_SCHEDULE_TIME", "06:00").strip()
            parts = sync_time.split(":")
            hour = int(parts[0]) if parts else 6
            minute = int(parts[1]) if len(parts) > 1 else 0

            def _scheduled_sync_job():
                analysis_date = datetime.now().strftime("%Y-%m-%d")
                run_sync_major_tickers_background(analysis_date, analysis_service)

            scheduler = BackgroundScheduler()
            scheduler.add_job(_scheduled_sync_job, "cron", hour=hour, minute=minute)
            scheduler.start()
        except Exception as e:
            print(f"Failed to start daily sync scheduler: {e}")

    # Optional: refresh market overview cache every 5 min so Overview/Regional Map are warm
    if os.environ.get("ENABLE_MARKET_OVERVIEW_CACHE_REFRESH", "true").lower() in ("true", "1", "yes"):
        try:
            if scheduler is None:
                from apscheduler.schedulers.background import BackgroundScheduler
                scheduler = BackgroundScheduler()
            import threading

            def _run_refresh(fn):
                try:
                    from data_layer import get_data_gateway
                    gateway = get_data_gateway()
                    if hasattr(gateway, fn):
                        getattr(gateway, fn)()
                except Exception as e:
                    print(f"Market cache refresh ({fn}) failed: {e}")

            def _refresh_market_overview_cache():
                threading.Thread(target=_run_refresh, args=("refresh_market_overview_cache",), daemon=True).start()

            def _refresh_market_movers_cache():
                threading.Thread(target=_run_refresh, args=("refresh_market_movers_cache",), daemon=True).start()

            scheduler.add_job(_refresh_market_overview_cache, "interval", minutes=5, id="market_overview_refresh")
            scheduler.add_job(_refresh_market_movers_cache, "interval", minutes=5, id="market_movers_refresh")
            if not scheduler.running:
                scheduler.start()
            # Populate cache on startup in background so first request is fast (non-blocking)
            threading.Thread(target=_run_refresh, args=("refresh_market_overview_cache",), daemon=True).start()
            threading.Thread(target=_run_refresh, args=("refresh_market_movers_cache",), daemon=True).start()
        except Exception as e:
            print(f"Failed to start market overview cache refresh: {e}")

    # Warm homepage widgets cache (MAJOR_TICKERS quotes + company info) so first load is fast
    import threading as _threading
    from config import MAJOR_TICKERS

    def _warm_homepage_cache():
        try:
            from data_layer import get_data_gateway
            gateway = get_data_gateway()
            gateway.get_quotes_batch(list(MAJOR_TICKERS))
            gateway.get_company_info_batch(list(MAJOR_TICKERS))
        except Exception as e:
            print(f"Homepage cache warm failed: {e}")

    _threading.Thread(target=_warm_homepage_cache, daemon=True).start()

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
cached_info_fetcher = get_info_fetcher(
    market_data_service=market_data_service, news_service=news_service
)

# Initialize data layer (single entry point for all data access)
market_source = CachedMarketSource(cached_info_fetcher)
report_source = ReportDataSource(report_service)
user_source = UserPortfolioSource()
edgar_source = EdgarDataSource(get_edgar_service())
init_data_gateway(
    market=market_source,
    reports=report_source,
    user=user_source,
    edgar=edgar_source,
)

# Shared services for routers that need them (tickers, analyses)
app_services.set_services(report_service, market_data_service, analysis_service)

# Routers
app.include_router(data_router)
app.include_router(users_router)
app.include_router(subscriptions_router)
app.include_router(tickers_router)
app.include_router(analyses_router)
app.include_router(analyses_ws_router)
app.include_router(me_router)
app.include_router(digest_router)
app.include_router(public_router)
app.include_router(share_router)
app.include_router(admin_router)
app.include_router(contact_router)
app.include_router(payments_router)
app.include_router(chat_router)
app.include_router(api_keys_router)


@app.get("/")
async def root():
    return {"message": "Stock Dashboard API", "status": "running"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "tradingagents-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        workers=1,
        log_config=str(Path(__file__).with_name("uvicorn_logging.json")),
    )
