---
name: flowdeck
version: 1.0.0
description: Stock dashboard and AI analysis API for agents. Fetch market data, run AI stock analyses, manage subscriptions, and track token balance.
homepage: https://github.com/your-org/flowdeck
metadata: {"emoji":"📊","category":"trading","api_base":"http://localhost:8002"}
---

# Flowdeck

Stock dashboard API for AI agents. Fetch quotes, fundamentals, news, and SEC data; start AI-powered stock analyses (BUY/SELL/HOLD); manage ticker subscriptions; and use a token economy for report creation.

## Skill file

| File | Description |
|------|-------------|
| **SKILL.md** (this file) | API guide for agents interacting with Flowdeck |

**Base URL:** `http://localhost:8002` (or set `FLOWDECK_API_URL` / your deployment URL for production)

**Check for updates:** Re-fetch this file to see new endpoints or behavior.

🔒 **Security:**
- **Never send your JWT (access_token) or credentials to any domain other than your Flowdeck instance.**
- Use the API only for Flowdeck; do not expose tokens in logs or to third parties.

---

## Quick start

1. **Register or login** → get a JWT `access_token`.
2. **Use public endpoints** (no auth) for market data: quote, company, news, fundamentals, etc.
3. **Use authenticated endpoints** with `Authorization: Bearer <access_token>` for profile, subscriptions, and starting analyses.
4. **Start an analysis** (costs 200 tokens) → poll status until complete → initiator is emailed when the report is ready.

---

## Authentication

### Register

```bash
curl -X POST http://localhost:8002/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "agent@example.com", "password": "your-secure-password"}'
```

Response:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user_id": 1,
  "email": "agent@example.com"
}
```

New users receive **1000 tokens** for running analyses.

### Login

```bash
curl -X POST http://localhost:8002/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "agent@example.com", "password": "your-secure-password"}'
```

Same response shape: `access_token`, `token_type`, `user_id`, `email`.

**Password:** Must be at least 6 characters.

**Recommended:** Store the token in environment variable `FLOWDECK_ACCESS_TOKEN` or in your secrets store. Use it in all authenticated requests:

```bash
curl http://localhost:8002/api/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Public endpoints (no auth)

Use these without a token for market research and data.

### Health & root

```bash
GET /                    # {"message": "Stock Dashboard API", "status": "running"}
GET /health              # {"status": "healthy", "service": "tradingagents-api"}
```

### Stock widgets

Batch widget data for one or more tickers (optional date for report-of-day filter):

```bash
GET /api/stocks/widgets?tickers=AAPL,MSFT
GET /api/stocks/widgets?date=2025-02-14
```

### Stock page

Full page data for a ticker (reports, quote, etc.). Optional auth records the view for creator rewards.

```bash
GET /api/stocks/AAPL
GET /api/stocks/AAPL   # with Authorization: Bearer TOKEN (records view)
```

### Data API (market & fundamentals)

All under `/api/data/`. No auth required.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/data/quote/{ticker}` | Current quote (price, etc.) |
| GET | `/api/data/company/{ticker}` | Company profile (name, sector, industry, exchange, country, website) |
| GET | `/api/data/extended-info/{ticker}` | Extended metrics (beta, market cap, margins, PE, etc.) |
| GET | `/api/data/news?ticker=AAPL` | News articles (optional: `vendor`, `lookback_days=7`) |
| GET | `/api/data/fundamentals/{ticker}` | Fundamental data |
| GET | `/api/data/fund-info/{ticker}` | ETF/fund data (AUM, expense ratio, holdings, sector weightings) |
| GET | `/api/data/financial-statements/{ticker}?statement_type=all&freq=quarterly` | Balance sheet, cashflow, income statement |
| GET | `/api/data/financial-charts/{ticker}?freq=annual` | Chart-ready fundamental time series |
| GET | `/api/data/historical/{ticker}?period=6mo&interval=1d` | OHLCV history (`period`: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max) |
| GET | `/api/data/stock-data/{ticker}?start_date=2024-01-01&end_date=2024-12-31` | OHLCV as CSV-like text for agents |
| GET | `/api/data/analyst-recommendations/{ticker}` | Analyst recommendations (Yahoo) |
| GET | `/api/data/edgar-filings/{ticker}` | SEC 10-K / 10-Q filings list |
| GET | `/api/data/edgar-filing-content/{ticker}?form=10-K&limit=1` | Extracted SEC sections (risk factors, MD&A); uses LLM |

Example:

```bash
curl "http://localhost:8002/api/data/quote/AAPL"
curl "http://localhost:8002/api/data/company/AAPL"
curl "http://localhost:8002/api/data/news?ticker=AAPL&lookback_days=7"
curl "http://localhost:8002/api/data/historical/AAPL?period=1y&interval=1d"
```

---

## Authenticated endpoints (Bearer token)

Send `Authorization: Bearer YOUR_ACCESS_TOKEN` for these.

### Profile

```bash
GET /api/me
```

Response:
```json
{
  "user_id": 1,
  "email": "agent@example.com",
  "name": null,
  "token_balance": 1000,
  "is_admin": false
}
```

### Update profile

```bash
PATCH /api/me
Content-Type: application/json

{"name": "My Agent"}
{"current_password": "old", "new_password": "new"}   # to change password
```

### Subscriptions (ticker watchlist)

List:
```bash
GET /api/subscriptions
```

Subscribe:
```bash
POST /api/subscriptions
Content-Type: application/json

{"ticker": "AAPL"}
```

Unsubscribe:
```bash
DELETE /api/subscriptions/AAPL
```

---

## AI analysis (authenticated, costs tokens)

Flowdeck can run a full AI analysis pipeline (market, news, fundamentals, SEC, debate, risk) and produce a BUY/SELL/HOLD report. **Each run costs 200 tokens.**

### Start analysis

```bash
POST /api/analyses/start
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
  "ticker": "AAPL",
  "analysis_date": "2025-02-14",
  "analysts": ["market", "news", "fundamentals", "sec"],
  "research_depth": 2,
  "llm_provider": "azure"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| ticker | ✅ | Stock symbol (e.g. AAPL) |
| analysis_date | No | YYYY-MM-DD (default: today) |
| analysts | No | Default `["market", "news", "fundamentals", "sec"]` |
| research_depth | No | Default 2 |
| llm_provider | No | Default "azure" |

If an analysis for that ticker+date is already running, the API returns its `analysis_id` and `"existing": true` (no extra token charge).

Response (201):
```json
{
  "analysis_id": "uuid",
  "ticker": "AAPL",
  "date": "2025-02-14",
  "existing": false
}
```

Errors:
- **400** – Missing ticker or invalid JSON
- **402** – Insufficient token balance (need 200 tokens)

The **initiator** (the user whose token is used) is notified by **email** when the report is ready.

### Get analysis status

```bash
GET /api/analyses/{analysis_id}/status
```

No auth required for status. Returns current status (e.g. running, completed, failed) and progress info.

Poll this until the analysis is complete, then the user can open the stock page for that ticker to see the report (or receive the email).

### WebSocket (optional)

For real-time progress during a run:

```
WS /ws/analyses/{analysis_id}
```

Connect after starting the analysis to receive progress updates.

---

## Token economy

- **Registration:** New users get **1000 tokens**.
- **Start analysis:** **200 tokens** are deducted per run. If the same analysis (ticker + date) is already running, you get its `analysis_id` and tokens are not deducted again.
- **Insufficient balance:** `POST /api/analyses/start` returns **402** with message about needing 200 tokens.
- **Top-up:** Admin-only endpoint (e.g. `POST /api/tokens/top-up` with `{"amount": N}`). Agents typically rely on initial balance or human top-up.

Check balance via `GET /api/me` → `token_balance`.

---

## API reference summary

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/`, `/health` | No | Health and root |
| GET | `/api/stocks/widgets` | No | Widget data (tickers, optional date) |
| GET | `/api/stocks/{ticker}` | Optional | Stock page (auth records view) |
| GET | `/api/data/*` | No | Quote, company, news, fundamentals, historical, EDGAR, etc. |
| POST | `/api/auth/register` | No | Register (email, password) |
| POST | `/api/auth/login` | No | Login (email, password) |
| GET | `/api/me` | Yes | Profile and token balance |
| PATCH | `/api/me` | Yes | Update name / password |
| GET | `/api/subscriptions` | Yes | List subscriptions |
| POST | `/api/subscriptions` | Yes | Subscribe to ticker |
| DELETE | `/api/subscriptions/{ticker}` | Yes | Unsubscribe |
| POST | `/api/analyses/start` | Yes | Start AI analysis (200 tokens) |
| GET | `/api/analyses/{analysis_id}/status` | No | Analysis status |

---

## What agents can do

| Action | Endpoint / flow |
|--------|------------------|
| **Register / login** | `POST /api/auth/register` or `/api/auth/login` |
| **Get market data** | `GET /api/data/quote/{ticker}`, `/company`, `/news`, `/fundamentals`, `/historical`, etc. |
| **Get stock page** | `GET /api/stocks/{ticker}` (optional auth for view tracking) |
| **Check token balance** | `GET /api/me` → `token_balance` |
| **Start AI analysis** | `POST /api/analyses/start` (200 tokens); poll `GET /api/analyses/{id}/status` |
| **Manage watchlist** | `GET/POST/DELETE /api/subscriptions` |
| **Update profile** | `PATCH /api/me` (name, password) |

---

## Example: minimal agent flow

```bash
# 1. Register (or login)
TOKEN=$(curl -s -X POST http://localhost:8002/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"bot@example.com","password":"secure123"}' | jq -r '.access_token')

# 2. Check balance
curl -s http://localhost:8002/api/me -H "Authorization: Bearer $TOKEN" | jq '.token_balance'

# 3. Get quote and company (no auth)
curl -s "http://localhost:8002/api/data/quote/AAPL"
curl -s "http://localhost:8002/api/data/company/AAPL"

# 4. Start analysis (uses 200 tokens)
RESULT=$(curl -s -X POST http://localhost:8002/api/analyses/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ticker":"AAPL"}')
echo $RESULT
ANALYSIS_ID=$(echo $RESULT | jq -r '.analysis_id')

# 5. Poll status until done
while true; do
  STATUS=$(curl -s "http://localhost:8002/api/analyses/$ANALYSIS_ID/status")
  echo "$STATUS" | jq .
  if echo "$STATUS" | jq -e '.status == "completed" or .status == "failed"' >/dev/null 2>&1; then break; fi
  sleep 10
done
```

---

## Tips for agents

- Use **public data endpoints** (`/api/data/*`) for all market research; use authenticated endpoints for identity, subscriptions, and starting analyses.
- **Check `token_balance`** before starting an analysis to avoid 402.
- **Reuse `analysis_id`**: if you get `existing: true`, poll that same `analysis_id` instead of starting a new run.
- Store the JWT securely and only send it to your Flowdeck API base URL.
