---
name: flowdeck
version: 2.0.0
description: AI-powered ticker analysis platform with multi-agent analysis, conversational AI analyst, deterministic event signals, market data API, digests, and a token-based economy for agents.
homepage: https://flowdeck.biz
metadata: {"emoji":"📊","category":"trading","api_base":"https://flowdeck.biz"}
---

# Flowdeck

AI-powered ticker analysis platform for agents. Features include:
- **Multi-agent AI analysis** (BUY/SELL/HOLD recommendations, six selectable analysts)
- **Conversational AI Analyst** (persisted chat sessions, SSE streaming, tool visibility, charts)
- **Comprehensive market data** (quotes, fundamentals, news, SEC filings, technical indicators, insider activity, market overview)
- **Deterministic event signals** (price/volume/technical/insider/earnings events with a comparable score)
- **Daily & weekly digests** with schedules and email delivery
- **Prediction-market sentiment** (Polymarket)
- **Token economy** (1000 free tokens on signup; 200 per analysis, 20 per digest, variable for chat)
- **API key management** for programmatic access
- **Share links** for public, auth-free report views

## Skill file

| File | Description |
|------|-------------|
| **SKILL.md** (this file) | API guide for agents interacting with Flowdeck |

**Base URL:** `https://flowdeck.biz`

**Check for updates:** Re-fetch this file (`GET /api/SKILL.md`) to see new endpoints or behavior.

🔒 **Security:**
- **Never send your JWT (access_token) or credentials to any domain other than your Flowdeck instance.**
- Use the API only for Flowdeck; do not expose tokens in logs or to third parties.

---

## Quick start

1. **Register or login** → get a JWT `access_token`, or create an API key for programmatic access.
2. **Use public endpoints** (no auth) for market data: quote, company, news, fundamentals, indicators, events, etc.
3. **Use authenticated endpoints** with `Authorization: Bearer <access_token>` for profile, subscriptions, reports, chat, digests, and starting analyses.
4. **Read existing reports first** (`GET /api/data/reports/{ticker}` — free) before spending tokens on a new run.
5. **Start an analysis** (costs 200 tokens) → poll status or subscribe over WebSocket → the initiator is emailed when the report is ready.
6. **Chat with the AI Analyst** (variable token cost) → streaming or non-streaming, with live market data access.

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

New users receive **1000 tokens**.

### Login

```bash
curl -X POST https://flowdeck.biz/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "agent@example.com", "password": "your-secure-password"}'
```

Same response shape: `access_token`, `token_type`, `user_id`, `email`.

**Password:** Must be at least 6 characters.

### Delete account

```bash
DELETE /api/auth/account
Authorization: Bearer YOUR_ACCESS_TOKEN
```

Returns **204**. This is irreversible.

**Recommended:** Store the token in environment variable `FLOWDECK_ACCESS_TOKEN` or in your secrets store. Use it in all authenticated requests:

```bash
curl https://flowdeck.biz/api/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Public and mixed-access endpoints

Use these without a token for market research and data.

### Health, root, and platform info

```bash
GET /                    # {"message": "Stock Dashboard API", "status": "running"}
GET /health              # {"status": "healthy", "service": "tradingagents-api"}
GET /api/SKILL.md        # this file, as text/markdown
```

### Share links

Reports and digests can be shared as auth-free public views:

```bash
GET /api/share/{token}
```

No auth required. Resolves share tokens for **ticker reports** and **daily digests**; returns **404** for an
invalid/expired token or an unsupported type. Share tokens arrive as a ready-to-use `share_url` on report
and ticker-page responses — you do not construct them yourself.

### Ticker widgets

Batch widget data for one or more tickers:

```bash
GET /api/tickers/widgets?tickers=AAPL,MSFT
GET /api/tickers/widgets?date=2026-02-14&only_date=true
GET /api/tickers/widgets?latest_analyzed=true&limit=20&offset=0
```

| Param | Description |
|-------|-------------|
| `tickers` | Comma-separated symbols |
| `date` | Report-of-day filter (YYYY-MM-DD) |
| `only_date` | Return only tickers with a report on `date` |
| `recent_days` | Restrict to tickers analyzed within N days |
| `latest_analyzed` | Order by most recently analyzed |
| `include_events` | Attach event signal summary (default `true`) |
| `limit`, `offset` | Pagination |

Each widget carries `ticker`, `name`, `currency`, `is_major`, quote fields, `report_scores`, and — when
`include_events` is on — `dominant_events` and `event_count`.

### Ticker page

Full page data for a ticker. Optional auth records the view for creator rewards.

```bash
GET /api/tickers/AAPL
GET /api/tickers/AAPL   # with Authorization: Bearer TOKEN (records view, earns the report author tokens)
```

Includes quote/company data plus `report_run_id`, `report_days_ago`, `historical_analyses[]` (each with its
own `analysis_run_id`), `is_generating`, `generation_analysis_run_id`, `report_view_count`,
`report_earned_tokens`, and `share_url`.

### Data API (market & fundamentals)

All under `/api/data/`. Most endpoints are public; auth-required endpoints are marked.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/data/quote/{ticker}` | Current quote (price, change, volume, currency) |
| GET | `/api/data/company/{ticker}` | Company profile (name, sector, industry, exchange, country, website) |
| GET | `/api/data/extended-info/{ticker}` | Extended metrics (beta, market cap, margins, PE, etc.) |
| GET | `/api/data/market-rates` | FRED treasury yields / risk-free rate (cached 24 h) |
| GET | `/api/data/market-movers?count=8` | Top gainers/losers (`count` 1–100) |
| GET | `/api/data/market-overview?range=1d` | Indices, sectors, regions, commodities in one payload |
| GET | `/api/data/market-overview/section?section=indices` | One section only, paginated |
| GET | `/api/data/news?ticker=AAPL` | News articles (optional: `vendor`, `lookback_days=7`) |
| GET | `/api/data/news/batch?tickers=AAPL,MSFT` | Merged, de-duplicated news for up to 50 tickers |
| GET | `/api/data/news/batch/stream?tickers=AAPL,MSFT` | Same, as an NDJSON progressive stream |
| GET | `/api/data/global-news?lookback_days=7&limit=10` | Macro / world news (optional `query`, `curr_date`) |
| GET | `/api/data/insider-transactions/{ticker}?limit=50` | Latest insider transactions |
| GET | `/api/data/insider-sentiment/{ticker}?curr_date=YYYY-MM-DD` | Finnhub insider sentiment series |
| GET | `/api/data/reddit-company-social/{ticker}?search_terms=Apple,AAPL` | Reddit chatter (**`search_terms` required**) |
| GET | `/api/data/fundamentals/{ticker}` | Fundamental data |
| GET | `/api/data/fund-info/{ticker}` | ETF/fund data (AUM, expense ratio, holdings, sector weightings) |
| GET | `/api/data/financial-statements/{ticker}?statement_type=all&freq=quarterly` | Balance sheet, cashflow, income statement |
| GET | `/api/data/financial-charts/{ticker}?freq=annual` | Chart-ready fundamental time series |
| GET | `/api/data/historical/{ticker}?period=6mo&interval=1d` | OHLCV history (`period`: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max) |
| GET | `/api/data/ticker-data/{ticker}?start_date=2026-01-01&end_date=2026-06-30` | OHLCV as CSV-like text for agents |
| GET | `/api/data/indicators/{ticker}?indicator=rsi&look_back_days=30` | Technical indicator series |
| GET | `/api/data/analyst-recommendations/{ticker}` | Analyst recommendations (Yahoo) |
| GET | `/api/data/events/{ticker}?lookback_days=10` | Deterministic event signals + score |
| GET | `/api/data/future-events/{ticker}` | Upcoming earnings and ex-dividend dates |
| GET | `/api/data/similar-tickers/{ticker}?limit=10&offset=0` | Similar tickers by sector/industry (paginated) |
| GET | `/api/data/company-officers/{ticker}` | Company officers / management team |
| GET | `/api/data/edgar-filings/{ticker}` | SEC filings list: 10-K / 10-Q (US issuers), 20-F / 6-K / 40-F (foreign private issuers) |
| GET | `/api/data/edgar-filing-content/{ticker}?form=10-K&limit=1` | Extracted SEC sections (risk factors, MD&A); uses LLM |
| GET | `/api/data/reports/{ticker}` | **[Auth]** Latest AI-generated reports with recommendations |
| GET | `/api/data/reports/{ticker}/dates` | **[Auth]** `{ticker, dates: [...]}` — every date with a report |
| POST | `/api/data/reports/batch` | **[Auth]** Batch fetch reports for up to 50 tickers |

Example:

```bash
curl "https://flowdeck.biz/api/data/quote/AAPL"
curl "https://flowdeck.biz/api/data/company/AAPL"
curl "https://flowdeck.biz/api/data/news?ticker=AAPL&lookback_days=7"
curl "https://flowdeck.biz/api/data/historical/AAPL?period=1y&interval=1d"
curl "https://flowdeck.biz/api/data/indicators/AAPL?indicator=rsi&look_back_days=60"
```

#### Market overview

```bash
GET /api/data/market-overview?range=1d&limit_indices=6&offset_indices=0&limit_sectors=10&offset_sectors=0
GET /api/data/market-overview/section?section=sectors&limit=10&offset=0&range=1w
```

`range` accepts `1d`, `1w`, `1mo`, `3mo`, `6mo`, `ytd`. `section` accepts `indices`, `sectors`, `regions`,
`commodities` and returns `{section, items, total}`. A section that takes too long upstream returns **504** —
retry with a smaller `limit` or a shorter `range`.

#### Batch news

```bash
curl "https://flowdeck.biz/api/data/news/batch?tickers=AAPL,MSFT,NVDA"
curl -N "https://flowdeck.biz/api/data/news/batch/stream?tickers=AAPL,MSFT,NVDA"
```

Up to **50** tickers. Articles are merged and de-duplicated across tickers, and every article carries a
`tickers` list telling you which symbols it matched. The `/stream` variant returns
`application/x-ndjson` — one JSON object per line as each ticker's news lands, so a long fan-out
delivers partial results immediately.

#### Reddit social

`search_terms` is **required** and agent-supplied — Flowdeck does not guess the query for you. Pass the
company name and symbol you actually want matched; an empty value returns **400**.

```bash
curl "https://flowdeck.biz/api/data/reddit-company-social/AAPL?search_terms=Apple,AAPL&start_date=2026-08-01&end_date=2026-08-19"
```

#### SEC filing content

```bash
GET /api/data/edgar-filing-content/AAPL?form=10-K&limit=1
GET /api/data/edgar-filing-content/AAPL?raw=true            # full sec2md markdown, no LLM extraction
GET /api/data/edgar-filing-content/AAPL?accession=0000320193-25-000073
```

`raw=true` returns the whole filing as markdown. Passing `accession` selects one exact filing and makes
`form` / `limit` irrelevant.

---

## Event signals (deterministic, public)

Flowdeck derives events from market data using fixed rules — no LLM, so the same window always yields the
same events. Use them to decide *whether* a ticker is worth an analysis before spending tokens.

```bash
GET /api/data/events/AAPL?lookback_days=10          # 1–365, default 10
GET /api/tickers/event-summaries?tickers=AAPL,MSFT  # lightweight, batch
```

`/api/data/events/{ticker}` returns:

```json
{
  "ticker": "AAPL",
  "events": [
    {
      "event_type": "price_gap_up",
      "domain": "price",
      "detected_on": "2026-08-18",
      "window_start": "2026-08-08",
      "window_end": "2026-08-18",
      "strength": "medium",
      "metric_value": 3.4,
      "threshold_value": 2.0,
      "metadata": {},
      "description": "Human-readable explanation of the event."
    }
  ],
  "event_score": 7.5,
  "dominant_events": ["price_gap_up", "volume_spike"],
  "event_count": 4
}
```

`/api/tickers/event-summaries` returns only the cheap fields:
`{"summaries": {"AAPL": {"dominant_events": [...], "event_count": 4}, ...}}`.

**Event types:** `price_spike_up`, `price_spike_down`, `price_gap_up`, `price_gap_down`,
`volatility_expansion`, `volatility_compression`, `moving_average_cross`, `new_52w_high`, `new_52w_low`,
`volume_spike`, `earnings_upcoming`, `insider_buying`, `insider_selling`, `rsi_bullish_divergence`,
`rsi_bearish_divergence`. `strength` is `low`, `medium`, or `high`.

**Reading `event_score` correctly:** it is an **unbounded sum** of per-event weight × strength multiplier,
so **event count dominates severity** — a ticker with many mild events can outscore one with a single
alarming event. Treat it as "how much is going on here", not "how bad is it", and always look at
`dominant_events` alongside it. Across a real subscribed universe, observed scores ran roughly 2–14 with a
median near 5.

**Scores are not reproducible after the fact.** 52-week extremes and rolling statistics are computed from
the bars available at request time, so a score for a past window cannot be replayed without leaking later
data. If you need a comparable baseline, record the score when you observe it. Flowdeck itself does this:
each completed analysis stamps its own `event_score` / `dominant_events` into the run's
`trader_investment_plan` report metadata.

**Event-driven re-analysis:** on weekday mornings Flowdeck re-analyzes subscribed tickers whose signal has
both crossed an absolute floor and moved materially since their last analysis, subject to a multi-day
cooldown per ticker and a per-run cap. You get the resulting report (and subscriber email) without asking
for it; a ticker with no prior analysis is never auto-analyzed.

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
  "is_admin": false,
  "has_password": true,
  "has_completed_investor_profile": false
}
```

`has_password` is `false` for Google-only accounts — such an account cannot use `/api/auth/login` until a
password is set via `PATCH /api/me`.

### Update profile

```bash
PATCH /api/me
Content-Type: application/json

{"name": "My Agent"}
{"current_password": "old", "new_password": "new"}   # to change password
```

### Profile stats

```bash
GET /api/me/stats
```

### Investor profile

Shapes how the AI analyst and digests address you. All fields are optional.

```bash
GET   /api/me/investor-profile
PATCH /api/me/investor-profile
Content-Type: application/json

{
  "persona_type": "long_term_investor",
  "experience_level": "intermediate",
  "risk_tolerance": "moderate",
  "time_horizon": "5y+",
  "primary_goal": "retirement",
  "goals": ["income", "growth"],
  "constraints": ["no tobacco"],
  "preferred_style": "concise",
  "ai_memory_text": "I already hold AAPL and MSFT.",
  "date_of_birth": "1985-04-02"
}
```

### Subscriptions (ticker watchlist)

Subscribed tickers are what digests summarize and what the event monitor watches.

List:
```bash
GET /api/subscriptions
```

Subscribe:
```bash
POST /api/subscriptions
Content-Type: application/json

{"ticker": "AAPL", "email_updates": true}
```

`email_updates` defaults to `true`. Response: `{id, ticker, email_updates, created_at}`.

Update preferences:
```bash
PATCH /api/subscriptions/AAPL
Content-Type: application/json

{"email_updates": false}
```

Unsubscribe (**204**):
```bash
DELETE /api/subscriptions/AAPL
```

---

## Chat with AI Analyst (authenticated, costs tokens)

Flowdeck provides a conversational AI analyst with live access to market data, fundamentals, news,
technical indicators, events, and your reports. Conversations are **persisted as sessions and turns**, so an
agent can resume a thread later or read back a turn it did not stream.

### Chat (non-streaming)

```bash
POST /api/chat
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "What are the key risks for NVDA?"}
  ],
  "context": {"tickers": ["NVDA"]},
  "session_id": 17
}
```

`session_id` is optional — omit it to start a new session; the response tells you the id that was created.

Response:
```json
{
  "reply": "Based on current data...",
  "tokens_used": 48213,
  "platform_tokens_used": 5,
  "balance": 995,
  "follow_up_questions": ["How does that compare to AMD?"],
  "session_id": 17,
  "turn_id": 214,
  "llm_usage": {"input_tokens": 41000, "output_tokens": 7213}
}
```

**Read the two token fields carefully:** `tokens_used` is the raw **LLM** token count for the turn.
`platform_tokens_used` is what was actually **deducted from your balance** — that is the number to budget
against. See [Token economy](#token-economy) for the conversion.

### Chat (streaming)

```bash
POST /api/chat/stream
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
  "messages": [{"role": "user", "content": "Compare AAPL and MSFT fundamentals"}],
  "context": {"tickers": ["AAPL", "MSFT"]},
  "session_id": 17
}
```

Returns a Server-Sent Events stream. The **first** event identifies the turn so you can reconnect or poll it:

```
data: {"type":"started","turn_id":214,"session_id":17,"status":"running"}
```

Then, until the stream ends:

| Event | Payload |
|-------|---------|
| `thinking` | `{"type":"thinking","content":"..."}` — status narration |
| `tool_call` | `{"type":"tool_call","name":"get_quote","input":"...","output":"..."}` |
| `token` | `{"type":"token","content":"..."}` — response text delta |
| `done` | `{"type":"done","tokens_used":N,"tools_called":M,"follow_up_questions":[...]}` |
| `error` | `{"type":"error","content":"..."}` |

Charts arrive inside the text content as a `CHART_JSON:{...}` marker line — strip or parse those rather than
rendering them literally.

### Sessions and turns

```bash
GET    /api/chat/sessions              # list; each item may carry an active_turn
POST   /api/chat/sessions              # create a session explicitly
GET    /api/chat/sessions/{id}         # full message history + active_turn
DELETE /api/chat/sessions/{id}         # 204
GET    /api/chat/turns/{turn_id}       # status of one turn
```

`GET /api/chat/turns/{turn_id}` returns
`{id, session_id, status, last_thinking_status, error_message, created_at, updated_at}` — use it to poll a
turn whose SSE stream you dropped, instead of re-sending the message and paying twice.

Stored messages (`GET /api/chat/sessions/{id}`) include `tool_call_events`, `skill_activation_events`,
`charts`, `follow_up_questions`, `cost_usd`, and `model_metadata` alongside the text.

**Token cost:** variable, derived from the LLM tokens the turn consumed. Minimum **1** platform token per
message. Returns **402** if the balance is insufficient.

**Context:** the optional `context` object can include `tickers` (array of symbols) plus any other metadata
you want the analyst to see.

---

## Report access (authenticated, no token cost)

Read previously generated AI reports without starting a new analysis.

**Run identifiers:** each run is a row in `analysis_runs`; the canonical identifier is **`analysis_run_id`**
(integer). Reports and views are keyed by it — there is no separate string run id.

### Get reports for a single ticker

```bash
GET /api/data/reports/{ticker}
GET /api/data/reports/{ticker}?date=2026-03-04     # a specific date
GET /api/data/reports/{ticker}?date=42             # or an analysis_run_id
Authorization: Bearer YOUR_ACCESS_TOKEN
```

`date` accepts either `YYYY-MM-DD` or an `analysis_run_id`. Omit it for the latest run.

Response:
```json
{
  "report_run_id": 42,
  "report_date": "2026-03-04_10-30-00",
  "share_url": "https://flowdeck.biz/share/AbC123...",
  "reports": {
    "final_trade_decision": {
      "content": "Detailed analysis text...",
      "score": 75,
      "score_label": "Strong Buy",
      "key_takeaways": ["Revenue growth accelerating", "Valuation attractive"],
      "recommendation": "BUY",
      "expected_return_pct": 15.5,
      "bear_case_return_pct": -5.0,
      "bull_case_return_pct": 35.0,
      "current_price": 231.4,
      "currency": "USD",
      "confidence": "HIGH",
      "analysis_date": "2026-03-04",
      "generated_at": "2026-03-04T10:30:00Z",
      "days_ago": 0,
      "models_used": {"provider": "azure", "deep_think": "gpt-5", "quick_think": "gpt-5-mini"},
      "tps_plan": "Entry, target and stop levels as narrative text...",
      "bull_viewpoint": ["Bull point one", "Bull point two"],
      "bear_viewpoint": ["Bear point one"],
      "resources": [],
      "agent_steps": []
    },
    "market_report": {"content": "...", "score": 68, "key_takeaways": ["..."]},
    "valuation_report": {"content": "...", "fair_value_base": 245.0, "current_discount_pct": 5.6}
  }
}
```

If no reports exist:
```json
{"report_run_id": null, "report_date": null, "share_url": null, "reports": {}}
```

### Get reports for a specific historical run

```bash
GET /api/tickers/{ticker}/reports/{analysis_run_id}
Authorization: Bearer YOUR_ACCESS_TOKEN  # optional; auth records the view for creator rewards
```

`analysis_run_id` is an **integer** — e.g. `GET /api/tickers/AAPL/reports/42`. Same report shape as above.
Returns **404** if that run has no reports.

### List available report dates

```bash
GET /api/data/reports/{ticker}/dates
Authorization: Bearer YOUR_ACCESS_TOKEN
```

Returns `{"ticker": "AAPL", "dates": ["2026-03-04", "2026-02-14", ...]}`.

### Get reports for multiple tickers (batch)

```bash
POST /api/data/reports/batch
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{"tickers": ["AAPL", "MSFT", "GOOGL"]}
```

Up to **50** tickers per request. Each entry has the same
`{report_run_id, report_date, share_url, reports}` shape:

```json
{
  "tickers": {
    "AAPL": {"report_run_id": 42, "report_date": "2026-03-04_10-30-00", "share_url": "...", "reports": {...}},
    "GOOGL": {"report_run_id": null, "report_date": null, "share_url": null, "reports": {}}
  }
}
```

### Report keys

The `reports` object is keyed by **report type**. Which analyst reports are present depends on the
`analysts` chosen for that run; the three synthesis reports are present on every completed run.

| Key | Produced by | Description |
|-----|-------------|-------------|
| `market_report` | `market` analyst | Price action and market structure |
| `sentiment_report` | `social` analyst | Social/news sentiment |
| `fundamentals_report` | `fundamentals` analyst | Financials and business quality |
| `technical_report` | `technical` analyst | Technical indicators and setups |
| `sec_report` | `sec` analyst | SEC filing analysis (risk factors, MD&A) |
| `valuation_report` | `valuation` analyst | Fair value, DCF, comps |
| `investment_plan` | research debate | Bull/bear debate outcome |
| `trader_investment_plan` | trader | Trade plan; also carries the run's `event_score` / `dominant_events` |
| `final_trade_decision` | risk review | **Final BUY/SELL/HOLD recommendation with score** |

For the headline call, read **`final_trade_decision`**.

### Key fields in a report

| Field | Type | Description |
|-------|------|-------------|
| `content` | string | Full analysis text (markdown) |
| `score` | number | Numerical score (0–100) |
| `score_label` | string | Human-readable label ("Strong Buy", "Hold", …) |
| `recommendation` | string | BUY, SELL, or HOLD |
| `expected_return_pct` | number | Expected return percentage |
| `bull_case_return_pct` | number | Optimistic scenario return |
| `bear_case_return_pct` | number | Pessimistic scenario return |
| `current_price` | number | Price at analysis time |
| `currency` | string | Currency of the price figures |
| `confidence` | string | HIGH, MEDIUM, or LOW |
| `key_takeaways` | array of strings | Key insights |
| `tps_plan` | **string** | Target/entry/stop plan as narrative text |
| `bull_viewpoint`, `bear_viewpoint`, `neutral_viewpoint`, `risky_viewpoint`, `safe_viewpoint` | array of strings | Debate positions — **fields inside a report, not separate report keys** |
| `analysis_date` | string | YYYY-MM-DD |
| `generated_at` | string | ISO timestamp |
| `days_ago` | number | Age of the report in days |
| `models_used` | **object** | `{provider, deep_think, quick_think}` |
| `resources` | array | Sources cited during the run |
| `agent_steps` | array | Per-agent trace of the run |
| `input_tokens`, `output_tokens`, `total_tokens`, `cost_usd` | number | LLM accounting for the report |

`valuation_report` additionally may carry `fair_value_bear` / `fair_value_base` / `fair_value_bull`,
`current_discount_pct`, `valuation_conviction`, `valuation_key_assumptions`, `valuation_summary`,
`valuation_bridge`, `valuation_sensitivity`, `dcf`, `pe_comps`, and `ev_ebitda`. Fields that were not
produced are simply absent rather than filled with a guess.

**Note:** these endpoints do **not** cost tokens — they only read existing reports. To generate new ones use
`POST /api/analyses/start` (200 tokens).

---

## AI analysis (authenticated, costs tokens)

Flowdeck runs a full multi-agent pipeline (analysts → research debate → trader → risk review) and produces a
BUY/SELL/HOLD report. **Each run costs 200 tokens.**

### Start analysis

```bash
POST /api/analyses/start
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
  "ticker": "AAPL",
  "analysis_date": "2026-02-14",
  "analysts": ["market", "social", "fundamentals", "technical", "sec", "valuation"],
  "research_depth": 2,
  "llm_provider": "azure"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `ticker` | ✅ | Ticker symbol (e.g. AAPL) |
| `analysis_date` | No | YYYY-MM-DD (default: today) |
| `analysts` | No | Default **all six**: `["market", "social", "fundamentals", "technical", "sec", "valuation"]` |
| `research_depth` | No | Debate rounds; default 2 |
| `llm_provider` | No | Default from server config (typically `azure`) |
| `backend_url` | No | Override the LLM endpoint |
| `shallow_thinker` | No | Override the quick-thinking model |
| `deep_thinker` | No | Override the deep-thinking model |

Each analyst maps to one report key: `market` → `market_report`, `social` → `sentiment_report`,
`fundamentals` → `fundamentals_report`, `technical` → `technical_report`, `sec` → `sec_report`,
`valuation` → `valuation_report`. Note the value is **`social`**, not `news`.

If an analysis for that ticker+date is already running, the API returns its `analysis_run_id` with
`"existing": true` and the 200 tokens are refunded.

Response (200):
```json
{"analysis_run_id": 123, "ticker": "AAPL", "date": "2026-02-14", "existing": false}
```

Errors:
- **400** – Missing ticker or invalid JSON
- **402** – `"Insufficient token balance. Need 200 tokens to create a report."`
- **404** – `"Ticker '{ticker}' not found. Check the symbol and try again."`
- **500** – Pipeline failed to start

The **initiator** (the user whose token was spent) is emailed when the report is ready. Subscribers of the
ticker are notified too.

**Builds on prior runs:** when a ticker already has a completed run, each new analysis builds on it rather
than starting from scratch. Every report ends with a `## What changed since {date}` section calling out what
shifted versus the previous run — including any change in the directional recommendation (e.g. BUY → HOLD)
and why. The response shape is unchanged; the narrative lives inside each report's `content`.

### Get analysis status

```bash
GET /api/analyses/{analysis_run_id}/status
Authorization: Bearer YOUR_ACCESS_TOKEN
```

Returns the current status (running, completed, failed) and progress info; **404** if the run id is unknown.
Poll this, then read the reports for that ticker.

### WebSocket (optional)

For real-time progress during a run:

```
WS /ws/analyses/{analysis_run_id}?token=YOUR_ACCESS_TOKEN
```

Connect after starting the analysis to receive progress updates. The `token` query parameter must be a
JWT (WebSockets cannot set an `Authorization` header, and this endpoint does not accept `fd_live_...` API
keys); the connection closes with code **4001** if it is missing or invalid.

---

## Digests (authenticated, costs tokens)

A digest is a narrative brief across your subscribed tickers. **Each generated digest costs 20 tokens.**

### Generate or fetch a digest

```bash
GET /api/digest?span=daily&max_priority_tickers=5
GET /api/digest?span=weekly&date=2026-08-17
Authorization: Bearer YOUR_ACCESS_TOKEN
```

| Param | Description |
|-------|-------------|
| `span` | `daily` (default) or `weekly` (7 days ending on `date`) |
| `date` | Target date (YYYY-MM-DD); default today in `timezone` |
| `max_priority_tickers` | How many tickers get deep treatment; 1–20, default 5 |
| `user_note` | Free-text steer for this brief (max 2000 chars) |
| `narrative_style` | Style hint, e.g. `concise`, `professional`, `technical`, `story-like` |
| `user_focus_tickers` | Symbols the brief should focus on (repeatable query param) |
| `timezone` | IANA name, e.g. `Asia/Jerusalem`, used to resolve "today" |

The response carries `narrative`, `what_to_watch`, `priority_tickers`, `important_events`, `span_type` /
`span_label`, `references`, `resources`, `agent_steps`, `focus_snapshot`, and a `share_url` for the brief.
Returns **402** when the balance is under 20 tokens, **503** if the digest engine is unavailable.

### Digest history

```bash
GET    /api/digest/history/dates?days=90&timezone=America/New_York
GET    /api/digest/history/{slot}                 # slot = "2026-08-19" or "w:2026-08-17"
DELETE /api/digest/briefs/{execution_id}
POST   /api/digest/briefs/{execution_id}/send-email
```

Weekly slots are prefixed `w:` and keyed by the week's start date. Reading history is free.

### Digest schedules

```bash
GET /api/digest/schedules
PUT /api/digest/schedules/daily_digest
PUT /api/digest/schedules/weekly_digest
Content-Type: application/json

{
  "enabled": true,
  "hour": 7,
  "minute": 30,
  "day_of_week": 0,
  "timezone": "America/New_York",
  "metadata": {
    "user_note": "Focus on my semis exposure.",
    "narrative_style": "concise",
    "user_focus_tickers": ["NVDA", "AMD"]
  }
}
```

`day_of_week` is `0` = Monday … `6` = Sunday and is **required for `weekly_digest`**. Scheduled digests spend
20 tokens per run from the owning account, so keep an eye on the balance if you enable both.

---

## Prediction markets (Polymarket)

Public sentiment derived from Polymarket order flow.

```bash
GET /api/polymarket/ticker/{ticker}                      # aggregated sentiment for a ticker
GET /api/polymarket/markets/relevant/{ticker}?limit=20   # markets matched to the ticker
GET /api/polymarket/markets/trending?category=finance&limit=20
GET /api/polymarket/market/{market_id}
GET /api/polymarket/market/{market_id}/history?days=30
```

`category` accepts `finance`, `crypto`, `politics`, `economics`. Sentiment runs **0 = bearish → 1 = bullish**
with `0.5` neutral; confidence is derived from traded volume. Ticker aggregation scans up to 100 markets and
keeps the top 30 by relevance.

---

## Token economy

| Event | Effect |
|-------|--------|
| Registration | **+1000** tokens |
| Start analysis | **−200** tokens per run (refunded if it merges into an already-running run) |
| Generate digest | **−20** tokens per brief (including scheduled ones) |
| Chat turn | Variable, **minimum 1** token |
| Someone views your report | **+1** token per unique view, up to **400** per report within 14 days |
| Reading reports / data / history | **Free** |

**Chat conversion:** platform tokens are LLM tokens divided by a fixed ratio (currently **10,000 LLM tokens
per platform token**), rounded up, with a floor of 1. So a turn reporting `tokens_used: 48213` deducts
`platform_tokens_used: 5`. Budget against `platform_tokens_used`, not `tokens_used`.

**Insufficient balance:** any charged operation returns **402** with a message naming the required amount.

**Top-up:** `POST /api/tokens/top-up` exists but is **admin-only**. Agents rely on the initial balance, view
rewards, or a human top-up.

### Balance and usage

```bash
GET /api/tokens/balance
GET /api/tokens/transactions?limit=50&offset=0&transaction_type=analysis
GET /api/tokens/usage-stats?days=30
GET /api/tokens/usage-breakdown?days=30
GET /api/tokens/usage-history?days=90&limit=200
```

`usage-breakdown` returns `chat_cost`, `analysis_cost`, `digest_cost`, `purchases`, `rewards`, and
`total_llm_tokens` — the fastest way to see where a balance went. The balance is also on `GET /api/me` as
`token_balance`.

---

## API key management (authenticated)

For long-running programmatic access, create API keys instead of managing JWT lifetimes.

### Create API key

```bash
POST /api/api-keys
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{"name": "My Agent Key", "expires_at": "2027-12-31T23:59:59Z"}
```

Response (**201**; the key is shown only once):
```json
{
  "id": 1,
  "name": "My Agent Key",
  "key": "fd_live_1234567890abcdef...",
  "key_prefix": "fd_live_12345678",
  "is_active": true,
  "created_at": "2026-03-03T20:00:00Z",
  "expires_at": "2027-12-31T23:59:59Z",
  "warning": "Save this key now - it won't be shown again!"
}
```

**Important:** API keys start with the `fd_live_` prefix. Save the full key securely — it will not be shown again.

### List, toggle, revoke

```bash
GET    /api/api-keys                          # list (prefixes only, never the full key)
PATCH  /api/api-keys/{key_id}/deactivate      # disable without deleting
PATCH  /api/api-keys/{key_id}/activate        # re-enable
DELETE /api/api-keys/{key_id}                 # revoke permanently (204)
```

### Use API key

API keys work exactly like JWT tokens — same `Authorization: Bearer` header, **not** `X-API-Key`:

```bash
curl https://flowdeck.biz/api/me \
  -H "Authorization: Bearer fd_live_1234567890abcdef..."

curl https://flowdeck.biz/api/data/reports/AAPL \
  -H "Authorization: Bearer fd_live_1234567890abcdef..."

curl -X POST https://flowdeck.biz/api/data/reports/batch \
  -H "Authorization: Bearer fd_live_1234567890abcdef..." \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["AAPL", "MSFT", "GOOGL"]}'
```

API keys do **not** work on the analysis WebSocket — its `?token=` parameter is JWT-only
(`decode_token` in `auth.py` has no `fd_live_` branch). Use an `access_token` there.

---

## API reference summary

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/`, `/health` | No | Health and root |
| GET | `/api/SKILL.md` | No | This guide |
| GET | `/api/share/{token}` | No | Public shared report or digest view |
| POST | `/api/auth/register` | No | Register (email, password) |
| POST | `/api/auth/login` | No | Login (email, password) |
| DELETE | `/api/auth/account` | Yes | Delete account (204) |
| GET | `/api/tickers/widgets` | No | Widget data (tickers, date, pagination, events) |
| GET | `/api/tickers/event-summaries` | No | Batch `dominant_events` + `event_count` |
| GET | `/api/tickers/{ticker}` | Optional | Ticker page (auth records the view) |
| GET | `/api/tickers/{ticker}/reports/{analysis_run_id}` | Optional | Reports for one historical run |
| GET | `/api/data/quote|company|extended-info|fundamentals|fund-info/{ticker}` | No | Core ticker data |
| GET | `/api/data/market-rates` | No | Treasury yields / risk-free rate |
| GET | `/api/data/market-movers` | No | Top gainers and losers |
| GET | `/api/data/market-overview`, `/market-overview/section` | No | Indices, sectors, regions, commodities |
| GET | `/api/data/news`, `/news/batch`, `/news/batch/stream`, `/global-news` | No | News (single, batch, NDJSON stream, macro) |
| GET | `/api/data/insider-transactions/{ticker}`, `/insider-sentiment/{ticker}` | No | Insider activity |
| GET | `/api/data/reddit-company-social/{ticker}` | No | Reddit chatter (`search_terms` required) |
| GET | `/api/data/financial-statements|financial-charts/{ticker}` | No | Statements and time series |
| GET | `/api/data/historical/{ticker}`, `/ticker-data/{ticker}` | No | OHLCV (JSON, CSV-like text) |
| GET | `/api/data/indicators/{ticker}` | No | Technical indicator series |
| GET | `/api/data/analyst-recommendations/{ticker}` | No | Analyst recommendations |
| GET | `/api/data/events/{ticker}` | No | Deterministic event signals + score |
| GET | `/api/data/future-events/{ticker}` | No | Upcoming earnings / ex-dividend |
| GET | `/api/data/similar-tickers/{ticker}`, `/company-officers/{ticker}` | No | Peers and management |
| GET | `/api/data/edgar-filings/{ticker}`, `/edgar-filing-content/{ticker}` | No | SEC filings list and extracted content |
| GET | `/api/data/reports/{ticker}`, `/reports/{ticker}/dates` | Yes | Existing reports; available dates (free) |
| POST | `/api/data/reports/batch` | Yes | Reports for up to 50 tickers (free) |
| GET | `/api/me`, `/api/me/stats` | Yes | Profile, balance, usage statistics |
| PATCH | `/api/me` | Yes | Update name / password |
| GET/PATCH | `/api/me/investor-profile` | Yes | Investor profile used by AI features |
| GET | `/api/subscriptions` | Yes | List subscriptions |
| POST | `/api/subscriptions` | Yes | Subscribe (`ticker`, `email_updates`) |
| PATCH | `/api/subscriptions/{ticker}` | Yes | Update subscription preferences |
| DELETE | `/api/subscriptions/{ticker}` | Yes | Unsubscribe (204) |
| POST | `/api/chat` | Yes | Chat with AI analyst (variable tokens) |
| POST | `/api/chat/stream` | Yes | Chat with SSE streaming (variable tokens) |
| GET/POST | `/api/chat/sessions` | Yes | List / create chat sessions |
| GET/DELETE | `/api/chat/sessions/{id}` | Yes | Session history / delete (204) |
| GET | `/api/chat/turns/{turn_id}` | Yes | Poll a turn's status |
| POST | `/api/analyses/start` | Yes | Start AI analysis (200 tokens) |
| GET | `/api/analyses/{analysis_run_id}/status` | Yes | Analysis status |
| WS | `/ws/analyses/{analysis_run_id}?token=` | Yes | Live analysis progress |
| GET | `/api/digest` | Yes | Generate or fetch a digest (20 tokens) |
| GET | `/api/digest/history/dates`, `/history/{slot}` | Yes | Past digests (free) |
| DELETE | `/api/digest/briefs/{execution_id}` | Yes | Delete a digest |
| POST | `/api/digest/briefs/{execution_id}/send-email` | Yes | Email a digest |
| GET | `/api/digest/schedules` | Yes | Digest schedules |
| PUT | `/api/digest/schedules/{daily_digest\|weekly_digest}` | Yes | Update a schedule |
| GET | `/api/tokens/balance`, `/transactions`, `/usage-stats`, `/usage-breakdown`, `/usage-history` | Yes | Token accounting |
| POST | `/api/api-keys` | Yes | Create API key (201) |
| GET | `/api/api-keys` | Yes | List API keys |
| PATCH | `/api/api-keys/{key_id}/deactivate`, `/activate` | Yes | Toggle API key |
| DELETE | `/api/api-keys/{key_id}` | Yes | Revoke API key (204) |
| GET | `/api/polymarket/*` | No | Prediction-market sentiment and markets |

---

## What agents can do

| Action | Endpoint / flow |
|--------|------------------|
| **Register / login** | `POST /api/auth/register` or `/api/auth/login` |
| **Create API key** | `POST /api/api-keys` (for programmatic access) |
| **Get market data** | `GET /api/data/quote/{ticker}`, `/company`, `/news`, `/fundamentals`, `/historical`, `/indicators/{ticker}`, `/similar-tickers/{ticker}`, … |
| **Scan the whole market** | `GET /api/data/market-overview`, `/market-movers`, `/market-rates`, `/global-news` |
| **Triage which tickers matter** | `GET /api/data/events/{ticker}` or `GET /api/tickers/event-summaries?tickers=...` before spending tokens |
| **Get existing reports (free)** | `GET /api/data/reports/{ticker}` or `POST /api/data/reports/batch`; read `final_trade_decision` for the call |
| **Get reports for a historical run** | `GET /api/tickers/{ticker}/reports/{analysis_run_id}` (from `report_run_id` or `historical_analyses[].analysis_run_id`) |
| **List a ticker's report dates** | `GET /api/data/reports/{ticker}/dates` |
| **Get ticker page** | `GET /api/tickers/{ticker}` (optional auth records the view and rewards the author) |
| **Share a report publicly** | Use the `share_url` returned on report / ticker-page responses; readers hit `GET /api/share/{token}` |
| **Start AI analysis** | `POST /api/analyses/start` (200 tokens); poll `GET /api/analyses/{analysis_run_id}/status` or open the WebSocket |
| **Chat with AI analyst** | `POST /api/chat` or `/api/chat/stream`; resume via `session_id`, recover a dropped stream via `GET /api/chat/turns/{turn_id}` |
| **Get a daily / weekly brief** | `GET /api/digest?span=daily` (20 tokens); schedule with `PUT /api/digest/schedules/{slot}` |
| **Read prediction-market sentiment** | `GET /api/polymarket/ticker/{ticker}` |
| **Check token balance / spend** | `GET /api/me` → `token_balance`; `GET /api/tokens/usage-breakdown?days=30` |
| **Manage watchlist** | `GET/POST/PATCH/DELETE /api/subscriptions` |
| **Update profile** | `PATCH /api/me` (name, password), `PATCH /api/me/investor-profile` |
| **Manage API keys** | `GET/POST/PATCH/DELETE /api/api-keys` |

---

## Example: minimal agent flow

```bash
# 1. Register (or login)
TOKEN=$(curl -s -X POST https://flowdeck.biz/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"bot@example.com","password":"secure123"}' | jq -r '.access_token')

# 2. Check balance
curl -s https://flowdeck.biz/api/me -H "Authorization: Bearer $TOKEN" | jq '.token_balance'

# 3. Free research first — quote, events, and any existing report
curl -s "https://flowdeck.biz/api/data/quote/AAPL" | jq '.'
curl -s "https://flowdeck.biz/api/data/events/AAPL?lookback_days=10" | jq '{event_score, dominant_events}'
curl -s "https://flowdeck.biz/api/data/reports/AAPL" -H "Authorization: Bearer $TOKEN" \
  | jq '{report_run_id, days_ago: .reports.final_trade_decision.days_ago,
         call: .reports.final_trade_decision.recommendation}'

# 4. Only if the existing report is stale or missing, spend 200 tokens
RESULT=$(curl -s -X POST https://flowdeck.biz/api/analyses/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ticker":"AAPL"}')
echo "$RESULT"
ANALYSIS_RUN_ID=$(echo "$RESULT" | jq -r '.analysis_run_id')

# 5. Poll status until done
while true; do
  STATUS=$(curl -s "https://flowdeck.biz/api/analyses/$ANALYSIS_RUN_ID/status" \
    -H "Authorization: Bearer $TOKEN")
  echo "$STATUS" | jq .
  if echo "$STATUS" | jq -e '.status == "completed" or .status == "failed"' >/dev/null 2>&1; then break; fi
  sleep 10
done

# 6. Read the finished report
curl -s "https://flowdeck.biz/api/data/reports/AAPL" -H "Authorization: Bearer $TOKEN" \
  | jq '.reports.final_trade_decision | {recommendation, score, expected_return_pct, key_takeaways}'
```

---

## Tips for agents

- **Read before you spend.** `GET /api/data/reports/{ticker}` and `/api/data/events/{ticker}` are free;
  `POST /api/analyses/start` is 200 tokens. Check `days_ago` on `final_trade_decision` and the event score
  before re-running.
- **Read `final_trade_decision`** for the headline BUY/SELL/HOLD. The `*_viewpoint` values are **fields
  inside** a report, not separate report keys.
- **Budget against `platform_tokens_used`**, not `tokens_used` — the latter is raw LLM tokens and is ~10,000×
  larger.
- **Batch instead of looping.** `POST /api/data/reports/batch`, `/api/data/news/batch`, and
  `/api/tickers/widgets?tickers=` all take up to 50 symbols; `/api/tickers/event-summaries` is the cheap way
  to triage a watchlist.
- **Use the NDJSON stream** (`/api/data/news/batch/stream`) for large ticker sets so you can act on partial
  results.
- **Reuse `analysis_run_id`.** If `existing: true`, use that same id for status and the WebSocket. Afterwards
  use `analysis_run_id` / `report_run_id` with `GET /api/tickers/{ticker}/reports/{analysis_run_id}`.
- **Keep chat threads.** Pass `session_id` to continue a conversation with its history; if a stream drops,
  poll `GET /api/chat/turns/{turn_id}` instead of re-sending and paying twice.
- **Provide context** in chat requests (e.g. `{"tickers": ["AAPL"]}`) and fill in
  `PATCH /api/me/investor-profile` for responses tuned to your mandate.
- **Subscribing has side effects worth wanting:** subscribed tickers are what digests cover and what the
  event monitor auto-re-analyzes.
- **Create API keys** for long-running agents instead of managing JWT refresh; deactivate rather than delete
  while debugging.
- **Handle 402 explicitly** — it always means balance, never a bad request. Check
  `GET /api/tokens/usage-breakdown?days=30` to see what drained it.
- **Expect honest gaps.** Flowdeck omits fields it cannot compute rather than filling them with plausible
  values; treat a missing field as unknown, not as zero.
- Store credentials securely and only send them to your Flowdeck API base URL.
