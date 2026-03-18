"""
User portfolio source: user profile and subscription data (read-only).
Uses backend services for account and investor-profile context.
"""

from __future__ import annotations

from typing import Any


class UserPortfolioSource:
    """User profile and portfolio data source."""

    def get_user_context(self, user_id: int, db: Any) -> str:
        """Get user profile as a formatted string for AI context."""
        from services.user_profile_service import build_user_context_snapshot

        return build_user_context_snapshot(user_id, db)
