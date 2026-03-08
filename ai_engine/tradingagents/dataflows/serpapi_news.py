"""Global news via SerpAPI (Google News). Same SerpAPI usage as ai_engine.agent.tools.web_search."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Annotated, Optional

from dateutil.relativedelta import relativedelta


def get_global_news_serpapi(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of articles to return"] = 5,
    query: Annotated[Optional[str], "Optional search focus"] = None,
) -> str:
    """Get global/macro news from Google News via SerpAPI. Requires SERPAPI_KEY."""
    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        raise ValueError("SERPAPI_KEY not set. Set it in environment or backend/.env to use SerpAPI for global news.")

    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = curr_dt - relativedelta(days=look_back_days)
    # SerpAPI tbs expects mm/dd/yyyy
    start_str = start_dt.strftime("%m/%d/%Y")
    end_str = curr_dt.strftime("%m/%d/%Y")

    search_q = (
        (query.strip() if query and query.strip() else "")
        or "global economics OR macroeconomics OR financial markets OR trading news"
    )

    params = {
        "engine": "google",
        "tbm": "nws",
        "q": search_q,
        "num": min(limit, 20),
        "api_key": api_key,
        "tbs": f"cdr:1,cd_min:{start_str},cd_max:{end_str}",
    }
    url = "https://serpapi.com/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    error = data.get("error")
    if error:
        raise RuntimeError(f"SerpAPI error: {error}")

    # With tbm=nws, SerpAPI returns news_results; fallback to organic_results
    items = data.get("news_results") or data.get("organic_results") or []
    items = items[:limit]

    if not items:
        return ""

    lines = [f"## Global News (SerpAPI), from {start_dt.strftime('%Y-%m-%d')} to {curr_date}", ""]
    for i, item in enumerate(items, 1):
        title = item.get("title", "")
        link = item.get("link", "") or item.get("url", "")
        snippet = item.get("snippet", "")
        source = item.get("source", "")
        date = item.get("date", "") or item.get("published_at", "")
        date_str = f" ({date})" if date else ""
        source_str = f" — {source}" if source else ""
        lines.append(f"**{i}. {title}**{source_str}{date_str}")
        if snippet:
            lines.append(snippet)
        if link:
            lines.append(f"Source: {link}")
        lines.append("")

    return "\n".join(lines)
