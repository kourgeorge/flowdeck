"""Tools for portfolio deep research: data layer, reports API, SerpAPI."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from ai_engine.tradingagents.agents.utils.core_stock_tools import get_stock_data
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
    get_insider_sentiment,
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


# --- serpapi_search: web search (sync SerpAPI wrapped for async use) ---


def _serpapi_search_sync(query: str, num_results: int = 8, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Sync SerpAPI call (same logic as watchlist_consulting.web_research.serpapi_search)."""
    import urllib.parse
    import urllib.request

    key = api_key or os.environ.get("SERPAPI_KEY")
    if not key:
        raise ValueError("SERPAPI_KEY not set in environment or .env")
    params = {"engine": "google", "q": query, "api_key": key}
    url = "https://serpapi.com/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    error = data.get("error")
    if error:
        raise RuntimeError(f"SerpAPI error: {error}")
    results = []
    for item in data.get("organic_results", [])[:num_results]:
        domain = item.get("displayed_link") or item.get("source") or ""
        if isinstance(domain, str) and " › " in domain:
            domain = domain.split(" › ")[0].strip()
        results.append({
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "url": item.get("link", ""),
            "domain": domain,
        })
    return results


@tool
def serpapi_search(
    query: str,
    num_results: int = 8,
) -> str:
    """
    Search the web using Google via SerpAPI. Use for company news, industry context, recent events, and cross-checking claims.
    Returns title, snippet, and URL for each result.
    """
    results = _serpapi_search_sync(query, num_results=num_results)
    if not results:
        return "No results found. Try a different query."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.get('title', '')}\nURL: {r.get('url', '')}\n{r.get('snippet', '')}\n")
    return "\n".join(lines)


async def serpapi_search_async(query: str, num_results: int = 8, api_key: Optional[str] = None) -> str:
    """Async wrapper for use in graph nodes (runs sync SerpAPI in thread)."""
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        None,
        lambda: _serpapi_search_sync(query, num_results=num_results, api_key=api_key),
    )
    if not results:
        return "No results found."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.get('title', '')}\nURL: {r.get('url', '')}\n{r.get('snippet', '')}\n")
    return "\n".join(lines)


# --- Data tools: reuse tradingagents when available ---




def get_data_tools() -> List[Any]:
    """Return list of LangChain tools for stock/fundamentals/news/EDGAR from tradingagents.agents.utils."""
    tools: List[Any] = []

        
    tools.extend([
            get_stock_data,
            get_indicators,
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
            get_news,
            get_global_news,
            get_insider_sentiment,
            get_insider_transactions,
        ])
    
    tools.append(get_edgar_filing_content)
    return tools


def make_serpapi_tool(
    api_key: Optional[str] = None,
    num_results: int = 8,
) -> Any:
    """
    Return a LangChain tool that runs SerpAPI with the given api_key and num_results.
    Use this when config (e.g. from the graph) must override env (e.g. SERPAPI_KEY).
    """
    key = api_key or os.environ.get("SERPAPI_KEY")
    n = max(1, min(num_results, 20))

    @tool
    def web_search(query: str) -> str:
        """
        Search the web using Google via SerpAPI. Use for company news, industry context, recent events, and cross-checking claims.
        Returns title, snippet, and URL for each result.
        """
        if not key:
            raise ValueError("SERPAPI_KEY not set. Set it in environment or pass via config to enable web search.")
        results = _serpapi_search_sync(query, num_results=n, api_key=key)
        if not results:
            return "No results found. Try a different query."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"[{i}] {r.get('title', '')}\nURL: {r.get('url', '')}\n{r.get('snippet', '')}\n")
        return "\n".join(lines)

    web_search.name = "web_search"
    return web_search


def get_all_tools(config: Optional[Any] = None) -> List[Any]:
    """
    Return all tools for the portfolio research graph: data tools (tradingagents)
    + get_latest_reports + serpapi_search.
    """
    tools: List[Any] = []
    tools.extend(get_data_tools())
    tools.append(get_latest_reports)
    tools.append(serpapi_search)
    return tools
