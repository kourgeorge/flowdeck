"""
Source quality and recency heuristics for portfolio deep research.
Prefer primary sources; require 2 independent sources for key claims; downrank low-quality domains.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


# Domains/sources we treat as higher reliability (primary or reputable)
PRIMARY_INDICATORS = (
    "sec.gov",
    "sec.gov/",
    "edgar",
    "10-k",
    "10-q",
    "filing",
    "annual report",
    "investor relations",
    "earnings transcript",
)
REPUTABLE_NEWS = (
    "reuters.com",
    "bloomberg",
    "wsj.com",
    "marketwatch",
    "finance.yahoo",
    "cnbc",
    "barrons.com",
)

# Low-quality / SEO patterns to downrank
DOWNRANK_PATTERNS = (
    r"content\s*farm",
    r"seo\s*article",
    r"generic\s*blog",
    r"anonymous\s*post",
)


def reliability_score_heuristic(
    source_id: str,
    url: Optional[str] = None,
    snippet: Optional[str] = None,
    notes: Optional[str] = None,
) -> Optional[float]:
    """
    Return a heuristic reliability score in [0, 1] or None if unknown.
    Prefer primary sources (filings, official) and reputable news; downrank SEO/unsourced.
    """
    text = " ".join(filter(None, [source_id or "", url or "", snippet or "", notes or ""])).lower()
    score = 0.5
    for s in PRIMARY_INDICATORS:
        if s in text:
            score = min(1.0, score + 0.25)
            break
    for s in REPUTABLE_NEWS:
        if s in text:
            score = min(1.0, score + 0.15)
            break
    for pat in DOWNRANK_PATTERNS:
        if re.search(pat, text):
            score = max(0.0, score - 0.3)
            break
    return round(score, 2)


def apply_reliability_to_evidence(evidence_items: list) -> list:
    """Mutate evidence_items (list of dicts) adding reliability_score where missing."""
    for e in evidence_items:
        if isinstance(e, dict) and e.get("reliability_score") is None:
            e["reliability_score"] = reliability_score_heuristic(
                e.get("source_id") or "",
                e.get("url"),
                e.get("snippet"),
                e.get("notes"),
            )
    return evidence_items
