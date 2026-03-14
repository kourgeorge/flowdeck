#!/usr/bin/env python3
"""
Validate the layer refactor: import and call each new service with a real DB session.
Run from repo root: python backend/scripts/validate_layer_services.py
Or from backend: python scripts/validate_layer_services.py (with PYTHONPATH including repo root)
"""
import os
import sys
from pathlib import Path

# Repo root and backend on path (same as run.py)
backend_dir = Path(__file__).resolve().parents[1]
project_root = backend_dir.parent
for p in (str(project_root), str(backend_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)
os.chdir(backend_dir)

from database import SessionLocal, init_db

def main():
    init_db()
    db = SessionLocal()
    try:
        # 1. Public stats (read-only)
        from services.public_stats_service import get_public_stats
        stats = get_public_stats(db)
        assert "total_analyses" in stats and "total_reports" in stats and "unique_tickers_analyzed" in stats
        print("OK public_stats_service.get_public_stats")

        # 2. ApiKey service (list empty; create would need user_id)
        from services import api_key_service
        keys = api_key_service.list_by_user(db, 99999)
        assert isinstance(keys, list)
        print("OK api_key_service.list_by_user")

        # 3. Subscription service (list empty)
        from services import subscription_service
        subs = subscription_service.list_for_user(db, 99999)
        assert isinstance(subs, list)
        print("OK subscription_service.list_for_user")

        # 4. Me service – get_user_stats for non-existent user
        from services import me_service
        me_service.get_user_by_id(db, 99999)
        stats = me_service.get_user_stats(db, 99999)
        assert "analyses_created" in stats and "member_since" in stats
        print("OK me_service.get_user_stats")

        # 5. Digest service – empty history
        from services.digest_service import get_digest_dates, get_digests_for_date
        dates, count_by_date = get_digest_dates(db, 99999, 90)
        assert isinstance(dates, list) and isinstance(count_by_date, dict)
        briefs = get_digests_for_date(db, 99999, "2025-01-01")
        assert isinstance(briefs, list)
        print("OK digest_service.get_digest_dates, get_digests_for_date")

        # 6. Chat persistence – list empty; get_session_for_user returns None
        from services.chat_persistence import get_session_for_user, list_sessions_for_user
        assert get_session_for_user(db, 1, 99999) is None
        assert list_sessions_for_user(db, 99999, 10) == []
        print("OK chat_persistence.get_session_for_user, list_sessions_for_user")

        # 7. Admin service – stats and mission control data
        from services import admin_service
        admin_stats = admin_service.get_stats(db)
        assert "total_users" in admin_stats and "analyses_last_24h" in admin_stats
        entries = admin_service.load_mission_control_entries()
        assert isinstance(entries, list)
        items = admin_service.get_mission_control_items(db)
        assert isinstance(items, list)
        print("OK admin_service.get_stats, load_mission_control_entries, get_mission_control_items")

        print("\nAll layer services validated successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
