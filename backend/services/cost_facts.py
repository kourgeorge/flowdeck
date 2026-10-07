"""Snapshot usage alongside its source transaction, without retaining content."""
import json
import math

from sqlalchemy import select

from models.db_models import ChatMessage, ChatTurn, Execution, OperationCost, Report


def parse_metadata(raw):
    try:
        result = json.loads(raw) if isinstance(raw, str) else raw
        return result if isinstance(result, dict) else {}
    except (ValueError, TypeError):
        return {}


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else 0.0
    except (ValueError, TypeError, OverflowError):
        return 0.0


def token_count(meta):
    return int(number(meta.get("total_tokens"))) if meta.get("total_tokens") is not None else (
        int(number(meta.get("input_tokens"))) + int(number(meta.get("output_tokens"))))


def model_usage(meta):
    """Use measured per-call usage; keep unmeasured legacy costs unattributed."""
    cost, tokens = number(meta.get("cost_usd")), token_count(meta)
    config = meta.get("models_used") if isinstance(meta.get("models_used"), dict) else {}
    provider = str(meta.get("provider") or config.get("provider") or "unknown")
    calls = meta.get("per_call")
    parts = []
    if isinstance(calls, list):
        parts = [{"model": str(c.get("model") or "unattributed"), "provider": str(c.get("provider") or provider),
                  "cost_usd": number(c.get("cost_usd")), "total_tokens": token_count(c)}
                 for c in calls if isinstance(c, dict)]
    used_cost, used_tokens = sum(p["cost_usd"] for p in parts), sum(p["total_tokens"] for p in parts)
    if parts and used_cost <= cost + 0.000001 and used_tokens <= tokens:
        if cost - used_cost > 0.000001 or tokens > used_tokens:
            parts.append({"model": "unattributed", "provider": provider,
                          "cost_usd": max(0, cost - used_cost), "total_tokens": tokens - used_tokens})
        return parts
    model = meta.get("model")
    if not model and config.get("quick_think") == config.get("deep_think"):
        model = config.get("deep_think") or config.get("model")
    return [{"model": str(model or "unattributed"), "provider": provider,
             "cost_usd": cost, "total_tokens": tokens}]


def _write(connection, values, meta, *, backfill=False):
    table = OperationCost.__table__
    key = values["source_key"]
    exists = connection.execute(select(table.c.source_key).where(table.c.source_key == key)).first()
    if exists and backfill:
        return
    values.update(cost_usd=number(meta.get("cost_usd")), total_tokens=token_count(meta),
                  model_usage_json=json.dumps(model_usage(meta)))
    if exists:
        connection.execute(table.update().where(table.c.source_key == key).values(**values))
    else:
        connection.execute(table.insert().values(**values))


def capture_report(connection, report, *, backfill=False):
    ex = connection.execute(select(Execution.__table__).where(Execution.id == report.execution_id)).mappings().first()
    if not ex or ex["execution_type"] not in ("ticker", "daily_digest", "weekly_digest"):
        return
    _write(connection, {"source_key": f"execution:{ex['id']}:{report.report_type}",
        "operation_type": "analysis" if ex["execution_type"] == "ticker" else "digest",
        "operation_id": ex["id"], "user_id": ex["creator_id"],
        "subject": ex["subject_id"], "occurred_at": ex["created_at"]},
        parse_metadata(report.metadata_json), backfill=backfill)


def capture_turn(connection, turn, *, backfill=False):
    if turn.status != "completed" or not turn.assistant_message_id:
        return
    msg = connection.execute(select(ChatMessage.__table__).where(ChatMessage.id == turn.assistant_message_id)).mappings().first()
    if not msg or msg["role"] != "assistant":
        return
    _write(connection, {"source_key": f"chat:{turn.id}", "operation_type": "chat", "operation_id": turn.id,
        "user_id": turn.user_id, "subject": "Chat turn", "occurred_at": msg["created_at"]},
        parse_metadata(msg["model_metadata_json"]), backfill=backfill)


def backfill_cost_facts(engine):
    """Idempotent startup migration. Previously deleted content cannot be recovered."""
    from types import SimpleNamespace
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE IF NOT EXISTS schema_versions (version INTEGER PRIMARY KEY)")
        if connection.exec_driver_sql("SELECT 1 FROM schema_versions WHERE version=2").first():
            return
        # Stream metadata only, never report or conversation text.
        for row in connection.execute(select(Report.execution_id, Report.report_type, Report.metadata_json)).mappings():
            capture_report(connection, SimpleNamespace(**row), backfill=True)
        for row in connection.execute(select(ChatTurn.id, ChatTurn.user_id, ChatTurn.status,
                                             ChatTurn.assistant_message_id)).mappings():
            capture_turn(connection, SimpleNamespace(**row), backfill=True)
        connection.exec_driver_sql("INSERT INTO schema_versions(version) VALUES (2)")
