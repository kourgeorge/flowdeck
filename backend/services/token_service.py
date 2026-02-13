"""Token economy: balance, cost per analysis, rewards per unique view, cap and window."""

from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from models.db_models import User, AnalysisRun, ReportView

INITIAL_BALANCE = 1000
COST_PER_ANALYSIS = 200
EARNINGS_PER_UNIQUE_VIEW = 1
MAX_REWARD_PER_REPORT = 400
REWARD_WINDOW_DAYS = 14  # 0 = no window


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


def deduct_for_analysis(user_id: int, ticker: str, run_id: str, db: Session) -> bool:
    """
    Deduct COST_PER_ANALYSIS from user and create AnalysisRun. Returns False if insufficient balance.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    balance = getattr(user, "token_balance", None)
    if balance is None:
        user.token_balance = INITIAL_BALANCE
        db.flush()
        balance = user.token_balance
    if balance < COST_PER_ANALYSIS:
        return False
    try:
        user.token_balance -= COST_PER_ANALYSIS
        run = AnalysisRun(
            ticker=ticker.upper(),
            run_id=run_id,
            creator_id=user_id,
            earned_tokens=0,
        )
        db.add(run)
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False


def record_view(ticker: str, run_id: str, viewer_id: int, db: Session) -> bool:
    """
    Record a unique view. If new and eligible, credit creator 1 token.
    Returns True if a new view was recorded (and possibly credited).
    Rules: no self-views, earned_tokens < MAX_REWARD_PER_REPORT, optional 14-day window.
    """
    ticker_upper = ticker.upper()
    existing = (
        db.query(ReportView)
        .filter(
            ReportView.ticker == ticker_upper,
            ReportView.run_id == run_id,
            ReportView.viewer_id == viewer_id,
        )
        .first()
    )
    if existing:
        return False

    run = (
        db.query(AnalysisRun)
        .filter(
            AnalysisRun.ticker == ticker_upper,
            AnalysisRun.run_id == run_id,
        )
        .first()
    )

    view = ReportView(
        ticker=ticker_upper,
        run_id=run_id,
        viewer_id=viewer_id,
    )
    db.add(view)

    if not run:
        db.commit()
        return True

    # No self-views
    if run.creator_id == viewer_id:
        db.commit()
        return True

    # Cap
    if run.earned_tokens >= MAX_REWARD_PER_REPORT:
        db.commit()
        return True

    # Reward window (optional)
    if REWARD_WINDOW_DAYS > 0:
        cutoff = run.created_at
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > cutoff + timedelta(days=REWARD_WINDOW_DAYS):
            db.commit()
            return True

    creator = db.query(User).filter(User.id == run.creator_id).first()
    if creator is not None:
        creator.token_balance = getattr(creator, "token_balance", 0) + EARNINGS_PER_UNIQUE_VIEW
        run.earned_tokens += 1
    db.commit()
    return True


def refund_for_analysis(user_id: int, ticker: str, run_id: str, db: Session) -> None:
    """Refund COST_PER_ANALYSIS and remove AnalysisRun (e.g. when analysis was already running)."""
    run = (
        db.query(AnalysisRun)
        .filter(
            AnalysisRun.ticker == ticker.upper(),
            AnalysisRun.run_id == run_id,
            AnalysisRun.creator_id == user_id,
        )
        .first()
    )
    if run:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.token_balance = getattr(user, "token_balance", 0) + COST_PER_ANALYSIS
        db.delete(run)
        db.commit()


def top_up(user_id: int, amount: int, db: Session) -> None:
    """Add amount to user's token_balance. Use positive amount."""
    if amount <= 0:
        return
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return
    user.token_balance = getattr(user, "token_balance", 0) + amount
    db.commit()


def get_view_count(ticker: str, run_id: str, db: Session) -> int:
    """Return number of unique views for this run."""
    return (
        db.query(ReportView)
        .filter(
            ReportView.ticker == ticker.upper(),
            ReportView.run_id == run_id,
        )
        .count()
    )


def get_run_earned_tokens(ticker: str, run_id: str, db: Session) -> int:
    """Return earned_tokens for this run (0 if no AnalysisRun)."""
    run = (
        db.query(AnalysisRun)
        .filter(
            AnalysisRun.ticker == ticker.upper(),
            AnalysisRun.run_id == run_id,
        )
        .first()
    )
    return run.earned_tokens if run else 0
