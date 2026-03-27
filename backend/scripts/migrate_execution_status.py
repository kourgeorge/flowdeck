"""
Migration script to add status, error_message, and completed_at fields to executions table.
Sets status based on whether reports exist for each execution.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from database import SessionLocal, engine
from models.db_models import Execution, Report


def migrate_execution_status():
    """Add status fields to executions table and populate based on existing data."""
    
    print("Starting execution status migration...")
    
    # Add columns to table
    with engine.connect() as conn:
        print("Adding status column...")
        try:
            conn.execute(text(
                "ALTER TABLE executions ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'running'"
            ))
            conn.commit()
            print("✓ Added status column")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("✓ Status column already exists")
            else:
                raise
        
        print("Adding error_message column...")
        try:
            conn.execute(text(
                "ALTER TABLE executions ADD COLUMN error_message TEXT"
            ))
            conn.commit()
            print("✓ Added error_message column")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("✓ Error_message column already exists")
            else:
                raise
        
        print("Adding completed_at column...")
        try:
            conn.execute(text(
                "ALTER TABLE executions ADD COLUMN completed_at DATETIME"
            ))
            conn.commit()
            print("✓ Added completed_at column")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("✓ Completed_at column already exists")
            else:
                raise
    
    # Create index on status
    with engine.connect() as conn:
        print("Creating index on status...")
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status)"
            ))
            conn.commit()
            print("✓ Created index on status")
        except Exception as e:
            print(f"Note: Index creation: {e}")
    
    # Update existing records based on whether they have reports
    db = SessionLocal()
    try:
        print("\nUpdating existing execution records...")
        
        # Get all executions with their report counts
        from sqlalchemy import func
        executions_with_reports = db.query(
            Execution.id,
            func.count(Report.id).label('report_count'),
            func.max(Report.created_at).label('last_report_at')
        ).outerjoin(
            Report, Report.execution_id == Execution.id
        ).group_by(
            Execution.id
        ).all()
        
        completed_count = 0
        failed_count = 0
        
        for exec_id, report_count, last_report_at in executions_with_reports:
            execution = db.query(Execution).filter(Execution.id == exec_id).first()
            if not execution:
                continue
            
            if report_count > 0:
                # Has reports = completed
                execution.status = "completed"
                execution.completed_at = last_report_at
                completed_count += 1
            else:
                # No reports = failed (or very recent running, but safer to mark as failed)
                execution.status = "failed"
                execution.error_message = "No reports generated (migrated from legacy data)"
                execution.completed_at = execution.created_at
                failed_count += 1
        
        db.commit()
        print(f"✓ Updated {completed_count} executions to 'completed'")
        print(f"✓ Updated {failed_count} executions to 'failed'")
        
    except Exception as e:
        print(f"Error updating execution records: {e}")
        db.rollback()
        raise
    finally:
        db.close()
    
    print("\n✅ Migration completed successfully!")
    print("\nSummary:")
    print("- Added status, error_message, and completed_at columns")
    print("- Created index on status column")
    print("- Updated existing records based on report existence")


if __name__ == "__main__":
    try:
        migrate_execution_status()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# Made with Bob
