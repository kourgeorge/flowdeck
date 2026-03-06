"""
Analyst recommendation tool:
  - AnalystRecommendationsTool — Wall Street recommendation consensus and trend
"""

from __future__ import annotations

from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult, ToolSpec

_ANALYST_RECOMMENDATIONS_SPEC = ToolSpec(
    name="get_analysts_recommendation",
    version="1.0",
    description=(
        "Get analyst recommendation consensus for a ticker (BUY/HOLD/SELL), recommendation trend breakdown "
        "(strong buy/buy/hold/sell/strong sell), and related analyst metadata such as target prices. "
        "Use when the user asks about Wall Street analyst sentiment, analyst consensus, or rating trends."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
        },
        "required": ["ticker"],
    },
    tags=["analysts", "recommendations", "fundamentals"],
)


class AnalystRecommendationsTool(BaseTool):
    spec = _ANALYST_RECOMMENDATIONS_SPEC

    def execute(self, ctx: ExecutionContext, *, ticker: str, **_) -> ToolResult:
        try:
            from ai_engine.tradingagents.agents.utils.fundamental_data_tools import get_analysts_recommendation

            data = get_analysts_recommendation.invoke({"ticker": ticker.upper()})
            return ToolResult(ok=True, data=data)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})
