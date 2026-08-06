"""User deletion helpers that remove account-owned data explicitly."""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models.db_models import (
    ApiKey,
    ChatMessage,
    ChatSession,
    ChatTurn,
    Execution,
    Report,
    ReportView,
    Subscription,
    Usage,
    User,
    UserProfile,
    UserSchedule,
)


def delete_user_and_owned_data(db: Session, user_id: int) -> bool:
    """Delete a user and rows that carry user data, independent of DB cascade settings."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False

    owned_execution_ids = db.query(Execution.id).filter(Execution.creator_id == user_id)
    user_session_ids = db.query(ChatSession.id).filter(ChatSession.user_id == user_id)

    try:
        db.query(ReportView).filter(
            or_(
                ReportView.viewer_id == user_id,
                ReportView.execution_id.in_(owned_execution_ids),
            )
        ).delete(synchronize_session=False)
        db.query(Report).filter(Report.execution_id.in_(owned_execution_ids)).delete(
            synchronize_session=False
        )
        db.query(Execution).filter(Execution.creator_id == user_id).delete(
            synchronize_session=False
        )

        db.query(ChatTurn).filter(
            or_(
                ChatTurn.user_id == user_id,
                ChatTurn.session_id.in_(user_session_ids),
            )
        ).delete(synchronize_session=False)
        db.query(ChatMessage).filter(ChatMessage.session_id.in_(user_session_ids)).delete(
            synchronize_session=False
        )
        db.query(ChatSession).filter(ChatSession.user_id == user_id).delete(
            synchronize_session=False
        )

        db.query(Usage).filter(Usage.user_id == user_id).delete(synchronize_session=False)
        db.query(ApiKey).filter(ApiKey.user_id == user_id).delete(synchronize_session=False)
        db.query(UserSchedule).filter(UserSchedule.user_id == user_id).delete(
            synchronize_session=False
        )
        db.query(Subscription).filter(Subscription.user_id == user_id).delete(
            synchronize_session=False
        )
        db.query(UserProfile).filter(UserProfile.user_id == user_id).delete(
            synchronize_session=False
        )

        db.delete(user)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True
