"""
Shared service instances for routers. Set once at startup from main; routers use getters.
Unifies service injection so routers do not rely on module-level set_* callbacks.
"""

from typing import Optional

from services.analysis_service import AnalysisService
from services.report_service import ReportService

_report_service: Optional[ReportService] = None
_analysis_service: Optional[AnalysisService] = None


def set_services(
    report_service: ReportService,
    analysis_service: AnalysisService,
) -> None:
    """Set shared services (called from main.py at startup)."""
    global _report_service, _analysis_service
    _report_service = report_service
    _analysis_service = analysis_service


def get_report_service() -> ReportService:
    if _report_service is None:
        raise RuntimeError("Report service not set. Call app_services.set_services() at startup.")
    return _report_service


def get_analysis_service() -> AnalysisService:
    if _analysis_service is None:
        raise RuntimeError("Analysis service not set. Call app_services.set_services() at startup.")
    return _analysis_service
