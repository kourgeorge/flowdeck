#!/usr/bin/env python3
"""Regenerate backend/services/email_logo_data_uri.txt from the repo logo.svg.
Run from repo root: python backend/scripts/refresh_email_logo_b64.py
The email renderer can fall back to runtime encoding, but this keeps the asset cached."""

import base64
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOGO_IN = REPO_ROOT / "logo.svg"
LOGO_OUT = REPO_ROOT / "backend" / "services" / "email_logo_data_uri.txt"

if not LOGO_IN.is_file():
    raise SystemExit(f"Logo not found: {LOGO_IN}")

data_uri = "data:image/svg+xml;base64," + base64.b64encode(LOGO_IN.read_bytes()).decode("ascii")
LOGO_OUT.write_text(data_uri)
print(f"Wrote {len(data_uri)} chars to {LOGO_OUT}")
