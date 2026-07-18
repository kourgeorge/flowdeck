#!/usr/bin/env python3
"""
Send sample versions of all Flowdeck email templates to a target inbox.

Usage:
  cd backend && python scripts/send_email_samples.py --to you@example.com
  cd backend && python scripts/send_email_samples.py --to you@example.com --ticker AAPL --recommendation SELL --confidence 6.4
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))
os.chdir(backend_root)

from dotenv import load_dotenv

load_dotenv(backend_root / ".env")
load_dotenv(backend_root.parent / ".env")

from services import email_service as es


def _send_admin_sample(to_email: str, ticker: str) -> bool:
    ticker_upper = ticker.upper()
    user_email = "sample.user@example.com"
    subject = f"New subscriber: {user_email} → {ticker_upper}"
    text_body = (
        f"A user just subscribed to {ticker_upper} on Flowdeck.\n\n"
        f"User: {user_email}\nTicker: {ticker_upper}\n\n"
        f"Dashboard: {es._get_frontend_url()}"
    )

    try:
        template = es._jinja_env.get_template("admin_new_subscription_email.html")
        html_body = template.render(
            user_email=user_email,
            ticker=ticker_upper,
            dashboard_url=es._get_frontend_url(),
        )
    except Exception:
        html_body = es._html_email_wrapper(
            title="New subscription",
            inner_body=f"<p>New subscription: {user_email} → {ticker_upper}</p>",
        )

    to_emails = [to_email]
    if es._get_smtp_password() and es._send_via_smtp(to_emails, subject, text_body, html_body):
        return True
    if es._get_api_key() and es._send_via_api(to_emails, subject, text_body, html_body):
        return True
    return False


def _send_daily_digest_sample(to_email: str, ticker: str) -> bool:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    brief_url = f"{es._get_frontend_url()}/dashboard?tab=digest"
    subject = f"Your Flowdeck Daily Brief - {today}"
    narrative = """## Market Highlights
The market opened with a constructive tone as large-cap technology continued to lead.

## Key Signals
Momentum remains favorable, but leadership is still narrow and worth monitoring.

## Risks & Opportunities
Near-term upside depends on earnings resilience and rate expectations staying stable."""
    what_to_watch = (
        f"Watch {ticker} price action around the latest support zone, along with any "
        "macro headlines that could shift sentiment."
    )
    text_body = (
        f"Your Daily Brief for {today} is ready.\n\n"
        f"Focus: {ticker}, SPY, QQQ\n\n"
        f"{narrative}\n\n"
        f"What to watch\n{what_to_watch}\n\n"
        f"View this brief in Flowdeck: {brief_url}"
    )

    try:
        template = es._jinja_env.get_template("daily_digest_email.html")
        html_body = template.render(
            digest_date=today,
            span_label="Daily",
            priority_tickers=[ticker, "SPY", "QQQ"],
            narrative_html=es._format_brief_narrative_for_email(narrative),
            what_to_watch=what_to_watch,
            brief_url=brief_url,
            preheader=f"Your Daily Brief for {today} is ready.",
        )
    except Exception:
        html_body = es._html_email_wrapper(
            title="Daily Brief",
            inner_body=f"<p>Your Daily Brief is ready. <a href='{brief_url}'>Open brief</a></p>",
            preheader=f"Your Daily Brief for {today} is ready.",
        )

    to_emails = [to_email]
    if es._get_smtp_password() and es._send_via_smtp(to_emails, subject, text_body, html_body):
        return True
    if es._get_api_key() and es._send_via_api(to_emails, subject, text_body, html_body):
        return True
    return False


def _sample_scores() -> dict:
    return {
        "market_report": {
            "score": 4.0,
            "score_label": "Market Score",
            "key_takeaways": ["Strong market momentum with broad participation", "Sector rotation favoring growth stocks"],
        },
        "sentiment_report": {
            "score": 3.0,
            "score_label": "Sentiment Score",
            "key_takeaways": ["Positive earnings surprise exceeded expectations", "Mixed social sentiment with cautious optimism"],
        },
        "fundamentals_report": {
            "score": 2.0,
            "score_label": "Fundamentals Score",
            "key_takeaways": ["Revenue growth remains healthy but margins under pressure"],
        },
        "technical_report": {
            "score": 4.0,
            "score_label": "Technical Score",
            "key_takeaways": ["Price action showing bullish momentum"],
        },
        "sec_report": {
            "score": 3.0,
            "score_label": "SEC Score",
            "key_takeaways": ["Recent filings show standard corporate activity"],
        },
        "investment_plan": {
            "score": 3.0,
            "score_label": "Conviction Score",
            "recommendation": "BUY",
            "confidence": 0.6,
            "bull_viewpoint": [
                "Strong earnings growth trajectory",
                "Market leadership in key segments",
                "Expanding margins and operational efficiency",
            ],
            "bear_viewpoint": [
                "Valuation premium to sector peers",
                "Macro headwinds could impact demand",
                "Competitive pressure intensifying",
            ],
            "neutral_viewpoint": [
                "Fundamentals are solid but largely priced in",
                "A balanced position with disciplined sizing is prudent",
                "Watch macro data before adding to the position",
            ],
            "key_takeaways": ["Risk/reward remains favorable with disciplined position sizing"],
        },
        "trader_investment_plan": {
            "score_label": "Trader Plan",
            "bull_viewpoint": ["Technical setup looks favorable"],
            "bear_viewpoint": ["Watch for resistance at key levels"],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send sample versions of all Flowdeck emails.")
    parser.add_argument("--to", required=True, help="Recipient email address")
    parser.add_argument("--ticker", default="MSFT", help="Ticker symbol for stock-related samples")
    parser.add_argument(
        "--recommendation",
        default="BUY",
        choices=["BUY", "SELL", "HOLD"],
        help="Recommendation value used in report sample",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=8.8,
        help="Confidence value used in report sample",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    to_email = (args.to or "").strip()
    ticker = (args.ticker or "").strip().upper()

    if not to_email or "@" not in to_email:
        raise SystemExit("Invalid --to email address")
    if not ticker:
        raise SystemExit("Invalid --ticker")

    print(f"Sending sample emails to: {to_email}")
    print(f"Ticker: {ticker}, Recommendation: {args.recommendation}, Confidence: {args.confidence:.1f}")

    results: dict[str, bool] = {}

    results["welcome_email"] = es.send_welcome_email(to_email)
    results["subscription_confirmation_email"] = es.send_subscription_confirmation(to_email, ticker)
    results["report_notification_email"] = es.send_report_notification(
        to_emails=[to_email],
        ticker=ticker,
        recommendation=args.recommendation,
        confidence=args.confidence,
        scores=_sample_scores(),
    )
    results["admin_new_subscription_email"] = _send_admin_sample(to_email, ticker)

    prev_contact_recipient = es.CONTACT_FORM_RECIPIENT
    try:
        es.CONTACT_FORM_RECIPIENT = to_email
        results["contact_form_email"] = es.send_contact_form_email(
            name="Sample User",
            email="sample.user@example.com",
            message="This is a sample contact-form email generated by send_email_samples.py",
        )
    finally:
        es.CONTACT_FORM_RECIPIENT = prev_contact_recipient

    results["daily_digest_email"] = _send_daily_digest_sample(to_email, ticker)

    print("\nSend results:")
    all_ok = True
    for key, value in results.items():
        status = "OK" if value else "FAIL"
        print(f"  [{status}] {key}")
        all_ok = all_ok and value

    if not all_ok:
        raise SystemExit("One or more sample emails failed to send")


if __name__ == "__main__":
    main()
