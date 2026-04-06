"""Build exact per-user token usage history across analysis, chat, and digest operations."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session, aliased

from models.db_models import ChatMessage, ChatSession, ChatTurn, Execution, Report, Usage


def _as_utc(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()


def _parse_json(raw: Optional[str]) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _as_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _summarize_reports_for_executions(db: Session, execution_ids: list[int]) -> dict[int, dict[str, Any]]:
    usage_by_execution: dict[int, dict[str, Any]] = {}
    if not execution_ids:
        return usage_by_execution

    rows = (
        db.query(Report.execution_id, Report.metadata_json)
        .filter(Report.execution_id.in_(execution_ids))
        .all()
    )
    for execution_id, metadata_json in rows:
        if execution_id is None:
            continue
        meta = _parse_json(metadata_json)
        input_tokens = _as_int(meta.get("input_tokens")) or 0
        output_tokens = _as_int(meta.get("output_tokens")) or 0
        total_tokens = _as_int(meta.get("total_tokens"))
        cost_usd = _as_float(meta.get("cost_usd")) or 0.0
        existing = usage_by_execution.setdefault(
            execution_id,
            {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
            },
        )
        existing["input_tokens"] += input_tokens
        existing["output_tokens"] += output_tokens
        existing["total_tokens"] += total_tokens if total_tokens is not None else input_tokens + output_tokens
        existing["cost_usd"] += cost_usd
    return usage_by_execution


def _parse_digest_subject(subject_id: Optional[str]) -> tuple[str, str]:
    raw = str(subject_id or "")
    parts = raw.split(":", 2)
    if len(parts) < 2:
        return ("Daily digest", raw or "Unknown digest")
    slot = parts[1] if len(parts) == 2 else f"{parts[1]}:{parts[2]}"
    if slot.startswith("w:"):
        end_date = slot[2:] or "Unknown date"
        return ("Weekly digest", end_date)
    return ("Daily digest", slot or "Unknown date")


def get_user_usage_history(
    db: Session,
    user_id: int,
    *,
    days: int = 90,
    limit: int = 200,
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    safe_limit = max(1, min(limit, 500))

    execution_rows = (
        db.query(Usage, Execution)
        .outerjoin(
            Execution,
            and_(
                Usage.related_entity_type == "execution",
                Usage.related_entity_id == Execution.id,
            ),
        )
        .filter(
            Usage.user_id == user_id,
            Usage.amount < 0,
            Usage.transaction_type.in_(("analysis_cost", "digest_cost")),
            Usage.created_at >= cutoff,
        )
        .order_by(Usage.created_at.desc())
        .all()
    )

    execution_usage = _summarize_reports_for_executions(
        db,
        [execution.id for _tx, execution in execution_rows if execution is not None],
    )

    assistant_message = aliased(ChatMessage)
    chat_cost_tx = aliased(Usage)
    chat_rows = (
        db.query(ChatTurn, ChatSession, assistant_message, chat_cost_tx)
        .join(ChatSession, ChatSession.id == ChatTurn.session_id)
        .outerjoin(assistant_message, assistant_message.id == ChatTurn.assistant_message_id)
        .outerjoin(
            chat_cost_tx,
            and_(
                chat_cost_tx.user_id == user_id,
                chat_cost_tx.transaction_type == "chat_cost",
                chat_cost_tx.related_entity_type == "chat_message",
                chat_cost_tx.related_entity_id == assistant_message.id,
            ),
        )
        .filter(
            ChatTurn.user_id == user_id,
            ChatTurn.status == "completed",
            ChatTurn.created_at >= cutoff,
        )
        .order_by(ChatTurn.created_at.desc())
        .all()
    )

    items: list[dict[str, Any]] = []
    summary = {
        "period_days": days,
        "total_operations": 0,
        "total_platform_tokens": 0,
        "total_llm_tokens": 0,
        "analysis_count": 0,
        "analysis_platform_tokens": 0,
        "analysis_llm_tokens": 0,
        "chat_count": 0,
        "chat_platform_tokens": 0,
        "chat_llm_tokens": 0,
        "digest_count": 0,
        "digest_platform_tokens": 0,
        "digest_llm_tokens": 0,
    }

    for tx, execution in execution_rows:
        platform_tokens = abs(int(tx.amount or 0))
        report_usage = execution_usage.get(execution.id if execution else -1, {})
        llm_total = _as_int(report_usage.get("total_tokens"))
        input_tokens = _as_int(report_usage.get("input_tokens"))
        output_tokens = _as_int(report_usage.get("output_tokens"))
        cost_usd = _as_float(report_usage.get("cost_usd"))

        if tx.transaction_type == "analysis_cost":
            kind = "analysis"
            title = "AI analysis"
            subject_label = str((execution.subject_id if execution else None) or _parse_json(tx.metadata_json).get("ticker") or "Unknown ticker")
            identifier = execution.id if execution else tx.related_entity_id
            status = execution.status if execution else "completed"
            summary["analysis_count"] += 1
            summary["analysis_platform_tokens"] += platform_tokens
            summary["analysis_llm_tokens"] += llm_total or 0
        else:
            kind = "digest"
            title, subject_label = _parse_digest_subject(execution.subject_id if execution else _parse_json(tx.metadata_json).get("subject_id"))
            identifier = execution.id if execution else tx.related_entity_id
            status = execution.status if execution else "completed"
            summary["digest_count"] += 1
            summary["digest_platform_tokens"] += platform_tokens
            summary["digest_llm_tokens"] += llm_total or 0

        sort_at = _as_utc(tx.created_at)
        items.append(
            {
                "kind": kind,
                "title": title,
                "subject_label": subject_label,
                "status": status,
                "platform_tokens": platform_tokens,
                "llm_tokens": llm_total,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": round(cost_usd, 6) if cost_usd else None,
                "created_at": _to_iso(tx.created_at),
                "execution_id": identifier,
                "chat_turn_id": None,
                "chat_session_id": None,
                "tools_called": None,
                "_sort_at": sort_at,
            }
        )
        summary["total_operations"] += 1
        summary["total_platform_tokens"] += platform_tokens
        summary["total_llm_tokens"] += llm_total or 0

    for turn, session, message, linked_tx in chat_rows:
        if linked_tx is None:
            continue
        model_metadata = _parse_json(message.model_metadata_json if message else None)
        llm_total = _as_int(model_metadata.get("total_tokens"))
        input_tokens = _as_int(model_metadata.get("input_tokens"))
        output_tokens = _as_int(model_metadata.get("output_tokens"))
        if llm_total is None and linked_tx is not None:
            llm_total = _as_int(linked_tx.llm_tokens)
        platform_tokens = abs(int(linked_tx.amount or 0))
        cost_usd = _as_float(model_metadata.get("cost_usd"))
        created_at = message.created_at if message and message.created_at else turn.created_at
        title = session.title.strip() if session and session.title else "Chat session"

        items.append(
            {
                "kind": "chat",
                "title": title,
                "subject_label": f"Turn #{turn.id}",
                "status": turn.status,
                "platform_tokens": platform_tokens,
                "llm_tokens": llm_total,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": round(cost_usd, 6) if cost_usd else None,
                "created_at": _to_iso(created_at),
                "execution_id": None,
                "chat_turn_id": turn.id,
                "chat_session_id": session.id if session else turn.session_id,
                "tools_called": message.tools_called if message else None,
                "_sort_at": _as_utc(created_at),
            }
        )

        summary["total_operations"] += 1
        summary["chat_count"] += 1
        summary["chat_platform_tokens"] += int(platform_tokens or 0)
        summary["chat_llm_tokens"] += llm_total or 0
        summary["total_platform_tokens"] += int(platform_tokens or 0)
        summary["total_llm_tokens"] += llm_total or 0

    items.sort(key=lambda item: item["_sort_at"], reverse=True)
    trimmed_items = items[:safe_limit]
    for item in trimmed_items:
        item.pop("_sort_at", None)

    return {
        "summary": summary,
        "items": trimmed_items,
        "returned_operations": len(trimmed_items),
    }
