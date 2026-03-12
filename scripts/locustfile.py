"""
Locust load test for the Flowdeck API.

Simulates concurrent users hitting heavy endpoints (widgets, ticker page,
similar-tickers, data API). Use this to stress-test the backend under load
and check tail latency, failure rate, and RPS.

Task weights (relative frequency):
  - load_first_page (6) — simulates dashboard first load: subscriptions → widgets → recent analyzed → market overview
  - get_subscribed_stocks (4) — simulates subscribed-stocks flow: list subscriptions → widgets for those tickers
  - get_widgets (10), get_ticker_page (8), get_similar_tickers (6) — heaviest
  - get_market_overview (5), get_quote (5), get_company_info (4), get_market_movers (4)
  - get_extended_info (3), get_market_overview_section (3)
  - get_analyst_recommendations (2), get_historical (2)
  - get_fundamentals (1), get_future_events (1), start_analysis (1, auth only)
  - Chat/session tasks (auth only): chat_turn (2), chat_stream_turn (1), chat_sessions (1 each)

Authentication:
  - Most endpoints are public. For start_analysis (POST /api/analyses/start),
    set env STRESS_TEST_TOKEN to a JWT or API key (fd_live_...). If unset,
    start_analysis is a no-op.

Install:
  pip install locust

Run (interactive UI):
  locust -f scripts/locustfile.py --host=http://127.0.0.1:8002
  # Open http://127.0.0.1:8089, set users and spawn rate, start.

Run (headless):
  locust -f scripts/locustfile.py --host=http://127.0.0.1:8002 \\
    --users 20 --spawn-rate 4 --run-time 2m --headless

See docs/STRESS_TEST.md for full usage and tips.
"""

import os
import random
from datetime import datetime

from locust import HttpUser, task, between

# Tickers to vary requests (heavy data endpoints)
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM", "V", "JNJ"]

# Market overview section and range options
MARKET_SECTIONS = ["indices", "sectors", "regions", "commodities"]
MARKET_RANGES = ["1d", "1w", "1mo", "3mo", "6mo", "ytd"]


class FlowdeckApiUser(HttpUser):
    """Simulates concurrent users hitting the API."""

    wait_time = between(0.5, 2.0)

    def on_start(self):
        """Set Bearer token from STRESS_TEST_TOKEN env for authenticated tasks (e.g. start_analysis)."""
        self.token = os.environ.get("STRESS_TEST_TOKEN", "").strip()
        self.auth_headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(6)
    def load_first_page(self):
        """Simulate dashboard first load: subscriptions (if auth) → widgets → recent analyzed first page → market overview."""
        if self.token:
            # 1) List subscriptions (dashboard needs this first)
            subs_resp = self.client.get(
                "/api/subscriptions",
                headers=self.auth_headers,
                name="/api/subscriptions [first-page]",
            )
            tickers = TICKERS
            if subs_resp.ok:
                try:
                    data = subs_resp.json()
                    subs = data.get("subscriptions") or []
                    if subs:
                        tickers = [s.get("ticker") for s in subs if s.get("ticker")]
                except Exception:
                    pass
            # 2) Widgets for subscribed tickers
            if tickers:
                self.client.get(
                    "/api/tickers/widgets",
                    params={"tickers": ",".join(tickers[:30])},
                    name="/api/tickers/widgets [subscribed]",
                )
            # 3) First page of recently analyzed (dashboard sidebar)
            today = datetime.now().strftime("%Y-%m-%d")
            self.client.get(
                "/api/tickers/widgets",
                params={
                    "date": today,
                    "only_date": "true",
                    "limit": 20,
                    "offset": 0,
                    "recent_days": "3",
                },
                name="/api/tickers/widgets [recent-first-page]",
            )
        else:
            # Unauthenticated: widgets for a fixed set + market overview
            self.client.get(
                "/api/tickers/widgets",
                params={"tickers": ",".join(TICKERS[:10])},
                name="/api/tickers/widgets [first-page]",
            )
        # 4) Market overview (dashboard top)
        range_ = random.choice(MARKET_RANGES)
        self.client.get(
            "/api/data/market-overview",
            params={"range": range_, "limit_indices": 6, "limit_sectors": 10, "limit_regions": 8, "limit_commodities": 12},
            name="/api/data/market-overview [first-page]",
        )

    @task(4)
    def get_subscribed_stocks(self):
        """Simulate subscribed-stocks flow: list subscriptions → widgets for those tickers. Auth only."""
        if not self.token:
            return
        subs_resp = self.client.get(
            "/api/subscriptions",
            headers=self.auth_headers,
            name="/api/subscriptions [subscribed-stocks]",
        )
        if not subs_resp.ok:
            return
        try:
            data = subs_resp.json()
            subs = data.get("subscriptions") or []
            tickers = [s.get("ticker") for s in subs if s.get("ticker")]
        except Exception:
            tickers = []
        if not tickers:
            tickers = TICKERS[:5]  # fallback so we still hit widgets
        self.client.get(
            "/api/tickers/widgets",
            params={"tickers": ",".join(tickers[:30])},
            headers=self.auth_headers,
            name="/api/tickers/widgets [subscribed-stocks]",
        )

    @task(10)
    def get_widgets(self):
        """Heavy: batch quotes + company names. No auth."""
        self.client.get(
            "/api/tickers/widgets",
            name="/api/tickers/widgets",
        )

    @task(8)
    def get_ticker_page(self):
        """Heavy: quote + company + reports lookup. No auth required."""
        ticker = random.choice(TICKERS)
        self.client.get(
            f"/api/tickers/{ticker}",
            name="/api/tickers/[ticker]",
            headers=self.auth_headers,
        )

    @task(6)
    def get_similar_tickers(self):
        """Heavy: sector batch + enrichment. No auth."""
        ticker = random.choice(TICKERS)
        self.client.get(
            f"/api/data/similar-tickers/{ticker}",
            params={"limit": 10},
            name="/api/data/similar-tickers/[ticker]",
        )

    @task(5)
    def get_market_overview(self):
        """Heavy: indices, sectors, regions, commodities. No auth."""
        range_ = random.choice(MARKET_RANGES)
        self.client.get(
            "/api/data/market-overview",
            params={"range": range_, "limit_indices": 6, "limit_sectors": 10, "limit_regions": 8, "limit_commodities": 12},
            name="/api/data/market-overview",
        )

    @task(4)
    def get_market_movers(self):
        """Top gainers/losers. No auth."""
        self.client.get(
            "/api/data/market-movers",
            params={"count": 8},
            name="/api/data/market-movers",
        )

    @task(3)
    def get_market_overview_section(self):
        """Single section of market overview (indices/sectors/regions/commodities). No auth."""
        section = random.choice(MARKET_SECTIONS)
        range_ = random.choice(MARKET_RANGES)
        self.client.get(
            "/api/data/market-overview/section",
            params={"section": section, "range": range_, "limit": 6},
            name="/api/data/market-overview/section",
        )

    @task(5)
    def get_quote(self):
        self.client.get(
            f"/api/data/quote/{random.choice(TICKERS)}",
            name="/api/data/quote/[ticker]",
        )

    @task(4)
    def get_company_info(self):
        self.client.get(
            f"/api/data/company/{random.choice(TICKERS)}",
            name="/api/data/company/[ticker]",
        )

    @task(3)
    def get_extended_info(self):
        self.client.get(
            f"/api/data/extended-info/{random.choice(TICKERS)}",
            name="/api/data/extended-info/[ticker]",
        )

    @task(2)
    def get_analyst_recommendations(self):
        self.client.get(
            f"/api/data/analyst-recommendations/{random.choice(TICKERS)}",
            name="/api/data/analyst-recommendations/[ticker]",
        )

    @task(2)
    def get_historical(self):
        self.client.get(
            f"/api/data/historical/{random.choice(TICKERS)}",
            params={"period": "1mo", "interval": "1d"},
            name="/api/data/historical/[ticker]",
        )

    @task(1)
    def get_fundamentals(self):
        self.client.get(
            f"/api/data/fundamentals/{random.choice(TICKERS)}",
            name="/api/data/fundamentals/[ticker]",
        )

    @task(1)
    def get_future_events(self):
        self.client.get(
            f"/api/data/future-events/{random.choice(TICKERS)}",
            name="/api/data/future-events/[ticker]",
        )

    @task(1)
    def start_analysis(self):
        """Requires auth (STRESS_TEST_TOKEN). Costs tokens. Very low weight."""
        if not self.token:
            return
        ticker = random.choice(TICKERS)
        self.client.post(
            "/api/analyses/start",
            json={"ticker": ticker},
            headers=self.auth_headers,
            name="/api/analyses/start",
        )

    @task(2)
    def chat_turn(self):
        """Authenticated chat turn with the analyst agent."""
        if not self.token:
            return
        self.client.post(
            "/api/chat",
            json={
                "messages": [
                    {"role": "user", "content": "Quick market summary for stress testing."}
                ],
                "context": {"tickers": random.sample(TICKERS, 2)},
            },
            headers=self.auth_headers,
            name="/api/chat",
        )

    @task(1)
    def chat_stream_turn(self):
        """Authenticated streamed chat turn (SSE)."""
        if not self.token:
            return
        self.client.post(
            "/api/chat/stream",
            json={
                "messages": [
                    {"role": "user", "content": "Streamed market update for stress testing."}
                ],
                "context": {"tickers": random.sample(TICKERS, 2)},
            },
            headers=self.auth_headers,
            name="/api/chat/stream",
        )

    @task(1)
    def chat_sessions_list(self):
        """List existing chat sessions for the current user."""
        if not self.token:
            return
        self.client.get(
            "/api/chat/sessions",
            headers=self.auth_headers,
            name="/api/chat/sessions [GET]",
        )

    @task(1)
    def chat_sessions_create_and_delete(self):
        """Create a chat session and then delete it."""
        if not self.token:
            return
        create_resp = self.client.post(
            "/api/chat/sessions",
            headers=self.auth_headers,
            name="/api/chat/sessions [POST]",
        )
        if create_resp.ok:
            payload = create_resp.json()
            session_id = payload.get("id")
            if session_id is not None:
                self.client.delete(
                    f"/api/chat/sessions/{session_id}",
                    headers=self.auth_headers,
                    name="/api/chat/sessions/{id} [DELETE]",
                )
