#!/usr/bin/env python3
"""
Extract deterministic events for a ticker over a recent date window.

Examples:
  python backend/scripts/extract_recent_events.py
  python backend/scripts/extract_recent_events.py --ticker MSFT --days 30
  python backend/scripts/extract_recent_events.py --ticker MSFT --start-date 2026-02-20 --end-date 2026-03-20
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent

for path in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)
os.chdir(BACKEND_ROOT)

load_dotenv(BACKEND_ROOT / ".env")
load_dotenv(REPO_ROOT / ".env")

from backend.processing import get_ticker_event_summary
from data_layer import get_data_gateway, init_data_gateway
from data_layer.market import MarketDataLayer
from database import init_db
from services.edgar_service import get_edgar_service
from services.report_service import ReportService


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract deterministic events for a ticker over a recent date window.",
    )
    parser.add_argument("--ticker", default="MSFT", help="Ticker symbol. Default: MSFT.")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Trailing window length in days when explicit dates are not supplied. Default: 30.",
    )
    parser.add_argument("--start-date", help="Window start date in YYYY-MM-DD.")
    parser.add_argument("--end-date", help="Window end date in YYYY-MM-DD. Default: today UTC.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full event summary as JSON instead of a formatted report.",
    )
    return parser.parse_args()


def _parse_iso_date(value: str, *, flag_name: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise SystemExit(f"Invalid {flag_name}: {value!r}. Expected YYYY-MM-DD.") from exc


def _resolve_window(args: argparse.Namespace) -> tuple[str, str]:
    if args.end_date:
        end_dt = _parse_iso_date(args.end_date, flag_name="--end-date")
    else:
        end_dt = datetime.now(timezone.utc).replace(tzinfo=None)

    if args.start_date:
        start_dt = _parse_iso_date(args.start_date, flag_name="--start-date")
    else:
        start_dt = end_dt - timedelta(days=max(args.days - 1, 0))

    if start_dt > end_dt:
        raise SystemExit("--start-date must be earlier than or equal to --end-date.")

    return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")


def _ensure_gateway() -> Any:
    try:
        return get_data_gateway()
    except Exception:
        init_data_gateway(
            market=MarketDataLayer(),
            reports=ReportService(),
            edgar=get_edgar_service(),
        )
        return get_data_gateway()


def _print_summary(ticker: str, start_date: str, end_date: str, summary: Any) -> None:
    print(f"Deterministic events for {ticker}")
    print(f"Window: {start_date} to {end_date}")
    print(f"Event score: {summary.event_score}")
    print(f"Event count: {summary.event_count}")
    print(
        "Dominant events: "
        + (", ".join(summary.dominant_events) if summary.dominant_events else "none")
    )
    print()

    if not summary.events:
        print("No events detected in this window.")
        return

    for index, event in enumerate(summary.events, start=1):
        print(f"{index}. {event.event_type} ({event.domain})")
        print(f"   strength: {event.strength}")
        print(f"   detected_on: {event.detected_on or '-'}")
        print(f"   window: {event.window_start or '-'} to {event.window_end or '-'}")
        if event.metric_value is not None:
            print(f"   metric_value: {event.metric_value}")
        if event.threshold_value is not None:
            print(f"   threshold_value: {event.threshold_value}")
        if event.metadata:
            print(f"   metadata: {json.dumps(event.metadata, sort_keys=True)}")
        print(f"   description: {event.description}")
        print()


def main() -> int:
    args = _parse_args()
    ticker = (args.ticker or "").strip().upper()
    if not ticker:
        raise SystemExit("--ticker must not be empty.")

    start_date, end_date = _resolve_window(args)

    init_db()
    gateway = _ensure_gateway()
    summary = get_ticker_event_summary(
        gateway,
        ticker,
        as_of_date=end_date,
        start_date=start_date,
        end_date=end_date,
    )

    if args.json:
        print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        _print_summary(ticker, start_date, end_date, summary)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
