"""
Public share endpoint: resolve token to report data (no auth).

Token encodes execution_id only. Report type is determined from Execution.execution_type.
Resolvers are registered per execution_type; add a new resolver to support a new report kind.
"""

import json
from typing import Any, Callable, Dict

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from database import SessionLocal
from data_layer import get_data_gateway
from models.db_models import Execution, Report
from services.share_service import decode_share_token

router = APIRouter(prefix="/api/share", tags=["share"])


def _resolve_ticker(db: Session, ex: Execution) -> Dict[str, Any]:
    """Build shared response for execution_type=ticker (stock analysis run)."""
    gw = get_data_gateway()
    reports = gw.get_reports_with_scores(ex.id)
    if not reports:
        raise HTTPException(status_code=404, detail="Report not found")
    ticker = (ex.subject_id or "").upper()
    report_date = ex.created_at.strftime("%Y-%m-%d") if ex.created_at else None
    company_name: str | None = None
    try:
        info = gw.get_company_info(ticker)
        if info and isinstance(info, dict):
            company_name = info.get("name") or None
    except Exception:
        pass
    return {
        "type": "ticker",
        "ticker": ticker,
        "company_name": company_name,
        "execution_id": ex.id,
        "report_date": report_date,
        "reports": reports,
    }


def _resolve_daily_digest(db: Session, ex: Execution) -> Dict[str, Any]:
    """Build shared response for execution_type=daily_digest (User Daily Brief)."""
    report = (
        db.query(Report)
        .filter(
            Report.execution_id == ex.id,
            Report.report_type == "daily_digest",
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    meta: Dict[str, Any] = {}
    if report.metadata_json:
        try:
            meta = json.loads(report.metadata_json) or {}
        except Exception:
            pass
    return {
        "type": "digest",
        "execution_id": ex.id,
        "narrative": report.content or "",
        "what_to_watch": meta.get("what_to_watch") or "",
        "digest_date": meta.get("digest_date") or "",
        "span_type": meta.get("span_type") or "daily",
        "span_label": meta.get("span_label") or "Daily",
        "priority_tickers": meta.get("priority_tickers") or [],
        "references": meta.get("references"),
        "resources": meta.get("resources"),
        "agent_steps": meta.get("agent_steps"),
        "important_events": meta.get("important_events") or [],
    }


# Registry: execution_type -> resolver(db, execution) -> response dict.
# To support a new report kind: add a resolver and register it here; frontend may need a view for the new type.
_SHARE_RESOLVERS: Dict[str, Callable[[Session, Execution], Dict[str, Any]]] = {
    "ticker": _resolve_ticker,
    "daily_digest": _resolve_daily_digest,
}


@router.get("/{token}")
async def get_shared_report(token: str):
    """
    Resolve a share token to report data. No authentication required.
    Works for any report kind (ticker analysis, daily brief, etc.) registered in the resolver map.
    """
    execution_id = decode_share_token(token)
    if execution_id is None:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    db = SessionLocal()
    try:
        ex = db.query(Execution).filter(Execution.id == execution_id).first()
        if not ex:
            raise HTTPException(status_code=404, detail="Report not found")

        resolver = _SHARE_RESOLVERS.get(ex.execution_type)
        if not resolver:
            raise HTTPException(
                status_code=404,
                detail=f"Share not supported for report type: {ex.execution_type}",
            )
        return resolver(db, ex)
    finally:
        db.close()
