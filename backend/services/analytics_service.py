"""Consistent admin analytics from retained, content-free operation cost facts.

All views attribute an operation's saved costs to its start time (assistant
message time for chat). One execution/turn is one operation in every view.
"""
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from typing import Any
from models.db_models import OperationCost, User


KINDS = ("chat", "analysis", "digest")


def _load_operations(db, days):
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    rows = db.query(OperationCost).filter(OperationCost.occurred_at >= cutoff).all()
    operations = {}
    for fact in rows:
        key = (fact.operation_type, fact.operation_id)
        op = operations.setdefault(key, {"operation_type": fact.operation_type,
            "operation_id": fact.operation_id, "user_id": fact.user_id,
            "subject": fact.subject, "created_at": fact.occurred_at,
            "cost_usd": 0.0, "llm_tokens": 0, "models": []})
        op["cost_usd"] += fact.cost_usd
        op["llm_tokens"] += fact.total_tokens
        op["models"].extend(json.loads(fact.model_usage_json))
    return list(operations.values())


def _emails(db, operations):
    ids = {op["user_id"] for op in operations}
    return dict(db.query(User.id, User.email).filter(User.id.in_(ids)).all())


def get_cost_breakdown_by_operation(db, days=30, *, _ops=None):
    operations = _load_operations(db, days) if _ops is None else _ops
    result = []
    for kind in KINDS:
        selected = [op for op in operations if op["operation_type"] == kind]
        count = len(selected)
        cost = sum(op["cost_usd"] for op in selected)
        tokens = sum(op["llm_tokens"] for op in selected)
        result.append({"operation_type": kind, "count": count, "total_cost_usd": round(cost, 6),
            "total_llm_tokens": tokens, "avg_cost_usd": round(cost/count, 6) if count else 0,
            "avg_llm_tokens": round(tokens/count, 2) if count else 0})
    return {"period_days": days, "total_cost_usd": round(sum(op["cost_usd"] for op in operations), 6),
            "total_llm_tokens": sum(op["llm_tokens"] for op in operations), "operations": result}


def get_cost_per_user(db, days=30, limit=100):
    operations = _load_operations(db, days)
    emails = _emails(db, operations)
    users = {}
    for op in operations:
        uid = op["user_id"]
        user = users.setdefault(uid, {"user_id": uid, "email": emails.get(uid, f"[deleted user {uid}]"),
            "total_cost_usd": 0.0, "total_llm_tokens": 0, "operation_count": 0,
            "chat_count": 0, "analysis_count": 0, "digest_count": 0})
        user["total_cost_usd"] += op["cost_usd"]
        user["total_llm_tokens"] += op["llm_tokens"]
        user["operation_count"] += 1
        user[op["operation_type"] + "_count"] += 1
    for user in users.values():
        user["total_cost_usd"] = round(user["total_cost_usd"], 6)
    return {"period_days": days, "users": sorted(users.values(),
        key=lambda user: (-user["total_cost_usd"], user["user_id"]))[:limit]}


def get_most_expensive_operations(db, days=30, limit=50, *, _ops=None):
    operations = _load_operations(db, days) if _ops is None else _ops
    emails = _emails(db, operations)
    result = []
    for op in sorted(operations, key=lambda op: (-op["cost_usd"], op["operation_id"]))[:limit]:
        result.append({k: v for k, v in op.items() if k not in ("models", "created_at", "cost_usd")})
        result[-1].update(cost_usd=round(op["cost_usd"], 6),
            created_at=op["created_at"].replace(tzinfo=timezone.utc).isoformat(),
            user_email=emails.get(op["user_id"], f"[deleted user {op['user_id']}]") )
    return {"period_days": days, "operations": result}


def get_usage_trends(db, days=30):
    operations = _load_operations(db, days)
    today = datetime.now(timezone.utc).date()
    daily = {}
    # Rolling windows include part of the first calendar day and today.
    for i in range(days + 1):
        day = (today - timedelta(days=i)).isoformat()
        daily[day] = {"date": day, "total_cost_usd": 0.0, "total_llm_tokens": 0,
                      "operation_count": 0, "chat_cost": 0.0, "analysis_cost": 0.0, "digest_cost": 0.0}
    for op in operations:
        data = daily[op["created_at"].date().isoformat()]
        data["total_cost_usd"] += op["cost_usd"]
        data[op["operation_type"] + "_cost"] += op["cost_usd"]
        data["total_llm_tokens"] += op["llm_tokens"]
        data["operation_count"] += 1
    for data in daily.values():
        for key in ("total_cost_usd", "chat_cost", "analysis_cost", "digest_cost"):
            data[key] = round(data[key], 6)
    return {"period_days": days, "daily_data": sorted(daily.values(), key=lambda data: data["date"])}


def get_model_usage_distribution(db, days=30, *, _ops=None):
    operations = _load_operations(db, days) if _ops is None else _ops
    models = {}
    for op in operations:
        seen = set()
        for part in op["models"]:
            key = (part["provider"], part["model"])
            model = models.setdefault(key, {"provider": key[0], "model": key[1], "count": 0,
                                           "total_cost_usd": 0.0, "total_tokens": 0})
            if key not in seen:
                model["count"] += 1
                seen.add(key)
            model["total_cost_usd"] += part["cost_usd"]
            model["total_tokens"] += part["total_tokens"]
    for model in models.values():
        model["total_cost_usd"] = round(model["total_cost_usd"], 6)
    return {"period_days": days, "models": sorted(models.values(), key=lambda m: -m["total_cost_usd"])}


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
    operations = _load_operations(db, days)
    
    # Get cost breakdown
    cost_breakdown = get_cost_breakdown_by_operation(db, days, _ops=operations)
    total_cost = cost_breakdown["total_cost_usd"]
    
    # Get most expensive operations
    expensive_ops = get_most_expensive_operations(db, days, limit=10, _ops=operations)
    
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
        if total_cost > 0 and op["count"] > 0 and op["total_cost_usd"] > total_cost * 0.5:
            recommendations.append({
                "priority": "medium",
                "category": "operation_balance",
                "title": f"{op['operation_type'].capitalize()} operations dominate costs",
                "description": f"{op['operation_type'].capitalize()} represents {(op['total_cost_usd']/total_cost*100):.1f}% of total costs. Consider optimizing {op['operation_type']} workflows.",
                "potential_savings_usd": round(op["total_cost_usd"] * 0.2, 2),
            })
    
    # Recommendation 3: Model usage
    model_dist = get_model_usage_distribution(db, days, _ops=operations)
    if model_dist["models"]:
        expensive_model = model_dist["models"][0]
        if total_cost > 0 and expensive_model["model"] != "unattributed" and expensive_model["total_cost_usd"] > total_cost * 0.6:
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
