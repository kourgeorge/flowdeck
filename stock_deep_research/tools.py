"""Tools for stock deep research: web search, optional EDGAR, think_tool."""

import asyncio
import logging
import os
from typing import Annotated, Any, List, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool

from stock_deep_research.config import SearchAPI, StockDeepResearchConfig

logger = logging.getLogger(__name__)


# --- Web search: DuckDuckGo (no API key) ---

@tool(description="Search the web for current information. Use for company news, market share, competitors, industry reports, and recent events.")
async def web_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 5,
) -> str:
    """Run a web search and return snippets. Uses DuckDuckGo when Tavily is not configured."""
    try:
        from duckduckgo_search import AsyncDDGS
    except ImportError:
        return (
            "Web search is not available: install duckduckgo-search with `pip install duckduckgo-search`. "
            "Or set TAVILY_API_KEY and use search_api=tavily."
        )
    try:
        async with AsyncDDGS() as ddgs:
            results = await ddgs.text(query, max_results=max_results)
        if not results:
            return "No results found. Try a different query."
        out = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            out.append(f"--- Result {i}: {title} ---\nURL: {href}\n{body}\n")
        return "\n".join(out)
    except Exception as e:
        logger.warning("DuckDuckGo search failed: %s", e)
        return f"Search failed: {e}"


# --- Tavily (optional, when API key is set) ---

async def _tavily_search_async(
    query: str,
    max_results: int = 5,
    config: Optional[RunnableConfig] = None,
) -> str:
    api_key = os.getenv("TAVILY_API_KEY") or (config or {}).get("configurable", {}).get("TAVILY_API_KEY")
    if not api_key:
        return "Tavily is not configured (no TAVILY_API_KEY). Use web_search instead or set TAVILY_API_KEY."
    try:
        from tavily import AsyncTavilyClient
    except ImportError:
        return "Tavily client not installed: pip install tavily-python"
    try:
        client = AsyncTavilyClient(api_key=api_key)
        response = await client.search(query, max_results=max_results, include_answer=True)
        results = response.get("results") or []
        answer = response.get("answer", "")
        out = []
        if answer:
            out.append(f"Answer: {answer}\n")
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            content = r.get("content", "")
            url = r.get("url", "")
            out.append(f"--- Result {i}: {title} ---\nURL: {url}\n{content}\n")
        return "\n".join(out) if out else "No results found."
    except Exception as e:
        logger.warning("Tavily search failed: %s", e)
        return f"Tavily search failed: {e}"


@tool(description="Search the web for current information (Tavily). Use for company news, market share, competitors, and industry data.")
async def tavily_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 5,
    config: RunnableConfig = None,
) -> str:
    """Run Tavily web search. Requires TAVILY_API_KEY."""
    return await _tavily_search_async(query, max_results=max_results, config=config)


# --- SEC EDGAR (optional, via Flowdeck backend) ---

def _get_edgar_client():
    """Return a callable that fetches EDGAR content from INFO_SERVICE_URL, or None."""
    base = os.getenv("INFO_SERVICE_URL", "").strip().rstrip("/")
    if not base:
        return None

    async def fetch(ticker: str, form: Optional[str] = None, max_filings: int = 1) -> str:
        import aiohttp
        url = f"{base}/api/data/edgar-filing-content/{ticker.upper()}"
        params = {}
        if form:
            params["form"] = form
        if max_filings:
            params["max_filings"] = max_filings
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params or None, timeout=60) as resp:
                    if resp.status != 200:
                        return f"EDGAR API returned status {resp.status}"
                    text = await resp.text()
                    return text or "No content returned."
        except Exception as e:
            return f"Failed to fetch EDGAR content: {e}"

    return fetch


@tool(description="Retrieve SEC EDGAR filing content for a US company: Risk Factors, MD&A, Competition, Business overview from 10-K/10-Q. Use when the research topic involves SEC filings, risk factors, or competition disclosure.")
async def get_edgar_filing_content(
    ticker: Annotated[str, "Ticker symbol (e.g. AAPL, AMZN)"],
    form: Annotated[Optional[str], "10-K or 10-Q; omit for latest of both"] = None,
    max_filings: Annotated[int, "Max number of filings to include"] = 1,
) -> str:
    """Fetch SEC EDGAR extracted sections for the given ticker. Requires INFO_SERVICE_URL pointing to Flowdeck backend."""
    client = _get_edgar_client()
    if not client:
        return (
            "SEC EDGAR is not configured. Set INFO_SERVICE_URL to your Flowdeck backend URL (e.g. http://localhost:8000) "
            "to enable 10-K/10-Q section extraction."
        )
    return await client(ticker, form=form, max_filings=max_filings)


# --- Think tool ---

@tool(description="Record a short reflection on research progress and next steps. Use between searches to plan.")
def think_tool(reflection: str) -> str:
    """Strategic reflection for planning next research steps."""
    return f"Reflection recorded: {reflection}"


# --- Tool assembly ---

async def get_all_tools(config: Optional[RunnableConfig] = None) -> List[Any]:
    """Return the list of tools for the researcher node: search (Tavily or DuckDuckGo), optional EDGAR, think_tool, ResearchComplete."""
    from stock_deep_research.state import ResearchComplete

    cfg = StockDeepResearchConfig.from_runnable_config(config)
    tools: List[Any] = [tool(ResearchComplete), think_tool]

    search_api = (cfg.search_api or "duckduckgo").lower()
    if search_api == SearchAPI.TAVILY.value:
        tools.append(tavily_search)
    elif search_api == SearchAPI.DUCKDUCKGO.value or search_api == "duckduckgo":
        tools.append(web_search)
    # else: no search (e.g. for testing)

    if cfg.info_service_url or os.getenv("INFO_SERVICE_URL"):
        tools.append(get_edgar_filing_content)

    return tools
