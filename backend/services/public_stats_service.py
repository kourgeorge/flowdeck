"""Public stats: platform-wide counts (analyses, reports, unique tickers)."""

from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from models.db_models import Execution, Report


def get_public_stats(db: Session) -> dict:
    """
    Return total_analyses, total_reports, unique_tickers_analyzed.
    Used by public API (no auth).
    """
    total_analyses = db.query(sqla_func.count(Execution.id)).scalar() or 0
    total_reports = db.query(sqla_func.count(Report.id)).scalar() or 0
    unique_tickers = (
        db.query(sqla_func.count(sqla_func.distinct(Execution.subject_id)))
        .filter(Execution.execution_type == "ticker")
        .scalar() or 0
    )
    return {
        "total_analyses": int(total_analyses),
        "total_reports": int(total_reports),
        "unique_tickers_analyzed": int(unique_tickers),
    }
