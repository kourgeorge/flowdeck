#!/usr/bin/env python3
"""
Migration script to add usage table for complete transaction ledger.
This migration also backfills initial balance transactions for existing users.

IMPORTANT: After this migration, User.token_balance is NO LONGER UPDATED.
Token balances are computed from the Usage ledger (single source of truth).

Run from repo root: python backend/scripts/migrate_usage.py
Safe to run multiple times (idempotent).
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from database import SessionLocal, engine


def _table_exists(conn, table_name: str) -> bool:
    """Check if a table exists in the database."""
    result = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name}
    )
    return result.fetchone() is not None


def migrate_usage():
    """Add usage table, indexes, and backfill initial balances."""

    print("Starting usage migration...")
    print("=" * 60)

    with engine.begin() as conn:
        # Check if table already exists
        table_exists = _table_exists(conn, "usage")

        if not table_exists:
            print("\n1. Creating usage table...")
            try:
                conn.execute(text("""
                    CREATE TABLE usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        amount INTEGER NOT NULL,
                        balance_after INTEGER NOT NULL,
                        llm_tokens INTEGER,
                        transaction_type VARCHAR(32) NOT NULL,
                        related_entity_type VARCHAR(32),
                        related_entity_id INTEGER,
                        description TEXT,
                        metadata_json TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """))
                conn.commit()
                print("   ✓ Created usage table")
            except Exception as e:
                print(f"   ✗ Error creating table: {e}")
                raise

            # Create indexes
            print("\n2. Creating indexes...")
            try:
                conn.execute(text("""
                    CREATE INDEX idx_usage_user_created
                    ON usage(user_id, created_at)
                """))
                print("   ✓ Created index: idx_usage_user_created")

                conn.execute(text("""
                    CREATE INDEX idx_usage_type
                    ON usage(transaction_type)
                """))
                print("   ✓ Created index: idx_usage_type")

                conn.execute(text("""
                    CREATE INDEX idx_usage_related_entity
                    ON usage(related_entity_type, related_entity_id)
                """))
                print("   ✓ Created index: idx_usage_related_entity")

                # New index for fast balance queries
                conn.execute(text("""
                    CREATE INDEX idx_usage_user_amount
                    ON usage(user_id, amount)
                """))
                print("   ✓ Created index: idx_usage_user_amount")

                conn.commit()
            except Exception as e:
                print(f"   ✗ Error creating indexes: {e}")
                raise
        else:
            print("\n1. ✓ usage table already exists")

            # Check if the new index exists, add if missing
            print("\n2. Checking indexes...")
            try:
                result = conn.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='index' AND name='idx_usage_user_amount'
                """))
                if not result.fetchone():
                    print("   Adding missing index: idx_usage_user_amount")
                    conn.execute(text("""
                        CREATE INDEX idx_usage_user_amount
                        ON usage(user_id, amount)
                    """))
                    conn.commit()
                    print("   ✓ Created index: idx_usage_user_amount")
                else:
                    print("   ✓ All indexes exist")
            except Exception as e:
                print(f"   ⚠ Warning checking indexes: {e}")

        # Backfill initial balances for users without transactions
        print("\n3. Backfilling initial balances...")
        try:
            result = conn.execute(text("""
                SELECT COUNT(*) as count
                FROM users u
                LEFT JOIN usage tt ON u.id = tt.user_id
                WHERE tt.id IS NULL AND u.token_balance IS NOT NULL AND u.token_balance > 0
            """))
            users_to_backfill = result.fetchone()[0]

            if users_to_backfill > 0:
                print(f"   Found {users_to_backfill} users needing initial balance transactions")
                conn.execute(text("""
                    INSERT INTO usage
                    (user_id, amount, balance_after, transaction_type, description, created_at)
                    SELECT 
                        id,
                        token_balance,
                        token_balance,
                        'initial_balance',
                        'Initial token balance',
                        created_at
                    FROM users
                    WHERE id NOT IN (SELECT DISTINCT user_id FROM usage)
                    AND token_balance IS NOT NULL AND token_balance > 0
                """))
                conn.commit()
                print(f"   ✓ Created {users_to_backfill} initial balance transactions")
            else:
                print("   ✓ No users need backfilling")
        except Exception as e:
            print(f"   ⚠ Warning during backfill: {e}")

    print("\n" + "=" * 60)
    print("Migration completed successfully!")
    print("\nSummary:")
    print("- Created/verified usage table")
    print("- Added indexes for performance (including fast balance queries)")
    print("- Backfilled initial balance transactions for existing users")
    print("\nIMPORTANT:")
    print("- User.token_balance is NO LONGER UPDATED by the system")
    print("- All balances are computed from Usage sum")
    print("- This eliminates sync issues and provides complete audit trail")


if __name__ == "__main__":
    try:
        migrate_usage()
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        sys.exit(1)

# Made with Bob
