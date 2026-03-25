#!/usr/bin/env python3
"""Send announcement emails to specified recipients or all users from the database.

Usage Examples:
    # Dry run to preview all users from database
    python scripts/send_announcement_email.py

    # Send to admin only
    python scripts/send_announcement_email.py --admin-only --send

    # Send to specific email addresses
    python scripts/send_announcement_email.py --to user1@example.com user2@example.com --send

    # Send to all users from database
    python scripts/send_announcement_email.py --send

    # Send to all users including internal accounts
    python scripts/send_announcement_email.py --include-internal --send

    # Use a specific database URL
    python scripts/send_announcement_email.py --database-url postgresql://user:pass@host/db --send

    # Dry run with limit to preview first 5 recipients
    python scripts/send_announcement_email.py --limit 5
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

# Add backend to path
repo_root = Path(__file__).resolve().parent.parent
backend_root = repo_root / "backend"
sys.path.insert(0, str(backend_root))
os.chdir(repo_root)

from dotenv import load_dotenv

load_dotenv(backend_root / ".env")
load_dotenv(repo_root / ".env")

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from services.email_service import (
    _send_via_smtp,
    _send_via_api,
    _get_smtp_password,
    _get_api_key,
    ADMIN_SUBSCRIBE_NOTIFY_EMAIL,
)

ANNOUNCEMENT_TEMPLATE_PATH = backend_root / "templates" / "announcement_email.html"
ANNOUNCEMENT_SUBJECT = "FlowDeck product update: 5 new features"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Send announcement email to specified recipients or all users."
    )
    parser.add_argument(
        "--to",
        nargs="+",
        help="Specific email address(es) to send to. If not provided, sends to all users from database.",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Actually send the email. Without this flag, the script runs in dry-run mode.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of recipient emails processed (only applies when querying database).",
    )
    parser.add_argument(
        "--exclude-admins",
        action="store_true",
        help="Exclude admin users from the recipient list (only applies when querying database).",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Explicit database URL to use instead of the configured default.",
    )
    parser.add_argument(
        "--include-internal",
        action="store_true",
        help="Include internal @flowdeck.internal accounts in the recipient list.",
    )
    parser.add_argument(
        "--admin-only",
        action="store_true",
        help="Send only to the admin email (ADMIN_SUBSCRIBE_NOTIFY_EMAIL).",
    )
    return parser.parse_args()


def candidate_database_urls(explicit_url: str | None = None) -> list[str]:
    """Return database URLs to try, in order."""
    urls: list[str] = []
    if explicit_url:
        urls.append(explicit_url)
    env_url = os.environ.get("DATABASE_URL")
    if env_url and env_url not in urls:
        urls.append(env_url)
    fallback_sqlite = f"sqlite:///{backend_root / 'flowdeck.db'}"
    if fallback_sqlite not in urls:
        urls.append(fallback_sqlite)
    return urls


def describe_database_url(database_url: str) -> str:
    """Return a safe string for logs."""
    if database_url.startswith("sqlite:///"):
        return database_url
    return database_url.split("://", 1)[0] + "://<redacted>"


def load_recipient_emails_from_url(
    database_url: str,
    limit: int | None = None,
    exclude_admins: bool = False,
    include_internal: bool = False,
) -> list[str]:
    """Return distinct user email addresses from the selected database."""
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)

    sql = """
        SELECT DISTINCT email
        FROM users
        WHERE email IS NOT NULL
          AND email != ''
    """
    if exclude_admins:
        sql += " AND is_admin IS NOT TRUE"
    if not include_internal:
        sql += " AND LOWER(email) NOT LIKE :internal_pattern"
    sql += " ORDER BY email ASC"
    if limit is not None:
        sql += " LIMIT :limit"

    try:
        with engine.connect() as conn:
            params: dict[str, object] = {}
            if not include_internal:
                params["internal_pattern"] = "%@flowdeck.internal"
            if limit is not None:
                params["limit"] = limit
            rows = conn.execute(text(sql), params).fetchall()
    finally:
        engine.dispose()

    return [row[0].strip() for row in rows if row and row[0] and "@" in row[0]]


def resolve_recipients_from_database(
    limit: int | None = None,
    exclude_admins: bool = False,
    database_url: str | None = None,
    include_internal: bool = False,
) -> tuple[list[str], str]:
    """Resolve recipients from the first database that has a usable users table."""
    last_error: Exception | None = None
    for url in candidate_database_urls(database_url):
        try:
            emails = load_recipient_emails_from_url(
                database_url=url,
                limit=limit,
                exclude_admins=exclude_admins,
                include_internal=include_internal,
            )
            return emails, url
        except OperationalError as exc:
            last_error = exc

    if last_error is not None:
        raise SystemExit(f"Could not load user emails from any configured database: {last_error}")
    raise SystemExit("No database URL configured")


def build_announcement_email() -> tuple[str, str, str]:
    """Build the announcement email subject and bodies."""
    email_html_path = ANNOUNCEMENT_TEMPLATE_PATH

    if not email_html_path.exists():
        raise FileNotFoundError(f"Email file not found at {email_html_path}")

    try:
        html_body = email_html_path.read_text(encoding="utf-8")
    except Exception as e:
        raise RuntimeError(f"Error reading email file: {e}") from e

    announcement_date = datetime.now().strftime("%B %d, %Y")
    html_body = (
        html_body.replace("{{FLOWDECK_LOGO_SRC}}", _get_logo_data_uri())
        .replace("{{ANNOUNCEMENT_DATE}}", announcement_date)
    )

    text_body = """
FlowDeck Product Update - {announcement_date}

Five new features are now live in FlowDeck:

1. Automatic Event Detection
Tracks meaningful market events across your portfolio, including price moves, volatility changes, earnings dates, insider activity, and 52-week highs or lows.

2. Daily & Weekly Briefs
Delivers scheduled market summaries for your watchlist with configurable tone and structure.

3. Personal Newsroom
Provides a redesigned, stock-focused news stream with faster scanning and better filtering.

4. Portfolio Pulse Dashboard
Brings holdings, performance, and key developments into a single portfolio view.

5. Investor Profile
Lets you define investing style and preferences so FlowDeck can tailor analysis and briefs more effectively.

All features are available now in your dashboard.

Visit FlowDeck: https://flowdeck.biz

The FlowDeck Team
""".format(announcement_date=announcement_date)

    return ANNOUNCEMENT_SUBJECT, text_body, html_body


def send_announcement_email(to_emails: Iterable[str]) -> bool:
    """Send the feature announcement email to one or more recipients."""
    recipients = [email.strip() for email in to_emails if email and email.strip()]
    if not recipients:
        print("No recipient emails provided.")
        return False

    try:
        subject, text_body, html_body = build_announcement_email()
    except Exception as e:
        print(e)
        return False

    print(f"Sending announcement email to {len(recipients)} recipient(s)...")
    if len(recipients) == 1:
        print(f"Recipient: {recipients[0]}")
    else:
        print(f"First recipient: {recipients[0]}")
        print(f"Last recipient: {recipients[-1]}")
    print(f"Subject: {subject}")

    # Try SMTP first, then API
    success = False

    if _get_smtp_password():
        print("Attempting to send via SMTP...")
        if _send_via_smtp(recipients, subject, text_body, html_body):
            print("✓ Email sent successfully via SMTP!")
            success = True
        else:
            print("✗ SMTP send failed")
    
    if not success and _get_api_key():
        print("Attempting to send via API...")
        if _send_via_api(recipients, subject, text_body, html_body):
            print("✓ Email sent successfully via API!")
            success = True
        else:
            print("✗ API send failed")
    
    if not success:
        print("\n✗ Failed to send email. Please check your email configuration:")
        print("  - AGENTMAIL_API_KEY or AGENTMAIL_SMTP_PASSWORD must be set in backend/.env")
        print("  - AGENTMAIL_INBOX_ID should be configured")
        return False

    return True


def _get_logo_data_uri() -> str:
    """Return the FlowDeck logo as a self-contained email-safe data URI."""
    cached_path = backend_root / "services" / "email_logo_data_uri.txt"
    if cached_path.is_file():
        try:
            cached_value = cached_path.read_text(encoding="utf-8").strip()
        except OSError:
            cached_value = ""
        if cached_value.startswith("data:image/"):
            return cached_value

    logo_path = repo_root / "logo.svg"
    if not logo_path.is_file():
        return ""

    try:
        svg_b64 = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:image/svg+xml;base64,{svg_b64}"


def main() -> None:
    """Main entry point for the script."""
    args = parse_args()
    
    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit must be greater than 0")

    # Determine recipients based on arguments
    recipients: list[str] = []
    
    if args.admin_only:
        # Send only to admin
        recipients = [ADMIN_SUBSCRIBE_NOTIFY_EMAIL]
        print(f"Sending to admin only: {ADMIN_SUBSCRIBE_NOTIFY_EMAIL}")
    elif args.to:
        # Send to specific email addresses
        recipients = args.to
        print(f"Sending to {len(recipients)} specified recipient(s)")
    else:
        # Query database for all users
        emails, database_url = resolve_recipients_from_database(
            limit=args.limit,
            exclude_admins=args.exclude_admins,
            database_url=args.database_url,
            include_internal=args.include_internal,
        )
        recipients = emails
        print(f"Using database: {describe_database_url(database_url)}")
        print(f"Resolved {len(recipients)} recipient(s) from users.email")
    
    # Show preview of recipients
    if recipients:
        preview_count = min(5, len(recipients))
        print("Preview:")
        for email in recipients[:preview_count]:
            print(f"  - {email}")
        if len(recipients) > preview_count:
            print(f"  ... and {len(recipients) - preview_count} more")

    if not args.send:
        print("\nDry run only. Re-run with --send to deliver the announcement.")
        return

    if not recipients:
        raise SystemExit("No valid recipient emails found")

    ok = send_announcement_email(recipients)
    if not ok:
        raise SystemExit("Announcement send failed")


if __name__ == "__main__":
    main()

# Made with Bob
