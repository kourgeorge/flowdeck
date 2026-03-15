"""
Reddit company social tool: discussions and sentiment from finance subreddits.

Use when the user asks about Reddit sentiment, social media buzz, retail investor
discussion, or what people are saying about a stock on Reddit.
"""

from __future__ import annotations

import datetime
from typing import List

from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult, ToolSpec

# ---------------------------------------------------------------------------
# RedditCompanySocialTool
# ---------------------------------------------------------------------------

_REDDIT_SPEC = ToolSpec(
    name="get_reddit_company_social",
    version="1.0",
    description=(
        "Get Reddit discussions and sentiment for a ticker from finance subreddits (e.g. r/stocks, r/investing). "
        "Returns posts and comments matching your search terms. "
        "Use when the user asks about Reddit sentiment, social media buzz, retail discussion, or what people are saying about a stock. "
        "Call get_ticker_quote first to get the company name, then pass search_terms like [company_name, ticker] (e.g. ['Apple', 'AAPL']). "
        "If the first call returns few results, you may call again with different search_terms (e.g. sector, product names)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT"},
            "search_terms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Terms to search for in Reddit (e.g. company name and ticker). Get company name from get_ticker_quote first, then pass e.g. ['Apple', 'AAPL'].",
            },
        },
        "required": ["ticker", "search_terms"],
    },
    tags=["reddit", "sentiment", "social", "company"],
)


class RedditCompanySocialTool(BaseTool):
    spec = _REDDIT_SPEC

    def execute(
        self,
        ctx: ExecutionContext,
        *,
        ticker: str,
        search_terms: List[str],
        **_,
    ) -> ToolResult:
        try:
            from ai_engine.tradingagents.agents.utils.news_data_tools import get_reddit_company_social

            today = datetime.date.today()
            start = (today - datetime.timedelta(days=7)).isoformat()
            end = today.isoformat()
            terms = [s.strip() for s in search_terms if s and str(s).strip()]
            if not terms:
                terms = [ticker.upper()]
            data = get_reddit_company_social.invoke({
                "ticker": ticker.upper(),
                "start_date": start,
                "end_date": end,
                "search_terms": terms,
            })
            return ToolResult(ok=True, data=data)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})
