"""
Extract resource entries from tool invocations for report metadata.

Each resource dict has: type, url? (optional), title?, ticker?, description?,
tool_name?, tool_input?, tool_output_preview? (when attached by extraction node).
Used to populate report_resources in agent state and persist in report metadata.
"""

import json
import re
from typing import Any, Dict, List

# SEC EDGAR index URL for filings (company search; we don't have doc URL from filing_content response)
_SEC_EDGAR_INDEX = "https://www.sec.gov/cgi-bin/browse-edgar"


def extract_resources_from_tool(
    tool_name: str, tool_args: Dict[str, Any], result: str
) -> List[Dict[str, Any]]:
    """
    Parse tool name, args, and result into a list of resource dicts.
    Returns [] or a list of { type, url?, title?, ticker?, description? }.
    """
    resources: List[Dict[str, Any]] = []
    args = tool_args or {}
    ticker = str(args.get("ticker") or args.get("symbol") or "").strip().upper()

    if tool_name == "get_news":
        resources = _resources_from_news(result, ticker)
    elif tool_name == "get_global_news":
        resources = _resources_from_global_news(result)
    elif tool_name == "get_edgar_filing_content":
        resources = _resources_from_edgar_filing_content(result, ticker)
    elif tool_name == "get_reddit_company_social":
        resources = _resources_from_reddit(args)
    elif tool_name in ("get_fundamentals", "get_balance_sheet", "get_cashflow", "get_income_statement"):
        if ticker:
            resources = [{"type": "fundamentals", "ticker": ticker, "description": f"Financial data for {ticker}"}]
    elif tool_name == "get_ticker_data":
        if ticker:
            resources = [{"type": "price_history", "ticker": ticker, "description": f"Historical market data for {ticker}"}]
    elif tool_name == "get_ticker_quote":
        if ticker:
            resources = [{"type": "market_quote", "ticker": ticker, "description": f"Quote snapshot for {ticker}"}]
    elif tool_name == "get_indicators":
        if ticker:
            resources = [{"type": "technical_indicators", "ticker": ticker, "description": f"Technical indicator snapshot for {ticker}"}]
    elif tool_name == "get_analysts_recommendation":
        if ticker:
            resources = [{"type": "analyst_recommendation", "ticker": ticker}]
    elif tool_name in ("get_insider_sentiment", "get_insider_transactions"):
        if ticker:
            resources = [{"type": "insider_data", "ticker": ticker}]
    else:
        # Generic: record that this tool was used (e.g. detect_divergence, detect_regime)
        if ticker:
            resources = [{"type": "tool", "ticker": ticker, "description": tool_name}]

    return resources


def _resources_from_news(result: str, ticker: str) -> List[Dict[str, Any]]:
    """Parse news API response (articles with link, title, publisher)."""
    out: List[Dict[str, Any]] = []
    try:
        data = json.loads(result) if isinstance(result, str) else result
        if not isinstance(data, dict):
            return out
        articles = data.get("articles") or data.get("data")
        if not isinstance(articles, list):
            return out
        for a in articles:
            if not isinstance(a, dict):
                continue
            link = (a.get("link") or a.get("url") or "").strip()
            title = (a.get("title") or "").strip() or None
            publisher = (a.get("publisher") or a.get("source") or "").strip() or None
            r: Dict[str, Any] = {"type": "news", "title": title or link or "News article"}
            if link:
                r["url"] = link
            if ticker:
                r["ticker"] = ticker
            if publisher:
                r["description"] = publisher
            out.append(r)
    except (json.JSONDecodeError, TypeError):
        if ticker:
            out.append({"type": "news", "ticker": ticker, "description": "News data"})
    return out


def _resources_from_global_news(result: str) -> List[Dict[str, Any]]:
    """Parse global news response: JSON with articles, or markdown/text with links."""
    out: List[Dict[str, Any]] = []
    text = result if isinstance(result, str) else ""
    try:
        data = json.loads(text) if text.strip().startswith("{") else None
        if isinstance(data, dict) and (data.get("articles") or data.get("data")):
            articles = data.get("articles") or data.get("data") or []
            for a in articles if isinstance(articles, list) else []:
                if not isinstance(a, dict):
                    continue
                link = (a.get("link") or a.get("url") or "").strip()
                title = (a.get("title") or "").strip() or None
                r: Dict[str, Any] = {"type": "global_news", "title": title or link or "Global news"}
                if link:
                    r["url"] = link
                out.append(r)
            return out
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: parse markdown/text for "Source: URL" lines and optional "**N. Title**" / "### Title"
    _url_re = re.compile(r"https?://[^\s\]\)]+")
    last_title: str | None = None
    for line in text.splitlines():
        line = line.strip()
        # "Source: https://..." (SerpAPI-style)
        if line.lower().startswith("source:") and "http" in line:
            url_match = _url_re.search(line)
            if url_match:
                url = url_match.group(0).rstrip(".,;:)")
                out.append({
                    "type": "global_news",
                    "title": last_title or "Global news article",
                    "url": url,
                })
            last_title = None
            continue
        # "**1. Title**" or "### Title"
        if line.startswith("**") and "**" in line[2:]:
            last_title = re.sub(r"^\*\*\d*\.?\s*", "", line).strip(" *")
        elif line.startswith("###"):
            last_title = line.lstrip("#").strip()
    # Any remaining URLs in the whole text not yet captured (e.g. inline links)
    if not out and text:
        for url_match in _url_re.finditer(text):
            url = url_match.group(0).rstrip(".,;:)")
            if len(url) < 400:  # skip junk
                out.append({"type": "global_news", "url": url, "title": "Global news"})
                break  # one generic link is enough
    if not out:
        out.append({"type": "global_news", "description": "Macro / global news"})
    return out


def _resources_from_edgar_filing_content(result: str, ticker: str) -> List[Dict[str, Any]]:
    """Parse EDGAR filing content response: filings with form, filing_date, accession_number."""
    out: List[Dict[str, Any]] = []
    try:
        data = json.loads(result) if isinstance(result, str) else result
        if not isinstance(data, dict):
            return out
        filings = data.get("filings")
        if not isinstance(filings, list):
            if ticker:
                out.append({"type": "sec_filing", "ticker": ticker, "description": "SEC EDGAR filing"})
            return out
        for f in filings:
            if not isinstance(f, dict):
                continue
            form = (f.get("form") or "").strip() or "Filing"
            filing_date = (f.get("filing_date") or "").strip()
            acc = (f.get("accession_number") or "").strip()
            desc = f"{form} filed {filing_date}" if filing_date else form
            r: Dict[str, Any] = {
                "type": "sec_filing",
                "ticker": ticker or None,
                "title": desc,
                "description": acc or desc,
            }
            # SEC doesn't give us doc URL in filing_content response; optional link to EDGAR index
            if acc:
                r["url"] = _SEC_EDGAR_INDEX
            out.append(r)
    except (json.JSONDecodeError, TypeError):
        if ticker:
            out.append({"type": "sec_filing", "ticker": ticker, "description": "SEC EDGAR filing"})
    return out


def _resources_from_reddit(args: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Reddit company social: we only have args (ticker, search_terms); result may be text."""
    ticker = (args.get("ticker") or "").strip().upper()
    if not ticker:
        return []
    return [{"type": "reddit", "ticker": ticker, "description": "Reddit company social / discussion"}]
