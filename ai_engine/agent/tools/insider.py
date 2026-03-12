"""
Insider trading tools:
  - InsiderTransactionsTool — recent insider buy/sell transactions
  - InsiderSentimentTool    — aggregated insider sentiment score
"""

from __future__ import annotations

import datetime

from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult, ToolSpec

# ---------------------------------------------------------------------------
# InsiderTransactionsTool
# ---------------------------------------------------------------------------

_INSIDER_TX_SPEC = ToolSpec(
    name="get_insider_transactions",
    version="1.0",
    description=(
        "Get recent insider trading transactions for a ticker: who bought or sold, "
        "how many shares, at what price, and their role (CEO, CFO, Director, etc.). "
        "Use when the user asks about insider activity, insider buying/selling, or management confidence."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
        },
        "required": ["ticker"],
    },
    tags=["insider", "transactions"],
)


class InsiderTransactionsTool(BaseTool):
    spec = _INSIDER_TX_SPEC

    def execute(self, ctx: ExecutionContext, *, ticker: str, **_) -> ToolResult:
        try:
            from ai_engine.tradingagents.agents.utils.news_data_tools import get_insider_transactions
            today = datetime.date.today().isoformat()
            data = get_insider_transactions.invoke({"ticker": ticker.upper(), "curr_date": today})
            return ToolResult(ok=True, data=data)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


# ---------------------------------------------------------------------------
# InsiderSentimentTool
# ---------------------------------------------------------------------------

_INSIDER_SENTIMENT_SPEC = ToolSpec(
    name="get_insider_sentiment",
    version="1.0",
    description=(
        "Get an aggregated insider sentiment score for a ticker: net insider buying vs selling trend, "
        "ratio of buyers to sellers, and overall sentiment direction. "
        "Use when the user asks about insider sentiment, whether insiders are bullish or bearish."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
        },
        "required": ["ticker"],
    },
    tags=["insider", "sentiment"],
)


class InsiderSentimentTool(BaseTool):
    spec = _INSIDER_SENTIMENT_SPEC

    def execute(self, ctx: ExecutionContext, *, ticker: str, **_) -> ToolResult:
        try:
            from ai_engine.tradingagents.agents.utils.news_data_tools import get_insider_sentiment
            today = datetime.date.today().isoformat()
            data = get_insider_sentiment.invoke({"ticker": ticker.upper(), "curr_date": today})
            return ToolResult(ok=True, data=data)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


