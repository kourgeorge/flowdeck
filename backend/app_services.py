"""
Shared service instances for routers. Set once at startup from main; routers use getters.
Unifies service injection so routers do not rely on module-level set_* callbacks.
"""

from typing import Optional

from services.analysis_service import AnalysisService

_analysis_service: Optional[AnalysisService] = None


def set_services(analysis_service: AnalysisService) -> None:
    """Set shared services (called from main.py at startup)."""
    global _analysis_service
    _analysis_service = analysis_service


def get_analysis_service() -> AnalysisService:
    if _analysis_service is None:
        raise RuntimeError("Analysis service not set. Call app_services.set_services() at startup.")
    return _analysis_service
