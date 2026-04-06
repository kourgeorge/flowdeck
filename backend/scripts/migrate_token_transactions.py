#!/usr/bin/env python3
"""
Migration script to add token_transactions table for complete transaction ledger.
Run from repo root: python backend/scripts/migrate_token_transactions.py
Safe to run multiple times (idempotent).
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from database import SessionLocal, engine


def _table_exists(conn, table_name: str) -> bool:
    """Check if table exists (SQLite)."""
    result = conn.execute(text(
        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
    ))
    return result.fetchone() is not None


def migrate_token_transactions():
    """Add token_transactions table and indexes."""
    
    print("Starting token_transactions migration...")
    
    with engine.connect() as conn:
        # Check if table already exists
        if _table_exists(conn, "token_transactions"):
            print("✓ token_transactions table already exists")
            return
        
        print("Creating token_transactions table...")
        try:
            conn.execute(text("""
                CREATE TABLE token_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    balance_after INTEGER NOT NULL,
                    llm_tokens INTEGER NULL,
                    transaction_type VARCHAR(32) NOT NULL,
                    related_entity_type VARCHAR(32) NULL,
                    related_entity_id INTEGER NULL,
                    metadata_json TEXT NULL,
                    description VARCHAR(255) NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """))
            conn.commit()
            print("✓ Created token_transactions table")
        except Exception as e:
            print(f"Error creating table: {e}")
            raise
        
        print("Creating indexes...")
        try:
            conn.execute(text("""
                CREATE INDEX idx_token_tx_user_created
                ON token_transactions(user_id, created_at)
            """))
            conn.commit()
            print("✓ Created index on (user_id, created_at)")
        except Exception as e:
            print(f"Note: Index creation: {e}")
        
        try:
            conn.execute(text("""
                CREATE INDEX idx_token_tx_type
                ON token_transactions(transaction_type)
            """))
            conn.commit()
            print("✓ Created index on transaction_type")
        except Exception as e:
            print(f"Note: Index creation: {e}")
        
        try:
            conn.execute(text("""
                CREATE INDEX idx_token_tx_related_entity
                ON token_transactions(related_entity_type, related_entity_id)
            """))
            conn.commit()
            print("✓ Created index on (related_entity_type, related_entity_id)")
        except Exception as e:
            print(f"Note: Index creation: {e}")
    
    print("\n✅ Migration completed successfully!")
    print("\nSummary:")
    print("- Created token_transactions table")
    print("- Added indexes for performance")
    print("- Ready to track all token balance changes")


if __name__ == "__main__":
    try:
        migrate_token_transactions()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# Made with Bob
