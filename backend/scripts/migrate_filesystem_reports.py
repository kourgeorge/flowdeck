#!/usr/bin/env python3
"""
Import existing filesystem reports (results/<TICKER>/<DATE>/reports/*.json) into SQLite.
Run from repo root: python backend/scripts/migrate_filesystem_reports.py
"""

import json
import sys
from pathlib import Path

# Add backend to path
BACKEND = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO_ROOT))

from services.report_service import save_report
from database import init_db

RESULTS_DIR = REPO_ROOT / "results"


def main() -> None:
    init_db()
    if not RESULTS_DIR.exists():
        print(f"Results dir not found: {RESULTS_DIR}")
        return
    count = 0
    for ticker_dir in sorted(RESULTS_DIR.iterdir()):
        if not ticker_dir.is_dir():
            continue
        ticker = ticker_dir.name.upper()
        for run_dir in ticker_dir.iterdir():
            if not run_dir.is_dir():
                continue
            run_id = run_dir.name
            reports_dir = run_dir / "reports"
            if not reports_dir.exists() or not reports_dir.is_dir():
                continue
            for f in reports_dir.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                except Exception as e:
                    print(f"Skip {f}: {e}")
                    continue
                content = data.get("content", "")
                meta = data.get("metadata", {})
                # Include top-level viewpoint fields in metadata
                for key in ("bull_viewpoint", "bear_viewpoint", "risky_viewpoint", "safe_viewpoint", "neutral_viewpoint"):
                    if key in data:
                        meta[key] = data[key]
                save_report(
                    ticker=ticker,
                    run_id=run_id,
                    report_type=f.stem,
                    content=content,
                    metadata=meta,
                )
                count += 1
    print(f"Imported {count} reports into SQLite.")


if __name__ == "__main__":
    main()
