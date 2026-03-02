"""
CompareStocksSkill — side-by-side multi-ticker comparison workflow.

Steps (per ticker):
  1. get_stock_quote    — current price and daily change
  2. get_fundamentals  — P/E, market cap, margins, EPS
  3. get_indicators    — RSI, MACD (technical momentum)

Synthesizes all results into a structured comparison table/summary.
"""

from __future__ import annotations

import re
from typing import Any

from ai_engine.agent.skill import BaseSkill, SkillResult, SkillSpec, SkillStep
from ai_engine.agent.tool import ExecutionContext


_SPEC = SkillSpec(
    name="compare_stocks",
    version="1.0",
    description=(
        "Run a side-by-side comparison of multiple stocks: "
        "fetch live quotes, fundamental metrics, and technical indicators "
        "for each ticker, then synthesize into a structured comparison."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of ticker symbols to compare, e.g. ['AAPL', 'MSFT', 'GOOGL']",
                "minItems": 2,
                "maxItems": 6,
            }
        },
        "required": ["tickers"],
    },
    tags=["comparison", "multi-stock", "analysis"],
    uses_tools=["get_stock_quote", "get_fundamentals", "get_indicators"],
)

_INTENT_PATTERNS = [
    "compare",
    "vs ",
    " vs ",
    "versus",
    "side by side",
    "side-by-side",
    "which is better",
    "which stock",
    "compare stocks",
    "compare these",
]


class CompareStocksSkill(BaseSkill):
    spec = _SPEC
    intent_patterns = _INTENT_PATTERNS

    def run(
        self,
        ctx: ExecutionContext,
        tool_executor: Any,
        *,
        tickers: list[str],
        **_,
    ) -> SkillResult:
        if not tickers or len(tickers) < 2:
            return SkillResult(
                ok=False,
                error={"code": "INVALID_INPUT", "message": "At least 2 tickers are required for comparison."},
            )

        tickers = [t.strip().upper() for t in tickers[:6]]
        steps: list[SkillStep] = []
        n = [0]

        def call(tool_name: str, **kwargs):
            return self.call_tool(tool_executor, ctx, steps, n, tool_name, **kwargs)

        # Per-ticker data collection
        ticker_data: list[dict] = []
        for ticker in tickers:
            q = call("get_stock_quote", symbol=ticker)
            f = call("get_fundamentals", ticker=ticker)
            i = call("get_indicators", ticker=ticker)
            ticker_data.append({
                "ticker": ticker,
                "quote": q.to_str() if q.ok else "N/A",
                "fundamentals": f.to_str() if f.ok else "N/A",
                "indicators": i.to_str() if i.ok else "N/A",
            })

        # Synthesize comparison
        tickers_str = " vs ".join(tickers)
        sections = [f"# ⚖️ Stock Comparison: {tickers_str}", ""]

        # Quote section
        sections.append("## 💰 Current Quotes")
        for td in ticker_data:
            sections.append(f"### {td['ticker']}")
            sections.append(td["quote"][:400])
            sections.append("")

        # Fundamentals section
        sections.append("## 📊 Fundamentals")
        for td in ticker_data:
            sections.append(f"### {td['ticker']}")
            sections.append(td["fundamentals"][:600])
            sections.append("")

        # Technical section
        sections.append("## 📉 Technical Indicators")
        for td in ticker_data:
            sections.append(f"### {td['ticker']}")
            sections.append(td["indicators"][:400])
            sections.append("")

        return SkillResult(
            ok=True,
            data="\n".join(sections),
            steps=steps,
            metrics={"tool_calls": len(steps), "tickers_compared": len(tickers)},
        )

    def matches(self, message: str) -> bool:
        """
        Custom intent matcher: only trigger if 2+ ticker-like tokens appear
        alongside a comparison keyword.
        """
        has_keyword = any(p in message for p in self.intent_patterns)
        if not has_keyword:
            return False
        # Count uppercase ticker-like tokens (2-5 chars)
        tickers_found = re.findall(r"\b[A-Z]{2,5}\b", message.upper())
        return len(set(tickers_found)) >= 2

# Made with Bob
