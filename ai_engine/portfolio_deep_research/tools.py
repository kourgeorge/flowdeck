"""Tools for portfolio deep research: data layer, reports API, SerpAPI."""

from __future__ import annotations

import json
import os
from typing import Any, List, Optional

from langchain_core.tools import tool

from ai_engine import serpapi_client

from ai_engine.tradingagents.agents.utils.core_stock_tools import get_ticker_data
from ai_engine.tradingagents.agents.utils.technical_indicators_tools import get_indicators
from ai_engine.tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
)
from ai_engine.tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_global_news,
    get_insider_transactions,
)
from ai_engine.tradingagents.agents.utils.edgar_tools import get_edgar_filing_content


def _info_service_base() -> Optional[str]:
    url = os.environ.get("INFO_SERVICE_URL", "").strip().rstrip("/")
    return url or None


# --- get_latest_reports: fetch existing deep-agent reports from backend ---


@tool
def get_latest_reports(tickers: str) -> str:
    """
    Fetch the latest analysis reports for the given tickers from the server.
    Input: comma-separated ticker symbols (e.g. 'AAPL,MSFT,GOOGL').
    Use this to load existing deep-agent reports (market, news, fundamentals, SEC, investment_plan, final_trade_decision) before doing further research.
    """
    import urllib.parse
    import urllib.request

    base = _info_service_base()
    if not base:
        raise ValueError(
            "INFO_SERVICE_URL is not set. Set it to your Flowdeck backend URL (e.g. http://localhost:8002) to load reports."
        )
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()][:50]
    if not ticker_list:
        raise ValueError("No tickers provided. Use comma-separated symbols, e.g. AAPL,MSFT.")

    url = f"{base}/api/data/reports/batch"
    data = json.dumps({"tickers": ticker_list}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.loads(resp.read().decode())

    result = out.get("tickers") or {}
    lines = []
    for t in ticker_list:
        info = result.get(t) or {}
        report_date = info.get("report_date")
        reports = info.get("reports") or {}
        if not report_date or not reports:
            lines.append(f"{t}: No reports found.")
            continue
        types = list(reports.keys())
        takeaways = []
        rec = None
        for rt, data in reports.items():
            kt = data.get("key_takeaways") or []
            if kt:
                takeaways.extend(kt[:2])
            if rt == "final_trade_decision" and data.get("recommendation"):
                rec = data.get("recommendation")
        rec = rec or reports.get("investment_plan", {}).get("recommendation") or "—"
        lines.append(
            f"{t} (run {report_date}): {', '.join(types)}. Recommendation: {rec}. "
            + ("Key takeaways: " + "; ".join(takeaways[:3]) if takeaways else "")
        )
    return "\n".join(lines)


# --- serpapi_search: web search ---


def _make_serpapi_search(api_key: Optional[str] = None) -> Any:
    """Build the serpapi_search tool; a None key means SERPAPI_KEY is read at call time."""

    @tool
    def serpapi_search(
        query: str,
        num_results: int = 8,
    ) -> str:
        """
        Search the web using Google via SerpAPI. Use for company news, industry context, recent events, and cross-checking claims.
        Returns title, snippet, and URL for each result.
        """
        return serpapi_client.format_results(
            serpapi_client.search(query, num_results=num_results, api_key=api_key)
        )

    return serpapi_search


serpapi_search = _make_serpapi_search()


# --- Data tools: reuse tradingagents when available ---




def get_data_tools() -> List[Any]:
    """Return list of LangChain tools for stock/fundamentals/news/EDGAR from tradingagents.agents.utils."""
    tools: List[Any] = []

        
    tools.extend([
            get_ticker_data,
            get_indicators,
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
            get_news,
            get_global_news,
            get_insider_transactions,
        ])
    
    tools.append(get_edgar_filing_content)
    return tools


def get_all_tools(config: Optional[Any] = None) -> List[Any]:
    """
    Return all tools for the portfolio research graph: data tools (tradingagents)
    + get_latest_reports + serpapi_search.
    """
    tools: List[Any] = []
    tools.extend(get_data_tools())
    tools.append(get_latest_reports)
    # PortfolioDeepResearchConfig.serpapi_key (from configurable or env) wins over the env var.
    key = getattr(config, "serpapi_key", None)
    tools.append(_make_serpapi_search(key) if key else serpapi_search)
    return tools
