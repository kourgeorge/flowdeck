"""Recover interrupted operations before a single-instance server accepts traffic."""
from datetime import datetime
from models.db_models import AnalysisJob, ChatReservation, ChatTurn, Execution
from services import token_service


def recover_interrupted_work():
    from database import SessionLocal
    from services.data_cache import clear_stop_requested, delete_analysis_status
    with SessionLocal() as db:
        interrupted = db.query(Execution).filter(Execution.status.in_(['queued', 'running'])).all()
        for execution in interrupted:
            execution.status = 'failed'
            execution.error_message = 'Server restarted before this operation completed. Any charge is refunded.'
            execution.completed_at = datetime.utcnow()
        for job in db.query(AnalysisJob).filter(AnalysisJob.active_key.isnot(None)):
            job.active_key = None
        ids = [row.id for row in interrupted]
        db.commit()
    for run_id in ids:
        delete_analysis_status('ticker', run_id)
        clear_stop_requested(run_id)
    reconcile_failed_charges()
    with SessionLocal() as db:
        for reservation in db.query(ChatReservation).filter_by(settled=False).all():
            token_service.record_transaction(reservation.user_id, reservation.amount, 'chat_release', db,
                commit=False, related_entity_type='chat_turn', related_entity_id=reservation.turn_id)
            reservation.settled = True
        for turn in db.query(ChatTurn).filter_by(status='running').all():
            turn.status = 'failed'
            turn.error_message = 'Server restarted. Reserved tokens were released.'
        db.commit()


def reconcile_failed_charges():
    from database import SessionLocal
    with SessionLocal() as db:
        failed = [(r.id, r.execution_type) for r in db.query(Execution).filter_by(status='failed')]
    for run_id, kind in failed:
        with SessionLocal() as db:
            if kind == 'ticker':
                token_service.refund_for_failed_execution(run_id, db)
            elif kind in ('daily_digest', 'weekly_digest'):
                token_service.refund_for_failed_digest(run_id, db)
