"""
User portfolio source: user profile and subscription data (read-only).
Uses User model and token_service from backend.
"""

from __future__ import annotations

from typing import Any


class UserPortfolioSource:
    """User profile and portfolio data source."""

    def get_user_context(self, user_id: int, db: Any) -> str:
        """Get user profile as a formatted string (email, name, balance, member since)."""
        from models.db_models import User
        from services import token_service

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return "User not found."
        balance = token_service.get_balance(user_id, db)
        member_since = (
            user.created_at.strftime("%B %d, %Y") if user.created_at else "Unknown"
        )
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
