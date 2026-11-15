"""
Shared period resolution and % return maths for the chat skills.

compare_stocks, portfolio_performance and chart_creation each used to carry
their own copy of these. The copies drifted: only compare_stocks got the
previous-close fix (d860a9f), so portfolio_performance's "last month" return
silently dropped the first session's move, and chart_creation had no week
cases so "1w" fell through to a full year. Keeping one copy here stops that.
"""

from __future__ import annotations

import datetime
import json
from typing import Optional

from ai_engine.price_series import parse_daily_closes


# A period return is measured from the last close *before* the start date, so
# the fetch has to reach back far enough to find one even across long market
# holidays (e.g. Christmas + New Year, or multi-day exchange closures).
PREVIOUS_CLOSE_LOOKBACK_DAYS = 14


def fetch_start_date(start_date: str) -> str:
    """Start date to request from the price tool so a previous close is included."""
    start = datetime.date.fromisoformat(start_date)
    return (start - datetime.timedelta(days=PREVIOUS_CLOSE_LOOKBACK_DAYS)).isoformat()


def _last_week(today: datetime.date) -> tuple[str, str, str]:
    last_monday = today - datetime.timedelta(days=today.weekday() + 7)
    last_friday = last_monday + datetime.timedelta(days=4)
    return last_monday.isoformat(), last_friday.isoformat(), "Last Week"


def _last_month(today: datetime.date) -> tuple[str, str, str]:
    last_month_end = today.replace(day=1) - datetime.timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    return last_month_start.isoformat(), last_month_end.isoformat(), "Last Month"


def _past_year(today: datetime.date) -> tuple[str, str, str]:
    start = today - datetime.timedelta(days=365)
    return start.isoformat(), today.isoformat(), "Past 1 Year"


# Each skill has its own sensible fallback for an empty or unknown period.
_DEFAULTS = {
    "week": _last_week,
    "month": _last_month,
    "1y": _past_year,
}


def resolve_period(
    period: Optional[str],
    default: str = "month",
    today: Optional[datetime.date] = None,
) -> tuple[str, str, str]:
    """Resolve a period string to (start_date, end_date, label).

    `default` ("week", "month" or "1y") is used when the period is empty or
    not recognised. `today` is only there so tests can pin the date.
    """
    today = today or datetime.date.today()
    p = (period or "").lower().strip()

    if ":" in p:
        parts = p.split(":", 1)
        try:
            start = datetime.date.fromisoformat(parts[0].strip())
            end = datetime.date.fromisoformat(parts[1].strip())
            return start.isoformat(), end.isoformat(), f"{start} to {end}"
        except ValueError:
            pass

    if p in ("week", "last week", "1w"):
        return _last_week(today)

    if p in ("this week", "current week"):
        this_monday = today - datetime.timedelta(days=today.weekday())
        return this_monday.isoformat(), today.isoformat(), "This Week"

    if p in ("month", "last month", "1m"):
        return _last_month(today)

    if p in ("this month", "current month"):
        start = today.replace(day=1)
        return start.isoformat(), today.isoformat(), "This Month"

    if p in ("ytd", "year to date"):
        start = today.replace(month=1, day=1)
        return start.isoformat(), today.isoformat(), "Year-to-Date"

    if p in ("1y", "1 year", "one year", "past year", "last year"):
        return _past_year(today)

    if p in ("3m", "3 months", "three months"):
        start = today - datetime.timedelta(days=90)
        return start.isoformat(), today.isoformat(), "Past 3 Months"

    if p in ("6m", "6 months", "six months"):
        start = today - datetime.timedelta(days=180)
        return start.isoformat(), today.isoformat(), "Past 6 Months"

    return _DEFAULTS[default](today)


def compute_period_returns(
    prices_json: str,
    tickers: Optional[list[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict]:
    """Parse multi-ticker price JSON and compute % returns, best first.

    Same as compute_period_returns_with_skipped, without the skipped list.
    """
    return compute_period_returns_with_skipped(prices_json, tickers, start_date, end_date)[0]


def compute_period_returns_with_skipped(
    prices_json: str,
    tickers: Optional[list[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> tuple[list[dict], list[str]]:
    """Compute % returns, best first, and list the tickers that were not measured.

    Same as compute_period_returns_with_reasons, with just the skipped names.
    """
    results, reasons = compute_period_returns_with_reasons(prices_json, tickers, start_date, end_date)
    return results, list(reasons)


# Why a ticker got no return. Shown to the user next to the ticker name.
NO_DATA = "no data at all"
NO_PRICE_BEFORE_START = "no price before the start"
NO_PRICE_IN_PERIOD = "no price in the period"
NOT_ENOUGH_PRICES = "not enough prices"


def compute_period_returns_with_reasons(
    prices_json: str,
    tickers: Optional[list[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> tuple[list[dict], dict[str, str]]:
    """Compute % returns, best first, plus {ticker: reason} for those not measured.

    With a start_date, the return runs from the last close before that date
    to the last close on or before end_date, so the first session's move is
    counted. A ticker with no close before start_date (e.g. a recent IPO) is
    skipped rather than measured from a later day. The skipped tickers come
    back with the reason, so callers can name them instead of hiding them;
    no return is ever made up for them. `tickers=None` means every ticker in
    the data. The reasons dict keeps the order of `tickers`.
    """
    try:
        raw = json.loads(prices_json)
    except Exception:
        return [], {t: NO_DATA for t in (tickers or [])}

    data = raw.get("data", {}) or {}
    if tickers is None:
        tickers = list(data.keys())
    results = []
    reasons: dict[str, str] = {}

    for ticker in tickers:
        csv_str = data.get(ticker) or data.get(ticker.upper())
        if not csv_str:
            reasons[ticker] = NO_DATA
            continue
        try:
            rows = parse_daily_closes(csv_str)
            if start_date:
                previous = [r for r in rows if r["Date"] < start_date]
                in_period = [r for r in rows if r["Date"] >= start_date and (not end_date or r["Date"] <= end_date)]
                if not previous and not in_period:
                    reasons[ticker] = NO_DATA
                    continue
                if not previous:
                    reasons[ticker] = NO_PRICE_BEFORE_START
                    continue
                if not in_period:
                    reasons[ticker] = NO_PRICE_IN_PERIOD
                    continue
                rows = [previous[-1]] + in_period
            if len(rows) < 2:
                reasons[ticker] = NOT_ENOUGH_PRICES
                continue
            first_close = float(rows[0]["Close"])
            last_close = float(rows[-1]["Close"])
            if first_close == 0:
                reasons[ticker] = NOT_ENOUGH_PRICES
                continue
            pct = (last_close - first_close) / first_close * 100
            results.append({
                "ticker": ticker,
                "start_price": round(first_close, 2),
                "end_price": round(last_close, 2),
                "return_pct": round(pct, 2),
                "start_date": rows[0].get("Date", ""),
                "end_date": rows[-1].get("Date", ""),
            })
        except Exception:
            reasons[ticker] = NO_DATA
            continue

    results.sort(key=lambda x: x["return_pct"], reverse=True)
    return results, reasons


def format_skipped_line(reasons: dict[str, str]) -> str:
    """One line naming each unmeasured ticker and why, or "" if none."""
    if not reasons:
        return ""
    named = ", ".join(f"{t} ({why})" for t, why in reasons.items())
    return f"No full price history for this period: {named}"
