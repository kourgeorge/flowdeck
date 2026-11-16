"""Backend entry point for the watchlist report pipeline (ai_engine/watchlist_consulting).

The pipeline needs the user's subscriptions, their latest reports and market data. All of
those live here in the backend, and ai_engine may not import backend modules (backend ->
ai_engine only), so this module loads them and passes them in.

Run from backend/:
    PYTHONPATH=.. python -m services.watchlist_report_service --email=user@example.com
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# watchlist_consulting modules import each other by bare name (from conductor import ...).
_WATCHLIST_DIR = Path(__file__).resolve().parents[2] / "ai_engine" / "watchlist_consulting"


def _ensure_watchlist_on_path() -> None:
    if str(_WATCHLIST_DIR) not in sys.path:
        sys.path.insert(0, str(_WATCHLIST_DIR))


def load_watchlist_payload(
    user_id: Optional[int] = None,
    email: Optional[str] = None,
    *,
    fetcher: Optional[Any] = None,
) -> Dict[str, Any]:
    """Look up the user and their subscriptions, then build the payload in ai_engine."""
    from database import SessionLocal
    from models.db_models import Subscription, User
    from services.info_fetcher import get_info_fetcher
    from services.report_service import ReportService

    from ai_engine.watchlist_consulting.report_payload import build_payload

    db = SessionLocal()
    try:
        row = None
        if user_id is not None:
            row = db.query(User).filter(User.id == user_id).first()
        elif email:
            row = db.query(User).filter(User.email == email).first()
        user = None
        tickers: List[str] = []
        if row:
            user = {"id": row.id, "email": getattr(row, "email", "") or "", "name": getattr(row, "name") or ""}
            tickers = [
                r.ticker
                for r in db.query(Subscription.ticker)
                .filter(Subscription.user_id == row.id)
                .order_by(Subscription.ticker)
                .all()
            ]
        return build_payload(
            user,
            tickers,
            report_service=ReportService(),
            quote_fetcher=fetcher or get_info_fetcher(),
        )
    finally:
        db.close()


def run_watchlist_pipeline(**kwargs: Any) -> Dict[str, Any]:
    """conductor.run_pipeline with the backend's payload loader and info fetcher passed in."""
    _ensure_watchlist_on_path()
    from conductor import run_pipeline  # type: ignore[import-not-found]
    from services.info_fetcher import get_info_fetcher

    fetcher = get_info_fetcher()
    return run_pipeline(
        payload_loader=lambda **kw: load_watchlist_payload(**kw, fetcher=fetcher),
        fetcher=fetcher,
        **kwargs,
    )


def main(argv: Optional[List[str]] = None) -> int:
    _ensure_watchlist_on_path()
    from build_report import main as build_report_main  # type: ignore[import-not-found]
    from services.info_fetcher import get_info_fetcher

    fetcher = get_info_fetcher()
    return build_report_main(
        argv,
        payload_loader=lambda **kw: load_watchlist_payload(**kw, fetcher=fetcher),
        fetcher=fetcher,
    )


if __name__ == "__main__":
    sys.exit(main())
