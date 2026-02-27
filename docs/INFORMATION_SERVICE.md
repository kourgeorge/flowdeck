# Information Fetcher Service

The **Information Fetcher Engine** is a single service that fetches data from different sources (yfinance, news vendors, fundamentals, etc.) and exposes a unified REST API. Both the **dashboard UI** and **AI agents** use this API so they see the same data.

## API layer

| Prefix | Role |
|--------|------|
| `/api/data/*` | **Canonical raw market data** – single source of truth for UI and programmatic access |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/quote/{ticker}` | Current market quote |
| GET | `/news?ticker=...&vendor=...&lookback_days=7` | News articles |
| GET | `/company/{ticker}` | Company profile (name, sector, industry, etc.) |
| GET | `/extended-info/{ticker}` | Extended metrics (beta, market cap, PE, etc.) |
| GET | `/fundamentals/{ticker}` | Fundamental data |
| GET | `/financial-statements/{ticker}?statement_type=all&freq=quarterly` | Balance sheet, cashflow, income statement |
| GET | `/financial-charts/{ticker}?freq=annual` | Chart-ready time series (Revenue, EPS, Debt, FCF, etc.) |
| GET | `/historical/{ticker}?period=6mo&interval=1d` | Historical OHLCV |
| GET | `/stock-data/{ticker}?start_date=...&end_date=...` | OHLCV time series (for agents) |
| GET | `/analyst-recommendations/{ticker}` | Analyst recommendations |

Full URLs: e.g. `GET /api/data/quote/AAPL`.

## Dashboard UI

The UI fetches raw market data from `/api/data/*` (quote, news, fundamentals, statements, charts, historical, analyst recs). UI-specific views (widgets, full page) come from `/api/tickers/*`.

## AI agents

When you want agents to use the same data as the dashboard:

1. Start the backend (so the Information API is available).
2. Set the info service URL for the agents:
   - **Environment:** `export INFO_SERVICE_URL=http://localhost:8002`
   - **Config:** In `tradingagents/default_config.py` or your config, set `"info_service_url": "http://localhost:8002"`.

Then the agent tools (`get_news`, `get_stock_data`, `get_fundamentals`, `get_financial_statements`, `get_financial_charts`, etc.) will call `/api/data/*` instead of the local dataflow vendors.

## Summary

- **Engine:** `backend/services/info_fetcher.py` – single entry point for all fetching.
- **API:** `backend/routers/data_api.py` – REST routes mounted at `/api/data`.
- **Client:** `tradingagents/dataflows/info_service_client.py` – used by agents when `INFO_SERVICE_URL` is set.
