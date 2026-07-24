"""
SEC filing exploration tools - like file exploration tools for code.
Agent can grep, read sections, get TOC, etc.
"""

from langchain_core.tools import tool
from typing import Annotated, Optional

from ...datasources.info_service_client import get_edgar_full_text, require_info_service
from .sec_file_explorer import SECFilingExplorer


# Cache current filing being explored, keyed by (ticker, form) so the 10-K and
# 10-Q of the same company do not clobber each other.
_current_explorer: Optional[SECFilingExplorer] = None
_current_key: Optional[tuple] = None


def _normalize_form(form: str) -> str:
    """Normalize an agent-supplied filing type to the exact SEC form string."""
    f = (form or "").strip().upper().replace(" ", "")
    if f in ("10K", "10-K"):
        return "10-K"
    if f in ("10Q", "10-Q"):
        return "10-Q"
    raise ValueError(f"Unsupported form '{form}'. Use '10-K' or '10-Q'.")


def _get_explorer(ticker: str, form: str) -> SECFilingExplorer:
    """
    Get or create an explorer for a specific (ticker, form) filing.

    `form` is required so every tool operates on the same filing the agent is
    analyzing (the latest 10-K or 10-Q), rather than whatever the newest filing
    happens to be - Item 1 Business / Competition only exist in the 10-K.
    """
    global _current_explorer, _current_key

    ticker = ticker.upper()
    form = _normalize_form(form)
    key = (ticker, form)

    if _current_explorer and _current_key == key:
        return _current_explorer

    # Fetch full text of the requested form from backend (raw=true)
    require_info_service()
    result = get_edgar_full_text(ticker, form=form)

    if result.get("error"):
        raise ValueError(f"Failed to load {form} filing: {result['error']}")

    _current_explorer = SECFilingExplorer(
        filing_text=result["text"],
        filing_metadata=result["filing"],
    )
    _current_key = key

    return _current_explorer


@tool
def grep_sec_filing(
    ticker: Annotated[str, "ticker symbol"],
    form: Annotated[str, "filing type to search: '10-K' or '10-Q'"],
    pattern: Annotated[str, "search pattern (regex)"],
    context: Annotated[int, "context lines (default 3)"] = 3,
    max_results: Annotated[int, "max results (default 10)"] = 10,
) -> str:
    """
    Search SEC filing for pattern (like grep -C).
    Use to find specific terms, phrases, or concerns.

    Examples:
        grep_sec_filing("AAPL", "10-K", "revenue growth")
        grep_sec_filing("MSFT", "10-Q", "regulatory|antitrust")
    """
    explorer = _get_explorer(ticker, form)
    matches = explorer.grep(pattern, context, max_results)
    
    if not matches:
        return f"No matches for '{pattern}'"
    
    lines = [f"grep '{pattern}' - {len(matches)} matches:\n"]
    for i, m in enumerate(matches, 1):
        lines.append(f"Match {i} (Line {m['line_number']}):")
        for ctx in m['context_before']:
            lines.append(f"  {ctx}")
        lines.append(f"→ {m['matched_line']}")
        for ctx in m['context_after']:
            lines.append(f"  {ctx}")
        lines.append("")
    
    return '\n'.join(lines)


@tool
def read_sec_section(
    ticker: Annotated[str, "ticker symbol"],
    form: Annotated[str, "filing type to read from: '10-K' or '10-Q'"],
    section: Annotated[str, "section: risk_factors, mda, business, competition, legal_proceedings, market_risk"],
    max_chars: Annotated[int, "max chars (default 20000)"] = 20000,
) -> str:
    """
    Read specific section from SEC filing.
    Like reading a specific function/class from a code file.
    """
    explorer = _get_explorer(ticker, form)
    content = explorer.find_section(section, max_chars)
    
    if content:
        return f"Section: {section}\n\n{content}"
    return f"Section '{section}' not found"


@tool
def get_sec_toc(
    ticker: Annotated[str, "ticker symbol"],
    form: Annotated[str, "filing type: '10-K' or '10-Q'"],
) -> str:
    """
    Get table of contents for SEC filing.
    Like listing all functions/classes in a code file.
    Use this FIRST to see what's in the filing.
    """
    explorer = _get_explorer(ticker, form)
    sections = explorer.get_toc()
    
    if not sections:
        return "No TOC found"
    
    filing = explorer.metadata
    lines = [f"TOC: {filing.get('form')} filed {filing.get('filing_date')}\n"]
    
    for sec in sections:
        lines.append(f"Item {sec['item']}: {sec['name']}")
        lines.append(f"  Lines {sec['line_start']}-{sec['line_end']} ({sec['char_count']:,} chars)")
        lines.append(f"  {sec['preview']}\n")
    
    return '\n'.join(lines)


@tool
def get_sec_stats(
    ticker: Annotated[str, "ticker symbol"],
    form: Annotated[str, "filing type: '10-K' or '10-Q'"],
) -> str:
    """Get filing statistics (size, word count, top terms)."""
    explorer = _get_explorer(ticker, form)
    stats = explorer.get_stats()
    filing = explorer.metadata
    
    lines = [f"Stats: {filing.get('form')}"]
    lines.append(f"{stats['total_chars']:,} chars, {stats['total_words']:,} words, {stats['total_lines']:,} lines\n")
    lines.append("Top terms:")
    for term, count in stats['top_terms'][:10]:
        lines.append(f"  {term}: {count}")
    
    return '\n'.join(lines)


@tool
def read_sec_lines(
    ticker: Annotated[str, "ticker symbol"],
    form: Annotated[str, "filing type: '10-K' or '10-Q'"],
    start: Annotated[int, "start line (1-indexed)"],
    end: Annotated[int, "end line (inclusive)"],
) -> str:
    """
    Read specific line range from filing.
    Like reading lines X-Y from a code file.
    """
    explorer = _get_explorer(ticker, form)
    return explorer.get_lines(start, end)


@tool
def extract_competitors(
    ticker: Annotated[str, "ticker symbol"],
    form: Annotated[str, "filing type: '10-K' or '10-Q'. Competition lives in the 10-K's Item 1, so choose '10-K' for competitor analysis"],
) -> str:
    """
    Mine the SEC filing for sentences that name or describe direct competitors.

    Targets Item 1 Competition language: "We compete with ...",
    "Our competitors include ...", "competitive landscape", etc.
    The Item 1 Business/Competition section exists only in the 10-K, so choose
    form="10-K" for competitor analysis (a 10-Q contains none).

    Returns JSON with:
      - total_matches (int)
      - signals: list of {line_number, matched_line, context_before, context_after, signal_type}
      - summary: human-readable count string

    Use this when you need to identify named competitors, assess competitive
    intensity, or evaluate the company's stated competitive position.
    """
    explorer = _get_explorer(ticker, form)
    return explorer.extract_competitors()


@tool
def extract_tam_disclosures(
    ticker: Annotated[str, "ticker symbol"],
    form: Annotated[str, "filing type: '10-K' or '10-Q'. TAM/market-size sits in Item 1 Business, so choose '10-K'"],
) -> str:
    """
    Mine the SEC filing for Total Addressable Market (TAM), Serviceable
    Addressable Market (SAM), and CAGR disclosures.

    Companies cite third-party market size estimates (Gartner, IDC, etc.)
    inside Item 1 Business Overview. This tool finds those passages.
    The Item 1 Business section exists only in the 10-K, so choose form="10-K"
    for market-size analysis (a 10-Q contains none).

    Returns JSON with:
      - total_matches (int)
      - signals: list of {line_number, matched_line, context_before, context_after,
                          signal_type}  # "tam_label" | "dollar_market_size" | "cagr" | "market_opportunity"
      - summary: human-readable count string

    Use this when you need to assess the company's stated market opportunity,
    growth potential, or industry size claims.
    """
    explorer = _get_explorer(ticker, form)
    return explorer.extract_tam_disclosures()


@tool
def extract_customer_concentration(
    ticker: Annotated[str, "ticker symbol"],
    form: Annotated[str, "filing type: '10-K' or '10-Q' (10-K has the fullest disclosures)"],
) -> str:
    """
    Mine the SEC filing for customer and supplier concentration disclosures.

    Under ASC 280, companies must disclose any customer exceeding 10% of
    revenue. Sole-source supplier risk appears in risk factors.

    Returns JSON with:
      - total_matches (int)
      - signals: list of {line_number, matched_line, context_before, context_after,
                          signal_type}  # "customer_revenue_pct" | "major_customer" |
                                        # "sole_supplier" | "supplier_concentration"
      - summary: human-readable count string

    Use this when you need to assess revenue concentration risk, customer
    dependency, or supply-chain single-source vulnerabilities.
    """
    explorer = _get_explorer(ticker, form)
    return explorer.extract_customer_concentration()


@tool
def extract_porter_signals(
    ticker: Annotated[str, "ticker symbol"],
    form: Annotated[str, "filing type: '10-K' (richest Item 1A Risk Factors) or '10-Q'"],
) -> str:
    """
    Mine Item 1A Risk Factors for language that maps to Porter's Five Forces.

    Each matched passage is tagged with the force it represents:
      - rivalry        : pricing pressure, market share, intense competition
      - new_entrants   : barriers to entry, capital requirements
      - substitutes    : switching costs, alternative products/platforms
      - buyer_power    : customer bargaining, volume discounts, churn
      - supplier_power : sole-source supplier, raw material shortage

    Returns JSON with:
      - total_matches (int)
      - by_force: dict keyed by force name, each containing a list of
                  {line_number, matched_line, context_before, context_after, signal_type}
      - summary: human-readable string listing active forces

    Use this to synthesize a Porter's Five Forces analysis grounded in the
    company's own disclosed risk language.
    """
    explorer = _get_explorer(ticker, form)
    return explorer.extract_porter_signals()

# Made with Bob
