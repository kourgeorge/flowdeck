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
stock-dashboard/
├── backend/          # FastAPI backend
│   ├── main.py      # FastAPI application
│   ├── config.py    # Configuration
│   ├── models/      # Pydantic models
│   └── services/    # Business logic services
└── frontend/        # React frontend
    └── src/
        ├── pages/    # Page components
        ├── components/  # Reusable components
        └── services/   # API clients
```

## Setup

### Backend

1. Navigate to the backend directory:
```bash
cd stock-dashboard/backend
```

2. Create a conda environment (recommended):
```bash
conda env create -f environment.yml
conda activate stock-dashboard
```

**Note**: The environment uses Python 3.11 for compatibility. If you're using Python 3.13, you may encounter issues with pydantic-core. The conda environment will automatically use Python 3.11.

Alternatively, if you prefer pip (use Python 3.10-3.12), from the **repository root**:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt   # root requirements.txt includes backend deps
```

3. Make sure you're in the TradingAgents repository root (where `tradingagents` package is accessible)

4. Run the backend server:

From the repository root (TradingAgents directory):
```bash
cd stock-dashboard/backend
python run.py
```

Or use uvicorn directly:
```bash
cd stock-dashboard/backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Important**: Make sure you're running from the `stock-dashboard/backend` directory, and that the TradingAgents repository root (where `tradingagents` package is) is accessible.

The backend will start on `http://localhost:8002`

**Note**: Port 8002 is used to avoid conflicts with other services (e.g. Django on 8000, or SSH tunnels on 8001).

**Verify backend is running**: Open `http://localhost:8002/health` in your browser - it should return `{"status": "healthy", ...}`

### Frontend

1. Navigate to the frontend directory (from repo root use `stock-dashboard/frontend`; if you're already in `stock-dashboard`, use `frontend`):
```bash
cd stock-dashboard/frontend   # from TradingAgents repo root
# or
cd frontend                   # if you're already in stock-dashboard/
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

Edit `backend/config.py` to customize the list of stocks shown on the homepage:

```python
MAJOR_STOCKS = [
    "SPY", "AAPL", "MSFT", "GOOGL", "TSLA", 
    "IBM", "META", "NVDA", "AMZN", "JPM"
]
```

### Daily sync of major stocks reports

To ensure every major stock has a report for the current day, you can trigger a sync manually or on a schedule.

**Manual trigger:** Call the sync API (backend must be running):

```bash
curl -X POST http://localhost:8002/api/sync/major-stocks -H "Content-Type: application/json" -d "{}"
```

**Cron (recommended):** Run the provided script daily so reports are generated even when the dashboard is not open. The backend must be running when the cron job runs (e.g. run the backend as a service).

From the repository root (TradingAgents):

```bash
# Optional: set if backend is not on localhost:8002
export BACKEND_URL=http://localhost:8002
./scripts/sync_major_stocks_daily.sh
```

Example crontab (run at 6:00 AM every day; adjust path and ensure backend is up):

```cron
0 6 * * * /path/to/TradingAgents/scripts/sync_major_stocks_daily.sh
```

**Optional in-app scheduler:** If the backend runs 24/7, you can enable a daily sync job inside the FastAPI process instead of using cron:

- `ENABLE_DAILY_SYNC=true` — enable the in-process daily sync job
- `SYNC_SCHEDULE_TIME=06:00` — time to run (default 6:00 AM server time)

Add these to your `.env` or environment before starting the backend.

### Results Directory

The backend reads reports from the `results/` directory. Make sure the path in `backend/config.py` is correct:

```python
RESULTS_DIR = "results"  # Resolved to repo root (TradingAgents/results)
```

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
- `POST /api/sync/major-stocks` - Ensure each major stock has a report for today (or optional `analysis_date` in body). Returns immediately with `triggered` / `skipped`; analyses run in background.

## Technology Stack

- **Backend**: FastAPI, Python, yfinance
- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **Real-time**: WebSocket
- **Data Source**: TradingAgents results directory

## Data Storage

### Report Storage Location

Stock analysis reports are stored in the `results/` directory at the TradingAgents repository root:

```
TradingAgents/
├── results/
│   ├── IBM/
│   │   ├── 2025-12-21/
│   │   │   ├── reports/
│   │   │   │   ├── final_trade_decision.json
│   │   │   │   ├── market_report.json
│   │   │   │   ├── news_report.json
│   │   │   │   ├── fundamentals_report.json
│   │   │   │   └── ...
│   │   │   └── message_tool.log
│   │   └── 2025-12-18/
│   │       └── ...
│   ├── AAPL/
│   │   └── ...
│   └── ...
```

The backend reads reports from this directory structure. The path is configured in `backend/config.py` as `RESULTS_DIR = "results"` and is resolved to the repository root (so reports live in `TradingAgents/results/`).

### Market Data

Real-time market data (prices, quotes, etc.) is fetched live using the `yfinance` library. This data is not stored locally but is retrieved on-demand when you view stocks.

## Troubleshooting

### "Failed to load stock data" Error

If you see this error on the frontend:

1. **Check if backend is running**: Make sure the backend server is running on `http://localhost:8002`
   ```bash
   cd stock-dashboard/backend
   python run.py
   ```
You should see: `INFO: Uvicorn running on http://0.0.0.0:8002`

   **Note**: If port 8002 is in use, set `PORT=8003` when running the backend and update the frontend proxy in `frontend/vite.config.ts` to match.

2. **Check if frontend is running**: Make sure the frontend is running on `http://localhost:3003`
   ```bash
   cd stock-dashboard/frontend
   npm run dev
   ```
   You should see: `Local: http://localhost:3003/`

3. **Test backend services**: Run the test script to verify data access:
   ```bash
   cd stock-dashboard/backend
   python check_backend.py
   ```
   This will verify that the backend can read reports and fetch market data.

4. **Check browser console**: Open browser developer tools (F12) and check:
   - **Console tab**: Look for API errors or CORS issues
   - **Network tab**: Check if requests to `http://localhost:8000/api/...` are failing

5. **Check backend logs**: Look at the terminal where the backend is running for error messages

6. **Verify results directory**: Make sure the `results/` directory exists at the TradingAgents root:
   ```bash
   ls -la results/
   ```

7. **Test API directly**: Try accessing the API directly in your browser:
   - `http://localhost:8002/health` - Should return JSON with status
   - `http://localhost:8002/api/tickers/widgets` - Should return widget data
   - `http://localhost:8002/docs` - FastAPI interactive docs

8. **Check CORS**: If you see CORS errors in the browser console, the backend CORS is configured to allow `localhost:3003`, but verify the backend is actually running

9. **Check frontend proxy**: The frontend `vite.config.ts` proxies `/api` and `/ws` to `http://localhost:8002`. If you run the backend on a different port, update the proxy target to match.

10. **Verify proxy is working**: Check the Vite dev server console for proxy logs. The updated config includes logging to show when requests are proxied.

## Notes

- The backend requires access to the `tradingagents` package from the parent directory
- Market data is fetched using yfinance (requires internet connection)
- Reports are read from the existing `results/` directory structure
- All reports are publicly accessible (no authentication required)
- New reports are generated when you click "Generate Report" and are saved to `results/{TICKER}/{DATE}/reports/`
- Widgets always show current price from yfinance (when available)
- Recommendations are only shown when a report exists
