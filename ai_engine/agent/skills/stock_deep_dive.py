"""
StockDeepDiveSkill — comprehensive single-stock analysis workflow.

Steps:
  1. get_stock_quote       — current price and daily performance
  2. get_platform_reports  — FlowDeck AI recommendation + all report summaries
  3. get_news              — recent company news (last 7 days)
  4. get_indicators        — technical indicators (RSI, MACD, Bollinger)
  5. get_fundamentals      — key valuation metrics

Synthesizes all results into a structured deep-dive report.
"""

from __future__ import annotations

from typing import Any

from ai_engine.agent.skill import BaseSkill, SkillResult, SkillSpec, SkillStep
from ai_engine.agent.tool import ExecutionContext


_SPEC = SkillSpec(
    name="stock_deep_dive",
    version="1.0",
    description=(
        "Run a comprehensive multi-step analysis of a single stock: "
        "current quote, AI platform reports, recent news, technical indicators, "
        "and fundamental metrics — all synthesized into one structured report."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA",
            }
        },
        "required": ["ticker"],
    },
    tags=["analysis", "stock", "comprehensive"],
    uses_tools=[
        "get_stock_quote",
        "get_platform_reports",
        "get_news",
        "get_indicators",
        "get_fundamentals",
    ],
)

_INTENT_PATTERNS = [
    "deep dive",
    "deep-dive",
    "full analysis",
    "comprehensive analysis",
    "complete analysis",
    "full report",
    "everything about",
    "tell me everything",
    "deep analysis",
]


class StockDeepDiveSkill(BaseSkill):
    spec = _SPEC
    intent_patterns = _INTENT_PATTERNS

    def run(
        self,
        ctx: ExecutionContext,
        tool_executor: Any,
        *,
        ticker: str,
        **_,
    ) -> SkillResult:
        ticker = ticker.strip().upper()
        steps: list[SkillStep] = []
        n = [0]  # mutable step counter for call_tool

        def call(tool_name: str, **kwargs):
            return self.call_tool(tool_executor, ctx, steps, n, tool_name, **kwargs)

        quote_result       = call("get_stock_quote", symbol=ticker)
        reports_result     = call("get_platform_reports", ticker=ticker)
        news_result        = call("get_news", ticker=ticker)
        indicators_result  = call("get_indicators", ticker=ticker)
        fundamentals_result = call("get_fundamentals", ticker=ticker)

        sections = [f"# 📊 Deep Dive: {ticker}", ""]
        if quote_result.ok:
            sections += ["## 💰 Current Quote", quote_result.to_str(), ""]
        if reports_result.ok:
            sections += ["## 🤖 FlowDeck AI Analysis", reports_result.to_str(), ""]
        if fundamentals_result.ok:
            sections += ["## 📈 Fundamentals", fundamentals_result.to_str(), ""]
        if indicators_result.ok:
            sections += ["## 📉 Technical Indicators", indicators_result.to_str(), ""]
        if news_result.ok:
            sections += ["## 📰 Recent News", news_result.to_str(), ""]

        all_results = [quote_result, reports_result, news_result, indicators_result, fundamentals_result]
        failed = [r for r in all_results if not r.ok]
        if len(failed) == len(all_results):
            return SkillResult(
                ok=False,
                error={"code": "ALL_STEPS_FAILED", "message": f"All data fetches failed for {ticker}."},
                steps=steps,
            )

        return SkillResult(
            ok=True,
            data="\n".join(sections),
            steps=steps,
            metrics={"tool_calls": len(steps), "failed_steps": len(failed)},
        )

# Made with Bob
