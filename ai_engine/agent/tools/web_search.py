"""WebSearchTool — search the web via SerpAPI for any query."""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request

from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult, ToolSpec

logger = logging.getLogger(__name__)

_WEB_SEARCH_SPEC = ToolSpec(
    name="web_search",
    version="1.0",
    description=(
        "Your ONLY gateway to live internet data. Use this tool whenever the information needed is NOT already "
        "provided by the other available tools (get_platform_reports, get_stock_quote, get_stock_data, "
        "get_indicators, get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement, "
        "get_news, get_global_news, get_insider_transactions, get_insider_sentiment). "
        "This covers ANY online content: breaking news, earnings call transcripts, analyst upgrades/downgrades, "
        "price target changes, SEC/regulatory filings, IPO details, M&A activity, product launches, "
        "macroeconomic data releases (CPI, GDP, jobs report), central bank decisions, geopolitical events, "
        "competitor analysis, industry trends, company background, executive changes, legal proceedings, "
        "social media sentiment, Reddit/Twitter discussions, blog posts, research papers, or ANY other "
        "topic that requires fetching current information from the web. "
        "When in doubt about whether another tool covers the question, use this tool to search online."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "The search query, e.g. 'Apple Q1 2025 earnings results', "
                    "'Fed interest rate decision March 2025', 'NVDA analyst price target upgrade'"
                ),
            }
        },
        "required": ["query"],
    },
    tags=["web", "search", "internet"],
)


class WebSearchTool(BaseTool):
    spec = _WEB_SEARCH_SPEC

    def execute(self, ctx: ExecutionContext, *, query: str, **_) -> ToolResult:
        try:
            result = _do_web_search(query)
            return ToolResult(ok=True, data=result)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


def _do_web_search(query: str) -> str:
    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        return "Web search is unavailable: SERPAPI_KEY is not configured."

    params = {
        "engine": "google",
        "q": query,
        "num": 10,
        "api_key": api_key,
    }
    url = "https://serpapi.com/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    error = data.get("error")
    if error:
        return f"Web search error: {error}"

    lines = [f"## Web Search Results for: {query}", ""]

    # Answer box
    answer_box = data.get("answer_box")
    if answer_box:
        title = answer_box.get("title", "")
        answer = answer_box.get("answer") or answer_box.get("snippet", "")
        if title:
            lines.append(f"**{title}**")
        if answer:
            lines.append(answer)
        lines.append("")

    # Knowledge graph
    kg = data.get("knowledge_graph")
    if kg:
        kg_title = kg.get("title", "")
        kg_desc = kg.get("description", "")
        if kg_title:
            lines.append(f"**{kg_title}**: {kg_desc}")
            lines.append("")

    # Organic results
    organic = data.get("organic_results", [])
    for i, result in enumerate(organic[:8], 1):
        title = result.get("title", "")
        link = result.get("link", "")
        snippet = result.get("snippet", "")
        date = result.get("date", "")
        date_str = f" ({date})" if date else ""
        lines.append(f"**{i}. {title}**{date_str}")
        if snippet:
            lines.append(snippet)
        if link:
            lines.append(f"Source: {link}")
        lines.append("")

    # Top stories
    top_stories = data.get("top_stories", [])
    if top_stories:
        lines.append("### Top Stories")
        for story in top_stories[:5]:
            title = story.get("title", "")
            source = story.get("source", "")
            date = story.get("date", "")
            link = story.get("link", "")
            date_str = f" ({date})" if date else ""
            source_str = f" — {source}" if source else ""
            lines.append(f"- **{title}**{source_str}{date_str}")
            if link:
                lines.append(f"  {link}")
        lines.append("")

    if len(lines) <= 2:
        return f"No results found for: {query}"

    return "\n".join(lines)

# Made with Bob
