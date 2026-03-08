"""
News tools:
  - NewsTool       — recent company-specific news (last 7 days)
  - GlobalNewsTool — global market/macro news (last 7 days)
"""

from __future__ import annotations

import datetime
from typing import Optional

from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult, ToolSpec

# ---------------------------------------------------------------------------
# NewsTool
# ---------------------------------------------------------------------------

_NEWS_SPEC = ToolSpec(
    name="get_news",
    version="1.0",
    description=(
        "Get recent news articles for a specific ticker from the last 7 days. "
        "Use when the user asks about recent news, events, announcements, or catalysts for a specific company."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
        },
        "required": ["ticker"],
    },
    tags=["news", "company"],
)


class NewsTool(BaseTool):
    spec = _NEWS_SPEC

    def execute(self, ctx: ExecutionContext, *, ticker: str, **_) -> ToolResult:
        try:
            from ai_engine.tradingagents.agents.utils.news_data_tools import get_news
            today = datetime.date.today()
            start = (today - datetime.timedelta(days=7)).isoformat()
            end = today.isoformat()
            data = get_news.invoke({"ticker": ticker.upper(), "start_date": start, "end_date": end})
            return ToolResult(ok=True, data=data)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


# ---------------------------------------------------------------------------
# GlobalNewsTool
# ---------------------------------------------------------------------------

_GLOBAL_NEWS_SPEC = ToolSpec(
    name="get_global_news",
    version="1.0",
    description=(
        "Get global market and macroeconomic news from the last 7 days (no ticker needed). "
        "Use when the user asks about market conditions, macro trends, Fed policy, interest rates, "
        "sector trends, or general market news not specific to one company. "
        "Pass 'query' to focus the search (e.g. 'key risks 2026', 'inflation Fed')."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Optional search focus (e.g. key risks, inflation, geopolitical). If omitted, returns general macro/market news.",
            }
        },
        "required": [],
    },
    tags=["news", "macro", "global"],
)


class GlobalNewsTool(BaseTool):
    spec = _GLOBAL_NEWS_SPEC

    def execute(self, ctx: ExecutionContext, *, query: Optional[str] = None, **_) -> ToolResult:
        try:
            from ai_engine.tradingagents.agents.utils.news_data_tools import get_global_news
            today = datetime.date.today().isoformat()
            payload = {"curr_date": today, "look_back_days": 7, "limit": 10}
            if query and query.strip():
                payload["query"] = query.strip()
            data = get_global_news.invoke(payload)
            return ToolResult(ok=True, data=data)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})

# Made with Bob
