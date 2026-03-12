"""Market movers tool — daily top gainers and losers (US market) from the data API."""

from __future__ import annotations

import json
from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult, ToolSpec

_SPEC = ToolSpec(
    name="get_daily_market_movers",
    version="1.0",
    description=(
        "Get today's top gainers and top losers in the US market. "
        "Returns two lists: biggest percentage gainers and biggest percentage losers. "
        "Use when the user asks about top gainers, top losers, best/worst performers today, "
        "or daily market movers. Optional 'count' (default 8) limits how many per list (1–100)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "count": {
                "type": "integer",
                "description": "Number of gainers and losers to return (each). Default 8, max 100.",
                "default": 8,
            },
        },
        "required": [],
    },
    tags=["market", "gainers", "losers", "screener"],
)


class MarketMoversTool(BaseTool):
    spec = _SPEC

    def execute(self, ctx: ExecutionContext, *, count: int = 8, **_) -> ToolResult:
        try:
            from ai_engine.tradingagents.dataflows.info_service_client import (
                get_market_movers,
                is_configured,
            )
            if not is_configured():
                return ToolResult(
                    ok=False,
                    error={"code": "CONFIG", "message": "Info service URL not configured (INFO_SERVICE_URL)."},
                )
            count = max(1, min(100, count))
            data = get_market_movers(count=count)
            return ToolResult(ok=True, data=json.dumps(data, default=str))
        except ValueError as e:
            return ToolResult(ok=False, error={"code": "CONFIG", "message": str(e)})
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})
