"""Token economy: balance, cost per analysis, rewards per unique view, cap and window."""

from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from config import LLM_TOKENS_PER_PLATFORM_TOKEN
from models.db_models import User, Execution, ReportView

INITIAL_BALANCE = 1000
COST_PER_ANALYSIS = 200
EARNINGS_PER_UNIQUE_VIEW = 1
MAX_REWARD_PER_REPORT = 400
REWARD_WINDOW_DAYS = 14  # 0 = no window

SYSTEM_USER_EMAIL = "system@flowdeck.internal"


def get_system_user_id(db: Session) -> int:
    """Return user id for the system account (sync/cron runs). Creates the user if missing."""
    user = db.query(User).filter(User.email == SYSTEM_USER_EMAIL).first()
    if user:
        return user.id
    user = User(
        email=SYSTEM_USER_EMAIL,
        name="System",
        token_balance=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user.id


def ensure_user_balance(user_id: int, db: Session) -> None:
    """Set token_balance to INITIAL_BALANCE for legacy users missing the column (idempotent)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return
    if getattr(user, "token_balance", None) is None:
        user.token_balance = INITIAL_BALANCE
        db.commit()


def get_balance(user_id: int, db: Session) -> int:
    """Return current token balance for the user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return 0
    balance = getattr(user, "token_balance", None)
    if balance is None:
        ensure_user_balance(user_id, db)
        db.refresh(user)
        return getattr(user, "token_balance", 0)
    return balance


def record_execution(
    creator_id: int,
    execution_type: str,
    subject_type: str,
    subject_id: str,
    db: Session,
    *,
    commit: bool = True,
) -> Optional[int]:
    """
    Create an Execution and return its id. Does not deduct tokens.
    If commit=True (default), commits and returns id. If commit=False, flushes so id is set and caller must commit.
    """
    ex = Execution(
        execution_type=execution_type,
        subject_type=subject_type,
        subject_id=subject_id,
        creator_id=creator_id,
        earned_tokens=0,
    )
    db.add(ex)
    if commit:
        db.commit()
        db.refresh(ex)
        return ex.id
    db.flush()
    return ex.id


def record_analysis_run(creator_id: int, ticker: str, db: Session) -> Optional[int]:
    """
    Record a ticker analysis run without deducting tokens (e.g. admin/mission-control runs).
    Wrapper around record_execution(..., "ticker", "ticker", ticker).
    """
    return record_execution(creator_id, "ticker", "ticker", ticker.upper(), db)


def deduct_for_analysis(user_id: int, ticker: str, db: Session) -> Tuple[bool, Optional[int]]:
    """
    Deduct COST_PER_ANALYSIS from user and create Execution (ticker run).
    Returns (True, execution_id) on success, (False, None) if insufficient balance.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return (False, None)
    balance = getattr(user, "token_balance", None)
    if balance is None:
        user.token_balance = INITIAL_BALANCE
        db.flush()
        balance = user.token_balance
    if balance < COST_PER_ANALYSIS:
        return (False, None)
    try:
        user.token_balance -= COST_PER_ANALYSIS
        ex_id = record_execution(user_id, "ticker", "ticker", ticker.upper(), db, commit=False)
        db.commit()
        return (True, ex_id)
    except Exception:
        db.rollback()
        return (False, None)


def record_view(execution_id: int, viewer_id: int, db: Session) -> bool:
    """
    Record a unique view. If new and eligible, credit creator 1 token.
    Returns True if a new view was recorded (and possibly credited).
    Rules: no self-views, earned_tokens < MAX_REWARD_PER_REPORT, optional 14-day window.
    """
    ex = db.query(Execution).filter(Execution.id == execution_id).first()
    if not ex:
        return False

    existing = (
        db.query(ReportView)
        .filter(
            ReportView.execution_id == execution_id,
            ReportView.viewer_id == viewer_id,
        )
        .first()
    )
    if existing:
        return False

    view = ReportView(
        viewer_id=viewer_id,
        execution_id=execution_id,
    )
    db.add(view)

    # No self-views
    if ex.creator_id == viewer_id:
        db.commit()
        return True

    # Cap
    if ex.earned_tokens >= MAX_REWARD_PER_REPORT:
        db.commit()
        return True

    # Reward window (optional)
    if REWARD_WINDOW_DAYS > 0:
        cutoff = ex.created_at
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > cutoff + timedelta(days=REWARD_WINDOW_DAYS):
            db.commit()
            return True

    creator = db.query(User).filter(User.id == ex.creator_id).first()
    if creator is not None:
        creator.token_balance = getattr(creator, "token_balance", 0) + EARNINGS_PER_UNIQUE_VIEW
        ex.earned_tokens += 1
    db.commit()
    return True


def delete_execution(execution_id: int, db: Session) -> None:
    """Remove Execution without refunding (e.g. admin race when start_analysis returned existing=True)."""
    ex = db.query(Execution).filter(Execution.id == execution_id).first()
    if ex:
        db.delete(ex)
        db.commit()


def delete_analysis_run(execution_id: int, db: Session) -> None:
    """Backward-compat alias for delete_execution."""
    delete_execution(execution_id, db)


def refund_for_execution(user_id: int, execution_id: int, db: Session) -> None:
    """Refund COST_PER_ANALYSIS and remove Execution (e.g. when analysis was already running)."""
    ex = (
        db.query(Execution)
        .filter(
            Execution.id == execution_id,
            Execution.creator_id == user_id,
        )
        .first()
    )
    if ex:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.token_balance = getattr(user, "token_balance", 0) + COST_PER_ANALYSIS
        db.delete(ex)
        db.commit()


def refund_for_analysis(user_id: int, execution_id: int, db: Session) -> None:
    """Backward-compat alias for refund_for_execution."""
    refund_for_execution(user_id, execution_id, db)


def llm_tokens_to_platform_tokens(llm_tokens: int) -> int:
    """Convert LLM token count to platform tokens using configured ratio. Minimum 1."""
    if llm_tokens < 1:
        llm_tokens = 1
    # ceil(llm_tokens / ratio) without floating point
    platform = (llm_tokens + LLM_TOKENS_PER_PLATFORM_TOKEN - 1) // LLM_TOKENS_PER_PLATFORM_TOKEN
    return max(1, platform)


def deduct_for_chat(user_id: int, llm_tokens: int, db: Session) -> bool:
    """
    Deduct chat cost from user's token_balance. llm_tokens is the raw LLM token count
    for the exchange; it is converted to platform tokens using LLM_TOKENS_PER_PLATFORM_TOKEN
    (e.g. 10000 LLM tokens = 1 platform token). Returns False if insufficient balance.
    Deducts at least 1 platform token; floors balance at 0.
    """
    platform_tokens = llm_tokens_to_platform_tokens(llm_tokens)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    balance = getattr(user, "token_balance", None)
    if balance is None:
        user.token_balance = INITIAL_BALANCE
        db.flush()
        balance = user.token_balance
    if balance < 1:
        return False
    try:
        user.token_balance = max(0, balance - platform_tokens)
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False


def top_up(user_id: int, amount: int, db: Session) -> None:
    """Add amount to user's token_balance. Use positive amount."""
    if amount <= 0:
        return
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return
    user.token_balance = getattr(user, "token_balance", 0) + amount
    db.commit()


def get_view_count(execution_id: int, db: Session) -> int:
    """Return number of unique views for this execution."""
    return (
        db.query(ReportView)
        .filter(ReportView.execution_id == execution_id)
        .count()
    )


def get_run_earned_tokens(execution_id: int, db: Session) -> int:
    """Return earned_tokens for this execution (0 if not found)."""
    ex = db.query(Execution).filter(Execution.id == execution_id).first()
    return ex.earned_tokens if ex else 0
