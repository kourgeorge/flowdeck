"""Contact form submission – sends email to admin."""

import logging
import threading
import time
from collections import deque

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from services.email_service import send_contact_form_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Contact"])

# The route needs no sign-in and every POST sends one email, so without caps
# anyone could script ~1 MB emails (nginx's default body limit) to the admin
# inbox and burn the send quota shared with report and digest emails.
NAME_MAX_LENGTH = 200
EMAIL_MAX_LENGTH = 254  # RFC 5321 limit on a full address
MESSAGE_MAX_LENGTH = 5000


class ContactRequest(BaseModel):
    name: str = Field(default="", max_length=NAME_MAX_LENGTH)
    email: EmailStr = Field(max_length=EMAIL_MAX_LENGTH)
    message: str = Field(default="", max_length=MESSAGE_MAX_LENGTH)


# Simple sliding-window limit: RATE_LIMIT_MAX submissions per client IP per
# RATE_LIMIT_WINDOW_SECONDS. The state lives in this process's memory, so it
# is per worker process: with N uvicorn workers a client can get up to N times
# the limit, and a restart clears it. Good enough to stop a single script from
# flooding the inbox without adding a dependency or Redis round-trip.
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW_SECONDS = 600
# Bound on how many distinct IPs we track, so a flood of spoofed/rotating
# addresses can't grow this dict without limit.
_RATE_LIMIT_MAX_KEYS = 10_000

_hits: dict[str, deque[float]] = {}
_hits_lock = threading.Lock()


def reset_rate_limit() -> None:
    """Clear all limiter state (used by tests)."""
    with _hits_lock:
        _hits.clear()


def _client_ip(request: Request) -> str:
    # We use the socket peer address and deliberately ignore X-Forwarded-For:
    # nothing in the app trusts that header, and port 8002 is also published
    # directly in docker/compose.yml, so a caller could set it to any value and
    # dodge the limit. uvicorn only rewrites client.host from proxy headers
    # when the peer is in --forwarded-allow-ips.
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str) -> bool:
    """Record a hit for `ip`; return False if it is over the limit."""
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    with _hits_lock:
        if ip not in _hits and len(_hits) >= _RATE_LIMIT_MAX_KEYS:
            # Drop IPs whose hits have all expired; if still full, drop the
            # oldest-inserted entries rather than refuse everyone.
            for key in [k for k, q in _hits.items() if not q or q[-1] <= cutoff]:
                del _hits[key]
            while len(_hits) >= _RATE_LIMIT_MAX_KEYS:
                del _hits[next(iter(_hits))]
        q = _hits.setdefault(ip, deque())
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= RATE_LIMIT_MAX:
            return False
        q.append(now)
        return True


@router.post("/contact")
def submit_contact(req: ContactRequest, request: Request):
    """
    Submit the contact form. Sends an email to the admin with name, email, and message.
    No authentication required; rate limited per client IP.
    """
    if not _check_rate_limit(_client_ip(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many messages sent. Please wait a few minutes and try again.",
            headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
        )
    try:
        sent = send_contact_form_email(
            name=(req.name or "").strip(),
            email=req.email.strip(),
            message=(req.message or "").strip(),
        )
    except Exception:
        # Log the details server-side only; the client gets a fixed message so
        # SMTP/API errors (hosts, credentials, provider responses) never leak.
        logger.exception("Contact form email send failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message. Please try again or email us directly.",
        ) from None
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service is not configured. Please try again later or email us directly.",
        )
    return {"ok": True, "message": "Message sent successfully."}
