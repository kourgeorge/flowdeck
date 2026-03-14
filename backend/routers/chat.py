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
from database import get_db, SessionLocal
from models.db_models import ChatMessage, ChatSession
from services import token_service
from services.chat_persistence import save_assistant_message, save_user_message, update_session_after_messages
from services.chat_service import get_chat_service


def _build_model_metadata(llm_usage: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Build model_metadata dict from agent llm_usage + provider for storage."""
    if not llm_usage:
        return None
    from ai_engine.llm_provider import get_config_from_env
    provider = get_config_from_env().get("llm_provider", "openai")
    return {**llm_usage, "provider": provider}

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


class SessionListItem(BaseModel):
    id: int
    title: Optional[str] = None
    updated_at: str


class SessionListResponse(BaseModel):
    sessions: List[SessionListItem]


class SessionDetailResponse(BaseModel):
    id: int
    title: Optional[str] = None
    created_at: str
    updated_at: str
    messages: List[ChatMessageOut]


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


def _get_session_for_user(db: Session, session_id: int, user_id: int) -> Optional[ChatSession]:
    """Load session by id if it belongs to the user."""
    session = db.get(ChatSession, session_id)
    if session is None or session.user_id != user_id:
        return None
    return session


def _persist_turn_on_done(
    db: Session,
    user_id: int,
    session_id_for_persist: Optional[int],
    existing_message_count: int,
    body_messages: List[ChatMessageIn],
    acc_content: List[str],
    acc_tool_calls: List[Dict[str, Any]],
    acc_skill_events: List[Dict[str, Any]],
    acc_charts: List[Dict[str, Any]],
    tokens_used: int,
    model_metadata: Optional[Dict[str, Any]] = None,
    tools_called: Optional[int] = None,
    follow_up_questions: Optional[List[str]] = None,
) -> Optional[int]:
    """
    Deduct tokens, create session if needed, save user + assistant messages, update session.
    Returns session id (new or existing) or None.
    """
    try:
        token_service.deduct_for_chat(user_id, tokens_used, db)
    except Exception as deduct_err:
        logger.warning("Failed to deduct tokens for user_id=%s: %s", user_id, deduct_err)
    sid: Optional[int] = session_id_for_persist
    if not body_messages:
        return sid
    try:
        if sid is None:
            new_session = ChatSession(user_id=user_id)
            db.add(new_session)
            db.flush()
            sid = new_session.id
        base_order = existing_message_count if session_id_for_persist is not None else 0
        for i, um in enumerate(body_messages):
            save_user_message(db, sid, um.content, base_order + i)
        assistant_content = "".join(acc_content)
        save_assistant_message(
            db,
            sid,
            assistant_content,
            base_order + len(body_messages),
            model_metadata=model_metadata,
            tools_called=tools_called,
            tool_calls=acc_tool_calls if acc_tool_calls else None,
            skill_events=acc_skill_events if acc_skill_events else None,
            charts=acc_charts if acc_charts else None,
            follow_up_questions=follow_up_questions,
        )
        update_session_after_messages(
            db,
            sid,
            first_user_content=body_messages[0].content if body_messages else None,
        )
        db.commit()
    except Exception as persist_err:
        logger.exception("Failed to persist chat turn: %s", persist_err)
        db.rollback()
    return sid


@router.get("/chat/sessions", response_model=SessionListResponse)
async def list_sessions(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
):
    """List current user's chat sessions, most recently updated first."""
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return SessionListResponse(
        sessions=[
            SessionListItem(
                id=s.id,
                title=s.title,
                updated_at=s.updated_at.isoformat() if s.updated_at else "",
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
    session = ChatSession(user_id=current_user.id)
    db.add(session)
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
    session = _get_session_for_user(db, session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    messages = list(session.messages)
    return SessionDetailResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at.isoformat() if session.created_at else "",
        updated_at=session.updated_at.isoformat() if session.updated_at else "",
        messages=[_message_to_out(m) for m in messages],
    )


@router.delete("/chat/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a session and all its messages. 404 if not found or not owned by user."""
    session = _get_session_for_user(db, session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    db.delete(session)
    db.commit()


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
    # Check user has at least 1 token
    balance = token_service.get_balance(current_user.id, db)
    if balance < 1:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient token balance. Please purchase more tokens to continue chatting.",
        )

    user_id = current_user.id
    context = body.context or {}

    # When session_id is set, load session messages and prepend to request messages
    if body.session_id is not None:
        session = _get_session_for_user(db, body.session_id, user_id)
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        db_messages = [{"role": m.role, "content": m.content} for m in session.messages]
        messages = db_messages + [{"role": m.role, "content": m.content} for m in body.messages]
        existing_message_count = len(db_messages)
    else:
        messages = [{"role": m.role, "content": m.content} for m in body.messages]
        existing_message_count = 0

    # Run the agent in a thread pool (blocking LangChain calls)
    try:
        service = get_chat_service()
        result = await asyncio.to_thread(service.chat, messages, user_id, db, context)
    except Exception as e:
        logger.exception("Chat agent failed for user_id=%s: %s", current_user.id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat agent error: {str(e)}",
        )

    reply = result.get("reply", "")
    tokens_used = result.get("tokens_used", 1)
    platform_tokens_used = token_service.llm_tokens_to_platform_tokens(tokens_used)
    follow_up_questions = result.get("follow_up_questions")

    # Deduct tokens (best-effort; don't fail the response if deduction fails)
    try:
        token_service.deduct_for_chat(current_user.id, tokens_used, db)
    except Exception as e:
        logger.warning("Failed to deduct tokens for user_id=%s: %s", current_user.id, e)

    new_balance = token_service.get_balance(current_user.id, db)

    # Persist on first input: use existing session or create one
    persisted_session_id: Optional[int] = None
    if body.messages:
        try:
            sid = body.session_id
            if sid is None:
                new_session = ChatSession(user_id=user_id)
                db.add(new_session)
                db.flush()
                sid = new_session.id
                persisted_session_id = sid
            base_order = existing_message_count
            for i, um in enumerate(body.messages):
                save_user_message(db, sid, um.content, base_order + i)
            save_assistant_message(
                db,
                sid,
                reply,
                base_order + len(body.messages),
                model_metadata=_build_model_metadata(result.get("llm_usage")),
                tools_called=result.get("tools_called"),
                follow_up_questions=follow_up_questions,
            )
            update_session_after_messages(
                db,
                sid,
                first_user_content=body.messages[0].content if body.messages else None,
            )
            db.commit()
        except Exception as persist_err:
            logger.exception("Failed to persist chat turn: %s", persist_err)
            db.rollback()

    return ChatResponse(
        reply=reply,
        tokens_used=tokens_used,
        platform_tokens_used=platform_tokens_used,
        balance=new_balance,
        follow_up_questions=follow_up_questions,
        session_id=persisted_session_id,
        llm_usage=result.get("llm_usage"),
    )


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stream a chat turn as Server-Sent Events (SSE).

    Each SSE event is a JSON object:
      - ``{"type":"token","content":"..."}``  — incremental text chunk
      - ``{"type":"done","tokens_used":N}``   — stream finished; tokens deducted
      - ``{"type":"error","content":"..."}``  — error occurred

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

    # When session_id is set, load session messages and prepend to request messages
    session_id_for_persist: Optional[int] = None
    existing_message_count = 0
    if body.session_id is not None:
        session = _get_session_for_user(db, body.session_id, user_id)
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        db_messages = [{"role": m.role, "content": m.content} for m in session.messages]
        existing_message_count = len(db_messages)
        messages = db_messages + [{"role": m.role, "content": m.content} for m in body.messages]
        session_id_for_persist = body.session_id
    else:
        messages = [{"role": m.role, "content": m.content} for m in body.messages]

    async def event_generator() -> AsyncIterator[str]:
        service = get_chat_service()
        tokens_used = 1
        # Accumulators for persistence when session_id is set
        acc_content: List[str] = []
        acc_tool_calls: List[Dict[str, Any]] = []
        acc_charts: List[Dict[str, Any]] = []
        acc_skill_events: List[Dict[str, Any]] = []
        pending_skill_steps: List[Dict[str, Any]] = []
        try:
            loop = asyncio.get_event_loop()
            queue: asyncio.Queue[str | None] = asyncio.Queue()

            def run_generator():
                try:
                    for chunk in service.chat_stream(messages, user_id=user_id, db=db, context=context):
                        loop.call_soon_threadsafe(queue.put_nowait, chunk)
                except Exception as exc:
                    err_event = f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
                    loop.call_soon_threadsafe(queue.put_nowait, err_event)
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            thread_task = asyncio.get_event_loop().run_in_executor(None, run_generator)
            client_disconnected = False

            while True:
                item = await queue.get()
                if item is None:
                    break
                # Parse SSE payload once; if not valid JSON, forward as-is
                payload: Optional[Dict[str, Any]] = None
                try:
                    raw = item.removeprefix("data: ").strip()
                    payload = json.loads(raw)
                except Exception:
                    try:
                        yield item
                    except (asyncio.CancelledError, Exception):
                        client_disconnected = True
                        break
                    continue

                typ = payload.get("type")

                # Accumulate for persistence
                if typ == "token" and payload.get("content"):
                    acc_content.append(payload["content"])
                elif typ == "tool_call" and payload.get("name"):
                    acc_tool_calls.append({
                        "name": payload.get("name", ""),
                        "input": payload.get("input", ""),
                        "output": payload.get("output", ""),
                    })
                elif typ == "chart" and payload.get("spec"):
                    acc_charts.append(payload["spec"])
                elif typ == "skill_step":
                    pending_skill_steps.append({
                        "tool": payload.get("tool", ""),
                        "input": payload.get("input", ""),
                        "output": payload.get("output", ""),
                        "ok": payload.get("ok", True),
                    })
                elif typ == "skill_done" and payload.get("name"):
                    acc_skill_events.append({"name": payload.get("name"), "steps": list(pending_skill_steps)})
                    pending_skill_steps = []

                if typ == "done":
                    tokens_used = payload.get("tokens_used", 1)
                    platform_tokens_used = token_service.llm_tokens_to_platform_tokens(tokens_used)
                    if "follow_up_questions" not in payload:
                        payload["follow_up_questions"] = []
                    sid = _persist_turn_on_done(
                        db,
                        user_id,
                        session_id_for_persist,
                        existing_message_count,
                        body.messages,
                        acc_content,
                        acc_tool_calls,
                        acc_skill_events,
                        acc_charts,
                        tokens_used,
                        model_metadata=_build_model_metadata(payload.get("llm_usage")),
                        tools_called=payload.get("tools_called"),
                        follow_up_questions=payload.get("follow_up_questions"),
                    )
                    new_balance = token_service.get_balance(user_id, db)
                    payload["balance"] = new_balance
                    payload["platform_tokens_used"] = platform_tokens_used
                    if sid is not None:
                        payload["session_id"] = sid
                    tokens_used = 0  # so finally does not deduct again if yield fails
                    try:
                        yield f"data: {json.dumps(payload)}\n\n"
                    except (asyncio.CancelledError, Exception):
                        client_disconnected = True
                        break
                    continue

                try:
                    yield item
                except (asyncio.CancelledError, Exception):
                    client_disconnected = True
                    break

            # After client disconnect, drain queue and persist on "done" so user sees reply when they reload
            if client_disconnected:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    try:
                        raw = item.removeprefix("data: ").strip()
                        payload = json.loads(raw)
                    except Exception:
                        continue
                    typ = payload.get("type")
                    if typ == "token" and payload.get("content"):
                        acc_content.append(payload["content"])
                    elif typ == "tool_call" and payload.get("name"):
                        acc_tool_calls.append({
                            "name": payload.get("name", ""),
                            "input": payload.get("input", ""),
                            "output": payload.get("output", ""),
                        })
                    elif typ == "chart" and payload.get("spec"):
                        acc_charts.append(payload["spec"])
                    elif typ == "skill_step":
                        pending_skill_steps.append({
                            "tool": payload.get("tool", ""),
                            "input": payload.get("input", ""),
                            "output": payload.get("output", ""),
                            "ok": payload.get("ok", True),
                        })
                    elif typ == "skill_done" and payload.get("name"):
                        acc_skill_events.append({"name": payload.get("name"), "steps": list(pending_skill_steps)})
                        pending_skill_steps = []
                    if typ == "done":
                        tokens_used_val = payload.get("tokens_used", 1)
                        db_bg = SessionLocal()
                        try:
                            _persist_turn_on_done(
                                db_bg,
                                user_id,
                                session_id_for_persist,
                                existing_message_count,
                                body.messages,
                                acc_content,
                                acc_tool_calls,
                                acc_skill_events,
                                acc_charts,
                                tokens_used_val,
                                model_metadata=_build_model_metadata(payload.get("llm_usage")),
                                tools_called=payload.get("tools_called"),
                                follow_up_questions=payload.get("follow_up_questions"),
                            )
                            tokens_used = 0
                        finally:
                            db_bg.close()
                        break

            await thread_task

        except Exception as e:
            logger.exception("Chat stream failed for user_id=%s: %s", user_id, e)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        finally:
            if tokens_used > 0:
                try:
                    token_service.deduct_for_chat(user_id, tokens_used, db)
                except Exception as e:
                    logger.warning("Failed to deduct tokens for user_id=%s: %s", user_id, e)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


