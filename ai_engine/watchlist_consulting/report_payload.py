"""
Build the watchlist report payload for a user: subscriptions + latest report + quote per ticker.

The user, their subscribed tickers, a report service and an info fetcher are all passed
in. They live in the backend (database, ReportService, get_info_fetcher), and ai_engine
may not import backend modules (backend -> ai_engine only). The backend side is
backend/services/watchlist_report_service.py.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ai_engine.report_meta import pick_recommendation_meta


def build_payload(
    user: Optional[Dict[str, Any]],
    tickers: List[str],
    *,
    report_service: Any,
    quote_fetcher: Any,
) -> Dict[str, Any]:
    """
    Build the watchlist report payload for a user.

    Args:
        user: { id, email, name } or None when the user was not found.
        tickers: The user's subscribed tickers, ordered by ticker.
        report_service: Has get_latest_execution_for_ticker(ticker) and
                        get_reports_with_scores(execution_id, execution_type=...).
        quote_fetcher: Has get_quote(ticker) and optionally get_company_info(ticker).

    Returns:
        Dict with:
          - user: { id, email, name }
          - tickers: list of ticker strings
          - entries: list of per-ticker dicts (ticker, name, report_date, recommendation, confidence,
                     key_takeaways, score, score_label, expected_return_pct, bear_case_return_pct, bull_case_return_pct,
                     bull_viewpoint, bear_viewpoint, quote: { current_price, daily_change_percent }, report_scores)
    """
    if not user:
        return {"user": None, "tickers": [], "entries": [], "error": "User not found"}
    if not tickers:
        return {"user": user, "tickers": [], "entries": []}

    rs = report_service
    fetcher = quote_fetcher
    if rs is None or fetcher is None:
        raise ValueError("build_payload needs report_service and quote_fetcher from the backend")

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
            "neutral_viewpoint": None,
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
                scores_raw = rs.get_reports_with_scores(ar_id, execution_type="ticker")
                if scores_raw:
                    for k, v in scores_raw.items():
                        if v.get("score") is not None or v.get("score_label"):
                            entry["report_scores"][k] = {"score": v.get("score"), "score_label": v.get("score_label")}
                    # The Research Manager's investment_plan is the only report that carries
                    # the call, confidence and views since the Research/Risk merge; reading
                    # final_trade_decision/trader first left them empty or showed the Trader's call.
                    _rec_key, rec_meta = pick_recommendation_meta(scores_raw)
                    if rec_meta:
                        entry["recommendation"] = rec_meta.get("recommendation")
                        entry["confidence"] = rec_meta.get("confidence")

                    # Key takeaways from first report that has them
                    for v in scores_raw.values():
                        kt = v.get("key_takeaways")
                        if kt:
                            entry["key_takeaways"] = kt
                            break

                    # Score from the report that made the call, else the first one with a score
                    if rec_meta.get("score") is not None:
                        entry["score"] = rec_meta.get("score")
                        entry["score_label"] = rec_meta.get("score_label")
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

                    for view in ("bull_viewpoint", "bear_viewpoint", "neutral_viewpoint"):
                        if rec_meta.get(view) is not None:
                            entry[view] = rec_meta[view]
        except Exception as e:
            entry["report_error"] = str(e)

        entries.append(entry)

    return {"user": user, "tickers": tickers, "entries": entries}
