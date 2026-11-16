"""Pick which report's metadata carries the recommendation for an analysis run.

Since the Research/Risk merge (9c600ea) only investment_plan (Research Manager) carries
the recommendation, confidence and bull/bear/neutral views, and final_trade_decision is
no longer written. Older runs still have final_trade_decision, so it stays as a fallback,
and trader_investment_plan comes last. Every caller used to keep its own copy of this
order, and some had drifted (watchlist report read the trader first, the portfolio
figures read final_trade_decision first), so the order lives here once.

admin_service._extract_accuracy_inputs deliberately checks the trader first and does
not use this.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple

RECOMMENDATION_SOURCE_ORDER: Tuple[str, ...] = (
    "investment_plan",
    "final_trade_decision",
    "trader_investment_plan",
)


def pick_recommendation_meta(
    reports: Optional[Mapping[str, Any]],
) -> Tuple[Optional[str], Dict[str, Any]]:
    """Return (report_key, metadata) of the first report with a recommendation.

    Returns (None, {}) when no report has one, so callers show nothing rather than
    borrowing a confidence or view from a report that made no call.
    """
    if not isinstance(reports, Mapping):
        return None, {}
    for key in RECOMMENDATION_SOURCE_ORDER:
        meta = reports.get(key)
        if isinstance(meta, Mapping) and meta.get("recommendation"):
            return key, dict(meta)
    return None, {}
