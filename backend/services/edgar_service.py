"""
SEC EDGAR service: resolve ticker to CIK, list 10-K/10-Q filings, build SEC document links.

Uses official SEC APIs. No authentication required; User-Agent must identify the application.
Rate limit: 10 requests per second (SEC policy). We cache ticker->CIK and submissions.

Extended to fetch filing document HTML, convert to text, and use an LLM to extract
structured sections (Risk Factors, MD&A, Competition) for the SEC analyst.
"""

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

# SEC requires a descriptive User-Agent (see https://www.sec.gov/os/webmaster-faq)
USER_AGENT = "Flowdeck (contact@flowdeck.app)"

# Cache TTL in seconds (24h)
TICKER_CACHE_TTL = 24 * 60 * 60

# Allowed form types for filings list
FILING_FORMS = {"10-K", "10-Q"}

# Limits for document text and extraction (chars)
MAX_DOCUMENT_TEXT_CHARS = 100_000
MAX_TEXT_FOR_EXTRACTION_CHARS = 80_000
MAX_SECTION_CHARS = 12_000

# Cache TTL for extracted sections (24h)
EXTRACTION_CACHE_TTL = 24 * 60 * 60


class ExtractedSECSections(BaseModel):
    """Structured extraction from a SEC 10-K or 10-Q filing (LLM output)."""

    risk_factors: str = Field(
        default="",
        description="Item 1A Risk Factors (10-K) or Part II Item 1A (10-Q). Use empty string if not found.",
    )
    management_discussion_and_analysis: str = Field(
        default="",
        description="Item 7 MD&A (10-K) or Part I Item 2 MD&A (10-Q). Use empty string if not found.",
    )
    competition: str = Field(
        default="",
        description="Competition subsection from Item 1 Business. Use empty string if not found.",
    )
    business_overview: str = Field(
        default="",
        description="Brief overview of Item 1 Business (products, segments). Use empty string if not found.",
    )
    legal_proceedings: str = Field(
        default="",
        description="Item 3 Legal Proceedings. Use empty string if not found.",
    )
    market_risk_disclosures: str = Field(
        default="",
        description="Item 7A Quantitative and Qualitative Market Risk. Use empty string if not found.",
    )


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
        "ANNUAL REPORT PURSUANT TO SECTION 13",
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

    def _fetch_document_text(self, url: str) -> str:
        """Fetch document at URL, strip XBRL markup, extract text with BeautifulSoup, skip to narrative, truncate. Returns empty string on failure."""
        if not url:
            return ""
        self._throttle()
        try:
            r = requests.get(url, headers=self._get_headers_html(), timeout=30)
            r.raise_for_status()
            raw = r.text
        except Exception as e:
            logger.warning("Failed to fetch SEC document %s: %s", url[:80], e)
            return ""
        raw = _strip_xbrl_markup(raw)
        soup = BeautifulSoup(raw, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        text = _skip_to_narrative(text)
        return _truncate(text, MAX_DOCUMENT_TEXT_CHARS)

    def _get_extraction_llm(self):
        """Lazy-init LLM for section extraction (Azure or OpenAI from env)."""
        if self._extraction_llm is not None:
            return self._extraction_llm
        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
        azure_key = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
        if azure_endpoint and azure_key:
            from langchain_openai import AzureChatOpenAI
            model = os.environ.get("AZURE_QUICK_THINK_MODEL", "gpt-4o-mini")
            self._extraction_llm = AzureChatOpenAI(
                azure_deployment=model,
                model=model,
                azure_endpoint=azure_endpoint,
                api_key=azure_key,
                api_version=os.environ.get("OPENAI_API_VERSION", "2024-08-01-preview"),
                request_timeout=90,
                temperature=0.0,
            )
        else:
            from langchain_openai import ChatOpenAI
            api_key = os.environ.get("OPENAI_API_KEY", "").strip()
            if not api_key:
                raise ValueError(
                    "EDGAR extraction requires OPENAI_API_KEY or (AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY)"
                )
            self._extraction_llm = ChatOpenAI(
                model=os.environ.get("EDGAR_EXTRACTION_MODEL", "gpt-4o-mini"),
                temperature=0.0,
                request_timeout=90,
            )
        return self._extraction_llm

    def _extract_sections(self, full_text: str) -> Dict[str, Any]:
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
        prompt = """Below is the text of a SEC 10-K or 10-Q filing. Extract the following sections and return them.
Use empty string for any section you cannot find.

1. risk_factors: Item 1A Risk Factors (10-K) or Part II Item 1A (10-Q).
2. management_discussion_and_analysis: Item 7 Management's Discussion and Analysis (10-K) or Part I Item 2 MD&A (10-Q).
3. competition: The Competition (or competitive environment) subsection from Item 1 Business.
4. business_overview: Brief overview of Item 1 Business (products, segments, strategy) - optional.
5. legal_proceedings: Item 3 Legal Proceedings - optional.
6. market_risk_disclosures: Item 7A Quantitative and Qualitative Disclosures About Market Risk - optional.

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
        Get recent 10-K and 10-Q filings for the ticker.

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
        # Build list of (form, date, accession, primary_doc), then filter and dedupe by accession
        seen: set = set()
        for i in range(n):
            form = (forms[i] or "").strip()
            if form not in FILING_FORMS:
                continue
            acc = (accession_numbers[i] or "").strip()
            if not acc or acc in seen:
                continue
            seen.add(acc)
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
    ) -> Dict[str, Any]:
        """
        Get extracted sections (risk factors, MD&A, competition, etc.) for recent filings.

        Returns:
            {
                "filings": [{"form", "filing_date", "accession_number", "sections": {...}}],
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
        if form:
            filings_list = [f for f in filings_list if f.get("form") == form]
        filings_list = filings_list[:limit]
        now = time.monotonic()
        for f in filings_list:
            acc = f.get("accession_number") or ""
            form_type = f.get("form") or ""
            key = (ticker_upper, form_type, acc)
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
            url = f.get("url") or ""
            text = self._fetch_document_text(url)
            if not text:
                continue
            sections = self._extract_sections(text)
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
