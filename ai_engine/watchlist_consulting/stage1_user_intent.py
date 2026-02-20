"""
Stage 1: User Intent & Preferences Agent.
Input: optional user_profile, watchlist_payload.
Output: UserIntent (investor_style, risk_budget, time_horizon, constraints, report_style).
If profile missing, infer conservatively and set assumptions_stated / inferred_preferences_explanation.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pipeline_schemas import UserIntent


def run_user_intent(
    user_profile: Optional[Dict[str, Any]] = None,
    watchlist_payload: Optional[Dict[str, Any]] = None,
) -> UserIntent:
    """
    Produce UserIntent from optional user_profile and watchlist_payload.
    When profile is missing, infer long-term / medium risk and state assumptions.
    """
    if user_profile and isinstance(user_profile, dict):
        return _from_profile(user_profile)
    return _infer_defaults(watchlist_payload or {})


def _from_profile(profile: Dict[str, Any]) -> UserIntent:
    return UserIntent(
        investor_style=profile.get("investor_style") or profile.get("investorStyle") or "long-term",
        risk_budget=(profile.get("risk_budget") or profile.get("riskBudget") or "med").lower()[:3],
        time_horizon=profile.get("time_horizon") or profile.get("timeHorizon") or "months",
        constraints=profile.get("constraints") or [],
        report_style=profile.get("report_style") or profile.get("reportStyle") or "concise",
        assumptions_stated=False,
        inferred_preferences_explanation=None,
    )


def _infer_defaults(payload: Dict[str, Any]) -> UserIntent:
    # Conservative defaults: long-term, medium risk, concise report
    return UserIntent(
        investor_style="long-term",
        risk_budget="med",
        time_horizon="months",
        constraints=[],
        report_style="concise",
        assumptions_stated=True,
        inferred_preferences_explanation=(
            "No user profile was provided. Assumed: long-term investor, medium risk tolerance, "
            "multi-month horizon, concise report style. You can provide a profile (e.g. via --profile) to personalize."
        ),
    )
