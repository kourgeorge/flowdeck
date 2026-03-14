"""
Shareable report links: one token format for any report run.

Token encodes only execution_id. Report type is derived from Execution.execution_type
when resolving; new report types require no token format change.
"""

import json
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Optional[Fernet]:
    """Return Fernet instance if SHARE_SECRET_KEY is set; otherwise None."""
    key = (os.environ.get("SHARE_SECRET_KEY") or "").strip()
    if not key:
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        return None


def encode_share_token(execution_id: int) -> Optional[str]:
    """Encode execution_id into an opaque token. Returns None if share is not configured."""
    fernet = _get_fernet()
    if not fernet:
        return None
    payload = json.dumps({"e": execution_id}).encode("utf-8")
    return fernet.encrypt(payload).decode("ascii")


def decode_share_token(token: str) -> Optional[int]:
    """Decode token to execution_id. Returns None if invalid or share not configured."""
    fernet = _get_fernet()
    if not fernet or not (token or "").strip():
        return None
    try:
        dec = fernet.decrypt(token.encode("ascii")).decode("utf-8")
        data = json.loads(dec)
        e = data.get("e")
        if not isinstance(e, int):
            return None
        return int(e)
    except (InvalidToken, ValueError, TypeError):
        return None


def get_share_url(execution_id: int) -> Optional[str]:
    """Return the full share URL for this report run, or None if share is not configured."""
    t = encode_share_token(execution_id)
    if not t:
        return None
    base = (os.environ.get("FRONTEND_URL") or "http://localhost:5173").rstrip("/")
    return f"{base}/r/{t}"
