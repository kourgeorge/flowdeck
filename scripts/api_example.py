#!/usr/bin/env python3
"""
Example script demonstrating API access to the Flowdeck application.

Shows both:
  - Unauthenticated access (public endpoints, no signup required)
  - Authenticated access (signed-up users with JWT token)

Usage:
  python scripts/api_example.py [--base-url http://localhost:8002] [--no-register]

Requires the backend to be running (e.g. python run.py or uvicorn backend.main:app --port 8002).
"""

import argparse
import json
import sys
from datetime import datetime

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Flowdeck API access examples")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8002",
        help="API base URL (default: http://localhost:8002)",
    )
    parser.add_argument(
        "--no-register",
        action="store_true",
        help="Skip registration; use --email/--password for login only (user must exist)",
    )
    parser.add_argument(
        "--email",
        default=None,
        help="Email for login (when --no-register). Default: demo-{timestamp}@example.com",
    )
    parser.add_argument(
        "--password",
        default="demo123456",
        help="Password for register/login (default: demo123456)",
    )
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    session = requests.Session()
    session.headers["Content-Type"] = "application/json"

    # -------------------------------------------------------------------------
    # 1. UNAUTHENTICATED ACCESS (no signup, no token)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("1. UNAUTHENTICATED ACCESS (no token required)")
    print("=" * 70)

    # Health check
    print("\n[GET /health]")
    r = session.get(f"{base}/health")
    print(f"  Status: {r.status_code}")
    print(f"  Body:   {r.json()}")

    # Root
    print("\n[GET /]")
    r = session.get(f"{base}/")
    print(f"  Status: {r.status_code}")
    print(f"  Body:   {r.json()}")

    # Stock widgets (public)
    print("\n[GET /api/stocks/widgets?tickers=AAPL]")
    r = session.get(f"{base}/api/stocks/widgets", params={"tickers": "AAPL"})
    print(f"  Status: {r.status_code}")
    data = r.json()
    if r.ok and data.get("widgets"):
        w = data["widgets"][0]
        print(f"  Body:   ticker={w.get('ticker')}, price={w.get('current_price')}, has_report={w.get('has_report')}")
    else:
        print(f"  Body:   {json.dumps(data)[:200]}...")

    # Data API - quote (public)
    print("\n[GET /api/data/quote/AAPL]")
    r = session.get(f"{base}/api/data/quote/AAPL")
    print(f"  Status: {r.status_code}")
    if r.ok:
        q = r.json()
        print(f"  Body:   symbol={q.get('symbol')}, price={q.get('current_price')}")
    else:
        print(f"  Body:   {r.text[:150]}")

    # Data API - company info (public)
    print("\n[GET /api/data/company/AAPL]")
    r = session.get(f"{base}/api/data/company/AAPL")
    print(f"  Status: {r.status_code}")
    if r.ok:
        c = r.json()
        print(f"  Body:   {c.get('name')}, sector={c.get('sector')}")
    else:
        print(f"  Body:   {r.text[:150]}")

    # Stock page (works without auth; optional auth records view for creator rewards)
    print("\n[GET /api/stocks/AAPL] (no token)")
    r = session.get(f"{base}/api/stocks/AAPL")
    print(f"  Status: {r.status_code}")
    if r.ok:
        s = r.json()
        print(f"  Body:   ticker={s.get('ticker')}, has_reports={s.get('has_reports')}")
    else:
        print(f"  Body:   {r.text[:150]}")

    # Protected endpoint without token -> 401
    print("\n[GET /api/me] (no token - expect 401)")
    r = session.get(f"{base}/api/me")
    print(f"  Status: {r.status_code}")
    print(f"  Body:   {r.json() if r.headers.get('content-type', '').startswith('application/json') else r.text}")

    # -------------------------------------------------------------------------
    # 2. REGISTER & LOGIN (get JWT)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("2. AUTH: REGISTER & LOGIN")
    print("=" * 70)

    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    email = args.email or f"demo-{ts}@example.com"
    password = args.password

    token = None

    if not args.no_register:
        print("\n[POST /api/auth/register]")
        r = session.post(
            f"{base}/api/auth/register",
            json={"email": email, "password": password},
        )
        print(f"  Status: {r.status_code}")
        if r.ok:
            data = r.json()
            token = data.get("access_token")
            print(f"  Body:   user_id={data.get('user_id')}, email={data.get('email')}, token=...")
        else:
            print(f"  Body:   {r.json()}")
            if r.status_code == 409:
                print("  (User exists; will try login instead)")
                token = None  # fall through to login

    if token is None:
        print("\n[POST /api/auth/login]")
        r = session.post(
            f"{base}/api/auth/login",
            json={"email": email, "password": password},
        )
        print(f"  Status: {r.status_code}")
        if r.ok:
            data = r.json()
            token = data.get("access_token")
            print(f"  Body:   user_id={data.get('user_id')}, email={data.get('email')}, token=...")
        else:
            print(f"  Body:   {r.json()}")
            print("\n  Aborting: need valid token for authenticated examples.")
            sys.exit(1)

    session.headers["Authorization"] = f"Bearer {token}"

    # -------------------------------------------------------------------------
    # 3. AUTHENTICATED ACCESS (signed-in user)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("3. AUTHENTICATED ACCESS (with Bearer token)")
    print("=" * 70)

    # Profile
    print("\n[GET /api/me]")
    r = session.get(f"{base}/api/me")
    print(f"  Status: {r.status_code}")
    if r.ok:
        m = r.json()
        print(f"  Body:   user_id={m.get('user_id')}, email={m.get('email')}, token_balance={m.get('token_balance')}")
    else:
        print(f"  Body:   {r.json()}")

    # Stock page with auth (records view for creator rewards)
    print("\n[GET /api/stocks/AAPL] (with token)")
    r = session.get(f"{base}/api/stocks/AAPL")
    print(f"  Status: {r.status_code}")
    if r.ok:
        s = r.json()
        print(f"  Body:   ticker={s.get('ticker')}, has_reports={s.get('has_reports')}")
        if "report_view_count" in s and s["report_view_count"] is not None:
            print(f"          report_view_count={s['report_view_count']}, report_earned_tokens={s.get('report_earned_tokens')}")
    else:
        print(f"  Body:   {r.text[:150]}")

    # Subscriptions (auth required)
    print("\n[GET /api/subscriptions]")
    r = session.get(f"{base}/api/subscriptions")
    print(f"  Status: {r.status_code}")
    if r.ok:
        sub = r.json()
        print(f"  Body:   subscriptions={sub.get('subscriptions', [])}")
    else:
        print(f"  Body:   {r.json()}")

    # Subscribe to a ticker
    print("\n[POST /api/subscriptions]")
    r = session.post(
        f"{base}/api/subscriptions",
        json={"ticker": "AAPL"},
    )
    print(f"  Status: {r.status_code}")
    if r.ok:
        print(f"  Body:   {r.json()}")
    else:
        print(f"  Body:   {r.json()}")

    # Start analysis (auth required, costs 200 tokens)
    print("\n[POST /api/analyses/start] (dry-run: only shows request, does not actually start)")
    print("  Request body: {\"ticker\": \"AAPL\", \"analysis_date\": \"2025-02-14\"}")
    r = session.post(
        f"{base}/api/analyses/start",
        json={"ticker": "AAPL", "analysis_date": "2025-02-14"},
    )
    print(f"  Status: {r.status_code}")
    if r.ok:
        print(f"  Body:   {r.json()}")
    else:
        print(f"  Body:   {r.json()}")

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("""
Public (no auth):
  - GET /, /health
  - GET /api/stocks/widgets
  - GET /api/stocks/{ticker}  (optional auth for view recording)
  - GET /api/data/*           (quote, company, news, fundamentals, etc.)
  - POST /api/auth/register, /api/auth/login

Authenticated (Bearer token required):
  - GET /api/me, PATCH /api/me
  - GET/POST/DELETE /api/subscriptions
  - POST /api/analyses/start
  - GET /api/stocks/{ticker}  (records view for creator rewards when token present)

Admin only:
  - POST /api/tokens/top-up
  - POST /api/sync/major-stocks
""")


if __name__ == "__main__":
    main()
