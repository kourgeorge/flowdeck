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

from config import CORS_ORIGINS
from database import init_db
from routers import admin as admin_module
from routers import analyses as analyses_module
from routers import tickers as tickers_module
from routers.analyses import run_sync_major_tickers_background
from routers.data_api import router as data_router
from routers.users import router as users_router
from routers.subscriptions import router as subscriptions_router
from routers.admin import router as admin_router
from routers.contact import router as contact_router
from routers.payments import router as payments_router
from routers.chat import router as chat_router
from routers.api_keys import router as api_keys_router
from routers.tickers import router as tickers_router
from routers.analyses import router as analyses_router
from routers.me import router as me_router
from routers.public import router as public_router
from services.analysis_service import AnalysisService
from services.market_data_service import MarketDataService
from services.news_service import NewsService
from services.report_service import ReportService
from services.info_fetcher import get_info_fetcher


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
            from services.info_fetcher import get_info_fetcher

            def _run_refresh(fn):
                try:
                    engine = get_info_fetcher()
                    if hasattr(engine, fn):
                        getattr(engine, fn)()
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
            engine = get_info_fetcher()
            engine.get_quotes_batch(list(MAJOR_TICKERS))
            engine.get_company_info_batch(list(MAJOR_TICKERS))
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
get_info_fetcher(market_data_service=market_data_service, news_service=news_service)

# Routers
app.include_router(data_router, prefix="/api/data")
app.include_router(users_router)
app.include_router(subscriptions_router)
tickers_module.set_services(report_service, market_data_service)
app.include_router(tickers_router)
analyses_module.set_analysis_service(analysis_service)
analyses_module.set_market_data_service(market_data_service)
app.include_router(analyses_router)
app.include_router(me_router)
app.include_router(public_router)
admin_module.set_analysis_service(analysis_service)
app.include_router(admin_router)
app.include_router(contact_router)
app.include_router(payments_router)
app.include_router(chat_router, prefix="/api")
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
