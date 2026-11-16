"""SerpAPI (Google search) client shared by portfolio deep research and watchlist web research.

Lives at the ai_engine top level because watchlist_consulting imports its siblings by bare
name, so it cannot reach into portfolio_deep_research (or the other way round) cleanly.
ai_engine/agent/tools/web_search.py is separate on purpose: its output shape differs.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


def search(
    query: str,
    num_results: int,
    api_key: Optional[str] = None,
    timeout: int = 30,
) -> List[Dict[str, Any]]:
    """Return up to num_results Google results as dicts with title, snippet, url, domain.

    The key falls back to the SERPAPI_KEY env var. Raises ValueError with no key and
    RuntimeError when SerpAPI answers with an error body (it returns 200 for those).
    """
    key = api_key or os.getenv("SERPAPI_KEY")
    if not key:
        raise ValueError("SERPAPI_KEY not set in environment or .env")

    params = {"engine": "google", "q": query, "api_key": key}
    url = "https://serpapi.com/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())

    error = data.get("error")
    if error:
        raise RuntimeError(f"SerpAPI error: {error}")

    results = []
    for item in data.get("organic_results", [])[:num_results]:
        # displayed_link looks like "reuters.com › markets › ..."; keep only the site.
        domain = item.get("displayed_link") or item.get("source") or ""
        if isinstance(domain, str) and " › " in domain:
            domain = domain.split(" › ")[0].strip()
        results.append({
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "url": item.get("link", ""),
            "domain": domain,
        })
    return results


def format_results(results: List[Dict[str, Any]]) -> str:
    """Render results as numbered "[i] title / URL: url / snippet" blocks for an LLM tool reply."""
    if not results:
        return "No results found. Try a different query."
    return "\n".join(
        f"[{i}] {r.get('title', '')}\nURL: {r.get('url', '')}\n{r.get('snippet', '')}\n"
        for i, r in enumerate(results, 1)
    )
