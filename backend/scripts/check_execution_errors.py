#!/usr/bin/env python3
"""
Check execution errors in the database.

This script queries the executions table to find failed executions
and display their error messages.

Usage:
    python backend/scripts/check_execution_errors.py [--limit N] [--status STATUS]
"""

import argparse
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from database import SessionLocal
from models.db_models import Execution


def check_execution_errors(limit: int = 50, status: str = None):
    """
    Query and display execution errors.
    
    Args:
        limit: Maximum number of executions to display
        status: Filter by status ('running', 'completed', 'failed'), or None for all
    """
    db = SessionLocal()
    try:
        query = db.query(Execution)
        
        if status:
            query = query.filter(Execution.status == status)
        
        executions = query.order_by(Execution.created_at.desc()).limit(limit).all()
        
        if not executions:
            print(f"No executions found{f' with status={status}' if status else ''}")
            return
        
        print(f"\n{'ID':<8} {'Type':<20} {'Subject':<35} {'Status':<12} {'Created':<20} {'Error'}")
        print("=" * 150)
        
        for ex in executions:
            error_preview = ""
            if ex.error_message:
                # Truncate long error messages
                error_preview = ex.error_message[:80] + "..." if len(ex.error_message) > 80 else ex.error_message
                error_preview = error_preview.replace("\n", " ")
            
            print(
                f"{ex.id:<8} "
                f"{ex.execution_type:<20} "
                f"{ex.subject_id:<35} "
                f"{ex.status:<12} "
                f"{ex.created_at.strftime('%Y-%m-%d %H:%M:%S'):<20} "
                f"{error_preview}"
            )
        
        # Summary statistics
        print("\n" + "=" * 150)
        print("\nSummary:")
        
        status_counts = {}
        for ex in executions:
            status_counts[ex.status] = status_counts.get(ex.status, 0) + 1
        
        for status_name, count in sorted(status_counts.items()):
            print(f"  {status_name}: {count}")
        
        errors_count = sum(1 for ex in executions if ex.error_message)
        print(f"  With error messages: {errors_count}")
    
    except Exception as e:
        print(f"\n✗ Error querying database: {e}")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Check execution errors in the database"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of executions to display (default: 50)"
    )
    parser.add_argument(
        "--status",
        type=str,
        choices=["running", "completed", "failed"],
        help="Filter by execution status"
    )
    
    args = parser.parse_args()
    
    print("=" * 150)
    print("Execution Errors Check")
    print("=" * 150)
    print(f"Limit: {args.limit}")
    if args.status:
        print(f"Status filter: {args.status}")
    print("=" * 150)
    
    check_execution_errors(limit=args.limit, status=args.status)


if __name__ == "__main__":
    main()

# Made with Bob
