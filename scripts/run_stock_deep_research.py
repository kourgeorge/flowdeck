#!/usr/bin/env python3
"""
CLI to run the Stock Deep Research agent.

Usage:
  python scripts/run_stock_deep_research.py "Research Amazon (AMZN)"
  python scripts/run_stock_deep_research.py "Full report on Microsoft, focus on cloud and competition"
  INFO_SERVICE_URL=http://localhost:8000 python scripts/run_stock_deep_research.py "Competitive analysis of Apple"

Requires:
  - OPENAI_API_KEY (or ANTHROPIC_API_KEY / GOOGLE_API_KEY for other models)
  - pip install duckduckgo-search  (or set TAVILY_API_KEY for Tavily search)
  - Optional: INFO_SERVICE_URL for SEC EDGAR (Flowdeck backend)
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add repo root so stock_deep_research and tradingagents are importable
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from langchain_core.messages import HumanMessage

from stock_deep_research.graph import stock_researcher_graph


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_stock_deep_research.py \"<research question>\"", file=sys.stderr)
        print("Example: python run_stock_deep_research.py \"Research Amazon AMZN\"", file=sys.stderr)
        sys.exit(1)

    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print("Please provide a non-empty research question.", file=sys.stderr)
        sys.exit(1)

    config = {
        "configurable": {
            "research_model": os.getenv("STOCK_RESEARCH_MODEL", "openai:gpt-4o"),
            "compression_model": os.getenv("STOCK_COMPRESSION_MODEL", "openai:gpt-4o-mini"),
            "final_report_model": os.getenv("STOCK_FINAL_REPORT_MODEL", "openai:gpt-4o"),
            "search_api": os.getenv("STOCK_SEARCH_API", "duckduckgo"),
            "info_service_url": os.getenv("INFO_SERVICE_URL"),
            "max_researcher_iterations": int(os.getenv("STOCK_MAX_ITERATIONS", "15")),
            "max_concurrent_research_units": int(os.getenv("STOCK_MAX_CONCURRENT", "3")),
        }
    }

    async def run():
        initial = {"messages": [HumanMessage(content=question)]}
        result = await stock_researcher_graph.ainvoke(initial, config=config)
        report = result.get("final_report") or ""
        print(report)
        # Optionally save to file
        out_dir = REPO_ROOT / "results" / "stock_deep_research"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "latest_report.md"
        out_file.write_text(report, encoding="utf-8")
        print(f"\n[Report also saved to {out_file}]", file=sys.stderr)

    asyncio.run(run())


if __name__ == "__main__":
    main()
