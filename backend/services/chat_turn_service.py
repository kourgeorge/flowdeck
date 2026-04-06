"""
Server-owned chat turn lifecycle.

Turns persist the user prompt immediately, run the agent in a worker-owned DB
session, and persist the final assistant reply independently of the SSE client.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import SessionLocal
from models.db_models import ChatMessage, ChatTurn
from services import token_service
from services.chat_persistence import (
    create_session_for_user,
    get_session_for_user,
    save_assistant_message,
    save_user_message,
    update_session_after_messages,
)
from services.chat_service import get_chat_service

logger = logging.getLogger(__name__)


def _parse_sse_event(raw_event: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(raw_event.removeprefix("data: ").strip())
    except Exception:
        return None


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def turn_to_payload(turn: ChatTurn) -> Dict[str, Any]:
    return {
        "id": turn.id,
        "session_id": turn.session_id,
        "status": turn.status,
        "last_thinking_status": turn.last_thinking_status,
        "error_message": turn.error_message,
        "created_at": _iso(turn.created_at),
        "updated_at": _iso(turn.updated_at),
    }


def get_turn_for_user(db: Session, turn_id: int, user_id: int) -> Optional[ChatTurn]:
    turn = db.get(ChatTurn, turn_id)
    if turn is None or turn.user_id != user_id:
        return None
    return turn


def get_active_turn_for_session(db: Session, session_id: int, user_id: int) -> Optional[ChatTurn]:
    return (
        db.query(ChatTurn)
        .filter(
            ChatTurn.session_id == session_id,
            ChatTurn.user_id == user_id,
            ChatTurn.status == "running",
        )
        .order_by(ChatTurn.created_at.desc())
        .first()
    )


class ChatTurnService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[int, list[queue.Queue[Optional[Dict[str, Any]]]]] = {}

    def subscribe(self, turn_id: int) -> queue.Queue[Optional[Dict[str, Any]]]:
        q: queue.Queue[Optional[Dict[str, Any]]] = queue.Queue()
        with self._lock:
            self._subscribers.setdefault(turn_id, []).append(q)
        return q

    def unsubscribe(self, turn_id: int, q: queue.Queue[Optional[Dict[str, Any]]]) -> None:
        with self._lock:
            subscribers = self._subscribers.get(turn_id)
            if not subscribers:
                return
            self._subscribers[turn_id] = [item for item in subscribers if item is not q]
            if not self._subscribers[turn_id]:
                self._subscribers.pop(turn_id, None)

    def _publish(self, turn_id: int, payload: Optional[Dict[str, Any]]) -> None:
        with self._lock:
            subscribers = list(self._subscribers.get(turn_id, []))
        for q in subscribers:
            try:
                q.put_nowait(payload)
            except Exception:
                logger.debug("Dropping chat turn event for turn_id=%s", turn_id, exc_info=True)

    def prepare_turn(
        self,
        *,
        user_id: int,
        body_messages: List[Dict[str, str]],
        session_id: Optional[int],
    ) -> tuple[int, int, List[Dict[str, str]]]:
        db = SessionLocal()
        try:
            session = get_session_for_user(db, session_id, user_id) if session_id is not None else None
            if session_id is not None and session is None:
                raise ValueError("Session not found")
            if session is None:
                session = create_session_for_user(db, user_id)
                db.flush()

            history = [{"role": m.role, "content": m.content} for m in session.messages]
            next_sort_order = (
                db.query(func.max(ChatMessage.sort_order))
                .filter(ChatMessage.session_id == session.id)
                .scalar()
            )
            base_sort_order = (next_sort_order if next_sort_order is not None else -1) + 1
            user_message_id: Optional[int] = None
            for i, message in enumerate(body_messages):
                saved = save_user_message(db, session.id, message.get("content", ""), base_sort_order + i)
                user_message_id = saved.id
                history.append({"role": message.get("role", "user"), "content": message.get("content", "")})

            update_session_after_messages(
                db,
                session.id,
                first_user_content=body_messages[0].get("content") if body_messages else None,
            )

            turn = ChatTurn(
                session_id=session.id,
                user_id=user_id,
                status="running",
                user_message_id=user_message_id,
            )
            db.add(turn)
            db.flush()
            db.commit()
            return turn.id, session.id, history
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def run_turn_async(
        self,
        *,
        turn_id: int,
        session_id: int,
        user_id: int,
        messages: List[Dict[str, str]],
        context: Optional[Dict[str, Any]],
    ) -> None:
        thread = threading.Thread(
            target=self._execute_turn,
            kwargs={
                "turn_id": turn_id,
                "session_id": session_id,
                "user_id": user_id,
                "messages": messages,
                "context": context,
                "publish_events": True,
            },
            daemon=True,
        )
        thread.start()

    def run_turn_sync(
        self,
        *,
        turn_id: int,
        session_id: int,
        user_id: int,
        messages: List[Dict[str, str]],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return self._execute_turn(
            turn_id=turn_id,
            session_id=session_id,
            user_id=user_id,
            messages=messages,
            context=context,
            publish_events=False,
        )

    def _set_turn_state(
        self,
        db: Session,
        turn_id: int,
        *,
        status: Optional[str] = None,
        last_thinking_status: Optional[str] = None,
        error_message: Optional[str] = None,
        assistant_message_id: Optional[int] = None,
    ) -> None:
        turn = db.get(ChatTurn, turn_id)
        if turn is None:
            return
        if status is not None:
            turn.status = status
        turn.last_thinking_status = last_thinking_status
        turn.error_message = error_message
        if assistant_message_id is not None:
            turn.assistant_message_id = assistant_message_id
        turn.updated_at = datetime.utcnow()
        db.flush()

    def _complete_turn(
        self,
        *,
        db: Session,
        turn_id: int,
        session_id: int,
        user_id: int,
        content: str,
        tokens_used: int,
        model_metadata: Optional[Dict[str, Any]],
        tools_called: Optional[int],
        tool_calls: List[Dict[str, Any]],
        skill_events: List[Dict[str, Any]],
        charts: List[Dict[str, Any]],
        follow_up_questions: Optional[List[str]],
    ) -> Dict[str, Any]:
        next_sort_order = (
            db.query(func.max(ChatMessage.sort_order))
            .filter(ChatMessage.session_id == session_id)
            .scalar()
        )
        sort_order = (next_sort_order if next_sort_order is not None else -1) + 1

        assistant_message = save_assistant_message(
            db,
            session_id,
            content,
            sort_order,
            model_metadata=model_metadata,
            tools_called=tools_called,
            tool_calls=tool_calls or None,
            skill_events=skill_events or None,
            charts=charts or None,
            follow_up_questions=follow_up_questions,
        )

        try:
            token_service.deduct_for_chat(
                user_id,
                tokens_used,
                db,
                chat_message_id=assistant_message.id,
                model=str(model_metadata.get("model")) if model_metadata and model_metadata.get("model") else None,
                input_tokens=int(model_metadata.get("input_tokens")) if model_metadata and model_metadata.get("input_tokens") is not None else None,
                output_tokens=int(model_metadata.get("output_tokens")) if model_metadata and model_metadata.get("output_tokens") is not None else None,
                commit=False,
            )
        except Exception:
            logger.warning("Failed to deduct chat tokens for user_id=%s", user_id, exc_info=True)

        update_session_after_messages(db, session_id)
        self._set_turn_state(
            db,
            turn_id,
            status="completed",
            last_thinking_status=None,
            error_message=None,
            assistant_message_id=assistant_message.id,
        )
        db.commit()

        balance = token_service.get_balance(user_id, db)
        return {
            "type": "done",
            "turn_id": turn_id,
            "session_id": session_id,
            "tokens_used": tokens_used,
            "platform_tokens_used": token_service.llm_tokens_to_platform_tokens(tokens_used),
            "balance": balance,
            "tools_called": tools_called or 0,
            "follow_up_questions": follow_up_questions or [],
            "llm_usage": model_metadata or None,
            "content": content,
        }

    def _fail_turn(self, db: Session, turn_id: int, error_message: str) -> Dict[str, Any]:
        self._set_turn_state(
            db,
            turn_id,
            status="failed",
            last_thinking_status=None,
            error_message=error_message,
        )
        db.commit()
        return {
            "type": "error",
            "turn_id": turn_id,
            "content": error_message,
        }

    def _execute_turn(
        self,
        *,
        turn_id: int,
        session_id: int,
        user_id: int,
        messages: List[Dict[str, str]],
        context: Optional[Dict[str, Any]],
        publish_events: bool,
    ) -> Dict[str, Any]:
        db = SessionLocal()
        acc_content: List[str] = []
        acc_tool_calls: List[Dict[str, Any]] = []
        acc_charts: List[Dict[str, Any]] = []
        acc_skill_events: List[Dict[str, Any]] = []
        pending_skill_steps: List[Dict[str, Any]] = []
        last_thinking_status: Optional[str] = None
        final_payload: Optional[Dict[str, Any]] = None

        try:
            stream = get_chat_service().chat_stream(messages, user_id=user_id, db=db, context=context)
            for raw_event in stream:
                payload = _parse_sse_event(raw_event)
                if payload is None:
                    continue

                payload["turn_id"] = turn_id
                payload["session_id"] = session_id
                event_type = payload.get("type")

                if event_type == "thinking":
                    last_thinking_status = payload.get("content")
                    self._set_turn_state(
                        db,
                        turn_id,
                        status="running",
                        last_thinking_status=last_thinking_status,
                        error_message=None,
                    )
                    db.commit()
                elif event_type == "token" and payload.get("content"):
                    acc_content.append(payload["content"])
                elif event_type == "tool_call" and payload.get("name"):
                    acc_tool_calls.append(
                        {
                            "name": payload.get("name", ""),
                            "input": payload.get("input", ""),
                            "output": payload.get("output", ""),
                        }
                    )
                elif event_type == "chart" and payload.get("spec"):
                    acc_charts.append(payload["spec"])
                elif event_type == "skill_step":
                    pending_skill_steps.append(
                        {
                            "tool": payload.get("tool", ""),
                            "input": payload.get("input", ""),
                            "output": payload.get("output", ""),
                            "ok": payload.get("ok", True),
                        }
                    )
                elif event_type == "skill_done" and payload.get("name"):
                    acc_skill_events.append(
                        {"name": payload.get("name"), "steps": list(pending_skill_steps)}
                    )
                    pending_skill_steps = []
                elif event_type == "error":
                    raise RuntimeError(payload.get("content") or "Chat turn failed")
                elif event_type == "done":
                    final_payload = self._complete_turn(
                        db=db,
                        turn_id=turn_id,
                        session_id=session_id,
                        user_id=user_id,
                        content="".join(acc_content),
                        tokens_used=payload.get("tokens_used", 1),
                        model_metadata=payload.get("llm_usage"),
                        tools_called=payload.get("tools_called"),
                        tool_calls=acc_tool_calls,
                        skill_events=acc_skill_events,
                        charts=acc_charts,
                        follow_up_questions=payload.get("follow_up_questions"),
                    )
                    break

                if publish_events:
                    self._publish(turn_id, payload)

            if final_payload is None:
                raise RuntimeError("Chat turn ended without a completion event")

            if publish_events:
                self._publish(turn_id, final_payload)
            return final_payload
        except Exception as exc:
            logger.exception("Chat turn failed turn_id=%s", turn_id)
            error_payload = self._fail_turn(db, turn_id, str(exc))
            if publish_events:
                self._publish(turn_id, error_payload)
            return error_payload
        finally:
            if publish_events:
                self._publish(turn_id, None)
            db.close()


_chat_turn_service: Optional[ChatTurnService] = None


def get_chat_turn_service() -> ChatTurnService:
    global _chat_turn_service
    if _chat_turn_service is None:
        _chat_turn_service = ChatTurnService()
    return _chat_turn_service
