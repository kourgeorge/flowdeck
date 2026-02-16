# Flowdeck Backend (Node.js)

Alternative backend for the Stock Dashboard API implemented in Node.js. It exposes the **same REST and WebSocket API** as the Python backend so the existing frontend works without changes. AI analysis is still run by the **Python trading agents**, which are invoked as a subprocess by this backend.

## Architecture

- **Node server**: Handles all HTTP and WebSocket traffic (stocks, widgets, analyses, sync, and the Data API at `/api/data/*`).
- **Data API**: Implemented in Node using `yahoo-finance2` and Yahoo Finance public endpoints so that when the Python agents run, they call back to this Node server at `INFO_SERVICE_URL` for market/fundamental data.
- **Analysis**: When a client starts an analysis, the Node backend spawns a Python process (`backend/run_analysis_standalone.py`) that runs the TradingAgents graph. Progress is streamed as NDJSON on stdout; Node forwards it to WebSocket clients. Reports are written to the shared `results/` directory.

## Requirements

- **Node.js** 18+
- **Python** 3.x with the repo’s dependencies (so that `backend/run_analysis_standalone.py` and the `tradingagents` package run correctly). Set `AZURE_OPENAI_*` (or your LLM) env vars for the subprocess.

## Install and run

```bash
cd backend-node
npm install
npm run build
npm start
```

For development with auto-reload:

```bash
npm run dev
```

By default the server listens on port **8002** (same as the Python backend). Use `PORT` to override.

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | HTTP server port | `8002` |
| `RESULTS_DIR` | Results directory (relative to repo root or absolute) | `results` |
| `CORS_ORIGINS` | Comma-separated allowed origins | localhost:3003, 5173, 3000 |
| `BACKEND_URL` | Base URL of this backend (used as `INFO_SERVICE_URL` for the Python runner) | `http://127.0.0.1:8002` |
| `ENABLE_DAILY_SYNC` | Whether to run daily sync for major stocks | `true` |
| `SYNC_SCHEDULE_TIME` | Time for daily sync (HH:MM) | `06:00` |

The Python subprocess also needs LLM configuration (e.g. `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`).

## Frontend

Point the frontend at this backend by setting:

- `VITE_API_URL=http://localhost:8002`
- `VITE_WS_URL=localhost:8002` (or leave unset in dev if the proxy forwards `/ws` to the same host)

No frontend code changes are required; the API contract matches the Python backend.
