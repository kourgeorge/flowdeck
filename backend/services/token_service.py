"""Token economy: balance, cost per analysis, rewards per unique view, cap and window."""

import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict

from sqlalchemy.orm import Session

from config import LLM_TOKENS_PER_PLATFORM_TOKEN
from models.db_models import User, Execution, ReportView, Usage

INITIAL_BALANCE = 1000
COST_PER_ANALYSIS = 200
# Cost per User Daily Brief (daily or weekly)
COST_PER_DIGEST = 20
EARNINGS_PER_UNIQUE_VIEW = 1
MAX_REWARD_PER_REPORT = 400
REWARD_WINDOW_DAYS = 14  # 0 = no window


def get_balance_from_ledger(user_id: int, db: Session) -> int:
    """
    Calculate user's token balance from Usage ledger (single source of truth).
    This is the authoritative balance calculation.
    """
    from sqlalchemy import func
    result = (
        db.query(func.coalesce(func.sum(Usage.amount), 0))
        .filter(Usage.user_id == user_id)
        .scalar()
    )
    return int(result) if result is not None else 0


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
) -> Optional[Usage]:
    """
    Record a token transaction in the ledger (single source of truth).
    User.token_balance is NO LONGER UPDATED - it's computed from the ledger.
    
    Args:
        amount: Platform tokens to add (positive) or deduct (negative)
        llm_tokens: Raw LLM token count (only for chat operations)
        related_entity_type: Type of related entity ("execution", "chat_message", etc.)
        related_entity_id: ID of the related entity
        metadata: Additional context (conversion_rate, model, ticker, etc.)
    
    Returns:
        Usage record or None on failure
    """
    # Lock user row to prevent concurrent transactions
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        return None
    
    # Get current balance from ledger (single source of truth)
    current_balance = get_balance_from_ledger(user_id, db)
    
    # Check sufficient balance for debits (negative amounts)
    if amount < 0 and current_balance < abs(amount):
        return None  # Insufficient balance
    
    # Calculate new balance
    new_balance = current_balance + amount
    if new_balance < 0:
        return None  # Safety check - should not happen after above check
    
    # Create transaction record (this IS the balance update - no separate User.token_balance update)
    tx = Usage(
        user_id=user_id,
        amount=amount,  # Platform tokens
        llm_tokens=llm_tokens,  # Raw LLM tokens (null for non-chat operations)
        balance_after=new_balance,  # Snapshot for verification
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
    """
    Ensure user has initial balance transaction if they have no transactions yet.
    This is for backward compatibility with users created before the ledger system.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return
    
    # Check if user has any transactions
    has_transactions = (
        db.query(Usage)
        .filter(Usage.user_id == user_id)
        .first()
    ) is not None
    
    if not has_transactions:
        # Create initial balance transaction
        record_transaction(
            user_id=user_id,
            amount=INITIAL_BALANCE,
            transaction_type="initial_balance",
            description="Initial token balance",
            db=db,
            commit=True,
        )


def get_balance(user_id: int, db: Session) -> int:
    """
    Return current token balance for the user (computed from Usage ledger).
    This is the single source of truth for token balances.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return 0
    
    # Ensure user has initial balance if no transactions exist
    ensure_user_balance(user_id, db)
    
    # Calculate balance from ledger (single source of truth)
    return get_balance_from_ledger(user_id, db)


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
    Balance is computed from Usage ledger (single source of truth).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return (False, None)
    
    # Ensure user has initial balance
    ensure_user_balance(user_id, db)
    
    # Check balance from ledger
    balance = get_balance_from_ledger(user_id, db)
    if balance < COST_PER_ANALYSIS:
        return (False, None)
    
    try:
        # Create execution first
        ex_id = record_execution(user_id, "ticker", "ticker", ticker.upper(), db, commit=False)
        
        # Record transaction (this updates the ledger)
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
    Balance is computed from Usage ledger (single source of truth).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return (False, None)
    
    # Ensure user has initial balance
    ensure_user_balance(user_id, db)
    
    # Check balance from ledger
    balance = get_balance_from_ledger(user_id, db)
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
        
        # Record transaction (this updates the ledger)
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
    Record a unique view. If new and eligible, credit creator 1 token via transaction ledger.
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

    # Credit creator via transaction ledger
    creator = db.query(User).filter(User.id == ex.creator_id).first()
    if creator is not None:
        record_transaction(
            user_id=ex.creator_id,
            amount=EARNINGS_PER_UNIQUE_VIEW,
            transaction_type="view_reward",
            related_entity_type="execution",
            related_entity_id=execution_id,
            metadata={"viewer_id": viewer_id},
            description=f"View reward for execution {execution_id}",
            db=db,
            commit=False,
        )
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
    """
    Refund COST_PER_ANALYSIS via transaction ledger and remove Execution
    (e.g. when analysis was already running - race condition).
    """
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
            # Refund via transaction ledger
            record_transaction(
                user_id=user_id,
                amount=COST_PER_ANALYSIS,
                transaction_type="refund",
                related_entity_type="execution",
                related_entity_id=execution_id,
                metadata={"reason": "duplicate_execution"},
                description=f"Refund for duplicate execution {execution_id}",
                db=db,
                commit=False,
            )
        db.delete(ex)
        db.commit()


def refund_for_failed_execution(execution_id: int, db: Session) -> bool:
    """
    Refund COST_PER_ANALYSIS for a failed execution via transaction ledger.
    Does NOT delete the execution (keeps it for audit trail with status='failed').
    Returns True if refund was successful, False otherwise.
    """
    ex = db.query(Execution).filter(Execution.id == execution_id).first()
    if not ex:
        return False
    
    # Only refund if execution is marked as failed
    if ex.status != "failed":
        return False
    
    # Check if already refunded (look for existing refund transaction)
    from models.db_models import Usage
    existing_refund = (
        db.query(Usage)
        .filter(
            Usage.related_entity_type == "execution",
            Usage.related_entity_id == execution_id,
            Usage.transaction_type == "refund",
        )
        .first()
    )
    if existing_refund:
        return False  # Already refunded
    
    # Get the original deduction transaction to extract metadata
    original_tx = (
        db.query(Usage)
        .filter(
            Usage.related_entity_type == "execution",
            Usage.related_entity_id == execution_id,
            Usage.transaction_type == "analysis_cost",
        )
        .first()
    )
    
    # Build refund metadata
    import json
    metadata = {"execution_id": execution_id, "reason": "analysis_failed"}
    if original_tx and original_tx.metadata_json:
        try:
            original_meta = json.loads(original_tx.metadata_json)
            if "ticker" in original_meta:
                metadata["ticker"] = original_meta["ticker"]
        except Exception:
            pass
    
    # Record refund transaction
    ticker_info = f" for {metadata.get('ticker', 'unknown')}" if "ticker" in metadata else ""
    tx = record_transaction(
        user_id=ex.creator_id,
        amount=COST_PER_ANALYSIS,  # Positive amount = credit
        transaction_type="refund",
        related_entity_type="execution",
        related_entity_id=execution_id,
        metadata=metadata,
        description=f"Refund for failed analysis{ticker_info}",
        db=db,
        commit=True,
    )
    
    return tx is not None


def refund_for_failed_chat(chat_message_id: int, db: Session) -> bool:
    """
    Refund tokens for a failed chat message via transaction ledger.
    Returns True if refund was successful, False otherwise.
    
    Note: Currently chat tokens are only deducted on successful completion,
    so this function is mainly for future use or manual corrections.
    """
    from models.db_models import Usage

    # Check if already refunded
    existing_refund = (
        db.query(Usage)
        .filter(
            Usage.related_entity_type == "chat_message",
            Usage.related_entity_id == chat_message_id,
            Usage.transaction_type == "refund",
        )
        .first()
    )
    if existing_refund:
        return False  # Already refunded
    
    # Get the original deduction transaction
    original_tx = (
        db.query(Usage)
        .filter(
            Usage.related_entity_type == "chat_message",
            Usage.related_entity_id == chat_message_id,
            Usage.transaction_type == "chat_cost",
        )
        .first()
    )
    
    if not original_tx:
        return False  # No original transaction found
    
    # Build refund metadata
    import json
    metadata = {"chat_message_id": chat_message_id, "reason": "chat_failed"}
    if original_tx.metadata_json:
        try:
            original_meta = json.loads(original_tx.metadata_json)
            metadata["original_metadata"] = original_meta
        except Exception:
            pass
    
    # Record refund transaction (refund the platform tokens that were deducted)
    tx = record_transaction(
        user_id=original_tx.user_id,
        amount=abs(original_tx.amount),  # Positive amount = credit (original was negative)
        llm_tokens=original_tx.llm_tokens,  # Keep track of LLM tokens for reference
        transaction_type="refund",
        related_entity_type="chat_message",
        related_entity_id=chat_message_id,
        metadata=metadata,
        description=f"Refund for failed chat message",
        db=db,
        commit=True,
    )
    
    return tx is not None


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
    Balance is computed from Usage ledger (single source of truth).
    """
    platform_tokens = llm_tokens_to_platform_tokens(llm_tokens)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    
    # Ensure user has initial balance
    ensure_user_balance(user_id, db)
    
    # Check balance from ledger
    balance = get_balance_from_ledger(user_id, db)
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
