"""
Polymarket Search Keyword Generator

Generates the search terms used to find prediction markets relevant to a stock
ticker.  An LLM is given the company's info (name, sector, industry, business
summary) and asked for the phrases most likely to appear in real Polymarket
market titles.  Results are cached per ticker (LLM calls are rare) and fall back
to the deterministic narrative mapper whenever the LLM is unavailable or fails,
so the feature never returns zero keywords.
"""

import logging
from typing import Dict, List, Optional

# Backend-internal deps: both `services.*` (backend dir on path) and
# `backend.services.*` (project root on path) are valid entry points in this
# repo, so import defensively to work under either — see backend/run.py.
try:
    from services.data_cache import get_cached
    from services import polymarket_narrative_mapper
    from config import DATA_CACHE_TTL_COMPANY
except ImportError:  # pragma: no cover - depends on which root is on sys.path
    from backend.services.data_cache import get_cached
    from backend.services import polymarket_narrative_mapper
    from backend.config import DATA_CACHE_TTL_COMPANY

logger = logging.getLogger(__name__)

# Keywords are as stable as the company profile itself, so reuse the company
# info TTL (24h).  ~1 LLM call per ticker per day on the live endpoint.
_KEYWORD_CACHE_TTL = DATA_CACHE_TTL_COMPANY

# Cap on how much of the (often very long) business summary we feed the model.
_MAX_SUMMARY_CHARS = 1500


def generate_search_keywords(
    ticker: str,
    company_info: Optional[Dict] = None,
    limit: int = 12,
) -> List[str]:
    """
    Return an ordered list of Polymarket search terms for a ticker.

    LLM-generated (given company_info) with a guaranteed core of exact-match
    terms unioned in, cached per ticker, and falling back to the deterministic
    narrative mapper on any failure.

    Args:
        ticker: Stock ticker symbol (e.g. "NVDA").
        company_info: Optional dict with keys name, sector, industry,
            country, exchange, officers (list of {name, title} dicts),
            and longBusinessSummary/description.
        limit: Maximum number of keywords to return.

    Returns:
        Ordered, de-duplicated list of search terms (most specific first).
    """
    ticker_upper = (ticker or "").strip().upper()
    if not ticker_upper:
        return []

    cache_key = f"polymarket_keywords:{ticker_upper}"

    def _build() -> List[str]:
        return _generate(ticker_upper, company_info, limit)

    try:
        return get_cached(cache_key, _KEYWORD_CACHE_TTL, _build)
    except Exception as e:  # cache layer failure must not break the endpoint
        logger.warning(f"Keyword cache failed for {ticker_upper}: {e}; generating uncached")
        return _build()


def _generate(ticker_upper: str, company_info: Optional[Dict], limit: int) -> List[str]:
    """Core generation (uncached): LLM + guaranteed core, else deterministic fallback."""
    llm_keywords: List[str] = []
    try:
        llm_keywords = _generate_via_llm(ticker_upper, company_info, limit)
    except Exception as e:
        logger.warning(f"LLM keyword generation failed for {ticker_upper}: {e}")

    if llm_keywords:
        # Guarantee exact-match terms are always searched regardless of the LLM's output.
        core = [ticker_upper, f"({ticker_upper})", f"${ticker_upper}"]
        name = (company_info or {}).get("name")
        if name and name != ticker_upper:
            core.append(name)
        merged = _dedupe(core + llm_keywords)
        logger.info(f"Generated {len(merged)} LLM keywords for {ticker_upper}")
        return merged[:limit]

    # Fallback: existing deterministic rules.
    logger.info(f"Falling back to deterministic narrative mapper for {ticker_upper}")
    fallback = polymarket_narrative_mapper.map_ticker_to_narratives(ticker_upper, company_info)
    return _dedupe(fallback)[:limit]


def _dedupe(terms: List[str]) -> List[str]:
    """Order-preserving, case-insensitive de-duplication (drops blanks)."""
    seen: set = set()
    out: List[str] = []
    for term in terms:
        if not term:
            continue
        term = term.strip()
        key = term.lower()
        if term and key not in seen:
            seen.add(key)
            out.append(term)
    return out


def _generate_via_llm(
    ticker_upper: str,
    company_info: Optional[Dict],
    limit: int,
) -> List[str]:
    """
    Ask the configured LLM for Polymarket search terms.

    Raises on any failure (missing config/creds, provider error, empty output);
    the caller catches and falls back to the deterministic mapper.
    """
    # Lazy imports: ai_engine requires the project root on sys.path, and langchain
    # is heavy — importing here keeps this module cheap and lets ImportError fall
    # through to the deterministic path.
    from ai_engine.llm_provider import get_config_from_env, get_llm
    from langchain_core.messages import HumanMessage
    from pydantic import BaseModel, Field

    class KeywordList(BaseModel):
        """Structured keyword output."""
        keywords: List[str] = Field(
            description="Search phrases likely to appear in Polymarket market titles, most specific first."
        )

    info = company_info or {}
    name = info.get("name") or ticker_upper
    sector = info.get("sector") or "N/A"
    industry = info.get("industry") or "N/A"
    country = info.get("country") or "N/A"
    exchange = info.get("exchange") or "N/A"
    summary = (
        info.get("longBusinessSummary")
        or info.get("description")
        or info.get("business_summary")
        or ""
    )
    if summary:
        summary = summary[:_MAX_SUMMARY_CHARS]

    # Format current officers as "Name (Title)" lines so the LLM uses real,
    # up-to-date management names instead of guessing from training data.
    officers_raw = info.get("officers") or []
    if officers_raw:
        officers_str = "; ".join(
            f"{o['name']} ({o['title']})"
            for o in officers_raw
            if o.get("name") and o.get("title")
        )
    else:
        officers_str = "N/A"

    prompt = (
        "You generate search terms for finding prediction markets on Polymarket that are "
        "relevant to a public company's stock.\n\n"
        f"Company: {name}\n"
        f"Ticker: {ticker_upper}\n"
        f"Sector: {sector}\n"
        f"Industry: {industry}\n"
        f"Country: {country}\n"
        f"Exchange: {exchange}\n"
        f"Current management: {officers_str}\n"
        f"Business summary: {summary or 'N/A'}\n\n"
        "Return short search phrases (1-3 words each) that are LIKELY TO APPEAR IN POLYMARKET "
        "MARKET TITLES and are specific enough to match this company rather than unrelated ones. "
        "Prioritise, in order: the ticker and common company-name variants; flagship products or "
        "brands; well-known executives; then the dominant sector/theme the stock trades on. "
        "Avoid generic macro terms (e.g. 'inflation', 'interest rates') unless they are central to "
        "this company. Do not include explanations.\n\n"
        "Example for NVDA (NVIDIA): [\"Nvidia\", \"NVDA\", \"GPU\", \"AI chips\", \"Jensen Huang\", "
        "\"data center\", \"semiconductor\"].\n\n"
        f"Return at most {limit} phrases, ordered most specific first."
    )

    cfg = get_config_from_env()
    # Quick/cheap tier and deterministic temperature — this is lightweight extraction.
    llm = get_llm("quick", cfg, temperature=0.0, request_timeout=30)
    structured_llm = llm.with_structured_output(KeywordList, method="function_calling")
    result = structured_llm.invoke([HumanMessage(content=prompt)])

    keywords = getattr(result, "keywords", None)
    if not keywords and isinstance(result, dict):
        keywords = result.get("keywords")
    if not keywords:
        raise ValueError("LLM returned no keywords")

    return [str(k).strip() for k in keywords if str(k).strip()]
