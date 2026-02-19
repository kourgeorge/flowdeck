# Flowdeck

**Flowdeck** is a stock analysis web app with AI-powered reports, real-time market data, and multi-agent analysis. It is built on the TradingAgents framework: LLM-powered analysts (fundamentals, news, technical, sentiment), researchers, and risk management that collaborate to produce trading insights.

A separate **Stock Deep Research** agent can produce comprehensive company reports by autonomously searching the web and (optionally) SEC EDGAR. It does not output BUY/SELL/HOLD; see [docs/STOCK_DEEP_RESEARCH.md](docs/STOCK_DEEP_RESEARCH.md) and `scripts/run_stock_deep_research.py`.

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


---

## Project structure

| Path | Description |
|------|-------------|
| `frontend/` | TypeScript/React app (Vite) |
| `backend/` | Python FastAPI API |
| `tradingagents/` | Agents package (dataflows, graph) |

- **[Setup & run](docs/STOCK_DASHBOARD.md)** — Local development and running the app.
- **[Deployment guide](docs/DEPLOYMENT.md)** — Production deploy (systemd, Nginx, SSL).
- **[Database migrations](docs/DATABASE_MIGRATION.md)** — How to run migrations (e.g. token economy schema).

---

## Quick start

**1. Clone and install (from repo root)**

```bash
git clone <your-repo-url>
cd <project-directory>
python -m venv venv && source venv/bin/activate   # or: conda create -n flowdeck python=3.11 && conda activate flowdeck
pip install -r requirements.txt
```

**2. API keys**

Create a `.env` in the project root (or copy from `.env.example`):

- `OPENAI_API_KEY` (or Anthropic/Google/Azure; see `tradingagents/default_config.py`)
- `ALPHA_VANTAGE_API_KEY` for fundamentals/news ([free key](https://www.alphavantage.co/support/#api-key))

**3. Run backend and frontend**

```bash
cd backend && python run.py          # API on http://localhost:8002
cd frontend && npm install && npm run dev   # App on http://localhost:3003
```

---

## Using the agents in code

Flowdeck’s backend uses the `tradingagents` package. You can run the same graph in your own scripts:

```python
from ai_engine.tradingagents.graph.trading_graph import TradingAgentsGraph
from ai_engine.tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
# config["deep_think_llm"] = "gpt-4o-mini"
# config["quick_think_llm"] = "gpt-4o-mini"
ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2024-05-10")
print(decision)
```

Configuration options: `tradingagents/default_config.py`.

---


