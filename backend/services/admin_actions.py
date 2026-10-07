"""Transactional administrative mutations; callers translate domain errors to HTTP."""
import json

from sqlalchemy import text

from models.db_models import AnalysisJob, ChatTurn, Execution, Usage, User
from services import token_service


class AdminConflict(ValueError):
    pass


def grant_tokens(db, user_id: int, actor_id: int, amount: int, request_id: str, reason: str) -> int:
    db.execute(text("UPDATE users SET id=id WHERE id=:id"), {"id": user_id})
    if db.get(User, user_id) is None:
        raise LookupError("User not found")
    key = f"admin_grant:{actor_id}:{request_id}"
    previous = db.query(Usage).filter_by(operation_key=key).first()
    metadata = {"actor_id": actor_id, "reason": reason}
    if previous and (previous.user_id != user_id or previous.amount != amount
                     or json.loads(previous.metadata_json or '{}') != metadata):
        raise AdminConflict("Request ID was already used for a different grant")
    token_service.ensure_user_balance(user_id, db, commit=False)
    result = token_service.record_transaction(user_id, amount, "admin_adjustment", db,
        operation_key=key, metadata=metadata, description=reason, commit=False)
    if result is None:
        raise RuntimeError("Token grant could not be recorded")
    balance = token_service.get_balance_from_ledger(user_id, db)
    db.commit()
    return balance


def _settle_failed_execution(db, execution):
    if execution.status != "failed":
        return
    charges = db.query(Usage).filter(Usage.related_entity_type == "execution",
        Usage.related_entity_id == execution.id, Usage.transaction_type.in_(["analysis_cost", "digest_cost"]),
        Usage.amount < 0).all()
    for charge in charges:
        refund = token_service.record_transaction(charge.user_id, -charge.amount, "refund", db,
            related_entity_type="execution", related_entity_id=execution.id,
            metadata={"reason": "failed_execution_admin_deletion"}, commit=False)
        if refund is None:
            raise AdminConflict("Failed execution must be refunded before deletion")


def _require_terminal(db, execution):
    if execution.status not in ("completed", "failed") or db.query(AnalysisJob).filter(
        AnalysisJob.execution_id == execution.id, AnalysisJob.active_key.isnot(None)).first():
        raise AdminConflict("Stop this analysis and wait for it to finish before deleting it")


def delete_analysis(db, execution_id: int):
    db.execute(text("UPDATE executions SET id=id WHERE id=:id"), {"id": execution_id})
    execution = db.query(Execution).filter_by(id=execution_id).populate_existing().first()
    if execution is None:
        raise LookupError("Analysis not found")
    _require_terminal(db, execution)
    _settle_failed_execution(db, execution)
    db.delete(execution)
    db.commit()


def delete_user(db, user_id: int, actor_id: int):
    # Serialize last-admin checks as well as cascading work/ledger changes.
    db.execute(text("UPDATE users SET id=id WHERE is_admin=true OR id=:id"), {"id": user_id})
    user = db.query(User).filter_by(id=user_id).populate_existing().first()
    if user is None:
        raise LookupError("User not found")
    if user_id == actor_id:
        raise AdminConflict("You cannot delete your own administrator account")
    if user.is_admin and db.query(User).filter_by(is_admin=True).count() <= 1:
        raise AdminConflict("The last administrator cannot be deleted")
    executions = db.query(Execution).filter_by(creator_id=user_id).all()
    for execution in executions:
        _require_terminal(db, execution)
    if db.query(ChatTurn).filter_by(user_id=user_id, status="running").first():
        raise AdminConflict("Wait for this user's active chat to finish before deleting the account")
    for execution in executions:
        _settle_failed_execution(db, execution)
    db.delete(user)
    db.commit()
