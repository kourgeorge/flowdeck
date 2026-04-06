"""Token economy: balance, cost per analysis, rewards per unique view, cap and window."""

import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict

from sqlalchemy.orm import Session

from config import LLM_TOKENS_PER_PLATFORM_TOKEN
from models.db_models import User, Execution, ReportView, TokenTransaction

INITIAL_BALANCE = 1000
COST_PER_ANALYSIS = 200
# Cost per User Daily Brief (daily or weekly)
COST_PER_DIGEST = 20
EARNINGS_PER_UNIQUE_VIEW = 1
MAX_REWARD_PER_REPORT = 400
REWARD_WINDOW_DAYS = 14  # 0 = no window


def record_transaction(
    user_id: int,
    amount: int,  # Platform tokens (what affects balance)
    transaction_type: str,
    db: Session,
    *,
    llm_tokens: Optional[int] = None,  # Raw LLM token count (for chat)
    related_entity_type: Optional[str] = None,  # e.g., "execution", "chat_message"
    related_entity_id: Optional[int] = None,
    metadata: Optional[Dict] = None,
    description: Optional[str] = None,
    commit: bool = True,
) -> Optional[TokenTransaction]:
    """
    Record a token transaction and update user balance atomically.
    
    Args:
        amount: Platform tokens to add (positive) or deduct (negative)
        llm_tokens: Raw LLM token count (only for chat operations)
        related_entity_type: Type of related entity ("execution", "chat_message", etc.)
        related_entity_id: ID of the related entity
        metadata: Additional context (conversion_rate, model, ticker, etc.)
    
    Returns:
        TokenTransaction record or None on failure
    """
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        return None
    
    # Check sufficient balance for debits (negative amounts)
    if amount < 0 and user.token_balance < abs(amount):
        return None  # Insufficient balance
    
    # Update balance (platform tokens)
    new_balance = user.token_balance + amount
    if new_balance < 0:
        return None  # Safety check - should not happen after above check
    
    user.token_balance = new_balance
    
    # Create transaction record
    tx = TokenTransaction(
        user_id=user_id,
        amount=amount,  # Platform tokens
        llm_tokens=llm_tokens,  # Raw LLM tokens (null for non-chat operations)
        balance_after=new_balance,
        transaction_type=transaction_type,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        metadata_json=json.dumps(metadata) if metadata else None,
        description=description,
    )
    db.add(tx)
    
    if commit:
        db.commit()
        db.refresh(tx)
    else:
        db.flush()
    
    return tx

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
    Deduct COST_PER_ANALYSIS from user via transaction ledger and create Execution (ticker run).
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
        # Create execution first
        ex_id = record_execution(user_id, "ticker", "ticker", ticker.upper(), db, commit=False)
        
        # Record transaction
        metadata = {"ticker": ticker.upper(), "execution_id": ex_id}
        tx = record_transaction(
            user_id=user_id,
            amount=-COST_PER_ANALYSIS,
            transaction_type="analysis_cost",
            related_entity_type="execution",
            related_entity_id=ex_id,
            metadata=metadata,
            description=f"Analysis run for {ticker.upper()}",
            db=db,
            commit=False,
        )
        
        if tx:
            db.commit()
            return (True, ex_id)
        else:
            db.rollback()
            return (False, None)
    except Exception:
        db.rollback()
        return (False, None)


def deduct_for_digest(user_id: int, subject_id: str, db: Session) -> Tuple[bool, Optional[int]]:
    """
    Deduct COST_PER_DIGEST from user via transaction ledger and create Execution (daily/weekly digest run).
    subject_id: slot key, e.g. "user_id:YYYY-MM-DD" or "user_id:w:YYYY-MM-DD".
    Returns (True, execution_id) on success, (False, None) if insufficient balance or error.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return (False, None)
    balance = getattr(user, "token_balance", None)
    if balance is None:
        user.token_balance = INITIAL_BALANCE
        db.flush()
        balance = user.token_balance
    if balance < COST_PER_DIGEST:
        return (False, None)
    try:
        # Create execution first
        ex_id = record_execution(
            creator_id=user_id,
            execution_type="daily_digest",
            subject_type="user_date",
            subject_id=subject_id,
            db=db,
            commit=False,
        )
        
        # Record transaction
        metadata = {"subject_id": subject_id, "execution_id": ex_id}
        tx = record_transaction(
            user_id=user_id,
            amount=-COST_PER_DIGEST,
            transaction_type="digest_cost",
            related_entity_type="execution",
            related_entity_id=ex_id,
            metadata=metadata,
            description=f"Daily digest for {subject_id}",
            db=db,
            commit=False,
        )
        
        if tx:
            db.commit()
            return (True, ex_id)
        else:
            db.rollback()
            return (False, None)
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


def llm_tokens_to_platform_tokens(llm_tokens: int) -> int:
    """Convert LLM token count to platform tokens using configured ratio. Minimum 1."""
    if llm_tokens < 1:
        llm_tokens = 1
    # ceil(llm_tokens / ratio) without floating point
    platform = (llm_tokens + LLM_TOKENS_PER_PLATFORM_TOKEN - 1) // LLM_TOKENS_PER_PLATFORM_TOKEN
    return max(1, platform)


def deduct_for_chat(
    user_id: int,
    llm_tokens: int,
    db: Session,
    *,
    chat_message_id: Optional[int] = None,
    model: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    commit: bool = True
) -> bool:
    """
    Deduct chat cost via transaction ledger. llm_tokens is the raw LLM token count
    for the exchange; it is converted to platform tokens using LLM_TOKENS_PER_PLATFORM_TOKEN
    (e.g. 10000 LLM tokens = 1 platform token). Returns False if insufficient balance.
    Tracks both LLM tokens (actual usage) and platform tokens (what user pays).
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
        # Store detailed metadata for transparency and optimization
        metadata = {
            "conversion_rate": LLM_TOKENS_PER_PLATFORM_TOKEN,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        
        tx = record_transaction(
            user_id=user_id,
            amount=-platform_tokens,  # Platform tokens deducted
            llm_tokens=llm_tokens,  # Raw LLM tokens used
            transaction_type="chat_cost",
            related_entity_type="chat_message" if chat_message_id else None,
            related_entity_id=chat_message_id,
            metadata=metadata,
            description=f"Chat message ({llm_tokens:,} LLM tokens → {platform_tokens} platform tokens)",
            db=db,
            commit=commit,
        )
        return tx is not None
    except Exception:
        db.rollback()
        return False


def top_up(user_id: int, amount: int, db: Session, *, metadata: Optional[Dict] = None) -> bool:
    """
    Add tokens to user's balance via transaction ledger.
    Returns True on success, False on failure.
    """
    if amount <= 0:
        return False
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    
    description = f"Token purchase: {amount} tokens"
    tx = record_transaction(
        user_id=user_id,
        amount=amount,
        transaction_type="purchase",
        metadata=metadata,  # Can include: package_id, payment_id, price_usd
        description=description,
        db=db,
    )
    return tx is not None


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
