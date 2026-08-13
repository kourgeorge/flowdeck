"""
Deterministic heading-anchor section extraction for SEC filings (no LLM, no network).

sec2md slices sections by PART/ITEM once its page splitter has worked. When the
splitter collapses a filing to a single page (TSM/ASML 20-F) or the filing has no
ITEM structure at all (40-F wrappers, whose substance lives in EX-* exhibits),
sec2md returns nothing and the caller is left with an 80K-char-truncated LLM pass.

This module anchors on the section *headings* instead, which survives both cases.
It is the single source of truth for SEC heading patterns: used by the backend
(`backend/services/edgar_service.py`) to fill sections sec2md could not, and by
the agent-side explorer (`sec_file_explorer.SECFilingExplorer.find_section`).

Why it beats a plain `re.search` first-match:
  * the heading must start its line (so prose cross-references and table cells are
    not mistaken for a section start),
  * table-of-contents / cross-reference-table lines are rejected (dot leaders,
    trailing page numbers, markdown table pipes),
  * every candidate is scored - a numbered ITEM heading outranks a bare keyword,
    and a heading followed by real prose outranks one followed by nothing.

Keys are the backend's section contract: risk_factors, management_mda, competition,
business_overview, legal_proceedings, market_risk_disclosures.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

SECTION_KEYS: Tuple[str, ...] = (
    "risk_factors",
    "management_mda",
    "competition",
    "business_overview",
    "legal_proceedings",
    "market_risk_disclosures",
)

# Heading specificity. A numbered ITEM heading is unambiguous; a bare keyword is a
# last resort (integrated foreign annual reports often have nothing better).
TIER_ITEM = 3
TIER_TITLE = 2
TIER_KEYWORD = 1

# A section must be followed by at least this much text to be believable; kills
# leftover table-of-contents entries whose "body" is the next TOC line.
MIN_BODY_CHARS = 80

DEFAULT_MAX_CHARS = 20_000

# Apostrophes as they appear in "Management's": straight, curly, modifier letter, and
# U+0092 - the Windows-1252 right single quote (byte 0x92) mis-decoded as latin-1, which
# survives into the markdown of pre-2018 filings (Enbridge's 40-F exhibits).
_APOS = r"['\u2018\u2019\u02bc\u0092]?"
# Separators between an item number and its title: "Item 5. ", "ITEM 5 - ", "Item 5: ".
_SEP = r"[\s.:\-\u2013\u2014]*"


@dataclass(frozen=True)
class Anchor:
    """One heading pattern for one section key."""

    key: str
    pattern: str
    tier: int
    # Forms this anchor is valid for; empty means every form. Item *numbers* differ
    # by form (a 10-K's Item 3 is Legal Proceedings, a 20-F's is Key Information),
    # so numbered anchors are gated.
    forms: Tuple[str, ...] = ()

    def applies_to(self, form: Optional[str]) -> bool:
        return not self.forms or form is None or form in self.forms


ANCHORS: Tuple[Anchor, ...] = (
    # --- risk factors -----------------------------------------------------
    Anchor("risk_factors", rf"Item{_SEP}1A{_SEP}Risk\s+Factors", TIER_ITEM, ("10-K", "10-Q")),
    Anchor("risk_factors", rf"Item{_SEP}3{_SEP}D{_SEP}Risk\s+Factors", TIER_ITEM, ("20-F",)),
    Anchor("risk_factors", rf"Item{_SEP}3{_SEP}Key\s+Information", TIER_ITEM, ("20-F",)),
    Anchor("risk_factors", r"D\.\s*Risk\s+Factors", TIER_TITLE),
    Anchor("risk_factors", r"Risk\s+Factors\s+and\s+Risk\s+Management", TIER_TITLE),
    Anchor("risk_factors", r"Risk\s+Factors", TIER_KEYWORD),
    # --- MD&A -------------------------------------------------------------
    Anchor(
        "management_mda",
        rf"Item{_SEP}7{_SEP}Management{_APOS}s\s+Discussion\s+and\s+Analysis",
        TIER_ITEM,
        ("10-K",),
    ),
    Anchor(
        "management_mda",
        rf"Item{_SEP}2{_SEP}Management{_APOS}s\s+Discussion\s+and\s+Analysis",
        TIER_ITEM,
        ("10-Q",),
    ),
    Anchor(
        "management_mda",
        rf"Item{_SEP}5{_SEP}Operating\s+and\s+Financial\s+Review",
        TIER_ITEM,
        ("20-F",),
    ),
    Anchor("management_mda", r"Operating\s+and\s+Financial\s+Review(?:\s+and\s+Prospects)?", TIER_TITLE),
    Anchor("management_mda", rf"Management{_APOS}s\s+Discussion\s+and\s+Analysis", TIER_TITLE),
    # Integrated (IFRS-style) annual reports filed as a 20-F carry no MD&A heading;
    # ASML's own Item cross-reference table points Item 5 at "Financial performance".
    Anchor("management_mda", r"Financial\s+[Pp]erformance(?:\s+KPIs)?", TIER_KEYWORD),
    # --- business ---------------------------------------------------------
    Anchor("business_overview", rf"Item{_SEP}1{_SEP}Business\b", TIER_ITEM, ("10-K",)),
    Anchor(
        "business_overview",
        # Form 20-F captions this "Information on the Company"; filers routinely
        # substitute their own name ("ITEM 4. INFORMATION ABOUT SAP").
        rf"Item{_SEP}4{_SEP}Information\s+(?:on|about)\b",
        TIER_ITEM,
        ("20-F",),
    ),
    Anchor("business_overview", r"B\.\s*Business\s+Overview", TIER_TITLE),
    Anchor("business_overview", r"Business\s+Overview", TIER_KEYWORD),
    # "General Description of the Business" is the Canadian AIF (NI 51-102) heading that
    # carries a 40-F filer's business section; the prefix has to be part of the anchor or
    # the match starts mid-line and is rejected as prose.
    Anchor("business_overview", r"(?:General\s+)?Description\s+of(?:\s+the)?\s+Business", TIER_KEYWORD),
    # Same integrated-report case: Item 4.B maps to "Our business" / "Our business model".
    Anchor("business_overview", r"Our\s+[Bb]usiness(?:\s+(?:strategy|model))?", TIER_KEYWORD),
    # --- competition (no ITEM of its own on any form) ----------------------
    Anchor(
        "competition",
        r"Competitive\s+(?:Landscape|Environment|Conditions|Strengths|Position)",
        TIER_TITLE,
    ),
    Anchor("competition", r"Competition\s+and\s+Markets", TIER_TITLE),
    Anchor("competition", r"Competition", TIER_KEYWORD),
    # --- legal proceedings -------------------------------------------------
    # The 20-F home is subsection 8.A.7, so the bare heading is more precise than
    # anchoring on "Item 8 Financial Information" (which is mostly statements).
    Anchor("legal_proceedings", rf"Item{_SEP}3{_SEP}Legal\s+Proceedings", TIER_ITEM, ("10-K",)),
    Anchor("legal_proceedings", rf"Item{_SEP}1{_SEP}Legal\s+Proceedings", TIER_ITEM, ("10-Q",)),
    Anchor("legal_proceedings", r"Legal\s+(?:and\s+Regulatory\s+)?Proceedings", TIER_TITLE),
    # --- market risk -------------------------------------------------------
    Anchor(
        "market_risk_disclosures",
        rf"Item{_SEP}7A{_SEP}Quantitative\s+and\s+Qualitative",
        TIER_ITEM,
        ("10-K",),
    ),
    Anchor(
        "market_risk_disclosures",
        rf"Item{_SEP}3{_SEP}Quantitative\s+and\s+Qualitative",
        TIER_ITEM,
        ("10-Q",),
    ),
    Anchor(
        "market_risk_disclosures",
        rf"Item{_SEP}11{_SEP}Quantitative\s+and\s+Qualitative",
        TIER_ITEM,
        ("20-F",),
    ),
    Anchor(
        "market_risk_disclosures",
        r"Quantitative\s+and\s+Qualitative\s+Disclosures?\s+About\s+Market\s+Risk",
        TIER_TITLE,
    ),
    Anchor("market_risk_disclosures", r"(?:Financial|Market)\s+Risk\s+Management", TIER_TITLE),
    # Filers without an Item 7A/11 (40-F exhibits, integrated reports) title the same
    # content plainly. Safe as a keyword because it must now end its line.
    Anchor("market_risk_disclosures", r"Market\s+Risk", TIER_KEYWORD),
)

# Any ITEM/PART heading ends the preceding section, even one we have no anchor for.
_GENERIC_BOUNDARY = r"(?:Item\s+\d{1,2}[A-Z]?|PART\s+[IVX]{1,4})\b"

# Only whitespace and markdown decoration may precede a heading on its line. Filers
# nest emphasis, so allow a run of markers (Enbridge's exhibits use "****RISK FACTORS****").
_LINE_LEAD = re.compile(r"[ \t>]{0,8}(?:#{1,6}[ \t]*)?[*_]{0,6}[ \t]*")
# A bare-keyword heading must also *end* its line (modulo markdown decoration and
# punctuation). Filers bold mid-sentence fragments - ASML's "**our business - and
# takes into consideration**" would otherwise anchor business_overview to prose.
# ITEM and TITLE anchors stay permissive: their headings legitimately continue
# ("Item 1. Business", "Management's Discussion and Analysis of Financial Condition").
_LINE_TAIL = re.compile(r"[\s*_#:.\-\u2013\u2014]*")

# Filings converted from print layouts hard-wrap prose, so a sentence's continuation
# starts its own line ("competitive position and long-term / shareholder value creation").
# Real headings are capitalized; a lowercase first letter means we are mid-sentence.
_LOWERCASE_START = re.compile(r"[a-z]")

_DOT_LEADERS = re.compile(r"\.{3,}")
_TRAILING_PAGE = re.compile(r"[\s.]\d{1,4}[\s*_]*$")
_MD_HEADING = re.compile(r"^[ \t]*(?:#{1,6}\s|\*\*|__)")

# form -> (mega regex, group index -> Anchor or None for the generic boundary)
_COMPILED: Dict[str, Tuple[re.Pattern, Tuple[Optional[Anchor], ...]]] = {}


@dataclass
class SectionHit:
    """One extracted section."""

    key: str
    text: str
    start: int
    end: int
    matched_heading: str
    score: int
    truncated: bool


def _compiled(form: Optional[str]) -> Tuple[re.Pattern, Tuple[Optional[Anchor], ...]]:
    """
    Build (and cache) one alternation regex covering every active anchor plus the
    generic ITEM/PART boundary, so a whole filing is scanned in a single pass.

    Anchor patterns must contain no capturing groups other than their own outer
    one, so `match.lastindex` identifies which alternative fired.
    """
    cache_key = form or ""
    hit = _COMPILED.get(cache_key)
    if hit is not None:
        return hit
    active = [a for a in ANCHORS if a.applies_to(form)]
    parts = [f"({a.pattern})" for a in active] + [f"({_GENERIC_BOUNDARY})"]
    regex = re.compile("|".join(parts), re.IGNORECASE)
    if regex.groups != len(parts):
        raise ValueError("anchor patterns must use non-capturing groups (?:...) only")
    meta: Tuple[Optional[Anchor], ...] = tuple(active) + (None,)
    _COMPILED[cache_key] = (regex, meta)
    return regex, meta


def _looks_like_toc(line: str) -> bool:
    """Table-of-contents or cross-reference-table row, not a section start."""
    return bool(
        "|" in line
        or _DOT_LEADERS.search(line)
        or _TRAILING_PAGE.search(line)
    )


def _scan(text: str, form: Optional[str]):
    """
    Single pass over the text. Returns (candidates_by_key, boundaries_by_tier).

    A hit only counts if the heading starts its line and the line is not TOC-like.

    Boundaries are bucketed by specificity so a section is only ended by a heading
    at least as specific as its own: "Item 1. Business" runs to the next ITEM, not
    to the "Competition" subheading nested inside it (which is extracted separately).
    """
    regex, meta = _compiled(form)
    candidates: Dict[str, List[Tuple[Anchor, int, int, str]]] = {}
    bounds: List[Tuple[int, int]] = []

    for m in regex.finditer(text):
        idx = m.lastindex
        if idx is None:
            continue
        anchor = meta[idx - 1]
        line_start = text.rfind("\n", 0, m.start()) + 1
        if not _LINE_LEAD.fullmatch(text[line_start : m.start()]):
            continue  # inline prose or a table cell, not a heading
        if _LOWERCASE_START.match(text, m.start()):
            continue  # a hard-wrapped sentence continuation
        line_end = text.find("\n", m.end())
        if line_end == -1:
            line_end = len(text)
        line = text[line_start:line_end]
        if _looks_like_toc(line):
            continue
        if (
            anchor is not None
            and anchor.tier == TIER_KEYWORD
            and not _LINE_TAIL.fullmatch(text[m.end() : line_end])
        ):
            continue
        # A bare ITEM/PART heading we have no anchor for still ends a section.
        bounds.append((line_start, TIER_ITEM if anchor is None else anchor.tier))
        if anchor is not None:
            candidates.setdefault(anchor.key, []).append(
                (anchor, line_start, m.end(), line.strip())
            )

    boundaries = {
        tier: sorted({o for o, t in bounds if t >= tier})
        for tier in (TIER_KEYWORD, TIER_TITLE, TIER_ITEM)
    }
    return candidates, boundaries


def _score(anchor: Anchor, line: str, body_len: int) -> int:
    score = anchor.tier * 100
    if _MD_HEADING.match(line):
        score += 30
    # Longer bodies win within a tier: a real section beats a stray heading.
    score += min(body_len, 20_000) // 1_000
    return score


def extract_section(
    text: str,
    key: str,
    form: Optional[str] = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> Optional[SectionHit]:
    """Extract one section by canonical key, or None if no credible heading exists."""
    if not text or key not in SECTION_KEYS:
        return None
    candidates, boundaries = _scan(text, form)
    return _best(text, candidates.get(key, []), boundaries, key, max_chars)


def extract_all_sections(
    text: str,
    form: Optional[str] = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> Dict[str, str]:
    """
    Extract every section in one pass. Keys with no credible heading map to "".
    An all-empty result means the caller should fall back to LLM extraction.
    """
    out: Dict[str, str] = {k: "" for k in SECTION_KEYS}
    if not text:
        return out
    candidates, boundaries = _scan(text, form)
    for key in SECTION_KEYS:
        hit = _best(text, candidates.get(key, []), boundaries, key, max_chars)
        if hit is not None:
            out[key] = hit.text
    return out


def _best(
    text: str,
    hits: List[Tuple[Anchor, int, int, str]],
    boundaries: Dict[int, List[int]],
    key: str,
    max_chars: int,
) -> Optional[SectionHit]:
    best: Optional[SectionHit] = None
    for anchor, start, match_end, line in hits:
        # The section runs to the next heading at least as specific as this one.
        # Boundaries are line starts, so searching past the heading's own match
        # end is enough to skip the heading itself.
        offsets = boundaries[anchor.tier]
        pos = bisect_right(offsets, match_end)
        end = offsets[pos] if pos < len(offsets) else len(text)
        body_len = end - start
        if body_len < MIN_BODY_CHARS:
            continue
        score = _score(anchor, line, body_len)
        truncated = body_len > max_chars
        if best is not None and (score, body_len) <= (best.score, best.end - best.start):
            continue
        best = SectionHit(
            key=key,
            text=text[start : min(end, start + max_chars)].strip(),
            start=start,
            end=end,
            matched_heading=line,
            score=score,
            truncated=truncated,
        )
    return best
