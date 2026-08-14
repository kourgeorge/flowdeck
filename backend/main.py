"""FastAPI application for ticker dashboard backend."""

import logging
import os
import signal
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure backend loggers have sensible defaults (uvicorn configures root; our loggers propagate)
logging.getLogger("services.analysis_service").setLevel(logging.INFO)
logging.getLogger("services.report_service").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

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
from routers.schedule import router as schedule_router
from routers.public import router as public_router
from routers.share import router as share_router
from routers.tokens import router as tokens_router
from routers.polymarket import router as polymarket_router
from data_layer import init_data_gateway
from data_layer.market import MarketDataLayer
from data_layer.sources.market import CachedMarketSource
from data_layer.sources.reports import ReportDataSource
from data_layer.sources.user import UserPortfolioSource
from data_layer.sources.edgar import EdgarDataSource
from services.analysis_service import AnalysisService
from services.report_service import ReportService
from services.edgar_service import get_edgar_service


# Holds the OS-level lock that elects a single scheduler-owning worker.
# Kept at module scope so the flock is held for the entire process lifetime.
_scheduler_lock_handle = None


def _acquire_scheduler_leadership() -> bool:
    """Elect exactly one process to run the background schedulers.

    With ``uvicorn --workers N`` every worker imports this module and runs
    ``lifespan``, so without gating all N workers would start duplicate
    schedulers -- multiplying upstream fetches, cache writes, and digest emails,
    and causing cross-process SQLite lock contention on the data cache. We take
    an exclusive, non-blocking flock held for the lifetime of the process;
    whichever worker wins is the sole scheduler owner. The others serve
    requests only.

    ``RUN_SCHEDULER`` overrides the election: ``0``/``false`` never runs the
    schedulers (pure API worker), ``1``/``true`` forces this process to run them
    (a single-worker deploy or a dedicated scheduler process).
    """
    global _scheduler_lock_handle
    mode = os.environ.get("RUN_SCHEDULER", "auto").strip().lower()
    if mode in ("0", "false", "no"):
        return False
    if mode in ("1", "true", "yes"):
        return True
    # "auto": elect one worker via an exclusive file lock.
    try:
        import fcntl
    except ImportError:
        # Non-Unix (no flock): assume a single process and run the schedulers.
        return True
    lock_path = os.environ.get(
        "SCHEDULER_LOCK_PATH", str(Path(__file__).with_name(".scheduler.lock"))
    )
    try:
        handle = open(lock_path, "w")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        # Another worker already holds the lock -> this worker is API-only.
        return False
    _scheduler_lock_handle = handle  # keep the handle alive to hold the lock
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB and start optional daily sync and market overview cache refresh."""
    init_db()
    from services.data_cache import ensure_data_cache
    ensure_data_cache()
    scheduler = None
    is_scheduler_leader = _acquire_scheduler_leadership()
    if is_scheduler_leader:
        logger.info(
            "Scheduler leader elected (pid=%s); starting background jobs", os.getpid()
        )
    else:
        logger.info(
            "This worker (pid=%s) is API-only; background schedulers disabled",
            os.getpid(),
        )
    if is_scheduler_leader and os.environ.get("ENABLE_DAILY_SYNC", "true").lower() in ("true", "1", "yes"):
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
    if is_scheduler_leader and os.environ.get("ENABLE_MARKET_OVERVIEW_CACHE_REFRESH", "true").lower() in ("true", "1", "yes"):
        try:
            if scheduler is None:
                from apscheduler.schedulers.background import BackgroundScheduler
                scheduler = BackgroundScheduler()
            # Hard timeout (seconds) for each cache refresh job.  Movers regularly
            # takes 45–95 s; give it a generous 4-minute ceiling so it can never
            # hold the APScheduler slot across a full 5-minute interval cycle.
            _REFRESH_TIMEOUT = int(os.environ.get("MARKET_CACHE_REFRESH_TIMEOUT", "240"))

            def _run_refresh(fn: str) -> None:
                started_at = time.monotonic()

                def _timeout_handler(signum, frame):
                    raise TimeoutError(f"Market cache refresh '{fn}' exceeded {_REFRESH_TIMEOUT}s timeout")

                # SIGALRM is Unix-only and only works on the main thread
                use_alarm = (
                    hasattr(signal, "SIGALRM")
                    and threading.current_thread() is threading.main_thread()
                )
                if use_alarm:
                    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
                    signal.alarm(_REFRESH_TIMEOUT)
                try:
                    from data_layer import get_data_gateway
                    gateway = get_data_gateway()
                    refresh_fn = getattr(gateway, fn, None)
                    if refresh_fn is None:
                        logger.warning("Market cache refresh skipped: gateway has no %s", fn)
                        return
                    logger.info("Starting market cache refresh: %s", fn)
                    refresh_fn()
                    logger.info(
                        "Completed market cache refresh: %s in %.2fs",
                        fn,
                        time.monotonic() - started_at,
                    )
                except TimeoutError:
                    logger.error(
                        "Market cache refresh (%s) killed after %ss timeout (elapsed: %.1fs)",
                        fn,
                        _REFRESH_TIMEOUT,
                        time.monotonic() - started_at,
                    )
                except Exception:
                    logger.exception("Market cache refresh (%s) failed", fn)
                finally:
                    if use_alarm:
                        signal.alarm(0)
                        signal.signal(signal.SIGALRM, old_handler)

            refresh_base = datetime.now()
            _JOB_KWARGS = dict(
                coalesce=True,           # collapse missed runs into one instead of stacking
                max_instances=1,         # never run the same job concurrently
                misfire_grace_time=60,   # drop a run if it missed its slot by >60 s
            )
            scheduler.add_job(
                partial(_run_refresh, "refresh_market_overview_cache"),
                "interval",
                minutes=5,
                id="market_overview_refresh",
                next_run_time=refresh_base,
                **_JOB_KWARGS,
            )
            scheduler.add_job(
                partial(_run_refresh, "refresh_market_movers_cache"),
                "interval",
                minutes=5,
                id="market_movers_refresh",
                next_run_time=refresh_base + timedelta(minutes=1),
                **_JOB_KWARGS,
            )
            scheduler.add_job(
                partial(_run_refresh, "refresh_homepage_widgets_cache"),
                "interval",
                minutes=5,
                id="homepage_widgets_refresh",
                next_run_time=refresh_base + timedelta(minutes=2),
                **_JOB_KWARGS,
            )
            if not scheduler.running:
                scheduler.start()
        except Exception as e:
            print(f"Failed to start market overview cache refresh: {e}")

    # Optional: scheduled jobs (currently User Daily Brief emails: daily/weekly digests)
    if is_scheduler_leader and os.environ.get("ENABLE_DIGEST_SCHEDULER", "false").lower() in ("true", "1", "yes"):
        try:
            if scheduler is None:
                from apscheduler.schedulers.background import BackgroundScheduler

                scheduler = BackgroundScheduler()

            from services.scheduler import run_scheduled_jobs
            import asyncio

            def _run_scheduled_jobs_sync():
                """Wrapper to run async scheduled jobs in a thread-safe manner."""
                try:
                    # Get or create event loop for this thread
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_closed():
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    # Run the coroutine
                    loop.run_until_complete(run_scheduled_jobs())
                except Exception:
                    logger.exception("Scheduled jobs execution failed")

            interval_minutes = int(os.environ.get("DIGEST_SCHEDULER_INTERVAL_MINUTES", "15"))
            scheduler.add_job(
                _run_scheduled_jobs_sync,
                "interval",
                minutes=interval_minutes,
                id="scheduled_jobs",
            )
            if not scheduler.running:
                scheduler.start()
        except Exception as e:
            print(f"Failed to start digest scheduler: {e}")

    # Optional: event-driven re-analysis. Re-runs a subscribed ticker's analysis when its
    # deterministic event signal is both high and much higher than at the last run, so a
    # stored report stops silently describing a stock that has moved on.
    #
    # Scheduled after the 06:00 daily sync on purpose: a ticker the sync just re-analyzed is
    # inside its cooldown and skipped rather than analyzed twice, which leaves the monitor's
    # attention for the subscribed tickers nothing else refreshes. Weekdays only -- the signal
    # is derived from market data that does not move over the weekend.
    #
    # Spend is bounded by COOLDOWN_HOURS in event_monitor_service: a ticker that fires cannot
    # fire again for three days, because the analysis it starts resets its own clock.
    if is_scheduler_leader and os.environ.get("ENABLE_EVENT_MONITOR", "true").lower() in ("true", "1", "yes"):
        try:
            if scheduler is None:
                from apscheduler.schedulers.background import BackgroundScheduler

                scheduler = BackgroundScheduler()

            from database import SessionLocal
            from services.event_monitor_service import run_event_monitor

            def _run_event_monitor_job():
                db = SessionLocal()
                try:
                    logger.info("Event monitor run: %s", run_event_monitor(db))
                except Exception:
                    logger.exception("Event monitor run failed")
                finally:
                    db.close()

            scheduler.add_job(
                _run_event_monitor_job,
                "cron",
                hour=int(os.environ.get("EVENT_MONITOR_HOUR", "7")),
                day_of_week="mon-fri",
                id="event_monitor",
                coalesce=True,
                max_instances=1,
                misfire_grace_time=600,
            )
            if not scheduler.running:
                scheduler.start()
        except Exception as e:
            print(f"Failed to start event monitor scheduler: {e}")

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
report_service = ReportService()
analysis_service = AnalysisService()

# Initialize data layer (single entry point for all data access; owns cache + vendors)
market_source = CachedMarketSource(MarketDataLayer())
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
app_services.set_services(report_service, analysis_service)

# Routers
app.include_router(data_router)
app.include_router(users_router)
app.include_router(subscriptions_router)
app.include_router(tickers_router)
app.include_router(analyses_router)
app.include_router(analyses_ws_router)
app.include_router(me_router)
app.include_router(digest_router)
app.include_router(schedule_router)
app.include_router(public_router)
app.include_router(share_router)
app.include_router(admin_router)
app.include_router(contact_router)
app.include_router(payments_router)
app.include_router(chat_router)
app.include_router(api_keys_router)
app.include_router(tokens_router)
app.include_router(polymarket_router)


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
