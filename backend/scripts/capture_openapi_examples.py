#!/usr/bin/env python3
"""Capture real 200-response examples for the Data API docs.

Calls the live data gateway for a fixed ticker set and writes truncated, dated
examples to `api_docs_examples.py`. A missing vendor credential (Finnhub, Reddit,
an LLM key) makes that one capture skip rather than aborting the run -- see
api_docs.py's data_responses() docstring for why a 200 example is optional.

Run from backend/, with the repo root also on PYTHONPATH (for
`from backend.processing import get_ticker_event_summary`, mirroring the
import data_api.py itself uses for GET /events/{ticker}):

    cd backend && PYTHONPATH=.. uv run python scripts/capture_openapi_examples.py
"""
import pprint
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import main  # noqa: E402  (module-level init_data_gateway() call)
from backend.processing import get_ticker_event_summary  # noqa: E402
from data_layer import get_data_gateway  # noqa: E402
from services.share_service import get_share_url  # noqa: E402

TICKER = "AAPL"
FUND_TICKER = "SPY"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
START_DATE = "2026-07-01"
END_DATE = TODAY

MAX_LIST_LEN = 2
MAX_STR_LEN = 400


def _truncate(value):
    # These examples get embedded as a literal JSON `example` in the OpenAPI schema, so
    # anything JSON can't represent -- datetime/date (pandas.Timestamp is a subclass),
    # numpy scalars from yfinance/yahooquery -- must become a plain value here, not just
    # for pprint's sake: a raw datetime or numpy.float64 in the written module would
    # either fail to import (no such name in scope) or fail FastAPI's schema serialization.
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _truncate(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_truncate(v) for v in list(value)[:MAX_LIST_LEN]]
    if isinstance(value, str):
        return value[:MAX_STR_LEN] + "..." if len(value) > MAX_STR_LEN else value
    if hasattr(value, "item") and not isinstance(value, (dict, list)):
        return _truncate(value.item())
    return value


def _capture(key, fn):
    try:
        result = fn()
        print(f"  ok:   {key}")
        return _truncate(result)
    except Exception as e:
        print(f"  skip: {key} ({e})")
        return None


def _reports_for_ticker(gw, ticker):
    latest = gw.get_latest_execution_for_ticker(ticker)
    if not latest:
        return {"report_run_id": None, "report_date": None, "reports": {}, "share_url": None}
    ar_id, date_display = latest
    reports = gw.get_reports_with_scores(ar_id)
    share_url = get_share_url(ar_id)
    return {"report_run_id": ar_id, "report_date": date_display, "reports": reports, "share_url": share_url}


def _edgar_filing_content(gw):
    # No LLM key is configured in every environment; raw=False needs one, raw=True doesn't.
    extracted = gw.get_edgar_filing_content(TICKER, None, 1, False, None)
    if extracted:
        return extracted
    return gw.get_edgar_filing_content(TICKER, None, 1, True, None)


def build_jobs(gw):
    return {
        "quote": lambda: gw.get_quote(TICKER),
        "market_rates": lambda: gw.get_market_rates(),
        "market_movers": lambda: gw.get_daily_market_movers(8),
        "market_overview": lambda: gw.get_market_overview(6, 0, 10, 0, 8, 0, 12, 0, "1d"),
        "market_overview_section": lambda: gw.get_market_overview_section("indices", 6, 0, "1d"),
        "news": lambda: gw.get_news(TICKER, lookback_days=7),
        "news_batch": lambda: gw.get_news_batch([TICKER, "MSFT"], lookback_days=7),
        "insider_transactions": lambda: gw.get_insider_transactions(TICKER, 50),
        "company": lambda: gw.get_company_info(TICKER),
        "extended_info": lambda: gw.get_extended_info(TICKER),
        "fund_info": lambda: gw.get_fund_info(FUND_TICKER),
        "fundamentals": lambda: gw.get_fundamentals(TICKER),
        "financial_statements": lambda: gw.get_financial_statements(
            TICKER, statement_type="all", freq="quarterly"
        ),
        "financial_charts": lambda: gw.get_financial_charts(TICKER, "annual"),
        "historical": lambda: gw.get_historical(TICKER, "6mo", "1d"),
        "ticker_data": lambda: {
            "ticker": TICKER,
            "start_date": START_DATE,
            "end_date": END_DATE,
            "data": gw.get_ticker_data(TICKER, START_DATE, END_DATE),
        },
        "indicators": lambda: {
            "ticker": TICKER,
            "indicator": "rsi",
            "data": gw.get_indicators(TICKER, "rsi", TODAY, 30),
        },
        "global_news": lambda: {"data": gw.get_global_news(TODAY, 7, 10, None)},
        "insider_sentiment": lambda: {"ticker": TICKER, "data": gw.get_insider_sentiment(TICKER, TODAY)},
        "reddit_company_social": lambda: {
            "ticker": TICKER,
            "data": gw.get_reddit_company_social(TICKER, START_DATE, END_DATE, ["Apple", "AAPL"]),
        },
        "analyst_recommendations": lambda: gw.get_analyst_recommendations(TICKER),
        "events": lambda: get_ticker_event_summary(
            gw, TICKER, as_of_date=TODAY, price_technical_lookback_days=10
        ).model_dump(),
        "future_events": lambda: gw.get_future_events(TICKER),
        "similar_tickers": lambda: gw.get_similar_tickers(TICKER, 10, 0),
        "company_officers": lambda: gw.get_company_officers(TICKER),
        "edgar_filings": lambda: gw.get_edgar_filings(TICKER),
        "edgar_filing_content": lambda: _edgar_filing_content(gw),
        "reports": lambda: _reports_for_ticker(gw, TICKER),
        "reports_dates": lambda: {"ticker": TICKER, "dates": gw.list_report_dates(TICKER)},
        "reports_batch": lambda: {"tickers": {TICKER: _reports_for_ticker(gw, TICKER)}},
    }


def _write(examples):
    out_path = Path(__file__).parent.parent / "api_docs_examples.py"
    formatted = pprint.pformat(examples, indent=4, width=100, sort_dicts=False)
    out_path.write_text(
        '"""Captured 200-response examples for the Data API docs.\n\n'
        "Generated by `scripts/capture_openapi_examples.py` -- do not hand-edit. Each value is\n"
        "a real response from the data gateway, truncated (arrays to 2 elements, strings to\n"
        "~400 chars) and dated in `_captured`. A missing key here just means `data_responses()`\n"
        "omits the 200 example for that endpoint; it never crashes the app.\n\n"
        "Re-run: cd backend && PYTHONPATH=.. uv run python scripts/capture_openapi_examples.py\n"
        '"""\n\n'
        "from typing import Any, Dict\n\n"
        f"EXAMPLES: Dict[str, Any] = {formatted}\n"
    )
    print(f"\nwrote {len(examples)} examples to {out_path}")


def run():
    gw = get_data_gateway()
    jobs = build_jobs(gw)
    examples = {}
    for key, fn in jobs.items():
        result = _capture(key, fn)
        if result is not None:
            if isinstance(result, dict):
                result["_captured"] = TODAY
            examples[key] = result
    _write(examples)


if __name__ == "__main__":
    run()
