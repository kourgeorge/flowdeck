"""Admin analytics service for comprehensive token usage and cost tracking."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, func, case
from sqlalchemy.orm import Session

from models.db_models import ChatMessage, ChatTurn, Execution, Report, Usage, User


def _parse_json(raw: Optional[str]) -> dict[str, Any]:
    """Parse JSON string safely."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _as_float(value: Any) -> Optional[float]:
    """Convert value to float safely."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_cost_breakdown_by_operation(
    db: Session,
    days: int = 30,
) -> dict[str, Any]:
    """
    Get LLM cost breakdown by operation type (chat, analysis, digest).
    
    Returns:
        {
            "period_days": int,
            "total_cost_usd": float,
            "total_llm_tokens": int,
            "operations": [
                {
                    "operation_type": str,  # "chat", "analysis", "digest"
                    "count": int,
                    "total_cost_usd": float,
                    "total_llm_tokens": int,
                    "avg_cost_usd": float,
                    "avg_llm_tokens": float
                }
            ]
        }
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get chat costs from ChatMessage metadata
    chat_messages_result = (
        db.query(
            func.count(ChatMessage.id).label("count"),
        )
        .join(ChatTurn, ChatTurn.assistant_message_id == ChatMessage.id)
        .filter(
            ChatMessage.created_at >= cutoff,
            ChatMessage.role == "assistant",
            ChatMessage.model_metadata_json.isnot(None),
        )
        .first()
    )
    
    # Calculate chat costs from metadata
    chat_cost = 0.0
    chat_tokens = 0
    chat_count = int(chat_messages_result[0] or 0) if chat_messages_result else 0
    
    # Get actual costs from chat messages
    chat_msgs_with_cost = (
        db.query(ChatMessage.model_metadata_json)
        .join(ChatTurn, ChatTurn.assistant_message_id == ChatMessage.id)
        .filter(
            ChatMessage.created_at >= cutoff,
            ChatMessage.role == "assistant",
            ChatMessage.model_metadata_json.isnot(None),
        )
        .all()
    )
    
    for (meta_json,) in chat_msgs_with_cost:
        meta = _parse_json(meta_json)
        cost = _as_float(meta.get("cost_usd"))
        if cost:
            chat_cost += cost
    
    # Get analysis costs from Report metadata
    analysis_reports = (
        db.query(Report.metadata_json)
        .join(Execution, Report.execution_id == Execution.id)
        .filter(
            Execution.execution_type == "ticker",
            Execution.created_at >= cutoff,
            Report.metadata_json.isnot(None),
        )
        .all()
    )
    
    analysis_cost = 0.0
    analysis_tokens = 0
    analysis_count = 0
    
    for (meta_json,) in analysis_reports:
        meta = _parse_json(meta_json)
        cost = _as_float(meta.get("cost_usd"))
        tokens = meta.get("total_tokens")
        if cost:
            analysis_cost += cost
        if tokens:
            analysis_tokens += int(tokens)
        analysis_count += 1
    
    # Get digest costs from Report metadata
    digest_reports = (
        db.query(Report.metadata_json)
        .join(Execution, Report.execution_id == Execution.id)
        .filter(
            Execution.execution_type == "daily_digest",
            Execution.created_at >= cutoff,
            Report.metadata_json.isnot(None),
        )
        .all()
    )
    
    digest_cost = 0.0
    digest_tokens = 0
    digest_count = 0
    
    for (meta_json,) in digest_reports:
        meta = _parse_json(meta_json)
        cost = _as_float(meta.get("cost_usd"))
        tokens = meta.get("total_tokens")
        if cost:
            digest_cost += cost
        if tokens:
            digest_tokens += int(tokens)
        digest_count += 1
    
    total_cost = chat_cost + analysis_cost + digest_cost
    total_tokens = chat_tokens + analysis_tokens + digest_tokens
    
    operations = [
        {
            "operation_type": "chat",
            "count": chat_count,
            "total_cost_usd": round(chat_cost, 6),
            "total_llm_tokens": chat_tokens,
            "avg_cost_usd": round(chat_cost / chat_count, 6) if chat_count > 0 else 0.0,
            "avg_llm_tokens": round(chat_tokens / chat_count, 2) if chat_count > 0 else 0.0,
        },
        {
            "operation_type": "analysis",
            "count": analysis_count,
            "total_cost_usd": round(analysis_cost, 6),
            "total_llm_tokens": analysis_tokens,
            "avg_cost_usd": round(analysis_cost / analysis_count, 6) if analysis_count > 0 else 0.0,
            "avg_llm_tokens": round(analysis_tokens / analysis_count, 2) if analysis_count > 0 else 0.0,
        },
        {
            "operation_type": "digest",
            "count": digest_count,
            "total_cost_usd": round(digest_cost, 6),
            "total_llm_tokens": digest_tokens,
            "avg_cost_usd": round(digest_cost / digest_count, 6) if digest_count > 0 else 0.0,
            "avg_llm_tokens": round(digest_tokens / digest_count, 2) if digest_count > 0 else 0.0,
        },
    ]
    
    return {
        "period_days": days,
        "total_cost_usd": round(total_cost, 6),
        "total_llm_tokens": total_tokens,
        "operations": operations,
    }


def get_cost_per_user(
    db: Session,
    days: int = 30,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Get cost per user over time period.
    
    Returns:
        {
            "period_days": int,
            "users": [
                {
                    "user_id": int,
                    "email": str,
                    "total_cost_usd": float,
                    "total_llm_tokens": int,
                    "operation_count": int,
                    "chat_count": int,
                    "analysis_count": int,
                    "digest_count": int
                }
            ]
        }
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get all users with activity
    users_data = {}
    
    # Chat costs per user
    chat_data = (
        db.query(
            ChatTurn.user_id,
            func.count(ChatTurn.id).label("count"),
        )
        .filter(
            ChatTurn.created_at >= cutoff,
            ChatTurn.status == "completed",
        )
        .group_by(ChatTurn.user_id)
        .all()
    )
    
    for user_id, count in chat_data:
        if user_id not in users_data:
            users_data[user_id] = {
                "chat_count": 0,
                "analysis_count": 0,
                "digest_count": 0,
                "total_cost": 0.0,
                "total_tokens": 0,
            }
        users_data[user_id]["chat_count"] = count
    
    # Get chat costs and tokens
    chat_messages = (
        db.query(
            ChatTurn.user_id,
            ChatMessage.model_metadata_json,
        )
        .join(ChatMessage, ChatTurn.assistant_message_id == ChatMessage.id)
        .filter(
            ChatTurn.created_at >= cutoff,
            ChatTurn.status == "completed",
            ChatMessage.model_metadata_json.isnot(None),
        )
        .all()
    )
    
    for user_id, meta_json in chat_messages:
        meta = _parse_json(meta_json)
        cost = _as_float(meta.get("cost_usd")) or 0.0
        tokens = meta.get("total_tokens") or 0
        if user_id in users_data:
            users_data[user_id]["total_cost"] += cost
            users_data[user_id]["total_tokens"] += int(tokens)
    
    # Analysis costs per user
    analysis_data = (
        db.query(
            Execution.creator_id,
            func.count(Execution.id).label("count"),
        )
        .filter(
            Execution.execution_type == "ticker",
            Execution.created_at >= cutoff,
        )
        .group_by(Execution.creator_id)
        .all()
    )
    
    for user_id, count in analysis_data:
        if user_id not in users_data:
            users_data[user_id] = {
                "chat_count": 0,
                "analysis_count": 0,
                "digest_count": 0,
                "total_cost": 0.0,
                "total_tokens": 0,
            }
        users_data[user_id]["analysis_count"] = count
    
    # Get analysis costs and tokens
    analysis_reports = (
        db.query(
            Execution.creator_id,
            Report.metadata_json,
        )
        .join(Report, Report.execution_id == Execution.id)
        .filter(
            Execution.execution_type == "ticker",
            Execution.created_at >= cutoff,
            Report.metadata_json.isnot(None),
        )
        .all()
    )
    
    for user_id, meta_json in analysis_reports:
        meta = _parse_json(meta_json)
        cost = _as_float(meta.get("cost_usd")) or 0.0
        tokens = meta.get("total_tokens") or 0
        if user_id in users_data:
            users_data[user_id]["total_cost"] += cost
            users_data[user_id]["total_tokens"] += int(tokens)
    
    # Digest costs per user
    digest_data = (
        db.query(
            Execution.creator_id,
            func.count(Execution.id).label("count"),
        )
        .filter(
            Execution.execution_type == "daily_digest",
            Execution.created_at >= cutoff,
        )
        .group_by(Execution.creator_id)
        .all()
    )
    
    for user_id, count in digest_data:
        if user_id not in users_data:
            users_data[user_id] = {
                "chat_count": 0,
                "analysis_count": 0,
                "digest_count": 0,
                "total_cost": 0.0,
                "total_tokens": 0,
            }
        users_data[user_id]["digest_count"] = count
    
    # Get digest costs and tokens
    digest_reports = (
        db.query(
            Execution.creator_id,
            Report.metadata_json,
        )
        .join(Report, Report.execution_id == Execution.id)
        .filter(
            Execution.execution_type == "daily_digest",
            Execution.created_at >= cutoff,
            Report.metadata_json.isnot(None),
        )
        .all()
    )
    
    for user_id, meta_json in digest_reports:
        meta = _parse_json(meta_json)
        cost = _as_float(meta.get("cost_usd")) or 0.0
        tokens = meta.get("total_tokens") or 0
        if user_id in users_data:
            users_data[user_id]["total_cost"] += cost
            users_data[user_id]["total_tokens"] += int(tokens)
    
    # Get user emails
    user_ids = list(users_data.keys())
    users = db.query(User.id, User.email).filter(User.id.in_(user_ids)).all()
    user_emails = {uid: email for uid, email in users}
    
    # Build result
    result_users = []
    for user_id, data in users_data.items():
        result_users.append({
            "user_id": user_id,
            "email": user_emails.get(user_id, f"[deleted user {user_id}]"),
            "total_cost_usd": round(data["total_cost"], 6),
            "total_llm_tokens": data["total_tokens"],
            "operation_count": data["chat_count"] + data["analysis_count"] + data["digest_count"],
            "chat_count": data["chat_count"],
            "analysis_count": data["analysis_count"],
            "digest_count": data["digest_count"],
        })
    
    # Sort by total cost descending
    result_users.sort(key=lambda x: x["total_cost_usd"], reverse=True)
    
    return {
        "period_days": days,
        "users": result_users[:limit],
    }


def get_most_expensive_operations(
    db: Session,
    days: int = 30,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Identify most expensive individual operations.
    
    Returns:
        {
            "period_days": int,
            "operations": [
                {
                    "operation_type": str,
                    "operation_id": int,
                    "user_id": int,
                    "user_email": str,
                    "subject": str,
                    "cost_usd": float,
                    "llm_tokens": int,
                    "created_at": str
                }
            ]
        }
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    operations = []
    
    # Get expensive chat operations
    chat_messages = (
        db.query(
            ChatMessage.id,
            ChatTurn.user_id,
            ChatTurn.session_id,
            ChatMessage.model_metadata_json,
            ChatMessage.created_at,
        )
        .join(ChatTurn, ChatTurn.assistant_message_id == ChatMessage.id)
        .filter(
            ChatMessage.created_at >= cutoff,
            ChatMessage.role == "assistant",
            ChatMessage.model_metadata_json.isnot(None),
        )
        .all()
    )
    
    for msg_id, user_id, session_id, meta_json, created_at in chat_messages:
        meta = _parse_json(meta_json)
        cost = _as_float(meta.get("cost_usd"))
        tokens = meta.get("total_tokens")
        if cost and cost > 0:
            operations.append({
                "operation_type": "chat",
                "operation_id": msg_id,
                "user_id": user_id,
                "subject": f"Chat session {session_id}",
                "cost_usd": cost,
                "llm_tokens": int(tokens) if tokens else 0,
                "created_at": created_at,
            })
    
    # Get expensive analysis operations
    analysis_reports = (
        db.query(
            Report.id,
            Execution.creator_id,
            Execution.subject_id,
            Report.metadata_json,
            Report.created_at,
        )
        .join(Execution, Report.execution_id == Execution.id)
        .filter(
            Execution.execution_type == "ticker",
            Report.created_at >= cutoff,
            Report.metadata_json.isnot(None),
        )
        .all()
    )
    
    for report_id, user_id, ticker, meta_json, created_at in analysis_reports:
        meta = _parse_json(meta_json)
        cost = _as_float(meta.get("cost_usd"))
        tokens = meta.get("total_tokens")
        if cost and cost > 0:
            operations.append({
                "operation_type": "analysis",
                "operation_id": report_id,
                "user_id": user_id,
                "subject": ticker or "Unknown",
                "cost_usd": cost,
                "llm_tokens": int(tokens) if tokens else 0,
                "created_at": created_at,
            })
    
    # Get expensive digest operations
    digest_reports = (
        db.query(
            Report.id,
            Execution.creator_id,
            Execution.subject_id,
            Report.metadata_json,
            Report.created_at,
        )
        .join(Execution, Report.execution_id == Execution.id)
        .filter(
            Execution.execution_type == "daily_digest",
            Report.created_at >= cutoff,
            Report.metadata_json.isnot(None),
        )
        .all()
    )
    
    for report_id, user_id, subject_id, meta_json, created_at in digest_reports:
        meta = _parse_json(meta_json)
        cost = _as_float(meta.get("cost_usd"))
        tokens = meta.get("total_tokens")
        if cost and cost > 0:
            operations.append({
                "operation_type": "digest",
                "operation_id": report_id,
                "user_id": user_id,
                "subject": subject_id or "Unknown",
                "cost_usd": cost,
                "llm_tokens": int(tokens) if tokens else 0,
                "created_at": created_at,
            })
    
    # Get user emails
    user_ids = list(set(op["user_id"] for op in operations))
    users = db.query(User.id, User.email).filter(User.id.in_(user_ids)).all()
    user_emails = {uid: email for uid, email in users}
    
    # Add emails and sort
    for op in operations:
        op["user_email"] = user_emails.get(op["user_id"], f"[deleted user {op['user_id']}]")
        op["created_at"] = op["created_at"].isoformat() if op["created_at"] else None
        op["cost_usd"] = round(op["cost_usd"], 6)
    
    operations.sort(key=lambda x: x["cost_usd"], reverse=True)
    
    return {
        "period_days": days,
        "operations": operations[:limit],
    }


def get_usage_trends(
    db: Session,
    days: int = 30,
) -> dict[str, Any]:
    """
    Get token usage and cost trends over time (daily aggregation).
    
    Returns:
        {
            "period_days": int,
            "daily_data": [
                {
                    "date": str,  # YYYY-MM-DD
                    "total_cost_usd": float,
                    "total_llm_tokens": int,
                    "chat_cost": float,
                    "analysis_cost": float,
                    "digest_cost": float,
                    "operation_count": int
                }
            ]
        }
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Initialize daily data structure
    daily_data = {}
    current = cutoff.date()
    end = datetime.now(timezone.utc).date()
    
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        daily_data[date_str] = {
            "date": date_str,
            "total_cost_usd": 0.0,
            "total_llm_tokens": 0,
            "chat_cost": 0.0,
            "analysis_cost": 0.0,
            "digest_cost": 0.0,
            "operation_count": 0,
        }
        current += timedelta(days=1)
    
    # Get chat data by day
    chat_messages = (
        db.query(
            func.date(ChatMessage.created_at).label("day"),
            ChatMessage.model_metadata_json,
        )
        .join(ChatTurn, ChatTurn.assistant_message_id == ChatMessage.id)
        .filter(
            ChatMessage.created_at >= cutoff,
            ChatMessage.role == "assistant",
            ChatMessage.model_metadata_json.isnot(None),
        )
        .all()
    )
    
    for day, meta_json in chat_messages:
        date_str = str(day)
        if date_str in daily_data:
            meta = _parse_json(meta_json)
            cost = _as_float(meta.get("cost_usd")) or 0.0
            tokens = meta.get("total_tokens") or 0
            daily_data[date_str]["chat_cost"] += cost
            daily_data[date_str]["total_cost_usd"] += cost
            daily_data[date_str]["total_llm_tokens"] += int(tokens)
            daily_data[date_str]["operation_count"] += 1
    
    # Get analysis data by day
    analysis_reports = (
        db.query(
            func.date(Report.created_at).label("day"),
            Report.metadata_json,
        )
        .join(Execution, Report.execution_id == Execution.id)
        .filter(
            Execution.execution_type == "ticker",
            Report.created_at >= cutoff,
            Report.metadata_json.isnot(None),
        )
        .all()
    )
    
    for day, meta_json in analysis_reports:
        date_str = str(day)
        if date_str in daily_data:
            meta = _parse_json(meta_json)
            cost = _as_float(meta.get("cost_usd")) or 0.0
            tokens = meta.get("total_tokens") or 0
            daily_data[date_str]["analysis_cost"] += cost
            daily_data[date_str]["total_cost_usd"] += cost
            daily_data[date_str]["total_llm_tokens"] += int(tokens)
            daily_data[date_str]["operation_count"] += 1
    
    # Get digest data by day
    digest_reports = (
        db.query(
            func.date(Report.created_at).label("day"),
            Report.metadata_json,
        )
        .join(Execution, Report.execution_id == Execution.id)
        .filter(
            Execution.execution_type == "daily_digest",
            Report.created_at >= cutoff,
            Report.metadata_json.isnot(None),
        )
        .all()
    )
    
    for day, meta_json in digest_reports:
        date_str = str(day)
        if date_str in daily_data:
            meta = _parse_json(meta_json)
            cost = _as_float(meta.get("cost_usd")) or 0.0
            tokens = meta.get("total_tokens") or 0
            daily_data[date_str]["digest_cost"] += cost
            daily_data[date_str]["total_cost_usd"] += cost
            daily_data[date_str]["total_llm_tokens"] += int(tokens)
            daily_data[date_str]["operation_count"] += 1
    
    # Round costs
    for data in daily_data.values():
        data["total_cost_usd"] = round(data["total_cost_usd"], 6)
        data["chat_cost"] = round(data["chat_cost"], 6)
        data["analysis_cost"] = round(data["analysis_cost"], 6)
        data["digest_cost"] = round(data["digest_cost"], 6)
    
    # Convert to sorted list
    result = sorted(daily_data.values(), key=lambda x: x["date"])
    
    return {
        "period_days": days,
        "daily_data": result,
    }


def get_model_usage_distribution(
    db: Session,
    days: int = 30,
) -> dict[str, Any]:
    """
    Get distribution of LLM model usage.
    
    Returns:
        {
            "period_days": int,
            "models": [
                {
                    "model": str,
                    "provider": str,
                    "count": int,
                    "total_cost_usd": float,
                    "total_tokens": int
                }
            ]
        }
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    model_data = {}
    
    # Get chat model usage
    chat_messages = (
        db.query(ChatMessage.model_metadata_json)
        .join(ChatTurn, ChatTurn.assistant_message_id == ChatMessage.id)
        .filter(
            ChatMessage.created_at >= cutoff,
            ChatMessage.role == "assistant",
            ChatMessage.model_metadata_json.isnot(None),
        )
        .all()
    )
    
    for (meta_json,) in chat_messages:
        meta = _parse_json(meta_json)
        model = meta.get("model", "unknown")
        provider = meta.get("provider", "unknown")
        cost = _as_float(meta.get("cost_usd")) or 0.0
        tokens = meta.get("total_tokens") or 0
        
        key = f"{provider}:{model}"
        if key not in model_data:
            model_data[key] = {
                "model": model,
                "provider": provider,
                "count": 0,
                "total_cost_usd": 0.0,
                "total_tokens": 0,
            }
        
        model_data[key]["count"] += 1
        model_data[key]["total_cost_usd"] += cost
        model_data[key]["total_tokens"] += int(tokens)
    
    # Get analysis/digest model usage from reports
    reports = (
        db.query(Report.metadata_json)
        .join(Execution, Report.execution_id == Execution.id)
        .filter(
            Report.created_at >= cutoff,
            Report.metadata_json.isnot(None),
        )
        .all()
    )
    
    for (meta_json,) in reports:
        meta = _parse_json(meta_json)
        
        # Try to get model info from models_used dict first, then fall back to direct fields
        models_used = meta.get("models_used", {})
        if isinstance(models_used, dict):
            model = models_used.get("model") or models_used.get("deep_think") or meta.get("model", "unknown")
            provider = models_used.get("provider") or meta.get("provider", "unknown")
        else:
            model = meta.get("model", "unknown")
            provider = meta.get("provider", "unknown")
        
        cost = _as_float(meta.get("cost_usd")) or 0.0
        tokens = meta.get("total_tokens") or 0
        
        key = f"{provider}:{model}"
        if key not in model_data:
            model_data[key] = {
                "model": model,
                "provider": provider,
                "count": 0,
                "total_cost_usd": 0.0,
                "total_tokens": 0,
            }
        
        model_data[key]["count"] += 1
        model_data[key]["total_cost_usd"] += cost
        model_data[key]["total_tokens"] += int(tokens)
    
    # Round costs and convert to list
    models = []
    for data in model_data.values():
        data["total_cost_usd"] = round(data["total_cost_usd"], 6)
        models.append(data)
    
    # Sort by cost descending
    models.sort(key=lambda x: x["total_cost_usd"], reverse=True)
    
    return {
        "period_days": days,
        "models": models,
    }


def get_cost_optimization_recommendations(
    db: Session,
    days: int = 30,
) -> dict[str, Any]:
    """
    Generate cost optimization recommendations based on usage patterns.
    
    Returns:
        {
            "period_days": int,
            "recommendations": [
                {
                    "priority": str,  # "high", "medium", "low"
                    "category": str,
                    "title": str,
                    "description": str,
                    "potential_savings_usd": float
                }
            ]
        }
    """
    recommendations = []
    
    # Get cost breakdown
    cost_breakdown = get_cost_breakdown_by_operation(db, days)
    total_cost = cost_breakdown["total_cost_usd"]
    
    # Get most expensive operations
    expensive_ops = get_most_expensive_operations(db, days, limit=10)
    
    # Recommendation 1: High-cost operations
    if expensive_ops["operations"]:
        top_op = expensive_ops["operations"][0]
        if top_op["cost_usd"] > 1.0:
            recommendations.append({
                "priority": "high",
                "category": "expensive_operations",
                "title": f"Review expensive {top_op['operation_type']} operations",
                "description": f"The most expensive {top_op['operation_type']} operation cost ${top_op['cost_usd']:.2f}. Consider optimizing prompts or reducing context size.",
                "potential_savings_usd": round(top_op["cost_usd"] * 0.3, 2),
            })
    
    # Recommendation 2: Operation type balance
    for op in cost_breakdown["operations"]:
        if op["count"] > 0 and op["total_cost_usd"] > total_cost * 0.5:
            recommendations.append({
                "priority": "medium",
                "category": "operation_balance",
                "title": f"{op['operation_type'].capitalize()} operations dominate costs",
                "description": f"{op['operation_type'].capitalize()} represents {(op['total_cost_usd']/total_cost*100):.1f}% of total costs. Consider optimizing {op['operation_type']} workflows.",
                "potential_savings_usd": round(op["total_cost_usd"] * 0.2, 2),
            })
    
    # Recommendation 3: Model usage
    model_dist = get_model_usage_distribution(db, days)
    if model_dist["models"]:
        expensive_model = model_dist["models"][0]
        if expensive_model["total_cost_usd"] > total_cost * 0.6:
            recommendations.append({
                "priority": "medium",
                "category": "model_selection",
                "title": f"Consider alternative to {expensive_model['model']}",
                "description": f"{expensive_model['model']} accounts for {(expensive_model['total_cost_usd']/total_cost*100):.1f}% of costs. Evaluate if cheaper models can handle some workloads.",
                "potential_savings_usd": round(expensive_model["total_cost_usd"] * 0.25, 2),
            })
    
    # Recommendation 4: Token efficiency
    for op in cost_breakdown["operations"]:
        if op["count"] > 0 and op["avg_llm_tokens"] > 10000:
            recommendations.append({
                "priority": "low",
                "category": "token_efficiency",
                "title": f"Optimize {op['operation_type']} token usage",
                "description": f"Average {op['operation_type']} uses {op['avg_llm_tokens']:.0f} tokens. Consider reducing context or using summarization.",
                "potential_savings_usd": round(op["total_cost_usd"] * 0.15, 2),
            })
    
    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda x: (priority_order[x["priority"]], -x["potential_savings_usd"]))
    
    return {
        "period_days": days,
        "recommendations": recommendations,
    }

# Made with Bob
