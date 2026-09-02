"""
Shared curl_cffi session for all yfinance calls.

yfinance's TickerBase and PriceHistory each do `session or Session(impersonate="chrome")`
in their constructors, so every yf.Ticker()/yf.download() call that doesn't pass a
session creates a brand-new curl_cffi session that is never closed. On a server that
polls dozens of tickers every 5 minutes (see backend/main.py's cache-refresh job), those
orphaned sessions accumulate until the OS OOM-kills the process. Passing this shared
session everywhere avoids the leak for Ticker() and download() calls.

PriceHistory is the one place this doesn't fully help: TickerBase._lazy_load_price_history()
(yfinance/base.py) constructs PriceHistory without forwarding any session at all, so
history()/dividends/splits/actions calls still orphan a session internally. That session is
provably dead within yfinance (grep confirms `self.session` is never read again in
scrapers/history.py), so close_orphaned_price_history_session() below closes it explicitly
right after such a call.
"""

from __future__ import annotations

import logging

from curl_cffi import requests as curl_requests

logger = logging.getLogger(__name__)

_session: curl_requests.Session | None = None


def get_yf_session() -> curl_requests.Session:
    global _session
    if _session is None:
        _session = curl_requests.Session(impersonate="chrome")
    return _session


def close_yf_session() -> None:
    global _session
    if _session is not None:
        try:
            _session.close()
        except Exception:
            logger.warning("Error closing shared yfinance session", exc_info=True)
        _session = None


def close_orphaned_price_history_session(ticker_obj) -> None:
    """Close the internal session yfinance's PriceHistory creates on .history()/.dividends/etc."""
    price_history = getattr(ticker_obj, "_price_history", None)
    session = getattr(price_history, "session", None)
    if session is not None and session is not get_yf_session():
        try:
            session.close()
        except Exception:
            logger.warning("Error closing orphaned PriceHistory session", exc_info=True)
