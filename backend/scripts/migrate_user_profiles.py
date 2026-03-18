#!/usr/bin/env python3
"""
Ensure the user_profiles table exists.
Run from repo root: python backend/scripts/migrate_user_profiles.py
Safe to run multiple times.
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from database import init_db, engine
from sqlalchemy import inspect


def main() -> None:
    init_db()
    if inspect(engine).has_table("user_profiles"):
        print("user_profiles table is present")
    else:
        raise RuntimeError("user_profiles table was not created")

    print("User profile migration done.")


if __name__ == "__main__":
    main()
