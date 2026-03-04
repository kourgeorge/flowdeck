---
name: flowdeck
version: 1.0.0
description: AI-powered stock analysis platform with multi-agent analysis, conversational AI analyst, market data API, and token-based economy for agents.
homepage: https://flowdeck.biz
metadata: {"emoji":"📊","category":"trading","api_base":"https://flowdeck.biz"}
---

# Flowdeck

AI-powered stock analysis platform for agents. Features include:
- **Multi-agent AI analysis** (BUY/SELL/HOLD recommendations)
- **Conversational AI Analyst** (chat with streaming responses)
- **Comprehensive market data** (quotes, fundamentals, news, SEC filings, technical indicators)
- **Trader Copilot** workspace (watchlist + stock detail + AI chat)
- **Token economy** (1000 free tokens on signup; 200 tokens per analysis, variable cost for chat)
- **API key management** for programmatic access

## Skill file

| File | Description |
|------|-------------|
| **SKILL.md** (this file) | API guide for agents interacting with Flowdeck |

**Base URL:** `https://flowdeck.biz`

**Check for updates:** Re-fetch this file to see new endpoints or behavior.

🔒 **Security:**
- **Never send your JWT (access_token) or credentials to any domain other than your Flowdeck instance.**
- Use the API only for Flowdeck; do not expose tokens in logs or to third parties.

---

## Quick start

1. **Register or login** → get a JWT `access_token` or create an API key for programmatic access.
2. **Use public endpoints** (no auth) for market data: quote, company, news, fundamentals, etc.
3. **Use authenticated endpoints** with `Authorization: Bearer <access_token>` for profile, subscriptions, chat, and starting analyses.
4. **Start an analysis** (costs 200 tokens) → poll status until complete → initiator is emailed when the report is ready.
5. **Chat with AI Analyst** (variable token cost based on tool usage) → get streaming or non-streaming responses with live market data access.

---

## Authentication

### Register

```bash
curl -X POST https://flowdeck.biz/api/auth/register \
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
curl -X POST https://flowdeck.biz/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "agent@example.com", "password": "your-secure-password"}'
```

Same response shape: `access_token`, `token_type`, `user_id`, `email`.

**Password:** Must be at least 6 characters.

**Recommended:** Store the token in environment variable `FLOWDECK_ACCESS_TOKEN` or in your secrets store. Use it in all authenticated requests:

```bash
curl https://flowdeck.biz/api/me \
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
GET /api/tickers/widgets?tickers=AAPL,MSFT
GET /api/tickers/widgets?date=2025-02-14
```

### Stock page

Full page data for a ticker (reports, quote, etc.). Optional auth records the view for creator rewards.

```bash
GET /api/tickers/AAPL
GET /api/tickers/AAPL   # with Authorization: Bearer TOKEN (records view)
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
| GET | `/api/data/reports/{ticker}` | **[Auth required]** Latest AI-generated reports with recommendations |
| POST | `/api/data/reports/batch` | **[Auth required]** Batch fetch reports for multiple tickers |

Example:

```bash
curl "https://flowdeck.biz/api/data/quote/AAPL"
curl "https://flowdeck.biz/api/data/company/AAPL"
curl "https://flowdeck.biz/api/data/news?ticker=AAPL&lookback_days=7"
curl "https://flowdeck.biz/api/data/historical/AAPL?period=1y&interval=1d"
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

## Chat with AI Analyst (authenticated, costs tokens)

Flowdeck provides a conversational AI analyst agent with live access to market data, fundamentals, news, technical indicators, and your reports.

### Chat (non-streaming)

```bash
POST /api/chat
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "What are the key risks for NVDA?"}
  ],
  "context": {
    "tickers": ["NVDA"]
  }
}
```

Response:
```json
{
  "reply": "Based on current data...",
  "tokens_used": 5,
  "balance": 995
}
```

### Chat (streaming)

```bash
POST /api/chat/stream
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "Compare AAPL and MSFT fundamentals"}
  ],
  "context": {
    "tickers": ["AAPL", "MSFT"]
  }
}
```

Returns Server-Sent Events (SSE) stream with:
- `data: {"type": "token", "content": "..."}` - streaming response tokens
- `data: {"type": "tool_start", "tool": "get_quote", "args": {...}}` - tool execution start
- `data: {"type": "tool_end", "tool": "get_quote", "result": {...}}` - tool execution result
- `data: {"type": "done", "tokens_used": 8, "balance": 992}` - final message

**Token cost**: Variable based on agent trajectory (tool calls + LLM steps). Minimum 1 token per message. Returns **402** if insufficient balance.

**Context**: Optional `context` object can include:
- `tickers`: Array of ticker symbols for context-aware responses
- Other metadata as needed

---

## Report access (authenticated, no token cost)

Access previously generated AI analysis reports without starting a new analysis. These endpoints provide read-only access to the report database.

### Get reports for single ticker

```bash
GET /api/data/reports/{ticker}
Authorization: Bearer YOUR_ACCESS_TOKEN
```

Returns the latest reports for a ticker with scores, recommendations, and key takeaways.

Response:
```json
{
  "report_date": "2026-03-04_10-30-00",
  "reports": {
    "final_recommendation": {
      "content": "Detailed analysis text...",
      "score": 75,
      "score_label": "Strong Buy",
      "key_takeaways": [
        "Revenue growth accelerating",
        "Strong competitive position",
        "Valuation attractive"
      ],
      "recommendation": "BUY",
      "expected_return_pct": 15.5,
      "bear_case_return_pct": -5.0,
      "bull_case_return_pct": 35.0,
      "confidence": "HIGH",
      "analysis_date": "2026-03-04",
      "generated_at": "2026-03-04T10:30:00Z",
      "days_ago": 0,
      "models_used": ["gpt-4", "claude-3"],
      "tps_plan": {
        "entry_points": [...],
        "exit_points": [...],
        "stop_loss": {...}
      }
    },
    "bull_viewpoint": {
      "content": "Bullish perspective...",
      "score": 85,
      "key_takeaways": [...]
    },
    "bear_viewpoint": {
      "content": "Bearish perspective...",
      "score": 45,
      "key_takeaways": [...]
    },
    "neutral_viewpoint": {...},
    "risky_viewpoint": {...},
    "safe_viewpoint": {...}
  }
}
```

If no reports exist for the ticker, returns:
```json
{
  "report_date": null,
  "reports": {}
}
```

### Get reports for multiple tickers (batch)

```bash
POST /api/data/reports/batch
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
  "tickers": ["AAPL", "MSFT", "GOOGL"]
}
```

Returns reports for up to 50 tickers in a single request.

Response:
```json
{
  "tickers": {
    "AAPL": {
      "report_date": "2026-03-04_10-30-00",
      "reports": {
        "final_recommendation": {...},
        "bull_viewpoint": {...}
      }
    },
    "MSFT": {
      "report_date": "2026-03-04_09-15-00",
      "reports": {...}
    },
    "GOOGL": {
      "report_date": null,
      "reports": {}
    }
  }
}
```

### Report types available

- **final_recommendation** - Overall trading recommendation with score and TPS plan
- **bull_viewpoint** - Bullish analysis perspective
- **bear_viewpoint** - Bearish analysis perspective
- **neutral_viewpoint** - Neutral/balanced perspective
- **risky_viewpoint** - Risk-focused analysis
- **safe_viewpoint** - Conservative analysis

### Key fields in reports

| Field | Type | Description |
|-------|------|-------------|
| content | string | Full analysis text |
| score | number | Numerical score (0-100) |
| score_label | string | Human-readable label (e.g., "Strong Buy", "Hold", "Sell") |
| recommendation | string | Trading action: BUY, SELL, or HOLD |
| expected_return_pct | number | Expected return percentage |
| bull_case_return_pct | number | Optimistic scenario return |
| bear_case_return_pct | number | Pessimistic scenario return |
| confidence | string | Confidence level: HIGH, MEDIUM, or LOW |
| key_takeaways | array | Array of key insights (strings) |
| tps_plan | object | Trading Plan Specification (entry/exit points, risk management) |
| analysis_date | string | Date of analysis (YYYY-MM-DD) |
| generated_at | string | ISO timestamp when report was generated |
| days_ago | number | How many days old the report is |
| models_used | array | LLM models used in analysis |

**Note:** These endpoints do **not** cost tokens - they only retrieve existing reports. To generate new reports, use `POST /api/analyses/start` (costs 200 tokens).

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

## API key management (authenticated)

For programmatic access, you can create API keys instead of using JWT tokens.

### Create API key

```bash
POST /api/api-keys
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
  "name": "My Agent Key",
  "expires_at": "2026-12-31T23:59:59Z"
}
```

Response (key shown only once):
```json
{
  "id": 1,
  "name": "My Agent Key",
  "key": "fd_live_1234567890abcdef...",
  "key_prefix": "fd_live_12345678",
  "is_active": true,
  "created_at": "2026-03-03T20:00:00Z",
  "expires_at": "2026-12-31T23:59:59Z",
  "warning": "Save this key now - it won't be shown again!"
}
```

**Important:** API keys start with `fd_live_` prefix. Save the full key securely - it won't be shown again!

### List API keys

```bash
GET /api/api-keys
Authorization: Bearer YOUR_ACCESS_TOKEN
```

### Revoke API key

```bash
DELETE /api/api-keys/{key_id}
Authorization: Bearer YOUR_ACCESS_TOKEN
```

### Use API key

API keys work exactly like JWT tokens - include them in the `Authorization: Bearer` header:

```bash
# Using API key with any authenticated endpoint
curl https://flowdeck.biz/api/me \
  -H "Authorization: Bearer fd_live_1234567890abcdef..."

# Get reports with API key
curl https://flowdeck.biz/api/data/reports/AAPL \
  -H "Authorization: Bearer fd_live_1234567890abcdef..."

# Batch reports with API key
curl -X POST https://flowdeck.biz/api/data/reports/batch \
  -H "Authorization: Bearer fd_live_1234567890abcdef..." \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["AAPL", "MSFT", "GOOGL"]}'
```

**Note:** API keys use the same `Authorization: Bearer` header as JWT tokens, not `X-API-Key`.

---

## Token economy

- **Registration:** New users get **1000 tokens**.
- **Start analysis:** **200 tokens** are deducted per run. If the same analysis (ticker + date) is already running, you get its `analysis_id` and tokens are not deducted again.
- **Chat:** Variable cost based on agent trajectory (tool calls + LLM steps). Minimum **1 token** per message. Typical range: 1-20 tokens per chat turn depending on complexity.
- **Insufficient balance:** Returns **402** with message about insufficient tokens.
- **Top-up:** Admin-only endpoint (e.g. `POST /api/tokens/top-up` with `{"amount": N}`). Agents typically rely on initial balance or human top-up.

Check balance via `GET /api/me` → `token_balance`.

---

## API reference summary

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/`, `/health` | No | Health and root |
| GET | `/api/tickers/widgets` | No | Widget data (tickers, optional date) |
| GET | `/api/tickers/{ticker}` | Optional | Stock page (auth records view) |
| GET | `/api/data/*` | No | Quote, company, news, fundamentals, historical, EDGAR, etc. |
| GET | `/api/data/reports/{ticker}` | Yes | Get latest reports for ticker (no token cost) |
| POST | `/api/data/reports/batch` | Yes | Get reports for multiple tickers (no token cost) |
| POST | `/api/auth/register` | No | Register (email, password) |
| POST | `/api/auth/login` | No | Login (email, password) |
| GET | `/api/me` | Yes | Profile and token balance |
| PATCH | `/api/me` | Yes | Update name / password |
| GET | `/api/subscriptions` | Yes | List subscriptions |
| POST | `/api/subscriptions` | Yes | Subscribe to ticker |
| DELETE | `/api/subscriptions/{ticker}` | Yes | Unsubscribe |
| POST | `/api/chat` | Yes | Chat with AI analyst (variable tokens) |
| POST | `/api/chat/stream` | Yes | Chat with streaming (variable tokens) |
| POST | `/api/api-keys` | Yes | Create API key |
| GET | `/api/api-keys` | Yes | List API keys |
| DELETE | `/api/api-keys/{key_id}` | Yes | Revoke API key |
| POST | `/api/analyses/start` | Yes | Start AI analysis (200 tokens) |
| GET | `/api/analyses/{analysis_id}/status` | No | Analysis status |

---

## What agents can do

| Action | Endpoint / flow |
|--------|------------------|
| **Register / login** | `POST /api/auth/register` or `/api/auth/login` |
| **Create API key** | `POST /api/api-keys` (for programmatic access) |
| **Get market data** | `GET /api/data/quote/{ticker}`, `/company`, `/news`, `/fundamentals`, `/historical`, etc. |
| **Get existing reports** | `GET /api/data/reports/{ticker}` or `POST /api/data/reports/batch` (no token cost) |
| **Get stock page** | `GET /api/tickers/{ticker}` (optional auth for view tracking) |
| **Check token balance** | `GET /api/me` → `token_balance` |
| **Chat with AI analyst** | `POST /api/chat` or `/api/chat/stream` (variable tokens) |
| **Start AI analysis** | `POST /api/analyses/start` (200 tokens); poll `GET /api/analyses/{id}/status` |
| **Manage watchlist** | `GET/POST/DELETE /api/subscriptions` |
| **Update profile** | `PATCH /api/me` (name, password) |
| **Manage API keys** | `GET/POST/DELETE /api/api-keys` |

---

## Example: minimal agent flow

```bash
# 1. Register (or login)
TOKEN=$(curl -s -X POST https://flowdeck.biz/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"bot@example.com","password":"secure123"}' | jq -r '.access_token')

# 2. Check balance
curl -s https://flowdeck.biz/api/me -H "Authorization: Bearer $TOKEN" | jq '.token_balance'

# 3. Get quote and company (no auth)
curl -s "https://flowdeck.biz/api/data/quote/AAPL"
curl -s "https://flowdeck.biz/api/data/company/AAPL"

# 4. Start analysis (uses 200 tokens)
RESULT=$(curl -s -X POST https://flowdeck.biz/api/analyses/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ticker":"AAPL"}')
echo $RESULT
ANALYSIS_ID=$(echo $RESULT | jq -r '.analysis_id')

# 5. Poll status until done
while true; do
  STATUS=$(curl -s "https://flowdeck.biz/api/analyses/$ANALYSIS_ID/status")
  echo "$STATUS" | jq .
  if echo "$STATUS" | jq -e '.status == "completed" or .status == "failed"' >/dev/null 2>&1; then break; fi
  sleep 10
done
```

---

## Tips for agents

- Use **public data endpoints** (`/api/data/*`) for all market research; use authenticated endpoints for identity, subscriptions, chat, and starting analyses.
- **Check `token_balance`** before starting an analysis or chat to avoid 402.
- **Reuse `analysis_id`**: if you get `existing: true`, poll that same `analysis_id` instead of starting a new run.
- **Use streaming chat** (`/api/chat/stream`) for real-time responses and tool visibility.
- **Create API keys** for long-running agents instead of managing JWT refresh.
- **Provide context** in chat requests (e.g. `{"tickers": ["AAPL"]}`) for better responses.
- Store credentials securely and only send them to your Flowdeck API base URL.
- **Monitor token usage**: Chat responses include `tokens_used` and updated `balance`.
