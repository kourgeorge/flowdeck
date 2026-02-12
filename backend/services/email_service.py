"""Send report notification, welcome, and admin emails via AgentMail (SMTP or HTTP API)."""

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

# Brand colors and layout (email-safe inline styles)
_BRAND_PRIMARY = "#0f766e"   # teal-700
_BRAND_PRIMARY_LIGHT = "#0d9488"  # teal-600
_BRAND_BG = "#f0fdfa"        # teal-50
_TEXT_DARK = "#134e4a"       # teal-900
_TEXT_MUTED = "#64748b"      # slate-500, readable on white
_FONT_FAMILY = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"


def _get_logo_url() -> str:
    """Absolute URL for the logo image (for use in HTML emails)."""
    base = _get_frontend_url()
    return f"{base}/logo.png"


def _html_email_wrapper(title: str, inner_body: str, preheader: Optional[str] = None) -> str:
    """Wrap email content in a consistent Flowdeck layout with logo and footer."""
    logo_url = _get_logo_url()
    preheader_html = ""
    if preheader:
        preheader_html = f'<div style="display:none;max-height:0;overflow:hidden;">{preheader}</div>'
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#e2e8f0;font-family:{_FONT_FAMILY};">
  {preheader_html}
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#e2e8f0;">
    <tr><td style="padding:32px 16px;">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:12px;box-shadow:0 4px 6px rgba(0,0,0,0.07);">
        <tr>
          <td style="padding:32px 32px 24px;text-align:center;border-bottom:1px solid #e2e8f0;">
            <a href="{_get_frontend_url()}" style="text-decoration:none;">
              <img src="{logo_url}" alt="Flowdeck" width="120" height="120" style="display:block;margin:0 auto;object-fit:contain;" />
            </a>
            <p style="margin:8px 0 0;font-size:13px;color:{_TEXT_MUTED};letter-spacing:0.5px;">AI-Powered Stock Analysis</p>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px 32px;">
            {inner_body}
          </td>
        </tr>
        <tr>
          <td style="padding:20px 32px;background:{_BRAND_BG};border-radius:0 0 12px 12px;text-align:center;">
            <p style="margin:0;font-size:12px;color:#64748b;">
              You received this email because you use <strong>Flowdeck</strong>.
            </p>
            <p style="margin:6px 0 0;font-size:11px;color:#94a3b8;">
              &copy; Flowdeck. All rights reserved.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


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
    """Public frontend base URL (web app users open in the browser). Used for all links in emails — dashboard, stock pages, etc. Set FRONTEND_URL in .env (e.g. https://your-domain.com); never use the backend API URL here."""
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
    """Return (subject, text_body, html_body). Link is to the stock page only, not a specific report."""
    report_url = f"{_get_frontend_url()}/stocks/{ticker.upper()}"
    ticker_upper = ticker.upper()
    subject = f"Your {ticker_upper} report is ready — Flowdeck"
    summary_lines = []
    if recommendation:
        summary_lines.append(f"Recommendation: {recommendation}")
    if confidence is not None:
        summary_lines.append(f"Confidence: {confidence:.1f}/10")
    summary_lines.append("")
    summary_lines.append(f"View full report: {report_url}")
    text_body = "\n".join(summary_lines)
    if not summary_lines or summary_lines == [""]:
        text_body = f"Your analysis report for {ticker_upper} is ready.\n\nView your report: {report_url}"

    def safe(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    rec_html = ""
    if recommendation:
        rec_html = f'<p style="margin:0 0 12px;font-size:15px;color:{_TEXT_DARK};"><strong>Recommendation:</strong> <span style="display:inline-block;padding:4px 10px;background:{_BRAND_BG};color:{_BRAND_PRIMARY};border-radius:6px;font-weight:600;">{safe(recommendation)}</span></p>'
    conf_html = ""
    if confidence is not None:
        conf_html = f'<p style="margin:0 0 20px;font-size:14px;color:#64748b;">Confidence: <strong>{confidence:.1f}/10</strong></p>'
    inner = f"""
    <h2 style="margin:0 0 20px;font-size:22px;color:{_TEXT_DARK};font-weight:600;">Your report is ready</h2>
    <p style="margin:0 0 16px;font-size:16px;color:#475569;line-height:1.5;">We've completed a new analysis for <strong>{safe(ticker_upper)}</strong>.</p>
    {rec_html}
    {conf_html}
    <p style="margin:24px 0 0;">
      <a href="{report_url}" style="display:inline-block;padding:14px 28px;background:{_BRAND_PRIMARY};color:#ffffff !important;text-decoration:none;font-weight:600;font-size:15px;border-radius:8px;">View full report</a>
    </p>
    <p style="margin:20px 0 0;font-size:13px;color:#94a3b8;">
      <a href="{report_url}" style="color:{_BRAND_PRIMARY_LIGHT};text-decoration:none;">{report_url}</a>
    </p>
    """
    html_body = _html_email_wrapper(
        title=f"Report for {ticker_upper}",
        inner_body=inner,
        preheader=f"New analysis for {ticker_upper}. " + (f"Recommendation: {recommendation}." if recommendation else "View your report."),
    )
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


# Admin email to notify when a user subscribes
ADMIN_SUBSCRIBE_NOTIFY_EMAIL = "kourgeorge@gmail.com"


def notify_admin_new_subscription(user_email: str, ticker: str) -> None:
    """
    Send a notification to the admin when a user subscribes.
    No-op if AgentMail is not configured.
    """
    ticker_upper = ticker.upper()
    subject = f"New subscriber: {user_email} → {ticker_upper}"
    text_body = (
        f"A user just subscribed to {ticker_upper} on Flowdeck.\n\n"
        f"User: {user_email}\nTicker: {ticker_upper}\n\n"
        f"Dashboard: {_get_frontend_url()}"
    )
    inner = f"""
    <h2 style="margin:0 0 8px;font-size:18px;color:{_TEXT_DARK};font-weight:600;">New subscription</h2>
    <p style="margin:0 0 20px;font-size:14px;color:#64748b;">Someone subscribed to a ticker on Flowdeck.</p>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
      <tr><td style="padding:12px 16px;background:{_BRAND_BG};font-size:12px;color:#64748b;font-weight:600;">User</td><td style="padding:12px 16px;background:#fff;font-size:14px;color:{_TEXT_DARK};">{user_email.replace("@", "&#64;")}</td></tr>
      <tr><td style="padding:12px 16px;background:{_BRAND_BG};font-size:12px;color:#64748b;font-weight:600;">Ticker</td><td style="padding:12px 16px;background:#fff;font-size:14px;color:{_TEXT_DARK};font-weight:600;">{ticker_upper}</td></tr>
    </table>
    <p style="margin:20px 0 0;">
      <a href="{_get_frontend_url()}" style="display:inline-block;padding:10px 20px;background:{_BRAND_PRIMARY};color:#ffffff !important;text-decoration:none;font-weight:600;font-size:14px;border-radius:8px;">Open Flowdeck</a>
    </p>
    """
    html_body = _html_email_wrapper(title="New subscription", inner_body=inner)
    to_emails = [ADMIN_SUBSCRIBE_NOTIFY_EMAIL]
    if _get_smtp_password():
        if _send_via_smtp(to_emails, subject, text_body, html_body):
            return
    if _get_api_key():
        _send_via_api(to_emails, subject, text_body, html_body)


def send_welcome_email(user_email: str) -> bool:
    """
    Send a welcome email to a newly registered user.
    Returns True if sent successfully (or email not configured).
    """
    subject = "Welcome to Flowdeck — you're all set"
    dashboard_url = _get_frontend_url()
    text_body = (
        f"Welcome to Flowdeck!\n\n"
        f"You're all set. Sign in and start exploring AI-powered stock analysis.\n\n"
        f"Get started: {dashboard_url}\n\n"
        f"— The Flowdeck team"
    )
    inner = f"""
    <h2 style="margin:0 0 12px;font-size:22px;color:{_TEXT_DARK};font-weight:600;">Welcome to Flowdeck</h2>
    <p style="margin:0 0 16px;font-size:16px;color:#475569;line-height:1.5;">Thanks for signing up. You're all set to use AI-powered stock analysis.</p>
    <ul style="margin:16px 0 24px;padding-left:20px;color:#475569;font-size:15px;line-height:1.7;">
      <li>Search any ticker and run deep-dive analyses</li>
      <li>Subscribe to tickers to get new reports by email</li>
      <li>Read market, news, and fundamentals insights in one place</li>
    </ul>
    <p style="margin:24px 0 0;">
      <a href="{dashboard_url}" style="display:inline-block;padding:14px 28px;background:{_BRAND_PRIMARY};color:#ffffff !important;text-decoration:none;font-weight:600;font-size:15px;border-radius:8px;">Go to Flowdeck</a>
    </p>
    <p style="margin:28px 0 0;font-size:14px;color:#94a3b8;">If you didn't create an account, you can ignore this email.</p>
    """
    html_body = _html_email_wrapper(
        title="Welcome to Flowdeck",
        inner_body=inner,
        preheader="You're all set. Start exploring AI-powered stock analysis.",
    )
    to_emails = [user_email]
    if not to_emails or "@" not in (to_emails[0] or ""):
        return True
    if _get_smtp_password() and _send_via_smtp(to_emails, subject, text_body, html_body):
        return True
    if _get_api_key() and _send_via_api(to_emails, subject, text_body, html_body):
        return True
    return False


def send_subscription_confirmation(user_email: str, ticker: str) -> bool:
    """
    Send the user an email confirming their subscription and explaining what they get.
    Returns True if sent successfully (or email not configured).
    """
    if not user_email or "@" not in user_email:
        return True
    ticker_upper = ticker.upper()
    stock_url = f"{_get_frontend_url()}/stocks/{ticker_upper}"
    subject = f"You're subscribed to {ticker_upper} — Flowdeck"
    text_body = (
        f"You're subscribed to {ticker_upper} on Flowdeck.\n\n"
        f"What you get:\n"
        f"• We'll email you when a new analysis report is ready for {ticker_upper}\n"
        f"• You can view the latest report and run new analyses anytime on the stock page\n"
        f"• Unsubscribe anytime from your Flowdeck account\n\n"
        f"View {ticker_upper}: {stock_url}\n\n"
        f"— The Flowdeck team"
    )
    inner = f"""
    <h2 style="margin:0 0 12px;font-size:22px;color:{_TEXT_DARK};font-weight:600;">You're subscribed to {ticker_upper}</h2>
    <p style="margin:0 0 20px;font-size:16px;color:#475569;line-height:1.5;">Here's what your subscription gives you:</p>
    <ul style="margin:0 0 24px;padding-left:20px;color:#475569;font-size:15px;line-height:1.8;">
      <li><strong>Email when new reports are ready</strong> — We'll notify you whenever a new analysis report is published for {ticker_upper}.</li>
      <li><strong>View the latest report anytime</strong> — Open the stock page to read the full analysis, key takeaways, and recommendation.</li>
      <li><strong>Run new analyses</strong> — Trigger a fresh deep-dive (market, news, fundamentals) whenever you want.</li>
      <li><strong>Unsubscribe anytime</strong> — You can manage or remove subscriptions from your Flowdeck account.</li>
    </ul>
    <p style="margin:24px 0 0;">
      <a href="{stock_url}" style="display:inline-block;padding:14px 28px;background:{_BRAND_PRIMARY};color:#ffffff !important;text-decoration:none;font-weight:600;font-size:15px;border-radius:8px;">View {ticker_upper} on Flowdeck</a>
    </p>
    <p style="margin:20px 0 0;font-size:13px;color:#94a3b8;">Ticker: <strong>{ticker_upper}</strong></p>
    """
    html_body = _html_email_wrapper(
        title=f"Subscribed to {ticker_upper}",
        inner_body=inner,
        preheader=f"You'll get an email when new {ticker_upper} reports are ready.",
    )
    to_emails = [user_email]
    if _get_smtp_password() and _send_via_smtp(to_emails, subject, text_body, html_body):
        return True
    if _get_api_key() and _send_via_api(to_emails, subject, text_body, html_body):
        return True
    return False


def notify_subscribers_new_report(
    ticker: str,
    run_id: str,
    recommendation: Optional[str] = None,
    confidence: Optional[float] = None,
    initiator_email: Optional[str] = None,
) -> None:
    """
    Get all subscribers for the ticker (and optionally the initiator) and send report notification emails.
    initiator_email: if set, the user who ran the analysis is also notified (in addition to subscribers).
    No-op if email is not configured or there are no recipients.
    """
    emails = list(get_subscriber_emails_for_ticker(ticker))
    if initiator_email and initiator_email.strip() and "@" in initiator_email:
        initiator_email = initiator_email.strip().lower()
        if initiator_email not in [e.lower() for e in emails]:
            emails.append(initiator_email)
    if not emails:
        return
    send_report_notification(
        to_emails=emails,
        ticker=ticker,
        run_id=run_id,
        recommendation=recommendation,
        confidence=confidence,
    )
