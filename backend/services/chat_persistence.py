"""
Persistence for chat sessions and messages.

Saves user and assistant messages with metadata (model_metadata, tool_calls, etc.)
and updates session updated_at / title.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.db_models import ChatMessage, ChatSession

logger = logging.getLogger(__name__)

# Max length for session title derived from first user message
SESSION_TITLE_MAX_LEN = 80


def save_user_message(
    db: Session,
    session_id: int,
    content: str,
    sort_order: int,
) -> ChatMessage:
    """Insert a user message and return it."""
    msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=content or "",
        sort_order=sort_order,
    )
    db.add(msg)
    db.flush()  # get msg.id if needed
    return msg


def save_assistant_message(
    db: Session,
    session_id: int,
    content: str,
    sort_order: int,
    *,
    model_metadata: Optional[Dict[str, Any]] = None,
    tools_called: Optional[int] = None,
    tool_calls: Optional[List[dict]] = None,
    skill_events: Optional[List[dict]] = None,
    charts: Optional[List[dict]] = None,
    follow_up_questions: Optional[List[str]] = None,
) -> ChatMessage:
    """Insert an assistant message with optional metadata; return it."""
    msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=content or "",
        sort_order=sort_order,
        model_metadata_json=json.dumps(model_metadata) if model_metadata else None,
        tools_called=tools_called,
        tool_calls_json=json.dumps(tool_calls) if tool_calls else None,
        skill_events_json=json.dumps(skill_events) if skill_events else None,
        charts_json=json.dumps(charts) if charts else None,
        follow_up_questions_json=json.dumps(follow_up_questions) if follow_up_questions else None,
    )
    db.add(msg)
    db.flush()
    return msg


def update_session_after_messages(
    db: Session,
    session_id: int,
    *,
    first_user_content: Optional[str] = None,
) -> None:
    """
    Update session updated_at and optionally set title from first user message.

    If first_user_content is provided and the session's title is null,
    set title to a truncated snippet of first_user_content.
    """
    session = db.get(ChatSession, session_id)
    if not session:
        return
    session.updated_at = datetime.utcnow()
    if first_user_content is not None and session.title is None:
        title = (first_user_content.strip()[:SESSION_TITLE_MAX_LEN] + "…") if len(first_user_content.strip()) > SESSION_TITLE_MAX_LEN else first_user_content.strip()
        if title:
            session.title = title
    db.flush()


def get_session_for_user(
    db: Session, session_id: int, user_id: int
) -> Optional[ChatSession]:
    """Load session by id if it belongs to the user. Otherwise None."""
    session = db.get(ChatSession, session_id)
    if session is None or session.user_id != user_id:
        return None
    return session


def list_sessions_for_user(
    db: Session, user_id: int, limit: int = 50
) -> List[ChatSession]:
    """List user's chat sessions, most recently updated first."""
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )


def create_session_for_user(db: Session, user_id: int) -> ChatSession:
    """Create a new chat session for the user. Caller must commit."""
    session = ChatSession(user_id=user_id)
    db.add(session)
    db.flush()
    return session


def delete_session_for_user(
    db: Session, session_id: int, user_id: int
) -> bool:
    """Delete session if it exists and belongs to user. Returns True if deleted."""
    session = get_session_for_user(db, session_id, user_id)
    if session is None:
        return False
    db.delete(session)
    db.commit()
    return True
