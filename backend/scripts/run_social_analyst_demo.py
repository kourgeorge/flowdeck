#!/usr/bin/env python3
"""
Run only the Social Media (sentiment) analyst for one ticker and show how it uses the Reddit tool.

Uses the real LLM provider (from .env / DEFAULT_CONFIG) and real backend—no mocks. The agent
has get_ticker_quote, get_news, and get_reddit_company_social; it is instructed to get the
company name (e.g. via get_quote) and pass search_terms to get_reddit_company_social. This
script instruments the Reddit tool call to print the search_terms the agent chose.

Usage:
  # Backend must be running; .env must have INFO_SERVICE_URL (or BACKEND_URL) and LLM keys.
  python backend/scripts/run_social_analyst_demo.py [--ticker AAPL] [--date 2025-03-15]

Requires: .env with INFO_SERVICE_URL or BACKEND_URL, and LLM API keys (e.g. OPENAI_API_KEY).
  Backend running for quote/Reddit API. For Reddit data, backend needs REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND.parent
for p in (str(REPO_ROOT), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from dotenv import load_dotenv
load_dotenv(BACKEND / ".env")
load_dotenv(REPO_ROOT / ".env")

# Capture Reddit tool args when the agent calls the info service
_reddit_calls: list[dict] = []


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Social Media Analyst only and show Reddit tool usage")
    parser.add_argument("--ticker", default="AAPL", help="Ticker to analyze (default: AAPL)")
    parser.add_argument("--date", default=None, help="Trade date YYYY-MM-DD (default: today UTC)")
    args = parser.parse_args()
    ticker = args.ticker.upper()
    trade_date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    info_url = os.getenv("INFO_SERVICE_URL", "").strip() or os.getenv("BACKEND_URL", "").strip()
    if not info_url:
        print("ERROR: Set INFO_SERVICE_URL or BACKEND_URL in .env (e.g. http://localhost:8002)")
        sys.exit(1)
    info_url = info_url.rstrip("/")

    # Ensure .env is loaded (e.g. when run from IDE)
    load_dotenv(BACKEND / ".env", override=False)
    # LLM provider must have API keys (from .env)
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("AZURE_OPENAI_API_KEY"):
        print("ERROR: Set OPENAI_API_KEY or AZURE_OPENAI_API_KEY in .env (script uses real LLM provider, no mocks)")
        sys.exit(1)
    print(f"Using info service: {info_url}")
    print(f"Running Social Media Analyst only for ticker={ticker} trade_date={trade_date}")
    print("(The agent will use get_quote/get_news, then get_reddit_company_social with search_terms.)\n")

    # Patch the function the tool actually calls so we log Reddit args when the agent uses the tool
    from ai_engine.tradingagents.agents.utils import news_data_tools
    _real_get_reddit = news_data_tools.get_reddit_company_social_via_service

    def _logged_reddit(ticker, start_date, end_date, search_terms, base_url=None):
        _reddit_calls.append({
            "ticker": ticker,
            "start_date": start_date,
            "end_date": end_date,
            "search_terms": list(search_terms) if search_terms else [],
        })
        print("\n[DEMO] get_reddit_company_social called with:")
        print(f"       ticker={ticker!r} start_date={start_date!r} end_date={end_date!r}")
        print(f"       search_terms={search_terms!r}")
        return _real_get_reddit(ticker, start_date, end_date, search_terms, base_url=base_url)

    news_data_tools.get_reddit_company_social_via_service = _logged_reddit

    from ai_engine.llm_provider import get_config_from_env
    from ai_engine.tradingagents.default_config import DEFAULT_CONFIG
    from ai_engine.tradingagents.graph.trading_graph import TradingAgentsGraph
    from ai_engine.tradingagents.graph.propagation import Propagator

    config = {**DEFAULT_CONFIG, "info_service_url": info_url}
    config.update(get_config_from_env())  # use Azure/OpenAI from env like analysis_service
    graph = TradingAgentsGraph(selected_analysts=["social"], config=config, debug=False)
    propagator = Propagator()
    init_state = propagator.create_initial_state(ticker, trade_date)
    graph_args = propagator.get_graph_args()

    print("Invoking graph (social analyst only)...")
    final_state = graph.graph.invoke(init_state, **graph_args)

    print("\n" + "=" * 60)
    print("RESULT: How the sentiment agent used the Reddit tool")
    print("=" * 60)
    if _reddit_calls:
        for i, call in enumerate(_reddit_calls, 1):
            print(f"\nCall #{i}:")
            print(f"  ticker       = {call['ticker']!r}")
            print(f"  start_date   = {call['start_date']!r}")
            print(f"  end_date     = {call['end_date']!r}")
            print(f"  search_terms = {call['search_terms']!r}")
        print("\nThe agent provides search_terms (e.g. company name + ticker from get_quote);")
        print("the backend uses only these terms for Reddit post filtering (no regex/heuristics).")
    else:
        print("\nThe Reddit tool was not called this run (agent may have used only get_news).")
    if final_state.get("sentiment_report"):
        snippet = (final_state["sentiment_report"] or "")[:400]
        print(f"\nSentiment report snippet:\n{snippet}...")
    resources = final_state.get("report_resources") or []
    print(f"\nReport resources collected: {len(resources)}")
    for i, r in enumerate(resources[:15], 1):
        print(f"  {i}. {r.get('type', '?')} | {r.get('title') or r.get('description') or r.get('url', '')} | ticker={r.get('ticker', '')}")
    if len(resources) > 15:
        print(f"  ... and {len(resources) - 15} more")
    print()


if __name__ == "__main__":
    main()
