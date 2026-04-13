"""Date span helpers for stocks discovery (aligned with digest daily/weekly slots)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal, Optional, Tuple

SpanType = Literal["daily", "weekly", "custom"]


def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def resolve_span(
    digest_date: str,
    span_type: SpanType,
    start_date: Optional[str],
    end_date: Optional[str],
) -> tuple[SpanType, Optional[str], str, Optional[int]]:
    """Return (span_type, start_date, end_date, span_trading_days)."""
    end_dt = parse_date(digest_date)
    if span_type == "weekly":
        start_dt = end_dt - timedelta(days=7)
        start_date = start_dt.strftime("%Y-%m-%d")
        end_date = digest_date
        span_trading_days: Optional[int] = 7
    elif span_type == "custom":
        if not start_date or not end_date:
            span_type = "daily"
            start_date = None
            end_date = digest_date
            span_trading_days = None
        else:
            end_date = end_date or digest_date
            try:
                sd = parse_date(start_date)
                ed = parse_date(end_date)
                span_trading_days = max(1, (ed - sd).days)
            except ValueError:
                span_trading_days = None
    else:
        start_date = None
        end_date = digest_date
        span_trading_days = None

    return span_type, start_date, end_date, span_trading_days


def digest_lookback_days(span_trading_days: Optional[int]) -> int:
    if span_trading_days is not None and span_trading_days > 0:
        return min(span_trading_days + 2, 31)
    return 2
