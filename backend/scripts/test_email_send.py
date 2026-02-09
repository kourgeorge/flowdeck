#!/usr/bin/env python3
"""
Verify email (AgentMail) configuration and optionally send a test report notification.
Usage:
  cd backend && python scripts/test_email_send.py
  TEST_EMAIL=you@example.com python scripts/test_email_send.py   # also send one test email
"""
import os
import sys
from pathlib import Path

# Ensure backend root is on path
backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))
os.chdir(backend_root)

from dotenv import load_dotenv
load_dotenv(backend_root / ".env")
load_dotenv(backend_root.parent / ".env")


def _mask(s: str, show: int = 4) -> str:
    if not s or len(s) <= show:
        return "***"
    return s[:show] + "*" * (len(s) - show)


def main() -> None:
    from services.email_service import (
        send_report_notification,
        _get_api_key,
        _get_smtp_password,
        _get_smtp_host,
        _get_smtp_port,
        _get_smtp_user,
        _get_agentmail_base,
        _get_inbox_id,
    )

    api_key = _get_api_key()
    smtp_pass = _get_smtp_password()
    smtp_user = _get_smtp_user()
    smtp_host = _get_smtp_host()
    smtp_port = _get_smtp_port()
    base = _get_agentmail_base()
    inbox_id = _get_inbox_id()

    print("Email (AgentMail) configuration:")
    print(f"  AGENTMAIL_API_KEY:    {'set (' + _mask(api_key or '') + ')' if api_key else 'not set'}")
    print(f"  AGENTMAIL_SMTP_*:     password={'set' if smtp_pass else 'not set'}, user={smtp_user}, host={smtp_host}, port={smtp_port}")
    print("  (SMTP user must be your inbox email from Dashboard → Inboxes; password = API key.)")
    print(f"  API base:             {base}")
    print(f"  Inbox ID:             {inbox_id or 'not set (will try to fetch from API)'}")
    print()

    if not api_key and not smtp_pass:
        print("ERROR: No email credentials. Set AGENTMAIL_API_KEY or AGENTMAIL_SMTP_PASSWORD in .env")
        sys.exit(1)

    # Optional: verify SMTP login (no email sent)
    smtp_ok = False
    if smtp_pass:
        import smtplib
        print("Testing SMTP connection and login...")
        try:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as server:
                server.login(smtp_user, smtp_pass)
            print("  SMTP login OK.")
            smtp_ok = True
        except Exception as e:
            print(f"  SMTP login FAILED: {e}")
            if api_key:
                print("  (Will try HTTP API for sending.)")
        print()

    # If SMTP failed, check API: list inboxes or require AGENTMAIL_INBOX_ID for send
    api_ok = False
    if api_key:
        import requests
        if inbox_id:
            print("AGENTMAIL_INBOX_ID is set; will try send via API if SMTP fails.")
            api_ok = True  # allow attempting send
        else:
            print("Testing AgentMail HTTP API (list inboxes)...")
            try:
                r = requests.get(
                    f"{base}/inboxes",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10,
                )
                if r.status_code == 200:
                    data = r.json()
                    inboxes = data if isinstance(data, list) else data.get("inboxes", data) or []
                    print(f"  API OK. Inboxes: {len(inboxes)}")
                    api_ok = True
                else:
                    print(f"  API FAILED: status {r.status_code} - {r.text[:200]}")
                    print("  Set AGENTMAIL_INBOX_ID to your inbox email (Dashboard → Inboxes) to try send anyway.")
            except Exception as e:
                print(f"  API FAILED: {e}")
        print()

    if not smtp_ok and not api_ok:
        print("ERROR: No working channel.")
        print("  1. Set AGENTMAIL_INBOX_ID to your inbox email (Dashboard → Inboxes).")
        print("  2. Use that same value as AGENTMAIL_SMTP_USER for SMTP (password = API key).")
        sys.exit(1)

    test_email = os.environ.get("TEST_EMAIL", "").strip()
    if test_email:
        print(f"Sending test report notification to: {test_email}")
        try:
            ok = send_report_notification(
                to_emails=[test_email],
                ticker="TEST",
                run_id="test-run",
                recommendation="HOLD",
                confidence=7.5,
            )
            if ok:
                print("SUCCESS: Test email sent. Check your inbox.")
            else:
                print("FAILED: send_report_notification returned False (check credentials and inbox).")
                sys.exit(1)
        except Exception as e:
            print(f"FAILED: {e}")
            sys.exit(1)
    else:
        print("Config looks present. To send a real test email, run:")
        print("  TEST_EMAIL=your@email.com python scripts/test_email_send.py")


if __name__ == "__main__":
    main()
