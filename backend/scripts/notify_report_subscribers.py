#!/usr/bin/env python3
"""
Send the latest report notification to all subscribers of a ticker.
Usage:
  cd backend && python scripts/notify_report_subscribers.py MSFT
"""
import os
import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))
os.chdir(backend_root)

from dotenv import load_dotenv
load_dotenv(backend_root / ".env")
load_dotenv(backend_root.parent / ".env")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/notify_report_subscribers.py TICKER")
        sys.exit(1)
    ticker = (sys.argv[1] or "").strip().upper()
    if not ticker:
        print("Usage: python scripts/notify_report_subscribers.py TICKER")
        sys.exit(1)

    from services.report_service import ReportService
    from services.email_service import get_subscriber_emails_for_ticker, notify_subscribers_new_report

    report_service = ReportService()
    latest = report_service.get_latest_analysis_run(ticker)
    if not latest:
        print(f"No report found for {ticker}. Run an analysis first.")
        sys.exit(1)
    analysis_run_id, latest_date = latest
    scores = report_service.get_reports_with_scores(ticker, analysis_run_id)
    # Prefer final_trade_decision, then trader_investment_plan for recommendation/confidence
    final_meta = scores.get("final_trade_decision") or {}
    if not final_meta.get("recommendation"):
        final_meta = scores.get("trader_investment_plan") or {}
    recommendation = final_meta.get("recommendation")
    confidence = final_meta.get("confidence")
    if confidence is not None and not isinstance(confidence, (int, float)):
        confidence = None

    emails = get_subscriber_emails_for_ticker(ticker)
    if not emails:
        print(f"No subscribers for {ticker}. Nothing to send.")
        sys.exit(0)

    print(f"Notifying {len(emails)} subscriber(s) for {ticker} (report {latest_date})...")
    print(f"Recommendation: {recommendation}, Confidence: {confidence}")
    if scores:
        print("Scores to be included in email:")
        for report_type, report_data in scores.items():
            score = report_data.get("score")
            score_label = report_data.get("score_label")
            if score is not None or score_label:
                display = f"  • {report_type}: "
                if score is not None:
                    display += f"{score:.1f}/10"
                    if score_label:
                        display += f" ({score_label})"
                elif score_label:
                    display += score_label
                print(display)
    notify_subscribers_new_report(
        ticker=ticker,
        analysis_run_id=analysis_run_id,
        recommendation=recommendation,
        confidence=confidence,
    )
    print("Done.")


if __name__ == "__main__":
    main()
