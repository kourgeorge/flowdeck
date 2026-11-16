# Stock Analysis Dashboard

A modern, investor-focused stock analysis website featuring real-time market data, AI-powered analysis reports, and beautiful widget-based interface.

## Features

- **Widget-Based Homepage**: View major stocks as attractive cards with real-time prices and recommendations
- **Individual Stock Pages**: Comprehensive analysis pages with:
  - Real-time market data (price, bid/ask, volume, 52-week range, today's range)
  - AI-powered recommendations (BUY/SELL/HOLD)
  - Detailed analysis reports (market, news, fundamentals, technical, sentiment, investment plan)
  - Historical reports archive
- **Stock Search**: Search for any ticker and generate reports on-demand
- **Real-time Updates**: Live price updates and WebSocket support for report generation

## Project Structure

```
flowdeck/
├── backend/             # FastAPI backend
│   ├── main.py          # FastAPI application
│   ├── run.py           # Starts the server on port 8002
│   ├── config.py        # Configuration
│   ├── routers/         # API endpoints
│   ├── models/          # Pydantic models
│   ├── services/        # Business logic services
│   └── tests/           # Backend tests
├── ai_engine/           # AI agents that write the analysis reports
├── scripts/             # Helper scripts (e.g. sync_major_stocks_daily.sh)
└── frontend/            # React frontend
    └── src/
        ├── pages/       # Page components
        ├── components/  # Reusable components
        └── services/    # API clients
```

## Setup

### Backend

1. Go to the repository root (the folder that holds `backend/`, `ai_engine/` and `frontend/`).

2. Create a virtual environment and install the Python packages (Python 3.10 or newer):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

If you use conda instead, `backend/environment.yml` is available:
```bash
conda env create -f backend/environment.yml
```

3. Create your settings file and fill in your keys (see the root `README.md` for which keys you need). `JWT_SECRET` must be set to a random string of at least 32 characters:
```bash
cp backend/.env.example backend/.env
```

4. Run the backend server from the repository root:
```bash
python backend/run.py
```

`run.py` adds the repository root to the Python path, so `backend` can import `ai_engine`. It always uses port 8002.

The backend will start on `http://localhost:8002`

**Note**: Port 8002 is used to avoid conflicts with other services (e.g. Django on 8000, or SSH tunnels on 8001).

**Verify backend is running**: Open `http://localhost:8002/health` in your browser - it should return `{"status": "healthy", ...}`

### Frontend

1. Go to the frontend directory (from the repository root):
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will start on `http://localhost:3003`

## Configuration

### URLs and origins (production)

Set these environment variables to avoid localhost defaults:

| Variable | Description | Example |
|----------|-------------|---------|
| `CORS_ORIGINS` | Comma-separated allowed CORS origins | `https://app.example.com,https://example.com` |
| `BACKEND_URL` | Backend base URL (for analysis service) | `https://api.example.com` |
| `VITE_API_URL` | Frontend: API base URL (production) | `https://api.example.com` |
| `VITE_DEV_PROXY_TARGET` | Frontend: dev proxy target (optional) | `http://127.0.0.1:8002` |

When `CORS_ORIGINS` is not set, the backend allows common local dev origins (localhost:3003, etc.). In production, set `CORS_ORIGINS` to your frontend URL(s).

### Major Stocks

Edit `MAJOR_TICKERS` in `backend/config.py` to customize the list of stocks shown on the homepage:

```python
MAJOR_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN",
    "NVDA", "META", "TSLA",
]
```

### Daily sync of major stocks reports

To ensure every major stock has a report for the current day, you can trigger a sync manually or on a schedule.

**Auth:** `POST /api/sync/major-stocks` is admin-only. Send an admin user's API key (`fd_live_...`, see [API_KEY_AUTHENTICATION.md](../docs/API_KEY_AUTHENTICATION.md)) as `Authorization: Bearer ...`. The examples below read it from the `FLOWDECK_ADMIN_API_KEY` environment variable; never paste the key into committed files. An admin JWT also works but expires, so use an API key for cron.

**Manual trigger:** Call the sync API (backend must be running):

```bash
curl -X POST http://localhost:8002/api/sync/major-stocks \
  -H "Authorization: Bearer $FLOWDECK_ADMIN_API_KEY" \
  -H "Content-Type: application/json" -d "{}"
```

**Cron (recommended):** Run the provided script daily so reports are generated even when the dashboard is not open. The backend must be running when the cron job runs (e.g. run the backend as a service).

From the repository root:

```bash
# Required: admin API key; the script exits with an error if it is missing
export FLOWDECK_ADMIN_API_KEY=fd_live_...
# Optional: set if backend is not on localhost:8002
export BACKEND_URL=http://localhost:8002
./scripts/sync_major_stocks_daily.sh
```

Example crontab (run at 6:00 AM every day; adjust path and ensure backend is up). Cron does not load your shell profile, so set the key in the crontab itself (`crontab` files are private to your user):

```cron
FLOWDECK_ADMIN_API_KEY=fd_live_...
0 6 * * * /path/to/flowdeck/scripts/sync_major_stocks_daily.sh
```

**Optional in-app scheduler:** If the backend runs 24/7, you can enable a daily sync job inside the FastAPI process instead of using cron:

- `ENABLE_DAILY_SYNC` — the in-process daily sync job is on by default; set it to `false` to turn it off
- `SYNC_SCHEDULE_TIME=06:00` — time to run (default 6:00 AM server time)

Add these to your `.env` or environment before starting the backend.

### Results Directory

Reports are saved in the database (`backend/flowdeck.db` by default; change it with `DATABASE_URL`). The `results/` folder at the repository root only gets markdown copies of reports if you set `WRITE_AI_REPORTS_TO_RESULTS=true`. Its path comes from `RESULTS_DIR` in `backend/config.py` (default `results`).

## Usage

1. **View Homepage**: Open `http://localhost:3003` to see stock widgets
2. **Search Stocks**: Use the search bar to find any ticker
3. **View Stock Page**: Click any widget to see detailed analysis
4. **Generate Report**: If no report exists, click "Generate Report" button
5. **Browse Reports**: Switch between different report types using tabs

## API Endpoints

**Data API** (raw market data, single source):
- `GET /api/data/quote/{ticker}` - Real-time market quote
- `GET /api/data/news?ticker=...` - News articles
- `GET /api/data/company/{ticker}` - Company profile
- `GET /api/data/extended-info/{ticker}` - Extended metrics
- `GET /api/data/fundamentals/{ticker}` - Fundamental data
- `GET /api/data/financial-statements/{ticker}` - Balance sheet, cashflow, income statement
- `GET /api/data/financial-charts/{ticker}` - Chart time series
- `GET /api/data/historical/{ticker}` - Historical OHLCV
- `GET /api/data/analyst-recommendations/{ticker}` - Analyst recommendations

**Stocks API** (UI views):
- `GET /api/tickers/widgets?tickers=...` - Widget data for stocks
- `GET /api/tickers/{ticker}` - Complete stock page (quote, reports, recommendations)

**Analysis API:**
- `POST /api/analyses/start` - Start new analysis
- `GET /api/analyses/{analysis_run_id}/status` - Get analysis status (integer path)
- `WS /ws/analyses/{analysis_run_id}` - WebSocket for real-time updates

**Sync API:**
- `POST /api/sync/major-stocks` (admin only) - Ensure each major stock has a report for today (or optional `analysis_date` in body). Returns immediately with `triggered` / `skipped`; analyses run in background.

## Technology Stack

- **Backend**: FastAPI, Python, yfinance
- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **Real-time**: WebSocket
- **Report storage**: SQLite database (`backend/flowdeck.db`)

## Data Storage

### Report Storage Location

Stock analysis reports are stored in the database, in the `backend/flowdeck.db` file by default. Set `DATABASE_URL` to use a different database.

If `WRITE_AI_REPORTS_TO_RESULTS=true`, the backend also writes markdown copies of each report into the `results/` folder (see `RESULTS_DIR` in `backend/config.py`). The database is still the source the website reads from.

### Market Data

Real-time market data (prices, quotes, etc.) is fetched live using the `yfinance` library. This data is not stored locally but is retrieved on-demand when you view stocks.

## Troubleshooting

### "Failed to load stock data" Error

If you see this error on the frontend:

1. **Check if backend is running**: Make sure the backend server is running on `http://localhost:8002`
   ```bash
   python backend/run.py
   ```
   You should see a line like: `Uvicorn running on http://0.0.0.0:8002`

   **Note**: The port is fixed at 8002 in `backend/run.py` (it does not read a `PORT` variable). If port 8002 is in use, free it, or change `port=8002` in `backend/run.py` and set `VITE_DEV_PROXY_TARGET` (for example `http://127.0.0.1:8003`) before `npm run dev` so the frontend proxy matches.

2. **Check if frontend is running**: Make sure the frontend is running on `http://localhost:3003`
   ```bash
   cd frontend
   npm run dev
   ```
   You should see: `Local: http://localhost:3003/`

3. **Check the health endpoint**: Run this and look for `"status":"healthy"`:
   ```bash
   curl http://localhost:8002/health
   ```

4. **Check browser console**: Open browser developer tools (F12) and check:
   - **Console tab**: Look for API errors or CORS issues
   - **Network tab**: Check if requests to `/api/...` are failing (in dev they go through the Vite proxy to `http://localhost:8002`)

5. **Check backend logs**: Look at the terminal where the backend is running for error messages

6. **Test API directly**: Try accessing the API directly in your browser:
   - `http://localhost:8002/health` - Should return JSON with status
   - `http://localhost:8002/api/tickers/widgets` - Should return widget data
   - `http://localhost:8002/api/docs` - FastAPI interactive docs

7. **Check CORS**: If you see CORS errors in the browser console, the backend CORS is configured to allow `localhost:3003`, but verify the backend is actually running

8. **Check frontend proxy**: The frontend `vite.config.ts` proxies `/api` and `/ws` to `http://127.0.0.1:8002` (or to `VITE_DEV_PROXY_TARGET` if set). If you run the backend on a different port, set that variable to match.

9. **Verify proxy is working**: Check the Vite dev server console for proxy logs. Each proxied request is logged as `[proxy] METHOD /path -> /path`.

## Notes

- The backend imports the `ai_engine` package from the repository root (`backend/run.py` sets this up)
- Market data is fetched using yfinance (requires internet connection)
- Reports are stored in the database (`backend/flowdeck.db` by default)
- Most pages and endpoints need no login, but some (for example `POST /api/sync/major-stocks`) are admin-only
- New reports are generated when you click "Generate Report"
- Widgets always show current price from yfinance (when available)
- Recommendations are only shown when a report exists
