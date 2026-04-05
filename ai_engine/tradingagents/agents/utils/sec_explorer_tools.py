"""
SEC filing exploration tools - like file exploration tools for code.
Agent can grep, read sections, get TOC, etc.
"""

from langchain_core.tools import tool
from typing import Annotated, Optional

from ...datasources.info_service_client import get_edgar_full_text, require_info_service
from .sec_file_explorer import SECFilingExplorer


# Cache current filing being explored
_current_explorer: Optional[SECFilingExplorer] = None
_current_ticker: Optional[str] = None


def _get_explorer(ticker: str) -> SECFilingExplorer:
    """Get or create explorer for ticker (fetches filing if needed)."""
    global _current_explorer, _current_ticker
    
    ticker = ticker.upper()
    
    if _current_explorer and _current_ticker == ticker:
        return _current_explorer
    
    # Fetch full text from backend (raw=true)
    require_info_service()
    result = get_edgar_full_text(ticker)
    
    if result.get("error"):
        raise ValueError(f"Failed to load filing: {result['error']}")
    
    _current_explorer = SECFilingExplorer(
        filing_text=result["text"],
        filing_metadata=result["filing"],
    )
    _current_ticker = ticker
    
    return _current_explorer


@tool
def grep_sec_filing(
    ticker: Annotated[str, "ticker symbol"],
    pattern: Annotated[str, "search pattern (regex)"],
    context: Annotated[int, "context lines (default 3)"] = 3,
    max_results: Annotated[int, "max results (default 10)"] = 10,
) -> str:
    """
    Search SEC filing for pattern (like grep -C).
    Use to find specific terms, phrases, or concerns.
    
    Examples:
        grep_sec_filing("AAPL", "revenue growth")
        grep_sec_filing("MSFT", "regulatory|antitrust")
    """
    explorer = _get_explorer(ticker)
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
    section: Annotated[str, "section: risk_factors, mda, business, competition, legal_proceedings, market_risk"],
    max_chars: Annotated[int, "max chars (default 20000)"] = 20000,
) -> str:
    """
    Read specific section from SEC filing.
    Like reading a specific function/class from a code file.
    """
    explorer = _get_explorer(ticker)
    content = explorer.find_section(section, max_chars)
    
    if content:
        return f"Section: {section}\n\n{content}"
    return f"Section '{section}' not found"


@tool
def get_sec_toc(ticker: Annotated[str, "ticker symbol"]) -> str:
    """
    Get table of contents for SEC filing.
    Like listing all functions/classes in a code file.
    Use this FIRST to see what's in the filing.
    """
    explorer = _get_explorer(ticker)
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
def get_sec_stats(ticker: Annotated[str, "ticker symbol"]) -> str:
    """Get filing statistics (size, word count, top terms)."""
    explorer = _get_explorer(ticker)
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
    start: Annotated[int, "start line (1-indexed)"],
    end: Annotated[int, "end line (inclusive)"],
) -> str:
    """
    Read specific line range from filing.
    Like reading lines X-Y from a code file.
    """
    explorer = _get_explorer(ticker)
    return explorer.get_lines(start, end)

# Made with Bob
