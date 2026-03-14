"""
Build the watchlist report payload for a user: subscriptions + latest report + quote per ticker.
Uses DB (User, Subscription), ReportService, and an info fetcher (quotes, company name).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Import after path setup when used as script; for direct import assume path is set
try:
    from database import SessionLocal
    from models.db_models import User, Subscription
    from services.report_service import ReportService
except ImportError:
    SessionLocal = None  # type: ignore
    User = Subscription = None  # type: ignore
    ReportService = None  # type: ignore


def _get_quote_fetcher():
    """Return the shared info fetcher for quotes (and company info). Lazy to avoid circular imports."""
    from services.info_fetcher import get_info_fetcher
    return get_info_fetcher()


def resolve_user(db, *, user_id: Optional[int] = None, email: Optional[str] = None) -> Optional[Any]:
    """Resolve user by id or email. Returns User or None."""
    if user_id is not None:
        return db.query(User).filter(User.id == user_id).first()
    if email:
        return db.query(User).filter(User.email == email).first()
    return None


def get_subscribed_tickers(db, user_id: int) -> List[str]:
    """Return list of tickers the user is subscribed to, ordered by ticker."""
    rows = (
        db.query(Subscription.ticker)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.ticker)
        .all()
    )
    return [r.ticker for r in rows]


def build_payload(
    user_id: Optional[int] = None,
    email: Optional[str] = None,
    report_service: Optional[ReportService] = None,
    quote_fetcher: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Build the watchlist report payload for a user.

    Args:
        user_id: User ID (use this or email).
        email: User email (use this or user_id).
        report_service: ReportService instance; if None, one is created.
        quote_fetcher: Fetcher with get_quote(ticker) and optionally get_company_info(ticker).
                      If None, uses get_info_fetcher().

    Returns:
        Dict with:
          - user: { id, email, name }
          - tickers: list of ticker strings
          - entries: list of per-ticker dicts (ticker, name, report_date, recommendation, confidence,
                     key_takeaways, score, score_label, expected_return_pct, bear_case_return_pct, bull_case_return_pct,
                     bull_viewpoint, bear_viewpoint, quote: { current_price, daily_change_percent }, report_scores)
    """
    if SessionLocal is None or User is None or Subscription is None or ReportService is None:
        raise RuntimeError("report_payload requires backend on sys.path (database, models, services)")

    db = SessionLocal()
    try:
        user = resolve_user(db, user_id=user_id, email=email)
        if not user:
            return {"user": None, "tickers": [], "entries": [], "error": "User not found"}

        tickers = get_subscribed_tickers(db, user.id)
        if not tickers:
            return {
                "user": {"id": user.id, "email": getattr(user, "email", "") or "", "name": getattr(user, "name") or ""},
                "tickers": [],
                "entries": [],
            }

        rs = report_service or ReportService()
        fetcher = quote_fetcher or _get_quote_fetcher()

        entries: List[Dict[str, Any]] = []
        for ticker in tickers:
            ticker = ticker.upper()
            entry: Dict[str, Any] = {
                "ticker": ticker,
                "name": ticker,
                "report_date": None,
                "recommendation": None,
                "confidence": None,
                "key_takeaways": [],
                "score": None,
                "score_label": None,
                "expected_return_pct": None,
                "bear_case_return_pct": None,
                "bull_case_return_pct": None,
                "bull_viewpoint": None,
                "bear_viewpoint": None,
                "quote": None,
                "report_scores": {},
            }

            # Company name
            try:
                info = fetcher.get_company_info(ticker)
                if info and info.get("name"):
                    entry["name"] = info["name"]
            except Exception:
                pass

            # Quote
            try:
                quote = fetcher.get_quote(ticker)
                if quote and isinstance(quote, dict):
                    entry["quote"] = {
                        "current_price": quote.get("current_price"),
                        "daily_change": quote.get("daily_change"),
                        "daily_change_percent": quote.get("daily_change_percent"),
                    }
            except Exception:
                pass

            # Latest report
            try:
                latest = rs.get_latest_execution_for_ticker(ticker)
                if latest:
                    ar_id, latest_date = latest
                    entry["report_date"] = latest_date
                    scores_raw = rs.get_reports_with_scores(ar_id)
                    if scores_raw:
                        for k, v in scores_raw.items():
                            if v.get("score") is not None or v.get("score_label"):
                                entry["report_scores"][k] = {"score": v.get("score"), "score_label": v.get("score_label")}
                        ftd = scores_raw.get("final_trade_decision") or {}
                        tip = scores_raw.get("trader_investment_plan") or {}
                        if ftd.get("recommendation"):
                            entry["recommendation"] = ftd["recommendation"]
                            entry["confidence"] = ftd.get("confidence")
                        elif tip.get("recommendation"):
                            entry["recommendation"] = tip["recommendation"]
                            entry["confidence"] = tip.get("confidence")

                        # Key takeaways from first report that has them
                        for v in scores_raw.values():
                            kt = v.get("key_takeaways")
                            if kt:
                                entry["key_takeaways"] = kt
                                break

                        # Score from final_trade_decision or first available
                        if ftd.get("score") is not None:
                            entry["score"] = ftd.get("score")
                            entry["score_label"] = ftd.get("score_label")
                        else:
                            for v in scores_raw.values():
                                if v.get("score") is not None:
                                    entry["score"] = v.get("score")
                                    entry["score_label"] = v.get("score_label")
                                    break

                        inv_plan = scores_raw.get("investment_plan") or {}
                        entry["expected_return_pct"] = inv_plan.get("expected_return_pct")
                        entry["bear_case_return_pct"] = inv_plan.get("bear_case_return_pct")
                        entry["bull_case_return_pct"] = inv_plan.get("bull_case_return_pct")

                        if ftd.get("bull_viewpoint") is not None:
                            entry["bull_viewpoint"] = ftd["bull_viewpoint"]
                        if ftd.get("bear_viewpoint") is not None:
                            entry["bear_viewpoint"] = ftd["bear_viewpoint"]
                        if not entry["bull_viewpoint"] and tip.get("bull_viewpoint") is not None:
                            entry["bull_viewpoint"] = tip["bull_viewpoint"]
                        if not entry["bear_viewpoint"] and tip.get("bear_viewpoint") is not None:
                            entry["bear_viewpoint"] = tip["bear_viewpoint"]
            except Exception as e:
                entry["report_error"] = str(e)

            entries.append(entry)

        return {
            "user": {
                "id": user.id,
                "email": getattr(user, "email", "") or "",
                "name": getattr(user, "name") or "",
            },
            "tickers": tickers,
            "entries": entries,
        }
    finally:
        db.close()
