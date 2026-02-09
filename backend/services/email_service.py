"""Send report notification emails via AgentMail (SMTP or HTTP API)."""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

import requests
from dotenv import load_dotenv

from database import SessionLocal
from models.db_models import Subscription, User

# Load env from backend/.env
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)
load_dotenv(dotenv_path=_env_path.parent.parent / ".env")


def _get_api_key() -> Optional[str]:
    return os.environ.get("AGENTMAIL_API_KEY") or None


def _get_smtp_password() -> Optional[str]:
    """SMTP password: API key (when set) or explicit AGENTMAIL_SMTP_PASSWORD."""
    return _get_api_key() or os.environ.get("AGENTMAIL_SMTP_PASSWORD")


def _get_agentmail_base() -> str:
    return os.environ.get("AGENTMAIL_API_BASE_URL", "https://api.agentmail.to/v0")


def _get_smtp_host() -> str:
    return os.environ.get("AGENTMAIL_SMTP_HOST", "smtp.agentmail.to")


def _get_smtp_port() -> int:
    return int(os.environ.get("AGENTMAIL_SMTP_PORT", "465"))


def _get_smtp_user() -> str:
    """SMTP username must be your inbox email (Dashboard → Inboxes). Password = API key."""
    return (
        os.environ.get("AGENTMAIL_SMTP_USER")
        or os.environ.get("AGENTMAIL_INBOX_ID")
        or "flowdeck@agentmail.to"
    )


def _get_frontend_url() -> str:
    return (os.environ.get("FRONTEND_URL") or "http://localhost:5173").rstrip("/")


def _get_inbox_id() -> Optional[str]:
    """Return configured inbox ID or fetch first inbox from API."""
    inbox_id = os.environ.get("AGENTMAIL_INBOX_ID") or None
    if inbox_id:
        return inbox_id
    api_key = _get_api_key()
    if not api_key:
        return None
    try:
        r = requests.get(
            f"{_get_agentmail_base()}/inboxes",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        inboxes = data if isinstance(data, list) else data.get("inboxes", data) or []
        if inboxes:
            first = inboxes[0]
            return first.get("id") or first.get("inbox_id") or str(first)
    except Exception:
        pass
    return None


def get_subscriber_emails_for_ticker(ticker: str) -> List[str]:
    """Return distinct user emails subscribed to the given ticker."""
    ticker_upper = (ticker or "").strip().upper()
    if not ticker_upper:
        return []
    db = SessionLocal()
    try:
        rows = (
            db.query(User.email)
            .join(Subscription, Subscription.user_id == User.id)
            .filter(Subscription.ticker == ticker_upper)
            .distinct()
            .all()
        )
        return [r.email for r in rows if r.email]
    finally:
        db.close()


def _build_report_email_bodies(
    ticker: str,
    run_id: str,
    recommendation: Optional[str] = None,
    confidence: Optional[float] = None,
) -> tuple[str, str, str]:
    """Return (subject, text_body, html_body)."""
    report_url = f"{_get_frontend_url()}/stocks/{ticker.upper()}"
    if run_id:
        report_url += f"?date={run_id}"
    subject = f"Flowdeck: New report for {ticker.upper()}"
    summary_lines = []
    if recommendation:
        summary_lines.append(f"Recommendation: {recommendation}")
    if confidence is not None:
        summary_lines.append(f"Confidence: {confidence:.1f}/10")
    summary_lines.append("")
    summary_lines.append(f"View full report: {report_url}")
    text_body = "\n".join(summary_lines)
    if not summary_lines or summary_lines == [""]:
        text_body = f"View your report: {report_url}"

    def safe(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    parts = [f"<p>{safe(line)}</p>" for line in summary_lines if line]
    if not parts:
        parts = [f'<p><a href="{report_url}">View your report</a></p>']
    else:
        parts.append(f'<p><a href="{report_url}">View full report</a></p>')
    html_body = "\n".join(parts)
    return subject, text_body, html_body


def _send_via_smtp(
    to_emails: List[str],
    subject: str,
    text_body: str,
    html_body: str,
) -> bool:
    """Send emails via SMTP. Returns True if at least one sent."""
    user = _get_smtp_user()
    password = _get_smtp_password()
    host = _get_smtp_host()
    port = _get_smtp_port()
    if not password:
        return False
    sent = 0
    for email in to_emails:
        if not email or "@" not in email:
            continue
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = user
            msg["To"] = email
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
            with smtplib.SMTP_SSL(host, port) as server:
                server.login(user, password)
                server.sendmail(user, [email], msg.as_string())
            sent += 1
        except Exception:
            pass
    return sent > 0


def _send_via_api(
    to_emails: List[str],
    subject: str,
    text_body: str,
    html_body: str,
) -> bool:
    """Send emails via AgentMail HTTP API. Returns True if at least one sent."""
    api_key = _get_api_key()
    inbox_id = _get_inbox_id()
    if not api_key or not inbox_id:
        return False
    url = f"{_get_agentmail_base()}/inboxes/{inbox_id}/messages/send"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"to": [], "subject": subject, "text": text_body, "html": html_body}
    sent = 0
    for email in to_emails:
        if not email or "@" not in email:
            continue
        payload["to"] = [email]
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=15)
            if r.status_code in (200, 201):
                sent += 1
        except Exception:
            pass
    return sent > 0


def send_report_notification(
    to_emails: List[str],
    ticker: str,
    run_id: str,
    recommendation: Optional[str] = None,
    confidence: Optional[float] = None,
) -> bool:
    """
    Send one email per recipient with report link and optional summary.
    Uses SMTP (smtp.agentmail.to) if AGENTMAIL_SMTP_PASSWORD or AGENTMAIL_API_KEY is set;
    otherwise falls back to AgentMail HTTP API.
    Returns True if at least one email was sent successfully.
    """
    if not to_emails:
        return True
    subject, text_body, html_body = _build_report_email_bodies(
        ticker, run_id, recommendation, confidence
    )
    if _get_smtp_password():
        if _send_via_smtp(to_emails, subject, text_body, html_body):
            return True
    if _get_api_key():
        return _send_via_api(to_emails, subject, text_body, html_body)
    return False


def notify_subscribers_new_report(
    ticker: str,
    run_id: str,
    recommendation: Optional[str] = None,
    confidence: Optional[float] = None,
) -> None:
    """
    Get all subscribers for the ticker and send them a report notification email.
    No-op if AgentMail is not configured or there are no subscribers.
    """
    emails = get_subscriber_emails_for_ticker(ticker)
    if not emails:
        return
    send_report_notification(
        to_emails=emails,
        ticker=ticker,
        run_id=run_id,
        recommendation=recommendation,
        confidence=confidence,
    )
