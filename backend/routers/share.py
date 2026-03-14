"""Public share endpoint: resolve obfuscated token to report data (no auth required)."""

from fastapi import APIRouter, HTTPException

from database import SessionLocal
from models.db_models import Execution
from services.report_service import ReportService
from services.share_service import decode_share_token

router = APIRouter(prefix="/api/share", tags=["share"])


@router.get("/{token}")
async def get_shared_report(token: str):
    """
    Resolve a share token to report data. No authentication required.
    Returns ticker, execution_id, report_date, and reports so the recipient can view the report.
    """
    decoded = decode_share_token(token)
    if not decoded:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    ticker, execution_id = decoded
    db = SessionLocal()
    try:
        ex = db.query(Execution).filter(Execution.id == execution_id).first()
        if not ex:
            raise HTTPException(status_code=404, detail="Report not found")
        if ex.execution_type != "ticker" or (ex.subject_id or "").upper() != ticker:
            raise HTTPException(status_code=404, detail="Report not found")

        report_svc = ReportService()
        reports = report_svc.get_reports_with_scores(execution_id)
        if not reports:
            raise HTTPException(status_code=404, detail="Report not found")

        report_date = ex.created_at.strftime("%Y-%m-%d") if ex.created_at else None
        return {
            "ticker": ticker,
            "execution_id": execution_id,
            "report_date": report_date,
            "reports": reports,
        }
    finally:
        db.close()
