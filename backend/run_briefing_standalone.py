#!/usr/bin/env python3
"""
Standalone User Daily Brief runner for cron or CLI.

Usage:
  python backend/run_digest_standalone.py --user-id 1 [--date 2025-03-13] [--max-priority 5]

Prints the brief narrative and what_to_watch to stdout (JSON or text).
Requires backend and repo root on PYTHONPATH; uses DB and get_info_fetcher from backend.
LLM is obtained via ai_engine.llm_provider (same as chat/analysis); load backend/.env so
AZURE_OPENAI_* or OPENAI_API_KEY are available.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
for p in (str(REPO_ROOT), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Load backend .env so llm_provider sees AZURE_OPENAI_* / OPENAI_API_KEY
from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run User Daily Brief for a user")
    parser.add_argument("--user-id", type=int, required=True, help="User ID")
    parser.add_argument("--date", type=str, default=None, help="Digest date YYYY-MM-DD (default: today)")
    parser.add_argument("--max-priority", type=int, default=5, help="Max priority tickers (default 5)")
    parser.add_argument("--json", action="store_true", help="Output full result as JSON")
    args = parser.parse_args()

    from datetime import datetime
    digest_date = args.date or datetime.utcnow().strftime("%Y-%m-%d")

    from database import init_db, SessionLocal
    init_db()
    db = SessionLocal()
    try:
        from ai_engine.briefing_agent import run_digest
        from services import token_service
        from services.report_service import save_report

        result = run_digest(
            user_id=args.user_id,
            digest_date=digest_date,
            db=db,
            config=None,
            max_priority_tickers=args.max_priority,
        )

        # Persist digest as Execution + Report (creator = user, subject = user_id:date)
        try:
            subject_id = f"{args.user_id}:{digest_date}"
            execution_id = token_service.record_execution(
                creator_id=args.user_id,
                execution_type="daily_digest",
                subject_type="user_date",
                subject_id=subject_id,
                db=db,
            )
            metadata = {
                "digest_date": result.digest_date,
                "priority_tickers": result.priority_tickers,
                "what_to_watch": result.what_to_watch,
            }
            save_report(
                execution_id,
                "daily_digest",
                content=result.narrative,
                metadata=metadata,
            )
            logger.info(
                "Persisted standalone daily digest execution_id=%s user_id=%s date=%s",
                execution_id,
                args.user_id,
                digest_date,
            )
        except Exception as e:
            logger.exception(
                "Failed to persist standalone daily digest for user_id=%s date=%s: %s",
                args.user_id,
                digest_date,
                e,
            )

        if args.json:
            print(json.dumps({
                "narrative": result.narrative,
                "what_to_watch": result.what_to_watch,
                "digest_date": result.digest_date,
                "priority_tickers": result.priority_tickers,
            }, indent=2))
        else:
            print("# User Daily Brief", result.digest_date)
            print()
            print(result.narrative)
            print()
            print("## What to watch")
            print(result.what_to_watch)
    finally:
        db.close()


if __name__ == "__main__":
    main()
