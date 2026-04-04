"""Send report notification, welcome, and admin emails via AgentMail (SMTP or HTTP API)."""

import os
import json
import html
import base64
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path
from typing import List, Optional

import requests
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

from database import SessionLocal
from models.db_models import Subscription, User, Execution, Report

# Load env from backend/.env
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)
load_dotenv(dotenv_path=_env_path.parent.parent / ".env")

# Setup Jinja2 template environment
_template_dir = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(_template_dir),
    autoescape=select_autoescape(['html', 'xml'])
)

# Brand colors and layout (email-safe inline styles)
_BRAND_PRIMARY = "#2563eb"   # blue-600
_FONT_FAMILY = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
_EMAIL_LOGO_CID = "flowdeck-logo"


def _get_email_logo_data_uri() -> str:
    """Return the self-contained Flowdeck logo as a data URI for email templates."""
    cached_path = Path(__file__).resolve().parent / "email_logo_data_uri.txt"
    if cached_path.is_file():
        try:
            cached_value = cached_path.read_text().strip()
        except OSError:
            cached_value = ""
        if cached_value.startswith("data:image/"):
            return cached_value

    logo_path = Path(__file__).resolve().parent.parent.parent / "logo.svg"
    if not logo_path.is_file():
        return ""
    try:
        svg_b64 = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:image/svg+xml;base64,{svg_b64}"


def _get_email_logo_png_bytes() -> bytes:
    """Extract the embedded PNG bytes from the repo logo.svg for email CID embedding."""
    logo_path = Path(__file__).resolve().parent.parent.parent / "logo.svg"
    if not logo_path.is_file():
        return b""
    try:
        svg_text = logo_path.read_text(encoding="utf-8")
    except OSError:
        return b""

    marker = "data:image/png;base64,"
    start = svg_text.find(marker)
    if start == -1:
        return b""
    start += len(marker)
    end = svg_text.find('"', start)
    if end == -1:
        return b""
    try:
        return base64.b64decode(svg_text[start:end])
    except Exception:
        return b""


_EMAIL_LOGO_DATA_URI = _get_email_logo_data_uri()
_EMAIL_LOGO_PNG_BYTES = _get_email_logo_png_bytes()

_jinja_env.globals["email_logo_src"] = _EMAIL_LOGO_DATA_URI


def _detect_text_direction(text: str) -> str:
    """
    Detect if text contains RTL (right-to-left) characters.
    Returns 'rtl' for Hebrew, Arabic, Persian, etc., otherwise 'ltr'.
    """
    if not text:
        return "ltr"
    
    # RTL Unicode ranges:
    # Hebrew: 0x0590-0x05FF
    # Arabic: 0x0600-0x06FF, 0x0750-0x077F, 0xFB50-0xFDFF, 0xFE70-0xFEFF
    # Persian/Urdu additions are within Arabic range
    rtl_chars = 0
    total_chars = 0
    
    for char in text:
        code = ord(char)
        # Skip whitespace and punctuation
        if char.isspace() or not char.isalnum():
            continue
        total_chars += 1
        # Check if character is in RTL range
        if (0x0590 <= code <= 0x05FF or  # Hebrew
            0x0600 <= code <= 0x06FF or  # Arabic
            0x0750 <= code <= 0x077F or  # Arabic Supplement
            0xFB50 <= code <= 0xFDFF or  # Arabic Presentation Forms-A
            0xFE70 <= code <= 0xFEFF):   # Arabic Presentation Forms-B
            rtl_chars += 1
    
    # If more than 30% of characters are RTL, consider the text RTL
    if total_chars > 0 and (rtl_chars / total_chars) > 0.3:
        return "rtl"
    return "ltr"

def _html_email_wrapper(
    title: str,
    inner_body: str,
    preheader: Optional[str] = None,
) -> str:
    """Wrap email content in a consistent Flowdeck layout; content centered, with Flowdeck title."""
    preheader_html = ""
    if preheader:
        preheader_html = f'<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{preheader}</div>'
    logo_html = ""
    if _EMAIL_LOGO_DATA_URI:
        logo_html = (
            f'<img src="{_EMAIL_LOGO_DATA_URI}" alt="Flowdeck" width="34" height="34" '
            'style="display:block;width:34px;height:34px;border:0;outline:none;text-decoration:none;">'
        )
    else:
        logo_html = (
            '<div style="width:34px;height:34px;border-radius:10px;background:#dbeafe;'
            'text-align:center;line-height:34px;font-size:13px;font-weight:700;color:#1d4ed8;">FD</div>'
        )
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
</head>
<body style="margin:0;padding:0;background:#dbe4ee;font-family:{_FONT_FAMILY};color:#0f172a;">
  {preheader_html}
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#dbe4ee;">
    <tr><td align="center" style="padding:28px 16px;">
      <table role="presentation" width="600" align="center" cellspacing="0" cellpadding="0" style="width:100%;max-width:600px;margin:0 auto;background:#f4f7fa;border:1px solid #bfccda;border-collapse:separate;border-spacing:0;border-radius:20px;">
        <tr>
          <td style="padding:26px 40px 22px;background:#1b2638;border-bottom:1px solid #314154;">
            <table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 0 18px;">
              <tr>
                <td style="vertical-align:middle;">{logo_html}</td>
                <td style="padding-left:12px;vertical-align:middle;">
                  <p style="margin:0;font-size:13px;line-height:1.4;color:#bfdbfe;text-transform:uppercase;letter-spacing:0.18em;font-weight:700;">Flowdeck</p>
                </td>
              </tr>
            </table>
            <h1 style="margin:0 0 12px;font-size:28px;line-height:1.2;color:#f8fafc;font-weight:700;">{title}</h1>
            <div style="font-size:15px;line-height:1.7;color:#d7e0ea;">
              {inner_body}
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:18px 40px 24px;background:#eef3f7;border-top:1px solid #d5dee8;">
            <p style="margin:0;font-size:12px;color:#64748b;">
              You received this email because you use <strong>Flowdeck</strong>.
            </p>
            <p style="margin:12px 0 0;font-size:11px;color:#94a3b8;">
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
            .filter(Subscription.ticker == ticker_upper, Subscription.email_updates)
            .distinct()
            .all()
        )
        return [r.email for r in rows if r.email]
    finally:
        db.close()


def _build_report_email_bodies(
    ticker: str,
    recommendation: Optional[str] = None,
    confidence: Optional[float] = None,
    scores: Optional[dict] = None,
) -> tuple[str, str, str]:
    """Return (subject, text_body, html_body). Link is to the stock page only, not a specific report."""
    display_confidence = confidence
    # Backward compatibility: some callers/store metadata as normalized 0-1 confidence.
    if display_confidence is not None and 0 <= display_confidence <= 1:
        display_confidence = display_confidence * 10

    report_url = f"{_get_frontend_url()}/tickers/{ticker.upper()}"
    ticker_upper = ticker.upper()
    subject = f"Your {ticker_upper} report is ready — Flowdeck"
    summary_lines = []
    if recommendation:
        summary_lines.append(f"Recommendation: {recommendation}")
    if display_confidence is not None:
        summary_lines.append(f"Confidence: {display_confidence:.1f}/10")
    # Add scores to text body
    if scores:
        summary_lines.append("")
        summary_lines.append("Analysis Scores:")
        for report_type, report_data in scores.items():
            score = report_data.get("score")
            score_label = report_data.get("score_label")
            if score is not None or score_label:
                display_name = report_type.replace("_", " ").title()
                if score is not None:
                    summary_lines.append(f"  • {display_name}: {score:.1f}/10" + (f" ({score_label})" if score_label else ""))
                elif score_label:
                    summary_lines.append(f"  • {display_name}: {score_label}")
    
    summary_lines.append("")
    summary_lines.append(f"View full report: {report_url}")
    text_body = "\n".join(summary_lines)
    if not summary_lines or summary_lines == [""]:
        text_body = f"Your analysis report for {ticker_upper} is ready.\n\nView your report: {report_url}"

    # These variables are kept for backwards compatibility with older templates,
    # but the current template reads data directly from the context.
    
    # Prepare scores data for template
    scores_list = []
    bull_view = None
    bear_view = None
    key_insights = []
    
    if scores:
        for report_type, report_data in scores.items():
            score = report_data.get("score")
            score_label = report_data.get("score_label")
            # Only include items that have a score, exclude final_trade_decision
            if score is not None and report_type != "final_trade_decision":
                display_name = report_type.replace("_", " ").title()
                # Remove " Report" suffix from display name
                display_name = display_name.replace(" Report", "")
                # Use consistent terminology with frontend
                if display_name == "Investment Plan":
                    display_name = "Research"
                # Color code based on score
                score_color = "#64748b"  # default gray
                if score >= 7:
                    score_color = "#1e40af"  # website dark-blue
                elif score >= 5:
                    score_color = "#1e40af"  # website dark-blue
                else:
                    score_color = "#dc2626"  # red-600
                
                scores_list.append({
                    "name": display_name,
                    "score": f"{score:.1f}",
                    "label": score_label,
                    "color": score_color
                })
            
            # Extract bull/bear viewpoints (keep as list for bullet points in email)
            # Check investment_plan, trader_investment_plan, and final_trade_decision
            if report_type in ("investment_plan", "trader_investment_plan", "final_trade_decision"):
                if not bull_view and report_data.get("bull_viewpoint"):
                    bv = report_data.get("bull_viewpoint")
                    if isinstance(bv, list) and bv:
                        bull_view = bv
                    elif isinstance(bv, str) and bv:
                        bull_view = [bv]
                if not bear_view and report_data.get("bear_viewpoint"):
                    bv = report_data.get("bear_viewpoint")
                    if isinstance(bv, list) and bv:
                        bear_view = bv
                    elif isinstance(bv, str) and bv:
                        bear_view = [bv]
            
            # Extract key takeaways/insights only from Market, News, and Fundamentals reports
            if report_type in ("market_report", "news_report", "fundamentals_report"):
                if report_data.get("key_takeaways"):
                    takeaways = report_data.get("key_takeaways")
                    if isinstance(takeaways, list):
                        key_insights.extend(takeaways[:2])  # Limit to first 2 per report
                    elif isinstance(takeaways, str):
                        key_insights.append(takeaways)
    
    # Limit key insights to 4 total (to keep email concise)
    key_insights = key_insights[:4] if key_insights else None
    
    # Render HTML from template
    try:
        template = _jinja_env.get_template("report_notification_email.html")
        # Detect text direction from key insights and viewpoints
        text_to_check = " ".join([
            " ".join(key_insights) if key_insights else "",
            " ".join(bull_view) if bull_view else "",
            " ".join(bear_view) if bear_view else "",
        ])
        text_direction = _detect_text_direction(text_to_check)
        html_body = template.render(
            ticker=ticker_upper,
            recommendation=recommendation,
            confidence=f"{display_confidence:.1f}" if display_confidence is not None else None,
            scores=scores_list if scores_list else None,
            key_insights=key_insights,
            bull_view=bull_view,
            bear_view=bear_view,
            report_url=report_url,
            profile_url=f"{_get_frontend_url()}/profile",
            preheader=f"New analysis for {ticker_upper}. " + (f"Recommendation: {recommendation}." if recommendation else "View your report."),
            text_direction=text_direction,
        )
    except Exception:
        # Fallback to simple wrapper if template fails
        html_body = _html_email_wrapper(
            title=f"Report for {ticker_upper}",
            inner_body=f"<p>Your report for {ticker_upper} is ready. <a href='{report_url}'>View report</a></p>",
            preheader=f"New analysis for {ticker_upper}."
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
            msg = MIMEMultipart("related")
            msg["Subject"] = subject
            msg["From"] = user
            msg["To"] = email
            alt = MIMEMultipart("alternative")
            alt.attach(MIMEText(text_body, "plain"))

            html_part = html_body
            if _EMAIL_LOGO_DATA_URI and _EMAIL_LOGO_PNG_BYTES:
                html_part = html_part.replace(_EMAIL_LOGO_DATA_URI, f"cid:{_EMAIL_LOGO_CID}")
            alt.attach(MIMEText(html_part, "html"))
            msg.attach(alt)

            if _EMAIL_LOGO_PNG_BYTES and f"cid:{_EMAIL_LOGO_CID}" in html_part:
                logo_part = MIMEImage(_EMAIL_LOGO_PNG_BYTES, _subtype="png")
                logo_part.add_header("Content-ID", f"<{_EMAIL_LOGO_CID}>")
                logo_part.add_header("Content-Disposition", "inline", filename="flowdeck-logo.png")
                msg.attach(logo_part)

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
    recommendation: Optional[str] = None,
    confidence: Optional[float] = None,
    scores: Optional[dict] = None,
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
        ticker=ticker,
        recommendation=recommendation,
        confidence=confidence,
        scores=scores,
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
    
    try:
        template = _jinja_env.get_template("admin_new_subscription_email.html")
        html_body = template.render(
            user_email=user_email,
            ticker=ticker_upper,
            dashboard_url=_get_frontend_url(),
            text_direction="ltr"  # Admin emails are in English
        )
    except Exception:
        # Fallback to simple wrapper if template fails
        html_body = _html_email_wrapper(
            title="New subscription",
            inner_body=f"<p>New subscription: {user_email} → {ticker_upper}</p>",
        )
    
    to_emails = [ADMIN_SUBSCRIBE_NOTIFY_EMAIL]
    if _get_smtp_password():
        if _send_via_smtp(to_emails, subject, text_body, html_body):
            return
    if _get_api_key():
        _send_via_api(to_emails, subject, text_body, html_body)


# Contact form submissions are sent to the same admin address
CONTACT_FORM_RECIPIENT = "kourgeorge@gmail.com"


def send_contact_form_email(name: str, email: str, message: str) -> bool:
    """
    Send the contact form submission to the admin (kourgeorge@gmail.com).
    Returns True if sent successfully; False if email is not configured or send failed.
    """
    subject = "Flowdeck – Contact form"
    text_body = (
        f"Contact form submission from Flowdeck.\n\n"
        f"Name: {name or '(not provided)'}\n"
        f"Email: {email or '(not provided)'}\n\n"
        f"Message:\n{message or '(empty)'}\n\n"
        f"Dashboard: {_get_frontend_url()}"
    )

    def safe(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("@", "&#64;")

    dashboard_url = _get_frontend_url()
    try:
        template = _jinja_env.get_template("contact_form_email.html")
        # Detect text direction from the message content
        text_direction = _detect_text_direction(message or "")
        html_body = template.render(
            name=name or "(not provided)",
            email=email or "",
            message=message or "(empty)",
            dashboard_url=dashboard_url,
            text_direction=text_direction,
        )
    except Exception:
        inner = f"""
        <p style="margin:0 0 16px;font-size:15px;color:#475569;line-height:1.7;">A new message was sent from the Flowdeck contact form.</p>
        <p style="margin:0 0 12px;font-size:15px;color:#475569;line-height:1.6;"><strong>Name:</strong> {safe(name) or '(not provided)'}</p>
        <p style="margin:0 0 12px;font-size:15px;color:#475569;line-height:1.6;"><strong>Email:</strong> {safe(email) or '(not provided)'}</p>
        <p style="margin:0 0 24px;font-size:15px;color:#475569;line-height:1.6;white-space:pre-wrap;"><strong>Message:</strong><br>{safe(message) or '(empty)'}</p>
        <p style="margin:0;"><a href="{dashboard_url}" style="display:inline-block;padding:13px 24px;background:{_BRAND_PRIMARY};color:#ffffff !important;text-decoration:none;font-weight:700;font-size:14px;border-radius:10px;">Open Flowdeck</a></p>
        """
        html_body = _html_email_wrapper(
            title="Contact form submission",
            inner_body=inner,
        )
    to_emails = [CONTACT_FORM_RECIPIENT]
    if _get_smtp_password() and _send_via_smtp(to_emails, subject, text_body, html_body):
        return True
    if _get_api_key() and _send_via_api(to_emails, subject, text_body, html_body):
        return True
    return False


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
    
    try:
        template = _jinja_env.get_template("welcome_email.html")
        html_body = template.render(
            dashboard_url=dashboard_url,
            text_direction="ltr"  # Welcome emails are in English
        )
    except Exception:
        # Fallback to simple wrapper if template fails
        html_body = _html_email_wrapper(
            title="Welcome to Flowdeck",
            inner_body=f"<p>Welcome to Flowdeck! <a href='{dashboard_url}'>Get started</a></p>",
            preheader="You're all set."
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
    stock_url = f"{_get_frontend_url()}/tickers/{ticker_upper}"
    subject = "Subscription confirmed — Flowdeck"
    text_body = (
        f"Your subscription is confirmed.\n\n"
        f"What you get:\n"
        f"• We'll email you when a new analysis report is ready for {ticker_upper}\n"
        f"• You can view the latest report and run new analyses anytime on the stock page\n"
        f"• Unsubscribe anytime from your Flowdeck account\n\n"
        f"View {ticker_upper}: {stock_url}\n\n"
        f"— The Flowdeck team"
    )
    
    try:
        template = _jinja_env.get_template("subscription_confirmation_email.html")
        html_body = template.render(
            ticker=ticker_upper,
            stock_url=stock_url,
            text_direction="ltr"  # Subscription emails are in English
        )
    except Exception:
        # Fallback to simple wrapper if template fails
        html_body = _html_email_wrapper(
            title="Subscription confirmed",
            inner_body=f"<p>Your subscription to {ticker_upper} is confirmed. <a href='{stock_url}'>View stock</a></p>",
            preheader=f"You'll get an email when new {ticker_upper} reports are ready."
        )
    
    to_emails = [user_email]
    if _get_smtp_password() and _send_via_smtp(to_emails, subject, text_body, html_body):
        return True
    if _get_api_key() and _send_via_api(to_emails, subject, text_body, html_body):
        return True
    return False


def notify_subscribers_new_report(
    ticker: str,
    execution_id: int,
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
    
    # Fetch scores from the report
    from services.report_service import ReportService
    report_service = ReportService()
    scores = None
    try:
        scores = report_service.get_reports_with_scores(execution_id)
    except Exception:
        pass  # Continue without scores if fetch fails
    
    send_report_notification(
        to_emails=emails,
        ticker=ticker,
        recommendation=recommendation,
        confidence=confidence,
        scores=scores,
    )


BRIEF_SECTION_TOKENS = {"market_highlights", "key_signals", "what_to_watch", "risks_opportunities"}


def _format_brief_narrative_for_email(narrative: str) -> str:
    """
    Format the digest narrative into HTML that roughly matches the Dashboard brief tab styling.
    - If the narrative uses structured sections (## headings + special tokens), render one block per section.
    - Otherwise, render a simple paragraph with preserved line breaks.
    - Converts markdown tables to HTML tables.
    """
    if not narrative:
        return ""

    lines = narrative.splitlines()
    # Remove standalone special-token lines.
    filtered = [ln for ln in lines if ln.strip() not in BRIEF_SECTION_TOKENS]

    text = "\n".join(filtered).strip()
    if not text:
        return ""

    # Detect markdown-style sections (## Heading)
    has_headings = any(ln.lstrip().startswith("## ") for ln in filtered)
    if not has_headings:
        escaped = html.escape(text)
        # Preserve paragraphs and simple line breaks.
        parts = [f"<p style=\"margin:0 0 8px;font-size:14px;line-height:1.7;color:#0f172a;\">{p}</p>"
                 for p in (escaped.replace("\r", "").split("\n\n"))]
        return "".join(parts)

    sections = []
    current_title = None
    current_body: list[str] = []

    def flush():
        if current_title is None:
            return
        body_text = "\n".join(current_body).strip()
        sections.append((current_title, body_text))

    for raw in filtered:
        line = raw.rstrip()
        if line.lstrip().startswith("## "):
            # New section.
            flush()
            current_title = line.lstrip()[3:].strip()
            current_body = []
        else:
            if current_title is None:
                # Ignore preamble lines before the first heading.
                continue
            current_body.append(line)
    flush()

    # Map section titles to colors with light backgrounds suitable for email.
    def section_styles(title: str) -> dict[str, str]:
        key = title.lower()
        if "market highlight" in key:
            return {
                "bg": "#eff6ff",
                "border": "#bfdbfe",
                "title": "#2563eb",
                "text": "#0f172a",
            }
        if "key signal" in key:
            return {
                "bg": "#f8fafc",
                "border": "#cbd5e1",
                "title": "#334155",
                "text": "#0f172a",
            }
        if "what to watch" in key:
            return {
                "bg": "#eff6ff",
                "border": "#bfdbfe",
                "title": "#475569",
                "text": "#334155",
            }
        if "risk" in key:
            return {
                "bg": "#fbfcfd",
                "border": "#cbd5e1",
                "title": "#64748b",
                "text": "#334155",
            }
        # Default neutral section with light background.
        return {
            "bg": "#f8fafc",
            "border": "#dbe2ea",
            "title": "#334155",
            "text": "#0f172a",
        }

    def _convert_markdown_table_to_html(text: str) -> str:
        """Convert markdown tables to HTML tables."""
        lines = text.split("\n")
        result_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Check if this line looks like a table row (contains |)
            if "|" in line and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                
                # Check if next line is a separator (contains | and -)
                if "|" in next_line and "-" in next_line:
                    # This is a table header
                    table_lines = [line]
                    i += 2  # Skip separator line
                    
                    # Collect table body rows
                    while i < len(lines) and "|" in lines[i]:
                        table_lines.append(lines[i].strip())
                        i += 1
                    
                    # Convert to HTML table
                    if table_lines:
                        table_html = _build_html_table(table_lines)
                        result_lines.append(table_html)
                    continue
            
            result_lines.append(line)
            i += 1
        
        return "\n".join(result_lines)
    
    def _build_html_table(table_lines: list[str]) -> str:
        """Build an HTML table from markdown table lines."""
        if not table_lines:
            return ""
        
        # Parse header
        header_cells = [cell.strip() for cell in table_lines[0].split("|") if cell.strip()]
        
        # Parse body rows
        body_rows = []
        for line in table_lines[1:]:
            cells = [cell.strip() for cell in line.split("|") if cell.strip()]
            if cells:
                body_rows.append(cells)
        
        # Build HTML
        table_style = (
            "width:100%;border-collapse:collapse;margin:8px 0;"
            "font-size:12px;background:#ffffff;border:1px solid #e2e8f0;"
        )
        th_style = (
            "padding:8px 10px;text-align:left;background:#f1f5f9;"
            "border-bottom:2px solid #cbd5e1;font-weight:600;color:#334155;"
        )
        td_style = (
            "padding:8px 10px;border-bottom:1px solid #e2e8f0;color:#0f172a;"
        )
        
        html_parts = [f'<table style="{table_style}">']
        
        # Header
        html_parts.append("<thead><tr>")
        for cell in header_cells:
            html_parts.append(f'<th style="{th_style}">{html.escape(cell)}</th>')
        html_parts.append("</tr></thead>")
        
        # Body
        html_parts.append("<tbody>")
        for row in body_rows:
            html_parts.append("<tr>")
            for cell in row:
                html_parts.append(f'<td style="{td_style}">{html.escape(cell)}</td>')
            html_parts.append("</tr>")
        html_parts.append("</tbody>")
        
        html_parts.append("</table>")
        return "".join(html_parts)

    html_sections: list[str] = []
    for title, body in sections:
        styles = section_styles(title)
        escaped_title = html.escape(title)
        
        # Convert markdown tables to HTML before escaping
        body_with_tables = _convert_markdown_table_to_html(body)
        
        # Process the body: escape non-table content, preserve table HTML
        body_parts = []
        for part in body_with_tables.split("\n"):
            if part.strip().startswith("<table"):
                # This is HTML table, keep as-is
                body_parts.append(part)
            elif "</table>" in part:
                body_parts.append(part)
            elif body_parts and body_parts[-1].strip().startswith("<table") and not "</table>" in body_parts[-1]:
                # Inside a table, keep accumulating
                body_parts[-1] += "\n" + part
            else:
                # Regular text, escape and convert line breaks
                if part.strip():
                    body_parts.append(html.escape(part))
        
        body_html = "<br>".join(body_parts)
        
        html_sections.append(
            (
                f"<div style=\"margin:0 0 20px;\">"
                f"<p style=\"margin:0 0 8px;font-size:13px;font-weight:700;"
                f"letter-spacing:0.08em;text-transform:uppercase;color:#64748b;\">"
                f"{escaped_title}</p>"
                f"<div style=\"font-size:14px;line-height:1.8;color:#0f172a;\">"
                f"{body_html}</div></div>"
            )
        )

    return "".join(html_sections)


def send_daily_digest_email_to_user(execution_id: int, user_email: str) -> bool:
    """
    Send a User Daily Brief (daily_digest execution) to the given user email.
    Returns True if sent successfully (or email not configured).
    """
    if not user_email or "@" not in user_email:
        return False

    db = SessionLocal()
    try:
        ex = (
            db.query(Execution)
            .filter(
                Execution.id == execution_id,
                Execution.execution_type == "daily_digest",
                Execution.subject_type == "user_date",
            )
            .first()
        )
        if not ex:
            return False

        report = (
            db.query(Report)
            .filter(
                Report.execution_id == ex.id,
                Report.report_type == "daily_digest",
            )
            .first()
        )
        if not report:
            return False

        meta: dict = {}
        if report.metadata_json:
            try:
                meta = json.loads(report.metadata_json) or {}
            except Exception:
                meta = {}

        digest_date = str(meta.get("digest_date") or "")
        span_label = str(meta.get("span_label") or "Daily")
        priority_tickers = meta.get("priority_tickers") or []
        if not isinstance(priority_tickers, list):
            priority_tickers = []
        what_to_watch = str(meta.get("what_to_watch") or "")
        narrative = report.content or ""

        from services.share_service import get_share_url

        share_url = get_share_url(execution_id)
        brief_url = share_url or f"{_get_frontend_url()}/dashboard?tab=digest"

        subject_parts = ["Your Flowdeck Daily Brief"]
        if digest_date:
            subject_parts.append(f"- {digest_date}")
        subject = " ".join(part for part in subject_parts if part)

        lines = []
        header_line = "Your latest Daily Brief is ready."
        if digest_date:
            header_line = f"Your Daily Brief for {digest_date} is ready."
        lines.append(header_line)
        if priority_tickers:
            lines.append("")
            lines.append("Focus: " + ", ".join(str(t) for t in priority_tickers))
        lines.append("")
        lines.append(narrative.strip())
        lines.append("")
        lines.append(f"View this brief in Flowdeck: {brief_url}")
        text_body = "\n".join(lines)

        # Render from shared template to match other emails
        try:
            template = _jinja_env.get_template("daily_digest_email.html")
            # Format narrative so section headings and colors roughly match the dashboard Brief card.
            narrative_html = _format_brief_narrative_for_email(narrative)
            # Detect text direction from narrative content
            text_direction = _detect_text_direction(narrative)
            html_body = template.render(
                digest_date=digest_date,
                span_label=span_label,
                priority_tickers=priority_tickers,
                narrative_html=narrative_html,
                what_to_watch=what_to_watch,
                brief_url=brief_url,
                preheader=f"Your Daily Brief for {digest_date} is ready." if digest_date else "Your Daily Brief is ready.",
                text_direction=text_direction,
            )
        except Exception:
            # Fallback to simple wrapper if template fails
            html_body = _html_email_wrapper(
                title="Daily Brief",
                inner_body=f"<p>Your Daily Brief is ready. <a href='{brief_url}'>Open brief</a></p>",
                preheader=f"Your Daily Brief for {digest_date} is ready." if digest_date else "Your Daily Brief is ready.",
            )

        to_emails = [user_email]
        if _get_smtp_password() and _send_via_smtp(to_emails, subject, text_body, html_body):
            return True
        if _get_api_key() and _send_via_api(to_emails, subject, text_body, html_body):
            return True
        return False
    finally:
        db.close()
