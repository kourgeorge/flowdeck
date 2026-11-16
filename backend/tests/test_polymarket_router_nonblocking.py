"""The Polymarket ticker route must not block the event loop (T-53).

The server runs with one worker, and since T-48 every Daily Brief calls
/api/polymarket/ticker/{ticker} once per priority ticker. The service call is
synchronous and slow, so if it runs inline every other request waits on it.
"""

import asyncio
import time

import httpx
from fastapi import FastAPI

from auth import get_current_user_optional
from routers import polymarket as polymarket_router


class _SlowService:
    def __init__(self, delay=1.0):
        self.delay = delay
        self.calls = []

    def get_ticker_sentiment(self, ticker, company_info=None, max_markets=50, top_n=10):
        self.calls.append({"max_markets": max_markets, "top_n": top_n})
        time.sleep(self.delay)
        return {
            "ticker": ticker.upper(),
            "overall_sentiment": None,
            "confidence": None,
            "trend": "unknown",
            "narratives": {},
            "top_markets": [],
            "last_updated": "2026-11-16T00:00:00",
            "market_count": 0,
        }


def _app(monkeypatch, service):
    async def no_company_info(ticker):
        return None

    monkeypatch.setattr(polymarket_router, "get_polymarket_service", lambda: service)
    monkeypatch.setattr(polymarket_router, "_fetch_company_info", no_company_info)
    app = FastAPI()
    app.include_router(polymarket_router.router)
    app.dependency_overrides[get_current_user_optional] = lambda: None

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    return app


def test_slow_ticker_sentiment_does_not_block_other_requests(monkeypatch):
    service = _SlowService()
    app = _app(monkeypatch, service)

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            slow = asyncio.create_task(client.get("/api/polymarket/ticker/NVDA"))
            # Let the slow request get into the service call before timing the ping.
            deadline = time.monotonic() + 5
            while not service.calls and not slow.done():
                assert time.monotonic() < deadline, "slow request never reached the service"
                await asyncio.sleep(0.01)
            # If the route ran the service inline, the loop was frozen for the
            # whole call and the slow request is already finished here.
            assert not slow.done(), "ticker route blocked the event loop"
            start = time.monotonic()
            ping = await client.get("/ping")
            ping_elapsed = time.monotonic() - start
            slow_resp = await slow
        return ping, ping_elapsed, slow_resp

    ping, ping_elapsed, slow_resp = asyncio.run(run())
    assert ping.status_code == 200
    assert ping_elapsed < 0.5
    assert slow_resp.status_code == 200
    assert slow_resp.json()["ticker"] == "NVDA"


def test_ticker_route_passes_and_caps_market_counts(monkeypatch):
    service = _SlowService(delay=0)
    app = _app(monkeypatch, service)

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            ok = await client.get("/api/polymarket/ticker/NVDA", params={"top_n": 3, "max_markets": 30})
            default = await client.get("/api/polymarket/ticker/NVDA")
            too_many = await client.get("/api/polymarket/ticker/NVDA", params={"top_n": 500})
        return ok, default, too_many

    ok, default, too_many = asyncio.run(run())
    assert ok.status_code == 200
    assert default.status_code == 200
    assert too_many.status_code == 422
    assert service.calls == [
        {"max_markets": 30, "top_n": 3},
        {"max_markets": 100, "top_n": 30},
    ]
