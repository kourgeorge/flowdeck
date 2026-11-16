"""
Shared parser for the get_user_subscriptions tool output.

portfolio_health and portfolio_performance each used to carry their own
regex, and they drifted: health had no digits (so 0700.HK and 6758.T were
silently dropped) and neither allowed "=" (so futures like GC=F vanished).
Subscriptions only strip and uppercase the ticker (backend/routers/
subscriptions.py), so anything the analyses router accepts can be saved.
The character set here matches the analyses router's ticker pattern.
"""

from __future__ import annotations

import re

# Lines look like: - **AAPL** — subscribed ...
_TICKER_RE = re.compile(r"\*\*([A-Z0-9.^=\-]{1,32})\*\*")


def parse_subscribed_tickers(subs_text: str) -> list[str]:
    """Extract ticker symbols from get_user_subscriptions output, deduped in order."""
    return list(dict.fromkeys(_TICKER_RE.findall(subs_text)))
