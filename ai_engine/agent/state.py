"""
AgentState — shared state TypedDict for the FlowDeck LangGraph chat agent.

All nodes read from and write to this state.  LangGraph merges updates
returned by each node using the annotated reducers.
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional, Sequence

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """
    State that flows through the FlowDeck chat agent graph.

    messages:       Full conversation history (LangGraph manages append-only via add_messages).
    user_id:        Authenticated user ID (None for anonymous).
    db:             SQLAlchemy session (injected per-request, not serialised).
    max_tool_calls: Hard cap on total tool invocations per turn.
    tool_calls_made: Running count of tool invocations this turn.
    skill_used:     Name of the skill that ran (if any), for metrics.
    skill_args:     Arguments extracted by the LLM for the selected skill.
    skill_steps:    List of tool steps executed by the skill workflow (for SSE streaming).
    system_prompt:  The full system prompt for this turn.
    context:        Arbitrary extra context dict (e.g. watchlist tickers).
    error:          Set if a fatal error occurred.
    
    # Planning & Todo Management
    task_type:      Task complexity: "simple" | "complex" | "long-horizon"
    planning_phase: Current phase: "analyzing" | "planning" | "awaiting_approval" | "executing" | "completed"
    todo_list:      List of todo items with status, dependencies, and metadata.
    current_step:   Index of the current step being executed (0-based).
    plan_approved:  Whether the user has approved the execution plan.
    discoveries:    New findings discovered during execution that may affect the plan.
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_id: Optional[int]
    db: Optional[Any]
    max_tool_calls: int
    tool_calls_made: int
    skill_used: Optional[str]
    skill_args: Optional[Dict[str, Any]]
    skill_steps: Optional[List[Dict[str, Any]]]
    system_prompt: str
    context: Optional[Dict[str, Any]]
    error: Optional[str]
    
    # Planning & Todo Management
    task_type: Optional[str]
    planning_phase: Optional[str]
    todo_list: Optional[List[Dict[str, Any]]]
    current_step: Optional[int]
    plan_approved: bool
    discoveries: Optional[List[str]]

# Made with Bob