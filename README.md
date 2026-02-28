# Flowdeck

**Flowdeck** is an AI-powered stock analysis platform built for independent investors. It combines real-time market data, multi-agent AI analysis, and a conversational **Trader Copilot** — so you can research stocks, read full AI reports, and ask follow-up questions all in one place.

---

## Features

| Feature | Description |
|---------|-------------|
| **Live Market Data** | Real-time prices, volume, bid/ask, 52-week range, and today's range for any ticker |
| **Multi-Agent AI Analysis** | A committee of specialized AI agents (market, news, fundamentals, technical, sentiment) collaborates to produce a BUY / SELL / HOLD recommendation with full reasoning |
| **Transparent Reports** | Six report tabs per stock — Market, News, Fundamentals, Technical, Sentiment, Investment Plan — so you can read the full AI reasoning, not just the final label |
| **Trader Copilot** | A side-by-side workspace: stock detail panel on the left, AI chat on the right. Ask follow-up questions about any stock while viewing its live data and reports |
| **AI Analyst Agent** | Standalone conversational AI with live access to prices, fundamentals, news, technical indicators, insider activity, and your saved reports. Responses stream in real-time |
| **On-Demand Reports** | Generate fresh AI analysis for any stock, any time — using your token balance |
| **Stock Subscriptions & Dashboard** | Subscribe to stocks and receive email updates when new analysis reports are available. Track your watchlist from a personalized dashboard |
| **Token Economy** | New users receive 1,000 free tokens on sign-up. Additional tokens can be purchased in packs |

---

## Project Structure

```
flowdeck/
├── ai_engine/
│   ├── tradingagents/          # Multi-agent analysis graph (analysts, researchers, risk mgmt, trader)
│   └── watchlist_consulting/   # Watchlist deep-research pipeline
├── backend/                    # FastAPI API server
│   ├── main.py
│   ├── models/                 # Pydantic + DB models
│   └── services/               # Business logic (analysis, chat, reports, tokens, email…)
└── frontend/                   # React + TypeScript app (Vite)
    └── src/
        ├── pages/              # Full-page views (Home, Stock, Copilot, Chat, Dashboard…)
        ├── components/         # Reusable UI components
        └── services/           # API clients and type definitions
```

---

## Quick Start

**1. Clone and install**

```bash
git clone <your-repo-url>
cd flowdeck
python -m venv venv && source venv/bin/activate
# or: conda create -n flowdeck python=3.11 && conda activate flowdeck
pip install -r requirements.txt
```

**2. Configure API keys**

Copy the example env file and fill in your keys:

```bash
cp backend/.env.example backend/.env
```

Required keys:
- `OPENAI_API_KEY` — or Anthropic / Google / Azure; see `ai_engine/tradingagents/default_config.py`
- `ALPHA_VANTAGE_API_KEY` — for fundamentals and news ([free key](https://www.alphavantage.co/support/#api-key))

**3. Run backend and frontend**

```bash
# Terminal 1 — API server (http://localhost:8002)
cd backend && python main.py

# Terminal 2 — Frontend dev server (http://localhost:3003)
cd frontend && npm install && npm run dev
```

Or use the convenience scripts:

```bash
./scripts/start_flowdeck.sh   # start both
./scripts/stop_flowdeck.sh    # stop both
```

---

## The Trader Copilot

The **Copilot** (`/copilot`) is a three-panel workspace designed for active research:

```
┌─────────────────┬──────────────────────────────┬──────────────────┐
│  Ticker List    │     Stock Detail Panel        │  AI Copilot Chat │
│  (watchlist)    │  live quote · report tabs     │  streaming · live│
│                 │  fundamentals · news          │  data access     │
└─────────────────┴──────────────────────────────┴──────────────────┘
```

- **Left panel** — your watchlist; add any ticker with the search box
- **Middle panel** — full stock detail: live quote, AI recommendation, all report tabs, fundamentals, news, insider activity
- **Right panel** — AI chat with full context: the selected ticker, all watchlist tickers, live prices, reports, and more

The Copilot chat is context-aware: when you select a ticker, the AI automatically knows which stock you're looking at and can answer questions like *"What are the key risks for NVDA?"* or *"Compare MSFT and GOOGL fundamentals"* without you having to specify the ticker each time.

---

## The AI Analyst Agent

The standalone **AI Analyst Agent** (`/chat`) gives you a full-page conversational interface with the same capabilities as the Copilot chat:

- Live stock quotes and historical data
- AI-generated reports and BUY/SELL/HOLD recommendations
- Fundamentals, balance sheet, cash flow, income statement
- Technical indicators
- Insider transactions and sentiment
- Company and global news
- Your watchlist and portfolio context

Responses stream token-by-token. Each message shows the number of tools accessed and tokens consumed, so you always know what data the AI used.

---

## The Multi-Agent Analysis Engine

Flowdeck's analysis is produced by the `tradingagents` package — a LangGraph-based multi-agent graph. You can run it directly in your own scripts:

```python
from ai_engine.tradingagents.graph.trading_graph import TradingAgentsGraph
from ai_engine.tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
# config["deep_think_llm"] = "gpt-4o"
# config["quick_think_llm"] = "gpt-4o-mini"

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2024-05-10")
print(decision)
```

**Analysis flow:**

1. **Specialized analysts** — Market, News, Fundamentals, Technical, and Sentiment analysts each produce a focused report and score
2. **Bull vs. Bear debate** — Two AI researchers argue both sides across multiple rounds, stress-testing the investment case
3. **Research manager + trader** — Synthesizes the debate into an investment plan and actionable stance
4. **Risk debate → recommendation** — Aggressive, cautious, and neutral risk perspectives debate before a final judge produces the BUY / SELL / HOLD

Configuration options: `ai_engine/tradingagents/default_config.py`

---

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production deployment (systemd, Nginx, SSL) |
| [docs/DEPLOYMENT_UBUNTU.md](docs/DEPLOYMENT_UBUNTU.md) | Ubuntu-specific deployment guide |
| [docs/DATABASE_MIGRATION.md](docs/DATABASE_MIGRATION.md) | Running database migrations |
| [docs/STOCK_DEEP_RESEARCH.md](docs/STOCK_DEEP_RESEARCH.md) | Stock Deep Research agent (comprehensive company reports) |
| [docs/AI_ANALYSIS_FLOW.md](docs/AI_ANALYSIS_FLOW.md) | Detailed AI analysis pipeline documentation |
| [docs/BILLING_INTEGRATION_SUMMARY.md](docs/BILLING_INTEGRATION_SUMMARY.md) | Token economy and PayPal billing |

---

## License

See [LICENSE](LICENSE).
