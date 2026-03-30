#!/usr/bin/env python3
"""
Cleanup script for stuck executions in 'running' status.

This script identifies and marks as 'failed' any executions that have been
stuck in 'running' status for more than a specified time threshold.

Usage:
    python backend/scripts/cleanup_stuck_executions.py [--dry-run] [--hours HOURS]
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from database import SessionLocal
from models.db_models import Execution


def cleanup_stuck_executions(dry_run: bool = True, hours_threshold: int = 2):
    """
    Find and mark stuck executions as failed.
    
    Args:
        dry_run: If True, only report what would be done without making changes
        hours_threshold: Consider executions stuck if running for more than this many hours
    """
    db = SessionLocal()
    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)
        
        # Find all executions stuck in 'running' status
        stuck_executions = (
            db.query(Execution)
            .filter(
                Execution.status == "running",
                Execution.created_at < cutoff_time
            )
            .all()
        )
        
        if not stuck_executions:
            print(f"✓ No stuck executions found (threshold: {hours_threshold} hours)")
            return
        
        print(f"\nFound {len(stuck_executions)} stuck executions:")
        print(f"{'ID':<8} {'Type':<20} {'Subject':<30} {'Created At':<25} {'Age (hours)':<12}")
        print("-" * 100)
        
        for execution in stuck_executions:
            age_hours = (datetime.now(timezone.utc) - execution.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            print(
                f"{execution.id:<8} "
                f"{execution.execution_type:<20} "
                f"{execution.subject_id:<30} "
                f"{execution.created_at.strftime('%Y-%m-%d %H:%M:%S'):<25} "
                f"{age_hours:.1f}"
            )
        
        if dry_run:
            print(f"\n[DRY RUN] Would mark {len(stuck_executions)} executions as 'failed'")
            print("Run with --no-dry-run to apply changes")
        else:
            # Mark all as failed
            for execution in stuck_executions:
                execution.status = "failed"
                execution.error_message = f"Execution stuck in 'running' status for more than {hours_threshold} hours. Marked as failed by cleanup script."
                execution.completed_at = datetime.now(timezone.utc)
            
            db.commit()
            print(f"\n✓ Successfully marked {len(stuck_executions)} executions as 'failed'")
    
    except Exception as e:
        print(f"\n✗ Error during cleanup: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Cleanup stuck executions in 'running' status"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Only show what would be done without making changes (default: True)"
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_false",
        dest="dry_run",
        help="Actually apply the changes to the database"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=2,
        help="Consider executions stuck if running for more than this many hours (default: 2)"
    )
    
    args = parser.parse_args()
    
    print("=" * 100)
    print("Stuck Executions Cleanup Script")
    print("=" * 100)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Threshold: {args.hours} hours")
    print("=" * 100)
    
    cleanup_stuck_executions(dry_run=args.dry_run, hours_threshold=args.hours)


if __name__ == "__main__":
    main()

# Made with Bob
