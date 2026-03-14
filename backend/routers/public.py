"""Public API: config, stats, SKILL.md (no auth)."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import MAJOR_TICKERS
from database import get_db
from services.public_stats_service import get_public_stats

router = APIRouter(prefix="/api", tags=["public"])


class PublicConfigResponse(BaseModel):
    preview_tickers: list[str]


class PublicStatsResponse(BaseModel):
    total_analyses: int
    total_reports: int
    unique_tickers_analyzed: int


@router.get("/SKILL.md")
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


@router.get("/config/public", response_model=PublicConfigResponse)
async def get_public_config():
    """Return public configuration (e.g. preview tickers visible without login)."""
    return PublicConfigResponse(preview_tickers=list(MAJOR_TICKERS))


@router.get("/stats", response_model=PublicStatsResponse)
async def get_public_stats_route(db: Session = Depends(get_db)):
    """Public stats about analyses and reports (no auth required)."""
    stats = get_public_stats(db)
    return PublicStatsResponse(
        total_analyses=stats["total_analyses"],
        total_reports=stats["total_reports"],
        unique_tickers_analyzed=stats["unique_tickers_analyzed"],
    )
