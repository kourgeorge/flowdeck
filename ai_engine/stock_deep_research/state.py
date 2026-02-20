"""Graph state definitions for the Stock Deep Research agent."""

import operator
from typing import Annotated, Optional

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


def _override_reducer(current_value, new_value):
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    return operator.add(current_value, new_value)


# --- Structured outputs (tool args / model outputs) ---


class ConductResearch(BaseModel):
    """Delegate a research task to a sub-researcher."""

    research_topic: str = Field(
        description="A single, detailed research topic (at least a paragraph). Focus on one aspect: e.g. competition, SEC filings, market share, legal, AI disruption, ESG."
    )


class ResearchComplete(BaseModel):
    """Signal that the research phase is complete and findings are ready for the report."""


class StockResearchQuestion(BaseModel):
    """Structured research brief for a company/ticker."""

    research_brief: str = Field(
        description="A comprehensive research brief: company/ticker, suggested sections (business model, competition, industry, SEC/10-K, market share, legal, rivalry, AI/ESG), and any user focus."
    )


# --- State types ---


class AgentInputState(MessagesState):
    """Input: messages only (user question, e.g. 'Research Amazon AMZN' or 'Full report on Microsoft')."""


class AgentState(MessagesState):
    """Main agent state: messages, research brief, supervisor context, notes, final report."""

    supervisor_messages: Annotated[list[MessageLikeRepresentation], _override_reducer]
    research_brief: Optional[str] = None
    raw_notes: Annotated[list[str], _override_reducer] = []
    notes: Annotated[list[str], _override_reducer] = []
    final_report: Optional[str] = None


class SupervisorState(TypedDict):
    """State for the lead researcher / supervisor."""

    supervisor_messages: Annotated[list[MessageLikeRepresentation], _override_reducer]
    research_brief: str
    notes: Annotated[list[str], _override_reducer]
    research_iterations: int
    raw_notes: Annotated[list[str], _override_reducer]
    _supervisor_next: Optional[str]  # "supervisor" | "end" for routing


class ResearcherState(TypedDict):
    """State for an individual researcher (one delegated topic)."""

    researcher_messages: Annotated[list[MessageLikeRepresentation], operator.add]
    tool_call_iterations: int
    research_topic: str
    compressed_research: Optional[str]
    raw_notes: Annotated[list[str], _override_reducer]
    _next: Optional[str]  # internal: "researcher" | "compress_research" for routing


class ResearcherOutputState(TypedDict):
    """Output of the researcher subgraph."""

    compressed_research: str
    raw_notes: list[str]
