#!/usr/bin/env python3
"""
Watchlist report: run pipeline (conductor) and generate HTML with Vega-Lite.
Run from repo root: python ai_engine/watchlist_consulting/build_report.py --email=user@example.com [--output=path]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend and watchlist_consulting are on path (when run as script from repo root)
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

# Load backend/.env so OPENAI_API_KEY / Azure and other config are available
try:
    from dotenv import load_dotenv
    load_dotenv(_BACKEND / ".env")
except ImportError:
    pass

from html_report import build_html  # noqa: E402


def _run_pipeline(args: argparse.Namespace) -> int:
    """Run conductor and write HTML (+ optional report_json / figure_data)."""
    from conductor import run_pipeline  # noqa: E402

    user_profile = None
    if args.profile:
        try:
            p = Path(args.profile)
            if p.exists():
                user_profile = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Warning: could not load profile from {args.profile}: {e}", file=sys.stderr)

    print("Running pipeline (conductor)...")
    result = run_pipeline(
        user_id=args.user_id,
        email=args.email,
        user_profile=user_profile,
        use_cache=not args.no_cache,
        skip_audit=args.skip_audit,
        web_breadth=getattr(args, "web_breadth", 3),
        web_depth=getattr(args, "web_depth", 2),
    )
    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1
    report_json = result.get("report_json")
    if not report_json:
        print("Error: no report_json from pipeline", file=sys.stderr)
        return 1
    payload = result.get("payload") or {}
    figure_specs = result.get("figure_specs") or []
    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    user = payload.get("user") or {}

    # Adapt report_json to agent_output shape for build_html
    rj = report_json.model_dump() if hasattr(report_json, "model_dump") else report_json
    agent_output = {
        "title": rj.get("title") or "Watchlist Report",
        "portfolio_summary": rj.get("watchlist_summary") or "",
        "narrative": rj.get("narrative") or "",
        "figure_explanations": rj.get("figure_explanations") or "",
        "per_ticker_highlights": [
            {"ticker": c.get("ticker"), "short_summary": c.get("summary") or ""}
            for c in rj.get("ticker_cards") or []
        ],
        "actions_section": rj.get("actions_section") or "",
        "references": rj.get("references") or [],
        "research_qa": rj.get("research_qa") or [],
    }

    html = build_html(agent_output, payload, figure_specs, report_date=report_date)

    out_dir = _SCRIPT_DIR / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.output:
        out_path = Path(args.output)
    else:
        user_slug = (user.get("email") or str(user.get("id", "unknown"))).replace("@", "_").replace(".", "_")
        out_path = out_dir / f"watchlist_report_{user_slug}_{report_date}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path}")

    if getattr(args, "write_json", False):
        json_path = out_path.with_suffix(".report.json")
        json_path.write_text(
            json.dumps(rj, default=str, indent=2),
            encoding="utf-8",
        )
        print(f"Wrote {json_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate watchlist report (HTML + Vega-Lite) for a user")
    parser.add_argument("--user-id", type=int, help="User ID")
    parser.add_argument("--email", type=str, help="User email")
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output HTML file path (default: out/watchlist_report_<user>_<date>.html)",
    )
    parser.add_argument("--profile", type=str, default=None, help="Path to optional user profile JSON")
    parser.add_argument("--no-cache", action="store_true", help="Disable pipeline cache (force recompute)")
    parser.add_argument("--skip-audit", action="store_true", help="Skip Stage 9 auditor (for dev)")
    parser.add_argument("--write-json", action="store_true", help="Also write report_json to .report.json")
    parser.add_argument("--web-breadth", type=int, default=3, help="Web research: number of initial search queries (0 to disable). Requires SERPAPI_KEY. Default 3.")
    parser.add_argument("--web-depth", type=int, default=2, help="Web research: depth (1=no follow-ups, 2=up to 2 follow-ups per query). Default 2.")
    args = parser.parse_args()

    if not args.user_id and not args.email:
        print("Error: provide --user-id or --email", file=sys.stderr)
        return 1

    return _run_pipeline(args)


if __name__ == "__main__":
    sys.exit(main())
