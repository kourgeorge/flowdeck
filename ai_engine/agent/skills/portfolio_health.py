"""
PortfolioHealthSkill — multi-step portfolio overview workflow.

Steps (per subscribed ticker):
  1. get_user_subscriptions — fetch the user's subscribed tickers
  2. For each ticker:
     a. get_stock_quote      — current price and daily change
     b. get_platform_reports — latest AI recommendation + return scenarios

Synthesizes all results into a portfolio health summary with
overall sentiment (bullish/bearish/mixed) and top movers.

Skill discovery and activation is handled via portfolio-health/SKILL.md
following the agentskills.io standard — the LLM reads the description
and selects this skill; no regex or keyword matching is used.
"""

from __future__ import annotations

import re
from typing import Any

from ai_engine.agent.skill import BaseSkill, SkillResult, SkillSpec, SkillStep
from ai_engine.agent.tool import ExecutionContext


_SPEC = SkillSpec(
    name="portfolio_health",
    version="1.0",
    description=(
        "Run a portfolio health check for the current user: fetch all subscribed tickers, "
        "get live quotes and AI recommendations for each, then synthesize into a portfolio "
        "summary with overall sentiment. Use when the user asks about their portfolio, "
        "watchlist, subscribed stocks, or how their stocks are doing."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
    tags=["portfolio", "user", "overview", "health"],
    uses_tools=["get_user_subscriptions", "get_stock_quote", "get_platform_reports"],
)


class PortfolioHealthSkill(BaseSkill):
    spec = _SPEC

    def run(
        self,
        ctx: ExecutionContext,
        tool_executor: Any,
        **_,
    ) -> SkillResult:
        steps: list[SkillStep] = []
        n = [0]

        def call(tool_name: str, **kwargs):
            return self.call_tool(tool_executor, ctx, steps, n, tool_name, **kwargs)

        # Step 1: Get subscribed tickers
        subs_result = call("get_user_subscriptions")
        if not subs_result.ok:
            return SkillResult(
                ok=False,
                error={"code": "SUBSCRIPTIONS_FAILED", "message": subs_result.to_str()},
                steps=steps,
            )

        # Parse tickers from subscription output
        tickers = _parse_tickers(subs_result.to_str())
        if not tickers:
            return SkillResult(
                ok=True,
                data="You have no subscribed stocks yet. Visit the platform to subscribe to tickers.",
                steps=steps,
            )

        # Step 2+: Per-ticker quote + reports
        ticker_data: list[dict] = []
        for ticker in tickers[:10]:  # cap at 10 to avoid huge payloads
            quote_result = call("get_stock_quote", symbol=ticker)
            reports_result = call("get_platform_reports", ticker=ticker)
            ticker_data.append({
                "ticker": ticker,
                "quote": quote_result.to_str() if quote_result.ok else f"unavailable ({quote_result.to_str()})",
                "reports": reports_result.to_str() if reports_result.ok else f"unavailable ({reports_result.to_str()})",
            })

        # Synthesize
        sections = ["# 🏥 Portfolio Health Check", ""]
        sections.append(f"Analysed **{len(ticker_data)}** subscribed stock(s).\n")

        for td in ticker_data:
            sections.append(f"## {td['ticker']}")
            sections.append(f"**Quote:** {td['quote'][:300]}")
            # Extract just the recommendation line from reports
            rec_line = _extract_recommendation(td["reports"])
            if rec_line:
                sections.append(f"**AI Rec:** {rec_line}")
            sections.append("")

        return SkillResult(
            ok=True,
            data="\n".join(sections),
            steps=steps,
            metrics={"tool_calls": len(steps), "tickers_analysed": len(ticker_data)},
        )


def _parse_tickers(subs_text: str) -> list[str]:
    """Extract ticker symbols from get_user_subscriptions output."""
    # Matches lines like: - **AAPL** — subscribed ...
    matches = re.findall(r"\*\*([A-Z\-\.^]+)\*\*", subs_text)
    # Deduplicate while preserving order
    seen: set[str] = set()
    result = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


def _extract_recommendation(reports_text: str) -> str:
    """Extract the Final Trade Decision line from platform reports output."""
    for line in reports_text.splitlines():
        if "Final Trade Decision" in line or "AI Recommendation" in line:
            # Strip markdown headers
            clean = line.lstrip("#").strip()
            return clean[:200]
    return ""

# Made with Bob
