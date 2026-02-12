#!/usr/bin/env python3
"""Regenerate backend/services/email_logo_b64.txt from frontend/public/logo.png.
Run from repo root: python backend/scripts/refresh_email_logo_b64.py
No runtime encoding in email service: this file is committed and loaded as-is."""

import base64
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOGO_IN = REPO_ROOT / "frontend" / "public" / "logo.png"
LOGO_OUT = REPO_ROOT / "backend" / "services" / "email_logo_b64.txt"

if not LOGO_IN.is_file():
    raise SystemExit(f"Logo not found: {LOGO_IN}")

b64 = base64.b64encode(LOGO_IN.read_bytes()).decode("ascii")
LOGO_OUT.write_text(b64)
print(f"Wrote {len(b64)} chars to {LOGO_OUT}")
