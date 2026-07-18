"""One-time migration: rescale all AI report scores from the 1-10 scale to 1-5.

Scores live only inside reports.metadata_json (there is no numeric column / CHECK
constraint), including:
  * the top-level "score" key (main analyst/decision reports), and
  * nested snapshots in daily_digest metadata under
    resources[].tool_output.platform_reports.<report_type>.score

This script walks each report's metadata JSON and rescales every dict key named
exactly "score" whose value is an int in 1..10 using paired halving:

    new = (old + 1) // 2      # 1,2->1  3,4->2  5,6->3  7,8->4  9,10->5

It also recomputes any derived "confidence" (0-1) that was stored as old/10, so it
stays consistent on the new scale (new = min(1, old_confidence * 2)).

Idempotency: every migrated row is stamped with "score_scale_v": 5 and rows already
carrying that marker are skipped, so re-running is safe.

IMPORTANT: run with the backend STOPPED (the DB is rewritten in place). A timestamped
backup copy of the .db file is made before any writes.

Usage:
    cd backend && python scripts/migrate_scores_1to5.py            # apply
    cd backend && python scripts/migrate_scores_1to5.py --dry-run  # report only
"""

import argparse
import datetime
import json
import os
import shutil
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "flowdeck.db")
SCALE_MARKER = "score_scale_v"
NEW_MAX = 5


def rescale_score(old):
    """Paired-halving 1-10 -> 1-5. Leaves anything outside int 1..10 untouched."""
    if isinstance(old, bool) or not isinstance(old, int):
        return old
    if 1 <= old <= 10:
        return (old + 1) // 2
    return old


def walk(node):
    """Recursively rescale every 'score' key (int 1-10) and any 'confidence' (0-1)."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "score":
                node[k] = rescale_score(v)
            elif k == "confidence" and isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1:
                node[k] = min(1.0, round(v * 2, 4))
            else:
                walk(v)
    elif isinstance(node, list):
        for item in node:
            walk(item)


def main():
    parser = argparse.ArgumentParser(description="Rescale report scores 1-10 -> 1-5.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing.")
    parser.add_argument("--db", default=DB_PATH, help="Path to the sqlite DB file.")
    args = parser.parse_args()

    db_path = os.path.abspath(args.db)
    if not os.path.exists(db_path):
        sys.exit(f"DB not found: {db_path}")

    if not args.dry_run:
        stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        backup = f"{db_path}.bak-{stamp}"
        shutil.copy(db_path, backup)
        print(f"Backup written: {backup}")

    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT id, metadata_json FROM reports WHERE metadata_json IS NOT NULL"
        ).fetchall()
        changed = skipped = errored = 0
        for rid, mj in rows:
            try:
                d = json.loads(mj)
            except (TypeError, ValueError):
                errored += 1
                continue
            if not isinstance(d, dict) or d.get(SCALE_MARKER) == NEW_MAX:
                skipped += 1
                continue
            walk(d)
            d[SCALE_MARKER] = NEW_MAX
            if not args.dry_run:
                con.execute(
                    "UPDATE reports SET metadata_json = ? WHERE id = ?",
                    (json.dumps(d), rid),
                )
            changed += 1
        if not args.dry_run:
            con.commit()
        mode = "DRY-RUN (no writes)" if args.dry_run else "APPLIED"
        print(f"{mode}: changed={changed} skipped={skipped} errored={errored} total={len(rows)}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
