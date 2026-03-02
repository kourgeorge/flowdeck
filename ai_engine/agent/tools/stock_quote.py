"""StockQuoteTool — get real-time stock quote for a ticker symbol."""

from __future__ import annotations

from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult, ToolSpec

_SPEC = ToolSpec(
    name="get_stock_quote",
    version="1.0",
    description=(
        "Get the real-time stock quote for a ticker: current price, daily change ($), "
        "daily change (%), bid/ask, day high/low, 52-week range, volume, and market status. "
        "Use when the user asks for the current price, today's performance, or live market data."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA",
            }
        },
        "required": ["symbol"],
    },
    tags=["market", "price", "realtime"],
)


class StockQuoteTool(BaseTool):
    spec = _SPEC

    def execute(self, ctx: ExecutionContext, *, symbol: str, **_) -> ToolResult:
        try:
            from ai_engine.tradingagents.agents.utils.core_stock_tools import get_stock_quote
            data = get_stock_quote.invoke({"symbol": symbol.upper()})
            return ToolResult(ok=True, data=data)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})

# Made with Bob
