"""
User-context tools — require user_id and db session injected at construction time.

These tools are NOT in ALL_TOOLS (which is for always-available tools).
Instead, ChatService creates instances per-request and registers them dynamically.

Usage:
    tools = make_user_context_tools(user_id=42, db=session)
    for t in tools:
        tool_registry.register(t)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult, ToolSpec

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# UserContextTool
# ---------------------------------------------------------------------------

_USER_CONTEXT_SPEC = ToolSpec(
    name="get_user_context",
    version="1.0",
    description=(
        "Get the current user's profile information: their email, display name, "
        "token balance, account type, and member-since date. "
        "Use when the user asks about their account, profile, token balance, or who they are."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
    tags=["user", "profile"],
)


class UserContextTool(BaseTool):
    """Fetches the current user's profile. Requires user_id + db at construction."""

    spec = _USER_CONTEXT_SPEC

    def __init__(self, user_id: int, db: Any) -> None:
        self._user_id = user_id
        self._db = db

    def execute(self, ctx: ExecutionContext, **_) -> ToolResult:
        try:
            result = _get_user_context(self._user_id, self._db)
            return ToolResult(ok=True, data=result)
        except Exception as exc:
            logger.exception("UserContextTool error: %s", exc)
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


def _get_user_context(user_id: int, db: Any) -> str:
    import sys
    import os
    _backend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")
    if _backend_dir not in sys.path:
        sys.path.insert(0, os.path.abspath(_backend_dir))

    from models.db_models import User  # type: ignore[import]
    from services import token_service  # type: ignore[import]

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return "User not found."
    balance = token_service.get_balance(user_id, db)
    member_since = user.created_at.strftime("%B %d, %Y") if user.created_at else "Unknown"
    name_str = f"Name: {user.name}" if user.name else "Name: (not set)"
    lines = [
        "# Your FlowDeck Profile",
        f"Email: {user.email}",
        name_str,
        f"Token Balance: {balance:,} tokens",
        f"Member Since: {member_since}",
        f"Account Type: {'Admin' if user.is_admin else 'Standard'}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# UserSubscriptionsTool
# ---------------------------------------------------------------------------

_USER_SUBSCRIPTIONS_SPEC = ToolSpec(
    name="get_user_subscriptions",
    version="1.0",
    description=(
        "Get the list of stock tickers the current user is subscribed to on FlowDeck, "
        "including subscription dates and email-update preferences. "
        "Use when the user asks about their watchlist, subscriptions, followed stocks, or portfolio tickers."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
    tags=["user", "subscriptions", "watchlist"],
)


class UserSubscriptionsTool(BaseTool):
    """Lists the user's subscribed tickers. Requires user_id + db at construction."""

    spec = _USER_SUBSCRIPTIONS_SPEC

    def __init__(self, user_id: int, db: Any) -> None:
        self._user_id = user_id
        self._db = db

    def execute(self, ctx: ExecutionContext, **_) -> ToolResult:
        try:
            result = _get_user_subscriptions(self._user_id, self._db)
            return ToolResult(ok=True, data=result)
        except Exception as exc:
            logger.exception("UserSubscriptionsTool error: %s", exc)
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


def _get_user_subscriptions(user_id: int, db: Any) -> str:
    import sys
    import os
    _backend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")
    if _backend_dir not in sys.path:
        sys.path.insert(0, os.path.abspath(_backend_dir))

    from models.db_models import Subscription  # type: ignore[import]

    subs = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
        .all()
    )
    if not subs:
        return "You have no subscribed stocks yet. Visit the platform to subscribe to tickers."
    lines = ["# Your Subscribed Stocks", ""]
    for s in subs:
        date_str = s.created_at.strftime("%Y-%m-%d") if s.created_at else "Unknown"
        email_flag = " (email updates on)" if s.email_updates else " (email updates off)"
        lines.append(f"- **{s.ticker}** — subscribed {date_str}{email_flag}")
    lines.append("")
    lines.append(f"Total: {len(subs)} subscribed stock(s)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PortfolioOverviewTool
# ---------------------------------------------------------------------------

_PORTFOLIO_OVERVIEW_SPEC = ToolSpec(
    name="get_portfolio_overview",
    version="1.0",
    description=(
        "Get a full portfolio overview for the current user: live stock quotes AND the latest "
        "FlowDeck AI recommendation (BUY/SELL/HOLD with confidence and return scenarios) "
        "for every stock they are subscribed to. "
        "Use when the user asks about their portfolio, how their stocks are doing, "
        "portfolio performance, or wants a summary of all their subscribed stocks."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
    tags=["user", "portfolio", "overview"],
)


class PortfolioOverviewTool(BaseTool):
    """Full portfolio overview (quotes + AI recs). Requires user_id + db at construction."""

    spec = _PORTFOLIO_OVERVIEW_SPEC

    def __init__(self, user_id: int, db: Any) -> None:
        self._user_id = user_id
        self._db = db

    def execute(self, ctx: ExecutionContext, **_) -> ToolResult:
        try:
            result = _get_portfolio_overview(self._user_id, self._db)
            return ToolResult(ok=True, data=result)
        except Exception as exc:
            logger.exception("PortfolioOverviewTool error: %s", exc)
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


def _get_portfolio_overview(user_id: int, db: Any) -> str:
    import sys
    import os
    _backend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")
    if _backend_dir not in sys.path:
        sys.path.insert(0, os.path.abspath(_backend_dir))

    from models.db_models import Subscription  # type: ignore[import]
    from services.report_service import ReportService  # type: ignore[import]
    from ai_engine.tradingagents.agents.utils.core_stock_tools import get_ticker_quote

    subs = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.ticker)
        .all()
    )
    if not subs:
        return "You have no subscribed stocks. Subscribe to tickers on the platform to build your portfolio."

    svc = ReportService()
    lines = ["# Your Portfolio Overview", ""]

    for s in subs:
        ticker = s.ticker
        lines.append(f"## {ticker}")

        # Live quote
        try:
            quote = get_ticker_quote.invoke({"symbol": ticker})
            lines.append(f"**Quote:** {quote}")
        except Exception as qe:
            lines.append(f"**Quote:** unavailable ({qe})")

        # Latest AI recommendation
        try:
            latest = svc.get_latest_analysis_run(ticker)
            if latest:
                ar_id, latest_date = latest
                reports = svc.get_reports_with_scores(ticker, ar_id)
                tip = reports.get("trader_investment_plan") or {}
                ftd = reports.get("final_trade_decision") or {}
                rec = tip.get("recommendation") or ftd.get("recommendation")
                conf = tip.get("confidence") or ftd.get("confidence")
                inv = reports.get("investment_plan") or {}
                exp = inv.get("expected_return_pct")
                bear_ret = inv.get("bear_case_return_pct")
                bull_ret = inv.get("bull_case_return_pct")

                if rec:
                    conf_str = f" ({conf*100:.0f}% confidence)" if conf else ""
                    lines.append(f"**AI Recommendation:** {rec}{conf_str} (as of {latest_date})")
                if any(v is not None for v in [exp, bear_ret, bull_ret]):
                    parts = []
                    if exp is not None:
                        parts.append(f"Expected: {exp:+.1f}%")
                    if bear_ret is not None:
                        parts.append(f"Bear: {bear_ret:+.1f}%")
                    if bull_ret is not None:
                        parts.append(f"Bull: {bull_ret:+.1f}%")
                    lines.append("**Return Scenarios:** " + " | ".join(parts))
            else:
                lines.append("**AI Recommendation:** No report available yet")
        except Exception as re_:
            lines.append(f"**AI Recommendation:** unavailable ({re_})")

        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

def make_user_context_tools(user_id: int, db: Any) -> list[BaseTool]:
    """
    Create all user-context tool instances bound to a specific user_id and db session.
    Call this per-request and register the returned tools into the ToolRegistry.
    """
    return [
        UserContextTool(user_id=user_id, db=db),
        UserSubscriptionsTool(user_id=user_id, db=db),
        PortfolioOverviewTool(user_id=user_id, db=db),
    ]

# Made with Bob
