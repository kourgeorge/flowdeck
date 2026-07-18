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
        "Get the current user's account profile, structured investor preferences, "
        "and saved AI memory. Includes email, display name, token balance, "
        "member-since date, investor/trader profile fields, and editable memory notes. "
        "Use when the user asks about their account, profile, preferences, token balance, or who they are."
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

    try:
        from data_layer import get_data_gateway
        return get_data_gateway().get_user_context(user_id, db)
    except (ImportError, RuntimeError):
        from services.user_profile_service import build_user_context_snapshot  # type: ignore[import]

        return build_user_context_snapshot(user_id, db)


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
    from ai_engine.tradingagents.agents.utils.core_stock_tools import get_ticker_quote

    try:
        from data_layer import get_data_gateway
        report_svc = get_data_gateway()
    except (ImportError, RuntimeError):
        from services.report_service import ReportService  # type: ignore[import]
        report_svc = ReportService()

    subs = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.ticker)
        .all()
    )
    if not subs:
        return "You have no subscribed stocks. Subscribe to tickers on the platform to build your portfolio."
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
            latest = report_svc.get_latest_execution_for_ticker(ticker)
            if latest:
                ar_id, latest_date = latest
                reports = report_svc.get_reports_with_scores(ar_id)
                inv = reports.get("investment_plan") or {}
                tip = reports.get("trader_investment_plan") or {}
                ftd = reports.get("final_trade_decision") or {}
                # investment_plan (Research Manager) is the authoritative recommendation source;
                # final_trade_decision / trader plan are historical fallbacks.
                rec = inv.get("recommendation") or ftd.get("recommendation") or tip.get("recommendation")
                conf = inv.get("confidence") or ftd.get("confidence") or tip.get("confidence")
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
# UpdateUserMemoryTool
# ---------------------------------------------------------------------------

_UPDATE_USER_MEMORY_SPEC = ToolSpec(
    name="update_user_memory",
    version="1.0",
    description=(
        "Save or append information to the user's persistent AI memory. "
        "This memory persists across all future conversations and helps personalize responses. "
        "Use when the user explicitly asks you to remember something (e.g., 'remember that I...', "
        "'save this preference', 'keep in mind that...') or when they share important context "
        "about their investment style, preferences, constraints, or goals that should be remembered long-term. "
        "The memory is appended to existing notes, so you can add new information without overwriting."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "memory_note": {
                "type": "string",
                "description": "The information to save to the user's memory. Be concise but specific.",
            }
        },
        "required": ["memory_note"],
    },
    tags=["user", "memory", "preferences"],
)


class UpdateUserMemoryTool(BaseTool):
    """Saves information to the user's persistent AI memory. Requires user_id + db at construction."""

    spec = _UPDATE_USER_MEMORY_SPEC

    def __init__(self, user_id: int, db: Any) -> None:
        self._user_id = user_id
        self._db = db

    def execute(self, ctx: ExecutionContext, **kwargs) -> ToolResult:
        try:
            memory_note = kwargs.get("memory_note", "")
            if not memory_note:
                return ToolResult(ok=False, error={"code": "MISSING_PARAM", "message": "memory_note is required"})
            result = _update_user_memory(self._user_id, self._db, memory_note)
            return ToolResult(ok=True, data=result)
        except Exception as exc:
            logger.exception("UpdateUserMemoryTool error: %s", exc)
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


def _update_user_memory(user_id: int, db: Any, memory_note: str) -> str:
    import sys
    import os
    _backend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")
    if _backend_dir not in sys.path:
        sys.path.insert(0, os.path.abspath(_backend_dir))

    from models.db_models import UserProfile  # type: ignore[import]
    from datetime import datetime

    # Get or create profile
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is None:
        profile = UserProfile(user_id=user_id)
        db.add(profile)
        db.flush()

    # Clean the memory note
    memory_note = memory_note.strip()
    if not memory_note:
        return "No memory note provided."

    # Append to existing memory with timestamp
    timestamp = datetime.utcnow().strftime("%Y-%m-%d")
    new_entry = f"[{timestamp}] {memory_note}"

    if profile.ai_memory_text:
        # Append with newline separator
        profile.ai_memory_text = f"{profile.ai_memory_text}\n{new_entry}"
    else:
        profile.ai_memory_text = new_entry

    # Truncate if too long (keep last 4000 chars)
    if len(profile.ai_memory_text) > 4000:
        profile.ai_memory_text = profile.ai_memory_text[-4000:]

    db.commit()
    db.refresh(profile)

    return f"✓ Saved to your AI memory: {memory_note}\n\nThis will be remembered in all future conversations."


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
        UpdateUserMemoryTool(user_id=user_id, db=db),
    ]

