"""Graph state and structured types for Portfolio Deep Research."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class Claim(BaseModel):
    """A claim that must be supported by evidence."""

    claim_text: str
    status: Literal["supported", "partially_supported", "disputed", "unknown"] = "unknown"
    required_evidence: Optional[str] = None  # description of required evidence types
    evidence_for: List[str] = Field(default_factory=list)  # source_ids
    evidence_against: List[str] = Field(default_factory=list)
    confidence: Optional[str] = None  # calibrated qualitative


def _list_reducer(current: list, new: Any) -> list:
    if new is None:
        return current
    if isinstance(new, list):
        return current + new
    return current + [new]


# --- Research state (portfolio-scoped) ---


class ResearchState(TypedDict, total=False):
    """State for the portfolio deep research graph."""

    messages: Annotated[list, operator.add]
    user_query: str
    tickers: List[str]
    plan: List[str]
    search_queries_run: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]
    evidence_items: Annotated[List[Dict[str, Any]], _list_reducer]
    claims: List[Claim]
    final_answer: Optional[str]
    final_report_html: Optional[str]
    figure_specs: Optional[List[Dict[str, Any]]]
    figure_data: Optional[Dict[str, Any]]
    payload: Optional[Dict[str, Any]]
    audit_log: Annotated[List[Dict[str, Any]], _list_reducer]
    existing_reports: Dict[str, Dict[str, Any]]
    narrative_output: Optional[Dict[str, Any]]
    # Portfolio Risk Profiling
    risk_profile: Optional[Dict[str, Any]]
    portfolio_questions: Optional[List[Dict[str, Any]]]
