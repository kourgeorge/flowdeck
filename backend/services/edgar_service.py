"""
SEC EDGAR service: resolve ticker to CIK, list filings, build SEC document links.

Covers domestic forms (10-K, 10-Q) and foreign private issuer forms (20-F, 6-K, 40-F).

Uses official SEC APIs. No authentication required; User-Agent must identify the application.
Rate limit: 10 requests per second (SEC policy). We cache ticker->CIK and submissions.

Extended to fetch filing document HTML, convert to text, and use an LLM to extract
structured sections (Risk Factors, MD&A, Competition) for the SEC analyst.
"""

import html as html_lib
import logging
import os
import re
import time
import warnings
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from ai_engine.tradingagents.agents.utils.sec_section_anchors import extract_all_sections

# SEC iXBRL documents are XML-ish; parsing them with an HTML parser (here and
# inside sec2md's lxml path) raises a cosmetic XMLParsedAsHTMLWarning per the
# bs4 docs. Silence it - the extracted text is unaffected.
try:
    from bs4 import XMLParsedAsHTMLWarning

    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except Exception:  # pragma: no cover - older bs4 without this warning class
    pass

logger = logging.getLogger(__name__)

# sec2md: deterministic SEC filing -> markdown + PART/ITEM section extraction.
# Guarded so the service still imports (and falls back to LLM extraction) if absent.
try:
    import sec2md

    _SEC2MD_AVAILABLE = True
except Exception as _sec2md_err:  # pragma: no cover - import environment issue
    sec2md = None  # type: ignore[assignment]
    _SEC2MD_AVAILABLE = False
    logging.getLogger(__name__).warning(
        "sec2md unavailable (%s); EDGAR extraction will use LLM fallback only", _sec2md_err
    )

# Section keys returned to callers (the output contract - do not change).
# `competition` has no own ITEM (it is a subsection of Business/Item 1) and is
# folded into business_overview on the sec2md path; the LLM fallback still fills it.
SECTION_KEYS = (
    "risk_factors",
    "management_mda",
    "competition",
    "business_overview",
    "legal_proceedings",
    "market_risk_disclosures",
)

SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"
# SGML header listing every document in a submission with its exhibit TYPE.
# Small (~5KB) and more stable to parse than the -index.html document table.
SEC_INDEX_HEADERS_URL = SEC_ARCHIVES_BASE + "/{cik}/{acc_nodash}/{accession}-index-headers.html"

# SEC requires a descriptive User-Agent (see https://www.sec.gov/os/webmaster-faq)
USER_AGENT = "Flowdeck (contact@flowdeck.app)"

# Cache TTL in seconds (24h)
TICKER_CACHE_TTL = 24 * 60 * 60

# Allowed form types for filings list.
# Domestic issuers file 10-K/10-Q; foreign private issuers file 20-F (annual,
# item-structured like a 10-K), 6-K (interim, free-form) and - for Canadian MJDS
# filers - 40-F (annual, a wrapper around the Canadian AIF/MD&A).
DOMESTIC_FORMS = {"10-K", "10-Q"}
FOREIGN_FORMS = {"20-F", "6-K", "40-F"}
FILING_FORMS = DOMESTIC_FORMS | FOREIGN_FORMS

# 6-K is filed constantly (monthly revenue, board changes, press releases) - some
# issuers have 700+ in the recent window - so cap it to keep the list usable.
# Annual/quarterly forms are naturally bounded and stay uncapped.
FORM_LIST_CAPS = {"6-K": 20}

# 6-K and 40-F carry their substance in EX-* attachments; the primary document is
# often just a cover page (e.g. SAP 6-K: 3.5K chars, Enbridge 40-F: 8.8K chars).
EXHIBIT_FORMS = {"6-K", "40-F"}
# Certifications, auditor consents and XBRL carry no narrative - skip them.
EXHIBIT_TYPE_SKIP_PREFIXES = ("EX-23", "EX-24", "EX-31", "EX-32", "EX-101", "EX-104")
MAX_EXHIBIT_DOCS = 4
# Some filers number their certifications ahead of the narrative (Enbridge's AIF and
# MD&A are EX-99.5/99.6, behind four EX-99.x certifications), so scan deeper than we
# keep and gate on document size: narrative exhibits run 100KB-17MB of HTML, while
# certifications, consents and cover letters top out around 20KB.
MAX_EXHIBIT_URLS = 12
MIN_EXHIBIT_HTML_CHARS = 40_000

# Limits for document text and extraction (chars)
MAX_DOCUMENT_TEXT_CHARS = 100_000
MAX_TEXT_FOR_EXTRACTION_CHARS = 80_000
MAX_SECTION_CHARS = 12_000

# Cache TTL for extracted sections (24h)
EXTRACTION_CACHE_TTL = 24 * 60 * 60


class ExtractedSECSections(BaseModel):
    """Structured extraction from a SEC filing (LLM output). Item numbers differ by form."""

    risk_factors: str = Field(
        default="",
        description="Risk Factors: Item 1A (10-K), Part II Item 1A (10-Q), Item 3.D (20-F). Use empty string if not found.",
    )
    management_discussion_and_analysis: str = Field(
        default="",
        description="MD&A: Item 7 (10-K), Part I Item 2 (10-Q), Item 5 Operating and Financial Review and Prospects (20-F). Use empty string if not found.",
    )
    competition: str = Field(
        default="",
        description="Competition subsection from the business description (Item 1 in a 10-K, Item 4.B in a 20-F). Use empty string if not found.",
    )
    business_overview: str = Field(
        default="",
        description="Brief business overview (products, segments): Item 1 (10-K), Item 4 Information on the Company (20-F). Use empty string if not found.",
    )
    legal_proceedings: str = Field(
        default="",
        description="Legal Proceedings: Item 3 (10-K), Item 8.A.7 (20-F). Use empty string if not found.",
    )
    market_risk_disclosures: str = Field(
        default="",
        description="Quantitative and Qualitative Disclosures About Market Risk: Item 7A (10-K), Item 11 (20-F). Use empty string if not found.",
    )


# Per-form section guides for the LLM extraction fallback. Item numbering differs
# by form, so telling the model to look for "Item 1A" in a 20-F would misfire.
_SECTION_GUIDE_10K_10Q = """1. risk_factors: Item 1A Risk Factors (10-K) or Part II Item 1A (10-Q).
2. management_discussion_and_analysis: Item 7 Management's Discussion and Analysis (10-K) or Part I Item 2 MD&A (10-Q).
3. competition: The Competition (or competitive environment) subsection from Item 1 Business.
4. business_overview: Brief overview of Item 1 Business (products, segments, strategy) - optional.
5. legal_proceedings: Item 3 Legal Proceedings - optional.
6. market_risk_disclosures: Item 7A Quantitative and Qualitative Disclosures About Market Risk - optional."""

_SECTION_GUIDE_20F = """1. risk_factors: Item 3.D Risk Factors (inside Item 3 Key Information).
2. management_discussion_and_analysis: Item 5 Operating and Financial Review and Prospects.
3. competition: The Competition subsection of Item 4.B Business Overview.
4. business_overview: Brief overview of Item 4 Information on the Company (products, segments, strategy) - optional.
5. legal_proceedings: Item 8.A.7 Legal Proceedings (inside Item 8 Financial Information) - optional.
6. market_risk_disclosures: Item 11 Quantitative and Qualitative Disclosures About Market Risk - optional.

Note: some foreign issuers file an integrated annual report with a Form 20-F
cross-reference table instead of ITEM-headed sections. In that case locate the
equivalent narrative headings (e.g. "Risk factors and risk management",
"Operating and financial review") rather than the item numbers."""

_SECTION_GUIDE_6K_40F = """This form has no fixed ITEM structure. Extract whatever the attached
report/exhibits disclose, mapping to the closest field and leaving the rest empty:
1. risk_factors: any risk, uncertainty or forward-looking caution disclosures.
2. management_discussion_and_analysis: operating and financial review, results commentary, outlook/guidance.
3. competition: any discussion of competitors or competitive position.
4. business_overview: description of the business, products or segments.
5. legal_proceedings: litigation, regulatory or contingency disclosures.
6. market_risk_disclosures: FX, interest rate, commodity or other market risk disclosures."""

_SECTION_GUIDE = {
    "10-K": _SECTION_GUIDE_10K_10Q,
    "10-Q": _SECTION_GUIDE_10K_10Q,
    "20-F": _SECTION_GUIDE_20F,
    "6-K": _SECTION_GUIDE_6K_40F,
    "40-F": _SECTION_GUIDE_6K_40F,
}


def _truncate(s: str, max_len: int) -> str:
    if not s or len(s) <= max_len:
        return s or ""
    return s[: max_len - 3].rstrip() + "..."


def _strip_xbrl_markup(text: str) -> str:
    """Remove XBRL/XML namespaced tags (e.g. <xbrli:context>, <ix:nonNumeric>) so narrative text is readable. Leaves HTML like <p>, <div>."""
    if not text:
        return ""
    # Remove tags whose name contains a colon (XML namespaces: xbrli:, ix:, us-gaap:, dei:, etc.)
    text = re.sub(r"<[^>]*:[^>]*>", "", text)
    # Collapse repeated whitespace and blank lines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _skip_to_narrative(text: str) -> str:
    """Skip SEC header and XBRL hidden block; start at the form title (e.g. UNITED STATES / FORM 10-K) so LLM sees narrative first."""
    if not text:
        return text
    markers = (
        "UNITED STATES\nSECURITIES AND EXCHANGE COMMISSION",
        "SECURITIES AND EXCHANGE COMMISSION\nWashington",
        "FORM 10-K",
        "FORM 20-F",
        "FORM 40-F",
        "FORM 6-K",
        "ANNUAL REPORT PURSUANT TO SECTION 13",
        "REPORT OF FOREIGN PRIVATE ISSUER",
    )
    for marker in markers:
        idx = text.find(marker)
        if idx != -1:
            return text[idx:]
    return text


class EdgarService:
    def __init__(self) -> None:
        self._ticker_map: Optional[Dict[str, Any]] = None
        self._ticker_map_at: float = 0
        self._last_request_at: float = 0
        self._min_interval = 0.12  # ~8 req/s to stay under 10
        # Extraction cache: (ticker, form, accession) -> (timestamp, sections_dict)
        self._extraction_cache: Dict[Tuple[str, str, str], Tuple[float, Dict[str, Any]]] = {}
        self._extraction_llm = None

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_at = time.monotonic()

    def _get_headers(self) -> Dict[str, str]:
        return {"User-Agent": USER_AGENT, "Accept": "application/json"}

    def _get_headers_html(self) -> Dict[str, str]:
        return {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}

    def _fetch_raw_html(self, url: str) -> str:
        """Fetch raw filing HTML at URL (throttled, SEC User-Agent). Empty string on failure."""
        if not url:
            return ""
        self._throttle()
        try:
            r = requests.get(url, headers=self._get_headers_html(), timeout=30)
            r.raise_for_status()
            return r.text
        except Exception as e:
            logger.warning("Failed to fetch SEC document %s: %s", url[:80], e)
            return ""

    @staticmethod
    def _html_to_text(raw: str, truncate: bool = True) -> str:
        """Strip XBRL markup, flatten HTML to text with BeautifulSoup, skip to narrative, optionally truncate."""
        if not raw:
            return ""
        raw = _strip_xbrl_markup(raw)
        soup = BeautifulSoup(raw, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        text = _skip_to_narrative(text)
        if truncate:
            return _truncate(text, MAX_DOCUMENT_TEXT_CHARS)
        return text  # Full text for exploration

    def _fetch_document_text(self, url: str, truncate: bool = True) -> str:
        """Fetch document at URL and convert to cleaned narrative text. Empty string on failure."""
        return self._html_to_text(self._fetch_raw_html(url), truncate=truncate)

    def _fetch_exhibit_urls(self, cik: str, accession: str) -> List[str]:
        """
        Resolve narrative EX-* exhibit document URLs for a submission.

        6-K and 40-F keep their substance in attachments, so the primary document
        alone is often an empty cover page. The submission's -index-headers.html
        lists every document with its exhibit TYPE (HTML-escaped SGML), which is
        the only place that mapping is exposed: index.json's `type` field holds an
        icon name, and exhibit filenames are not predictable (TSM uses
        `a2q26e_withguidancexfinal.htm` for EX-99.1, Royal Bank uses EX-1..EX-5).

        Returns document URLs in submission order, capped at MAX_EXHIBIT_URLS. The
        caller keeps only the substantial ones, so this cap is a scan budget rather
        than the number of documents fetched into the extraction text.
        """
        if not cik or not accession:
            return []
        acc_nodash = accession.replace("-", "")
        cik_int = str(int(cik))
        index_url = SEC_INDEX_HEADERS_URL.format(
            cik=cik_int, acc_nodash=acc_nodash, accession=accession
        )
        raw = self._fetch_raw_html(index_url)
        if not raw:
            return []
        # The SGML is HTML-escaped inside the page (&lt;TYPE&gt;EX-99.1).
        sgml = html_lib.unescape(raw)
        urls: List[str] = []
        for match in re.finditer(
            r"<TYPE>([^\s<]+)\s*<SEQUENCE>\s*\d+\s*<FILENAME>([^\s<]+)", sgml, re.IGNORECASE
        ):
            ex_type = match.group(1).strip().upper()
            filename = match.group(2).strip()
            if not ex_type.startswith("EX-"):
                continue
            if ex_type.startswith(EXHIBIT_TYPE_SKIP_PREFIXES):
                continue
            if not filename.lower().endswith((".htm", ".html")):
                continue
            urls.append(f"{SEC_ARCHIVES_BASE}/{cik_int}/{acc_nodash}/{filename}")
            if len(urls) >= MAX_EXHIBIT_URLS:
                break
        return urls

    def _html_to_markdown(self, raw_html: str, truncate: bool = False) -> str:
        """Convert filing HTML to markdown via sec2md (tables preserved); fall back to flattened text."""
        if not raw_html:
            return ""
        if _SEC2MD_AVAILABLE and sec2md is not None:
            try:
                pages: Any = sec2md.convert_to_markdown(raw_html, return_pages=True)
                text = "\n\n".join(p.content for p in pages) if pages else ""
                if text:
                    return text
            except Exception as e:
                logger.warning("sec2md markdown conversion failed: %s", e)
        return self._html_to_text(raw_html, truncate=truncate)

    def _fetch_filing_documents(
        self, cik: str, form_type: str, accession: str, primary_url: str
    ) -> List[str]:
        """
        Fetch the raw HTML of every document carrying a filing's narrative content.

        The primary document comes first. For EXHIBIT_FORMS (6-K, 40-F) the EX-*
        attachments are appended, since the primary document is frequently just a
        cover page. Exhibits below MIN_EXHIBIT_HTML_CHARS are skipped and the scan
        continues, so leading certifications do not consume the document budget.
        """
        htmls: List[str] = []
        primary = self._fetch_raw_html(primary_url)
        if primary:
            htmls.append(primary)
        if form_type in EXHIBIT_FORMS:
            kept = 0
            for exhibit_url in self._fetch_exhibit_urls(cik, accession):
                exhibit = self._fetch_raw_html(exhibit_url)
                if not exhibit or len(exhibit) < MIN_EXHIBIT_HTML_CHARS:
                    continue
                htmls.append(exhibit)
                kept += 1
                if kept >= MAX_EXHIBIT_DOCS:
                    break
        return htmls

    def _extract_sections_sec2md(self, raw_html: str, form_type: str) -> Optional[Dict[str, Any]]:
        """
        Deterministic ITEM-based section extraction via sec2md (no LLM).

        Reuses HTML we already fetched (convert_to_markdown, not parse_filing, so our
        throttle/User-Agent apply). Returns a sections dict, or None to signal the
        caller should fall back to LLM extraction (sec2md unavailable, parse error,
        or no items detected - e.g. older/non-standard filers).
        """
        if not _SEC2MD_AVAILABLE or sec2md is None or not raw_html:
            return None
        if form_type == "10-K":
            item_map = {
                "risk_factors": sec2md.Item10K.RISK_FACTORS,            # 1A
                "management_mda": sec2md.Item10K.MD_AND_A,              # 7
                "business_overview": sec2md.Item10K.BUSINESS,           # 1 (incl. competition subsection)
                "legal_proceedings": sec2md.Item10K.LEGAL_PROCEEDINGS,  # 3
                "market_risk_disclosures": sec2md.Item10K.MARKET_RISK,  # 7A
            }
        elif form_type == "10-Q":
            item_map = {
                "risk_factors": sec2md.Item10Q.RISK_FACTORS_P2,             # 1A.P2
                "management_mda": sec2md.Item10Q.MD_AND_A_P1,               # 2.P1
                "legal_proceedings": sec2md.Item10Q.LEGAL_PROCEEDINGS_P2,   # 1.P2
                "market_risk_disclosures": sec2md.Item10Q.MARKET_RISK_P1,   # 3.P1
            }
        elif form_type == "20-F":
            # sec2md knows the 20-F PART/ITEM structure but ships no Item20F enum,
            # so address items by string. 20-F items are coarser than a 10-K's:
            # Risk Factors are subsection 3.D inside Item 3 Key Information, and
            # Competition is 4.B inside Item 4, so those sections carry extra text.
            item_map = {
                "risk_factors": "ITEM 3",              # Key Information (incl. 3.D Risk Factors)
                "management_mda": "ITEM 5",            # Operating and Financial Review and Prospects
                "business_overview": "ITEM 4",         # Information on the Company (incl. 4.B competition)
                "legal_proceedings": "ITEM 8",         # Financial Information (8.A.7 Legal Proceedings)
                "market_risk_disclosures": "ITEM 11",  # Quantitative and Qualitative Market Risk
            }
        else:
            # 6-K is free-form and 40-F is a wrapper around Canadian AIF/MD&A
            # exhibits - neither has an ITEM structure to slice. Use the LLM path.
            return None
        try:
            # return_pages=True yields List[Page]; annotate Any to bypass the
            # str-overload the type checker infers from the literal kwarg.
            pages: Any = sec2md.convert_to_markdown(raw_html, return_pages=True)
            sections = sec2md.extract_sections(pages, filing_type=form_type)
        except Exception as e:
            logger.warning("sec2md extraction failed: %s", e)
            return None

        out: Dict[str, Any] = {k: "" for k in SECTION_KEYS}
        found = False
        for key, item in item_map.items():
            try:
                sec = sec2md.get_section(sections, item, filing_type=form_type)
            except Exception:
                sec = None
            if sec:
                out[key] = _truncate(sec.markdown(), MAX_SECTION_CHARS)
                found = True
        return out if found else None

    def _extract_sections_anchors(self, text: str, form_type: str) -> Optional[Dict[str, Any]]:
        """
        Deterministic heading-anchor extraction (no LLM) for what sec2md cannot slice:
        20-Fs whose pages its splitter collapses into one (TSM, ASML) and the 6-K/40-F
        exhibit narrative, which has no ITEM structure at all.

        Runs on the markdown of every document in the filing, so exhibit text is
        covered. Returns None when no section was found, so the caller can fall back.
        """
        if not text:
            return None
        try:
            found = extract_all_sections(text, form=form_type, max_chars=MAX_SECTION_CHARS)
        except Exception as e:
            logger.warning("anchor extraction failed: %s", e)
            return None
        return found if any(found.values()) else None

    def _get_extraction_llm(self):
        """Lazy-init LLM for section extraction using centralized llm_provider."""
        if self._extraction_llm is not None:
            return self._extraction_llm
        
        # Import here to avoid circular dependencies
        import sys
        from pathlib import Path
        
        # Add ai_engine to path if not already there
        ai_engine_path = str(Path(__file__).parent.parent.parent / "ai_engine")
        if ai_engine_path not in sys.path:
            sys.path.insert(0, ai_engine_path)
        
        from ai_engine.llm_provider import get_config_from_env, get_llm
        
        # Use centralized LLM provider (supports LiteLLM, Azure, OpenAI, etc.)
        config = get_config_from_env()
        self._extraction_llm = get_llm("quick", config)
        return self._extraction_llm

    def _extract_sections(self, full_text: str, form_type: str = "10-K") -> Dict[str, Any]:
        """Run LLM to extract structured sections from filing text. Returns dict for one filing."""
        text = _truncate(full_text, MAX_TEXT_FOR_EXTRACTION_CHARS)
        if not text:
            return {
                "risk_factors": "",
                "management_mda": "",
                "competition": "",
                "business_overview": "",
                "legal_proceedings": "",
                "market_risk_disclosures": "",
            }
        prompt = f"""Below is the text of a SEC {form_type} filing. Extract the following sections and return them.
Use empty string for any section you cannot find.

{_SECTION_GUIDE.get(form_type, _SECTION_GUIDE["10-K"])}

Keep each section concise but complete; you may truncate very long sections to the first ~12,000 characters.

Filing text:
"""
        try:
            llm = self._get_extraction_llm()
            chain = llm.with_structured_output(ExtractedSECSections)
            result = chain.invoke(prompt + text)
            return {
                "risk_factors": _truncate(result.risk_factors or "", MAX_SECTION_CHARS),
                "management_mda": _truncate(result.management_discussion_and_analysis or "", MAX_SECTION_CHARS),
                "competition": _truncate(result.competition or "", MAX_SECTION_CHARS),
                "business_overview": _truncate(result.business_overview or "", MAX_SECTION_CHARS),
                "legal_proceedings": _truncate(result.legal_proceedings or "", MAX_SECTION_CHARS),
                "market_risk_disclosures": _truncate(result.market_risk_disclosures or "", MAX_SECTION_CHARS),
            }
        except Exception as e:
            logger.warning("LLM extraction failed: %s", e)
            return {
                "risk_factors": "",
                "management_mda": "",
                "competition": "",
                "business_overview": "",
                "legal_proceedings": "",
                "market_risk_disclosures": "",
            }

    def _fetch_ticker_map(self) -> Dict[str, Any]:
        if self._ticker_map is not None and (time.monotonic() - self._ticker_map_at) < TICKER_CACHE_TTL:
            return self._ticker_map
        self._throttle()
        try:
            r = requests.get(SEC_COMPANY_TICKERS_URL, headers=self._get_headers(), timeout=15)
            r.raise_for_status()
            data = r.json()
            # SEC returns {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "..."}, "1": {...}, ...}
            self._ticker_map = data
            self._ticker_map_at = time.monotonic()
            return self._ticker_map
        except Exception as e:
            logger.warning("Failed to fetch SEC company tickers: %s", e)
            if self._ticker_map is not None:
                return self._ticker_map
            raise

    def ticker_to_cik(self, ticker: str) -> Optional[str]:
        """Resolve ticker to 10-digit zero-padded CIK. Returns None if not found."""
        ticker_upper = ticker.upper().strip()
        try:
            data = self._fetch_ticker_map()
        except Exception:
            return None
        for _key, entry in data.items():
            if isinstance(entry, dict) and entry.get("ticker") == ticker_upper:
                cik = entry.get("cik_str")
                if cik is not None:
                    return str(cik).zfill(10)
        return None

    def get_filings(self, ticker: str) -> Dict[str, Any]:
        """
        Get recent filings for the ticker: 10-K/10-Q for domestic issuers and
        20-F/6-K/40-F for foreign private issuers. High-volume forms are capped
        per FORM_LIST_CAPS.

        Returns:
            {
                "cik": str,
                "company_name": str | None,
                "filings": [{"form", "filing_date", "accession_number", "url", "description"}],
                "error": str | None  # set on partial failure (e.g. ticker not in EDGAR)
            }
        """
        ticker_upper = ticker.upper().strip()
        result: Dict[str, Any] = {
            "cik": "",
            "company_name": None,
            "filings": [],
            "error": None,
        }
        cik = self.ticker_to_cik(ticker_upper)
        if not cik:
            result["error"] = "Ticker not found in SEC EDGAR"
            return result
        result["cik"] = cik
        self._throttle()
        try:
            url = SEC_SUBMISSIONS_URL.format(cik=cik)
            r = requests.get(url, headers=self._get_headers(), timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("Failed to fetch SEC submissions for %s: %s", ticker_upper, e)
            result["error"] = "Could not load SEC filings"
            return result
        name = data.get("name")
        if name:
            result["company_name"] = name
        recent = data.get("filings", {}).get("recent")
        if not recent or not isinstance(recent, dict):
            return result
        forms = recent.get("form") or []
        filing_dates = recent.get("filingDate") or []
        accession_numbers = recent.get("accessionNumber") or []
        primary_docs = recent.get("primaryDocument") or []
        n = min(
            len(forms),
            len(filing_dates),
            len(accession_numbers),
            len(primary_docs),
        )
        # Build list of (form, date, accession, primary_doc), then filter and dedupe by accession.
        # SEC returns `recent` newest-first, so per-form counting keeps the newest N.
        seen: set = set()
        per_form_count: Dict[str, int] = {}
        for i in range(n):
            form = (forms[i] or "").strip()
            if form not in FILING_FORMS:
                continue
            cap = FORM_LIST_CAPS.get(form)
            if cap is not None and per_form_count.get(form, 0) >= cap:
                continue
            acc = (accession_numbers[i] or "").strip()
            if not acc or acc in seen:
                continue
            seen.add(acc)
            per_form_count[form] = per_form_count.get(form, 0) + 1
            filing_date = (filing_dates[i] or "").strip()
            primary_doc = (primary_docs[i] or "").strip()
            # Direct link to primary document: Archives/edgar/data/{cik}/{accession_no_dashes}/{primaryDoc}
            acc_no_dashes = acc.replace("-", "")
            cik_int = str(int(cik))  # no leading zeros in path
            doc_url = f"{SEC_ARCHIVES_BASE}/{cik_int}/{acc_no_dashes}/{primary_doc}" if primary_doc else ""
            description = f"{form} filed {filing_date}"
            result["filings"].append({
                "form": form,
                "filing_date": filing_date,
                "accession_number": acc,
                "url": doc_url,
                "description": description,
            })
        # Sort by filing_date descending (most recent first)
        result["filings"].sort(key=lambda x: x["filing_date"], reverse=True)
        return result

    def get_filing_content(
        self,
        ticker: str,
        form: Optional[str] = None,
        limit: int = 1,
        raw: bool = False,
        accession: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get filing content - either extracted sections (via LLM) or raw text (for exploration).

        For the exhibit-borne foreign forms (6-K, 40-F) the primary document is
        usually a cover page, so its narrative EX-* attachments are fetched and
        appended to the returned text before extraction.

        Args:
            ticker: Stock ticker
            form: Optional form filter - '10-K', '10-Q', '20-F', '6-K' or '40-F'
            limit: Number of filings to return
            raw: If True, return raw text without LLM extraction (for agent exploration).
                 If False, return LLM-extracted sections (current behavior, default).
            accession: Optional accession number to select one specific filing. When
                 provided, only that filing is returned (form/limit are ignored).

        Returns:
            {
                "filings": [
                    {
                        "form": str,
                        "filing_date": str,
                        "accession_number": str,
                        "sections": {...}  # if raw=False (LLM extracted)
                        "text": str,       # if raw=True (full text)
                        "char_count": int  # if raw=True
                    }
                ],
                "error": str | None
            }
        """
        out: Dict[str, Any] = {"filings": [], "error": None}
        ticker_upper = ticker.upper().strip()
        filings_result = self.get_filings(ticker_upper)
        if filings_result.get("error"):
            out["error"] = filings_result["error"]
            return out
        filings_list = filings_result.get("filings") or []
        if accession:
            filings_list = [f for f in filings_list if f.get("accession_number") == accession]
        else:
            if form:
                filings_list = [f for f in filings_list if f.get("form") == form]
            filings_list = filings_list[:limit]
        now = time.monotonic()
        
        cik = filings_result.get("cik") or ""

        for f in filings_list:
            acc = f.get("accession_number") or ""
            form_type = f.get("form") or ""
            url = f.get("url") or ""

            if raw:
                # RAW MODE: Return full text without LLM extraction (for agent exploration).
                # Prefer sec2md clean markdown (tables preserved); fall back to stripped text.
                logger.info(f"Fetching raw text for {ticker_upper} {form_type} (exploration mode)")
                htmls = self._fetch_filing_documents(cik, form_type, acc, url)
                if not htmls:
                    continue
                parts = [self._html_to_markdown(h) for h in htmls]
                text = "\n\n".join(p for p in parts if p)
                if not text:
                    continue

                out["filings"].append({
                    "form": form_type,
                    "filing_date": f.get("filing_date", ""),
                    "accession_number": acc,
                    "text": text,
                    "char_count": len(text),
                })
            else:
                # EXTRACTION MODE: sec2md deterministic extraction, LLM fallback.
                key = (ticker_upper, form_type, acc)

                # Check cache
                if key in self._extraction_cache:
                    ts, sections = self._extraction_cache[key]
                    if now - ts < EXTRACTION_CACHE_TTL:
                        out["filings"].append({
                            "form": form_type,
                            "filing_date": f.get("filing_date", ""),
                            "accession_number": acc,
                            "sections": sections,
                        })
                        continue
                    else:
                        del self._extraction_cache[key]

                htmls = self._fetch_filing_documents(cik, form_type, acc, url)
                if not htmls:
                    continue

                # Three deterministic-first tiers, merged per key.
                #
                # 1. sec2md ITEM slicing on the primary document. Wins where it
                #    works (10-K, 10-Q, page-splittable 20-F); returns None for the
                #    item-less forms (6-K, 40-F) whose substance is in the exhibits.
                sections = self._extract_sections_sec2md(htmls[0], form_type)
                if sections is None:
                    sections = {k: "" for k in SECTION_KEYS}

                # 2. Heading anchors over every document, filling only the keys
                #    sec2md left empty: the 40-F exhibit narrative, the untruncated
                #    tail of a 1-page 20-F, and `competition` (which has no ITEM of
                #    its own on any form). Costs a second markdown conversion of the
                #    primary document, on a 24h-cached path.
                if not all(sections.get(k) for k in SECTION_KEYS):
                    markdown = "\n\n".join(
                        m for m in (self._html_to_markdown(h) for h in htmls) if m
                    )
                    anchored = self._extract_sections_anchors(markdown, form_type)
                    if anchored:
                        for k in SECTION_KEYS:
                            if not sections.get(k):
                                sections[k] = anchored.get(k, "")

                # 3. LLM, only when nothing deterministic was found at all (free-form
                #    6-K, older/non-standard filers). Same trigger rate as before.
                if not any(sections.get(k) for k in SECTION_KEYS):
                    logger.info(
                        "no deterministic sections for %s %s; using LLM fallback",
                        ticker_upper,
                        form_type,
                    )
                    text = "\n\n".join(
                        t for t in (self._html_to_text(h, truncate=False) for h in htmls) if t
                    )
                    if not text:
                        continue
                    sections = self._extract_sections(text, form_type)
                self._extraction_cache[key] = (now, sections)
                
                out["filings"].append({
                    "form": form_type,
                    "filing_date": f.get("filing_date", ""),
                    "accession_number": acc,
                    "sections": sections,
                })
        
        return out


def get_edgar_service() -> EdgarService:
    """Return the shared EdgarService instance."""
    if not hasattr(get_edgar_service, "_instance"):
        get_edgar_service._instance = EdgarService()  # type: ignore[attr-defined]
    return get_edgar_service._instance  # type: ignore[attr-defined]
