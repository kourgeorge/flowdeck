#!/usr/bin/env python3
"""
Delete failed executions from the database.

This script permanently removes execution records with 'failed' status,
optionally filtered by error message pattern or date range.

Usage:
    # Delete all failed executions (dry run)
    python backend/scripts/delete_failed_executions.py

    # Actually delete them
    python backend/scripts/delete_failed_executions.py --no-dry-run

    # Delete only stuck executions marked by cleanup script
    python backend/scripts/delete_failed_executions.py --no-dry-run --pattern "stuck in 'running' status"

    # Delete failed executions older than N days
    python backend/scripts/delete_failed_executions.py --no-dry-run --older-than-days 7
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from database import SessionLocal
from models.db_models import Execution, Report


def delete_failed_executions(
    dry_run: bool = True,
    error_pattern: str = None,
    older_than_days: int = None,
    user_email: str = None,
):
    """
    Delete failed executions from the database.
    
    Args:
        dry_run: If True, only report what would be deleted without making changes
        error_pattern: Only delete executions with error messages containing this pattern
        older_than_days: Only delete executions older than this many days
        user_email: Only delete executions for this user email
    """
    db = SessionLocal()
    try:
        # Build query
        query = db.query(Execution).filter(Execution.status == "failed")
        
        if error_pattern:
            query = query.filter(Execution.error_message.like(f"%{error_pattern}%"))
        
        if older_than_days is not None:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
            query = query.filter(Execution.created_at < cutoff_date)
        
        if user_email:
            from models.db_models import User
            user = db.query(User).filter(User.email == user_email).first()
            if not user:
                print(f"✗ User not found: {user_email}")
                return
            query = query.filter(Execution.creator_id == user.id)
        
        failed_executions = query.all()
        
        if not failed_executions:
            print("✓ No failed executions found matching criteria")
            return
        
        print(f"\nFound {len(failed_executions)} failed executions to delete:")
        print(f"{'ID':<8} {'Type':<20} {'Subject':<35} {'Created':<20} {'Error Preview'}")
        print("=" * 150)
        
        for execution in failed_executions:
            error_preview = ""
            if execution.error_message:
                error_preview = execution.error_message[:60] + "..." if len(execution.error_message) > 60 else execution.error_message
                error_preview = error_preview.replace("\n", " ")
            
            print(
                f"{execution.id:<8} "
                f"{execution.execution_type:<20} "
                f"{execution.subject_id:<35} "
                f"{execution.created_at.strftime('%Y-%m-%d %H:%M:%S'):<20} "
                f"{error_preview}"
            )
        
        if dry_run:
            print(f"\n[DRY RUN] Would delete {len(failed_executions)} executions and their associated reports")
            print("Run with --no-dry-run to actually delete")
        else:
            # Delete associated reports first (foreign key constraint)
            deleted_reports = 0
            for execution in failed_executions:
                reports = db.query(Report).filter(Report.execution_id == execution.id).all()
                for report in reports:
                    db.delete(report)
                    deleted_reports += 1
            
            # Delete executions
            for execution in failed_executions:
                db.delete(execution)
            
            db.commit()
            print(f"\n✓ Successfully deleted:")
            print(f"  - {len(failed_executions)} executions")
            print(f"  - {deleted_reports} associated reports")
    
    except Exception as e:
        print(f"\n✗ Error during deletion: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Delete failed executions from the database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (default)
  python backend/scripts/delete_failed_executions.py

  # Delete all failed executions
  python backend/scripts/delete_failed_executions.py --no-dry-run

  # Delete only stuck executions marked by cleanup script
  python backend/scripts/delete_failed_executions.py --no-dry-run --pattern "stuck in 'running' status"

  # Delete failed executions older than 7 days
  python backend/scripts/delete_failed_executions.py --no-dry-run --older-than-days 7

  # Delete failed executions for specific user
  python backend/scripts/delete_failed_executions.py --no-dry-run --user kourgeorge@gmail.com
        """
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Only show what would be deleted without making changes (default: True)"
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_false",
        dest="dry_run",
        help="Actually delete the executions from the database"
    )
    parser.add_argument(
        "--pattern",
        type=str,
        help="Only delete executions with error messages containing this pattern"
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        help="Only delete executions older than this many days"
    )
    parser.add_argument(
        "--user",
        type=str,
        help="Only delete executions for this user email"
    )
    
    args = parser.parse_args()
    
    print("=" * 150)
    print("Delete Failed Executions Script")
    print("=" * 150)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE - WILL DELETE'}")
    if args.pattern:
        print(f"Error pattern filter: '{args.pattern}'")
    if args.older_than_days:
        print(f"Age filter: older than {args.older_than_days} days")
    if args.user:
        print(f"User filter: {args.user}")
    print("=" * 150)
    
    if not args.dry_run:
        confirm = input("\n⚠️  This will PERMANENTLY DELETE executions. Are you sure? (yes/no): ")
        if confirm.lower() != "yes":
            print("Aborted.")
            return
    
    delete_failed_executions(
        dry_run=args.dry_run,
        error_pattern=args.pattern,
        older_than_days=args.older_than_days,
        user_email=args.user,
    )


if __name__ == "__main__":
    main()

# Made with Bob
