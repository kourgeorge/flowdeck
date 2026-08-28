"""
Chat router: POST /api/chat  and  POST /api/chat/stream

Authenticated endpoints that run a stock market analyst ReAct agent.
Deducts tokens from the user's balance based on the number of agent trajectory steps.

Session persistence: optional session_id on request; GET/POST/DELETE /api/chat/sessions.
"""

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.db_models import ChatMessage
from services import token_service
from services.chat_persistence import (
    create_session_for_user,
    delete_session_for_user,
    get_session_for_user,
    list_sessions_for_user,
)
from services.chat_turn_service import (
    get_active_turn_for_session,
    get_chat_turn_service,
    get_turn_for_user,
    turn_to_payload,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Chat"])


class ChatMessageIn(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessageIn]
    context: Optional[Dict] = None  # optional context (e.g. {"tickers": ["AAPL", "MSFT"]})
    session_id: Optional[int] = None  # when set, load history and persist new messages


class ChatResponse(BaseModel):
    reply: str
    tokens_used: int  # LLM token count (for debugging/analytics)
    platform_tokens_used: int  # tokens deducted from balance (what the UI should show)
    balance: int
    follow_up_questions: Optional[List[str]] = None
    session_id: Optional[int] = None  # set when backend created a new session for this turn
    turn_id: Optional[int] = None
    llm_usage: Optional[Dict[str, Any]] = None  # input_tokens, output_tokens, cost_usd, per_call


# --- Session list/detail schemas ---


class ChatMessageOut(BaseModel):
    role: str
    content: str
    sort_order: int
    tokens_used: Optional[int] = None  # derived from model_metadata.total_tokens
    platform_tokens_used: Optional[int] = None  # tokens deducted from balance (for UI display)
    model_metadata: Optional[Dict[str, Any]] = None  # provider, input_tokens, output_tokens, total_tokens, cost_usd, per_call
    cost_usd: Optional[float] = None  # derived from model_metadata.cost_usd (for UI)
    tools_called: Optional[int] = None
    tool_call_events: Optional[List[Dict[str, Any]]] = None
    skill_activation_events: Optional[List[Dict[str, Any]]] = None
    charts: Optional[List[Dict[str, Any]]] = None
    follow_up_questions: Optional[List[str]] = None
    created_at: Optional[str] = None


class ChatSessionOut(BaseModel):
    id: int
    title: Optional[str] = None
    created_at: str
    updated_at: str


class ChatTurnStatusOut(BaseModel):
    id: int
    session_id: int
    status: str
    last_thinking_status: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SessionListItem(BaseModel):
    id: int
    title: Optional[str] = None
    updated_at: str
    active_turn: Optional[ChatTurnStatusOut] = None


class SessionListResponse(BaseModel):
    sessions: List[SessionListItem]


class SessionDetailResponse(BaseModel):
    id: int
    title: Optional[str] = None
    created_at: str
    updated_at: str
    messages: List[ChatMessageOut]
    active_turn: Optional[ChatTurnStatusOut] = None


def _message_to_out(m: ChatMessage) -> ChatMessageOut:
    """Convert DB ChatMessage to API schema with parsed JSON fields."""
    tool_call_events = None
    if m.tool_calls_json:
        try:
            tool_call_events = json.loads(m.tool_calls_json)
        except Exception as e:
            logger.warning("Failed to parse tool_calls_json for message id=%s: %s", getattr(m, "id", None), e)
    skill_activation_events = None
    if m.skill_events_json:
        try:
            skill_activation_events = json.loads(m.skill_events_json)
        except Exception as e:
            logger.warning("Failed to parse skill_events_json for message id=%s: %s", getattr(m, "id", None), e)
    charts = None
    if m.charts_json:
        try:
            charts = json.loads(m.charts_json)
        except Exception as e:
            logger.warning("Failed to parse charts_json for message id=%s: %s", getattr(m, "id", None), e)
    follow_up_questions = None
    if m.follow_up_questions_json:
        try:
            follow_up_questions = json.loads(m.follow_up_questions_json)
        except Exception as e:
            logger.warning("Failed to parse follow_up_questions_json for message id=%s: %s", getattr(m, "id", None), e)
    model_metadata = None
    tokens_used = None
    platform_tokens_used = None
    cost_usd = None
    if getattr(m, "model_metadata_json", None):
        try:
            model_metadata = json.loads(m.model_metadata_json)
            total = model_metadata.get("total_tokens")
            if total is not None:
                tokens_used = int(total)
                platform_tokens_used = token_service.llm_tokens_to_platform_tokens(tokens_used)
            cost_usd = model_metadata.get("cost_usd")
        except Exception as e:
            logger.warning("Failed to parse model_metadata_json for message id=%s: %s", getattr(m, "id", None), e)
    return ChatMessageOut(
        role=m.role,
        content=m.content or "",
        sort_order=m.sort_order,
        tokens_used=tokens_used,
        platform_tokens_used=platform_tokens_used,
        model_metadata=model_metadata,
        cost_usd=cost_usd,
        tools_called=m.tools_called,
        tool_call_events=tool_call_events,
        skill_activation_events=skill_activation_events,
        charts=charts,
        follow_up_questions=follow_up_questions,
        created_at=m.created_at.isoformat() if m.created_at else None,
    )


@router.get("/chat/sessions", response_model=SessionListResponse)
async def list_sessions(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
):
    """List current user's chat sessions, most recently updated first."""
    sessions = list_sessions_for_user(db, current_user.id, limit)
    return SessionListResponse(
        sessions=[
            SessionListItem(
                id=s.id,
                title=s.title,
                updated_at=s.updated_at.isoformat() if s.updated_at else "",
                active_turn=(
                    ChatTurnStatusOut(**turn_to_payload(active_turn))
                    if (active_turn := get_active_turn_for_session(db, s.id, current_user.id)) is not None
                    else None
                ),
            )
            for s in sessions
        ]
    )


@router.post("/chat/sessions", response_model=ChatSessionOut)
async def create_session(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new chat session."""
    session = create_session_for_user(db, current_user.id)
    db.commit()
    db.refresh(session)
    return ChatSessionOut(
        id=session.id,
        title=session.title,
        created_at=session.created_at.isoformat() if session.created_at else "",
        updated_at=session.updated_at.isoformat() if session.updated_at else "",
    )


@router.get("/chat/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get one session and its messages. 404 if not found or not owned by user."""
    session = get_session_for_user(db, session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    messages = list(session.messages)
    return SessionDetailResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at.isoformat() if session.created_at else "",
        updated_at=session.updated_at.isoformat() if session.updated_at else "",
        messages=[_message_to_out(m) for m in messages],
        active_turn=(
            ChatTurnStatusOut(**turn_to_payload(active_turn))
            if (active_turn := get_active_turn_for_session(db, session.id, current_user.id)) is not None
            else None
        ),
    )


@router.get("/chat/turns/{turn_id}", response_model=ChatTurnStatusOut)
async def get_turn_status(
    turn_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Poll a chat turn's status. 404 if it doesn't exist or belongs to another user."""
    turn = get_turn_for_user(db, turn_id, current_user.id)
    if turn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turn not found")
    return ChatTurnStatusOut(**turn_to_payload(turn))


@router.delete("/chat/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a session and all its messages. 404 if not found or not owned by user."""
    if not delete_session_for_user(db, session_id, current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run a chat turn with the stock market analyst agent.

    - Requires authentication (Bearer token).
    - Deducts tokens based on agent trajectory length (tool calls + LLM steps).
    - Minimum cost: 1 token per message.
    - Returns 402 if the user has insufficient token balance.
    """
    balance = token_service.get_balance(current_user.id, db)
    if balance < 1:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient token balance. Please purchase more tokens to continue chatting.",
        )

    user_id = current_user.id
    context = body.context or {}
    turn_service = get_chat_turn_service()

    try:
        turn_id, session_id, messages = turn_service.prepare_turn(
            user_id=user_id,
            body_messages=[{"role": m.role, "content": m.content} for m in body.messages],
            session_id=body.session_id,
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    except Exception as e:
        logger.exception("Failed to prepare chat turn for user_id=%s: %s", current_user.id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to prepare chat turn",
        )

    result = turn_service.run_turn_sync(
        turn_id=turn_id,
        session_id=session_id,
        user_id=user_id,
        messages=messages,
        context=context,
    )
    if result.get("type") == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("content") or "Chat agent error",
        )

    return ChatResponse(
        reply=result.get("content", ""),
        tokens_used=result.get("tokens_used", 1),
        platform_tokens_used=result.get("platform_tokens_used", 1),
        balance=result.get("balance", 0),
        follow_up_questions=result.get("follow_up_questions"),
        session_id=result.get("session_id"),
        turn_id=result.get("turn_id"),
        llm_usage=result.get("llm_usage"),
    )


@router.post(
    "/chat/stream",
    summary="Stream a chat turn (SSE)",
    response_description="`text/event-stream`, not JSON -- see the description for the event vocabulary.",
    responses={
        200: {
            "description": "SSE stream. Each event is `data: {json}\\n\\n`; see the event vocabulary above.",
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"},
                    "example": 'data: {"type": "started", "turn_id": 1, "session_id": 1, "status": "running"}\n\n',
                }
            },
        },
        402: {
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Insufficient token balance. Please purchase more tokens to continue chatting."
                    }
                }
            }
        },
        404: {"content": {"application/json": {"example": {"detail": "Session not found"}}}},
    },
)
async def chat_stream(
    body: ChatRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stream a chat turn as Server-Sent Events (SSE).

    Each SSE event is a JSON object, in the order they can appear:
      - ``{"type":"started","turn_id":N,"session_id":N,"status":"running"}``  — emitted first
      - ``{"type":"thinking","content":"..."}``                              — reasoning trace
      - ``{"type":"tool_call","name":"...","args":{...}}``                   — a tool the analyst invoked
      - ``{"type":"token","content":"..."}``                                 — incremental text chunk
      - ``{"type":"done","tokens_used":N}``                                  — stream finished; tokens deducted
      - ``{"type":"error","content":"..."}``                                 — error occurred

    - Requires authentication (Bearer token).
    - Returns 402 if the user has insufficient token balance.
    - If session_id is set: load session history, append body.messages, then persist new user + assistant messages on done.
    """
    balance = token_service.get_balance(current_user.id, db)
    if balance < 1:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient token balance. Please purchase more tokens to continue chatting.",
        )

    user_id = current_user.id
    context = body.context or {}
    turn_service = get_chat_turn_service()

    try:
        turn_id, session_id, messages = turn_service.prepare_turn(
            user_id=user_id,
            body_messages=[{"role": m.role, "content": m.content} for m in body.messages],
            session_id=body.session_id,
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    except Exception as e:
        logger.exception("Failed to prepare streamed chat turn for user_id=%s: %s", current_user.id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to prepare chat turn",
        )

    async def event_generator() -> AsyncIterator[str]:
        subscriber = turn_service.subscribe(turn_id)
        turn_service.run_turn_async(
            turn_id=turn_id,
            session_id=session_id,
            user_id=user_id,
            messages=messages,
            context=context,
        )
        try:
            yield f"data: {json.dumps({'type': 'started', 'turn_id': turn_id, 'session_id': session_id, 'status': 'running'})}\n\n"
            while True:
                payload = await asyncio.to_thread(subscriber.get)
                if payload is None:
                    break
                yield f"data: {json.dumps(payload)}\n\n"
        except Exception as e:
            logger.exception("Chat stream failed for user_id=%s: %s", user_id, e)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        finally:
            turn_service.unsubscribe(turn_id, subscriber)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
