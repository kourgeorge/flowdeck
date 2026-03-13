"""Public API: config, stats, SKILL.md (no auth)."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from config import MAJOR_TICKERS
from database import get_db
from models.db_models import Execution, Report

router = APIRouter(tags=["public"])


class PublicConfigResponse(BaseModel):
    preview_tickers: list[str]


class PublicStatsResponse(BaseModel):
    total_analyses: int
    total_reports: int
    unique_tickers_analyzed: int


@router.get("/api/SKILL.md")
async def get_skill_md():
    """Serve the SKILL.md file for AI agents."""
    skill_path = Path(__file__).resolve().parents[1] / "SKILL.md"
    try:
        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()
        return Response(
            content=content,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": 'inline; filename="SKILL.md"',
                "Cache-Control": "public, max-age=3600"
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="SKILL.md not found")


@router.get("/api/config/public", response_model=PublicConfigResponse)
async def get_public_config():
    """Return public configuration (e.g. preview tickers visible without login)."""
    return PublicConfigResponse(preview_tickers=list(MAJOR_TICKERS))


@router.get("/api/stats", response_model=PublicStatsResponse)
async def get_public_stats(db: Session = Depends(get_db)):
    """Public stats about analyses and reports (no auth required)."""
    total_analyses = db.query(sqla_func.count(Execution.id)).scalar() or 0
    total_reports = db.query(sqla_func.count(Report.id)).scalar() or 0
    unique_tickers = (
        db.query(sqla_func.count(sqla_func.distinct(Execution.subject_id)))
        .filter(Execution.execution_type == "ticker")
        .scalar() or 0
    )
    return PublicStatsResponse(
        total_analyses=int(total_analyses),
        total_reports=int(total_reports),
        unique_tickers_analyzed=int(unique_tickers),
    )
