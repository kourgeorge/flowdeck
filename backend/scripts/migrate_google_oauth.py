#!/usr/bin/env python3
"""
Database migration script for Google OAuth support.

This script adds the necessary columns to the users table to support Google OAuth:
- google_id: Stores the Google user ID
- Makes hashed_password nullable (for users who sign in with Google only)

Usage:
    python backend/scripts/migrate_google_oauth.py
"""

import sys
import os

# Add parent directory to path to import from backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text
from database import engine, SessionLocal


def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    db = SessionLocal()
    try:
        # SQLite-specific query to check if column exists
        result = db.execute(
            text(f"PRAGMA table_info({table_name})")
        ).fetchall()
        
        columns = [row[1] for row in result]  # Column name is at index 1
        return column_name in columns
    finally:
        db.close()


def check_column_nullable(table_name: str, column_name: str) -> bool:
    """Check if a column is nullable."""
    db = SessionLocal()
    try:
        result = db.execute(
            text(f"PRAGMA table_info({table_name})")
        ).fetchall()
        
        for row in result:
            if row[1] == column_name:  # Column name at index 1
                return row[3] == 0  # notnull at index 3 (0 = nullable, 1 = not null)
        return False
    finally:
        db.close()


def migrate():
    """Run the migration."""
    print("=" * 60)
    print("Google OAuth Database Migration")
    print("=" * 60)
    print()
    
    db = SessionLocal()
    
    try:
        # Check if google_id column exists
        if check_column_exists('users', 'google_id'):
            print("✓ Column 'google_id' already exists")
        else:
            print("Adding 'google_id' column to users table...")
            db.execute(text(
                "ALTER TABLE users ADD COLUMN google_id VARCHAR(255)"
            ))
            db.commit()
            print("✓ Added 'google_id' column")
        
        # Check if google_id has unique index
        print("Checking for unique index on 'google_id'...")
        result = db.execute(text(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='users' AND name='idx_users_google_id'"
        )).fetchone()
        
        if result:
            print("✓ Unique index on 'google_id' already exists")
        else:
            print("Creating unique index on 'google_id'...")
            db.execute(text(
                "CREATE UNIQUE INDEX idx_users_google_id ON users(google_id)"
            ))
            db.commit()
            print("✓ Created unique index on 'google_id'")
        
        # Check if hashed_password is nullable
        if check_column_nullable('users', 'hashed_password'):
            print("✓ Column 'hashed_password' is already nullable")
        else:
            print("Making 'hashed_password' nullable...")
            print("  Note: SQLite doesn't support ALTER COLUMN directly.")
            print("  Creating new table with updated schema...")
            
            # SQLite doesn't support ALTER COLUMN, so we need to:
            # 1. Create a new table with the correct schema
            # 2. Copy data from old table
            # 3. Drop old table
            # 4. Rename new table
            
            # Create temporary table with new schema
            db.execute(text("""
                CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    name VARCHAR(255),
                    hashed_password VARCHAR(255),
                    google_id VARCHAR(255) UNIQUE,
                    token_balance INTEGER NOT NULL DEFAULT 1000,
                    is_admin BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Copy data from old table
            db.execute(text("""
                INSERT INTO users_new (id, email, name, hashed_password, google_id, token_balance, is_admin, created_at, updated_at)
                SELECT id, email, name, hashed_password, google_id, token_balance, is_admin, created_at, updated_at
                FROM users
            """))
            
            # Drop old table
            db.execute(text("DROP TABLE users"))
            
            # Rename new table
            db.execute(text("ALTER TABLE users_new RENAME TO users"))
            
            # Recreate indexes
            db.execute(text("CREATE UNIQUE INDEX idx_users_email ON users(email)"))
            db.execute(text("CREATE UNIQUE INDEX idx_users_google_id ON users(google_id)"))
            
            db.commit()
            print("✓ Made 'hashed_password' nullable")
        
        print()
        print("=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Configure Google OAuth credentials in backend/.env")
        print("2. Install required package: pip install google-auth google-auth-oauthlib")
        print("3. Restart the backend server")
        print("4. Test the 'Continue with Google' button")
        print()
        
    except Exception as e:
        db.rollback()
        print()
        print("=" * 60)
        print("ERROR: Migration failed!")
        print("=" * 60)
        print(f"Error: {e}")
        print()
        print("Please check the error message and try again.")
        print("If the issue persists, you may need to manually update the database.")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    migrate()


