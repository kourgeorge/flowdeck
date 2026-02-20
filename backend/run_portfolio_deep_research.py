#!/usr/bin/env python3
"""
CLI to run the Portfolio Deep Research agent.

Usage:
  python backend/run_portfolio_deep_research.py --tickers AAPL,MSFT,GOOGL --query "Compare growth and risks"
  python backend/run_portfolio_deep_research.py --tickers NVDA,AMD "Deep dive on semiconductor exposure"

API keys are loaded from backend/.env (SERPAPI_KEY, LLM provider keys, INFO_SERVICE_URL).
Requires: SERPAPI_KEY for web search; OPENAI_API_KEY or Azure keys for LLM.
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_engine.portfolio_deep_research import portfolio_research_graph

# Load backend/.env so API keys are available
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / "backend" / ".env")
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass



def main():
    parser = argparse.ArgumentParser(description="Run Portfolio Deep Research")
    parser.add_argument("--tickers", type=str, required=True, help="Comma-separated tickers (e.g. AAPL,MSFT)")
    parser.add_argument("--query", type=str, default="", help="Research question (or pass as positional)")
    parser.add_argument("query_positional", nargs="?", default="", help="Research question (positional)")
    parser.add_argument("--out-dir", type=str, default=None, help="Output directory (default: results/portfolio_deep_research)")
    parser.add_argument("--no-html", action="store_true", help="Skip writing HTML report")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show step-by-step logs (default: True)")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress step logs (only errors)")
    args = parser.parse_args()

    # Step logs: default INFO for portfolio_deep_research; -q = WARNING, -v = INFO (no change)
    log_level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=log_level, datefmt="%H:%M:%S")
    logging.getLogger("ai_engine.portfolio_deep_research").setLevel(log_level)

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    if not tickers:
        print("Error: provide at least one ticker with --tickers", file=sys.stderr)
        sys.exit(1)

    query = (args.query or args.query_positional or "").strip()
    if not query:
        query = f"Portfolio research and comparison for {', '.join(tickers[:5])}"

    out_dir = Path(args.out_dir) if args.out_dir else REPO_ROOT / "results" / "portfolio_deep_research"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Backend uses port 8002; default when INFO_SERVICE_URL not in .env
    info_service_url = (os.getenv("INFO_SERVICE_URL") or "http://localhost:8002").strip().rstrip("/")
    # Keep configurable for deep models and tool calls.
    recursion_limit = int(os.getenv("PORTFOLIO_RECURSION_LIMIT", "40"))
    config = {
        "recursion_limit": recursion_limit,
        "configurable": {
            "info_service_url": info_service_url,
            "serpapi_key": os.getenv("SERPAPI_KEY"),
            "llm_provider": os.getenv("LLM_PROVIDER"),
            "max_search_results": int(os.getenv("PORTFOLIO_MAX_SEARCH_RESULTS", "8")),
        }
    }

    async def run():

        # Tickers and query are separate inputs; pass them through so no LLM interpret step is needed.
        initial = {
            "messages": [HumanMessage(content=query or f"Research: {', '.join(tickers)}")],
            "tickers": tickers,
            "user_query": query,
        }
        result = await portfolio_research_graph.ainvoke(initial, config=config)

        final_answer = result.get("final_answer") or ""
        final_html = result.get("final_report_html")
        run_id = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")

        # Markdown
        md_path = out_dir / f"report_{run_id}.md"
        md_path.write_text(final_answer, encoding="utf-8")
        print(final_answer)
        print(f"\n[Markdown saved to {md_path}]", file=sys.stderr)

        # HTML with figures
        if not args.no_html and final_html:
            html_path = out_dir / f"report_{run_id}.html"
            html_path.write_text(final_html, encoding="utf-8")
            print(f"[HTML saved to {html_path}]", file=sys.stderr)
        else:
            print("[No HTML generated (use INFO_SERVICE_URL and watchlist deps for figures)]", file=sys.stderr)

    asyncio.run(run())


if __name__ == "__main__":
    main()
