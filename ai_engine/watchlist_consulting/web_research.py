"""
Web research for watchlist report: SerpAPI search, query generation from intent/themes/tickers,
per-query analysis (learnings + follow-ups), optional depth, aggregation into WebResearchOutput.
Uses sync HTTP (urllib) and existing report_agent LLM; no aiohttp dependency.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from pipeline_schemas import ThemeOutput, UserIntent, WebLearning, WebResearchOutput

try:
    from report_agent import _get_llm
except ImportError:
    _get_llm = None


def serpapi_search(
    query: str,
    num_results: int = 5,
    api_key: Optional[str] = None,
    timeout: int = 30,
) -> List[Dict[str, Any]]:
    """
    Search the web using SerpAPI (Google Search Engine Results API). Sync.

    Returns:
        List of result dicts with title, snippet, url, domain
    """
    key = api_key or os.getenv("SERPAPI_KEY")
    if not key:
        raise ValueError("SERPAPI_KEY not set in environment or .env")

    params = {
        "engine": "google",
        "q": query,
        "api_key": key,
    }
    url = "https://serpapi.com/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())

    error = data.get("error")
    if error:
        raise RuntimeError(f"SerpAPI error: {error}")

    results = []
    for item in data.get("organic_results", [])[:num_results]:
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


def generate_search_queries(
    user_intent: UserIntent,
    theme_output: ThemeOutput,
    payload: Dict[str, Any],
    breadth: int,
    llm: Any = None,
) -> List[str]:
    """
    Generate breadth-many search queries from user intent, themes, and payload (tickers/sectors).
    """
    if llm is None:
        llm = _get_llm() if _get_llm else None
    if not llm:
        return []

    tickers = payload.get("tickers") or []
    entries = payload.get("entries") or []
    sectors: List[str] = []
    for e in entries:
        company = e.get("company_info") or {}
        s = company.get("sector") or company.get("industry")
        if s and s not in sectors:
            sectors.append(s)
    exposure = theme_output.exposure_snapshot
    if exposure:
        sectors = list(set(sectors + list(exposure.sector_counts.keys())[:5]))

    themes_str = ", ".join(t.theme for t in theme_output.dominant_themes[:5])
    risks_str = ", ".join(theme_output.common_risks[:5])
    tickers_str = ", ".join(tickers[:10])
    sectors_str = ", ".join(sectors[:8]) if sectors else "not specified"

    prompt = f"""You are helping build research queries for a personalized watchlist report.
Generate {breadth} specific search queries to find recent, relevant web content that will enrich the report.

Context:
- Investor style: {user_intent.investor_style}, risk: {user_intent.risk_budget}, horizon: {user_intent.time_horizon}
- Report style: {user_intent.report_style}
- Dominant themes in watchlist: {themes_str or "none"}
- Common risks: {risks_str or "none"}
- Tickers: {tickers_str or "none"}
- Sectors: {sectors_str}

Each query should be a single, specific search phrase (e.g. "[sector] outlook 2025", "[ticker] recent news", "[risk theme] impact on equities").
Mix: 1–2 intent-driven, 1–2 theme-driven, 1 ticker/sector-driven if relevant.
Return only the queries, one per line. No numbering or quotes."""

    from langchain_core.messages import HumanMessage
    response = llm.invoke([HumanMessage(content=prompt)])
    content = (getattr(response, "content", None) or str(response) or "").strip()
    queries = [q.strip() for q in content.split("\n") if q.strip()][:breadth]
    return queries


def analyze_search_results(
    query: str,
    results: List[Dict[str, Any]],
    llm: Any = None,
) -> Dict[str, Any]:
    """
    Extract learnings and follow-up questions from one set of search results.
    Returns dict with keys: learnings (list of str), follow_up_questions (list of str), source_quality (optional).
    """
    if not results:
        return {"learnings": [], "follow_up_questions": []}
    if llm is None:
        llm = _get_llm() if _get_llm else None
    if not llm:
        learnings = [r.get("snippet", "")[:200] for r in results[:3]]
        return {"learnings": learnings, "follow_up_questions": []}

    results_text = "\n\n".join([
        f"Title: {r.get('title', '')}\nSnippet: {r.get('snippet', '')}\nURL: {r.get('url', '')}\nDomain: {r.get('domain', '')}"
        for r in results
    ])

    prompt = f"""Analyze the following search results for the query: "{query}"

Search Results:
{results_text}

Extract key learnings and generate follow-up questions. Return a JSON object with:
- "learnings": List of key insights (3-5 short bullets)
- "follow_up_questions": List of 2-3 follow-up questions to explore further"""

    from langchain_core.messages import HumanMessage
    response = llm.invoke([HumanMessage(content=prompt)])
    content = (getattr(response, "content", None) or str(response) or "").strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1]
    try:
        out = json.loads(content)
        return {
            "learnings": out.get("learnings") or [],
            "follow_up_questions": out.get("follow_up_questions") or [],
        }
    except json.JSONDecodeError:
        return {"learnings": [], "follow_up_questions": []}


def run_web_research_sync(
    user_intent: UserIntent,
    theme_output: ThemeOutput,
    payload: Dict[str, Any],
    *,
    breadth: int = 3,
    depth: int = 2,
    num_results_initial: int = 5,
    num_results_followup: int = 3,
    max_follow_ups_per_query: int = 2,
    llm: Any = None,
) -> WebResearchOutput:
    """
    Run full web research: generate queries -> search -> analyze -> optional follow-up -> aggregate.
    Returns WebResearchOutput with deduped learnings and sources.
    """
    if breadth <= 0 or not os.getenv("SERPAPI_KEY"):
        return WebResearchOutput(
            learnings=[],
            sources=[],
            queries_used=[],
            stats={"total_learnings": 0, "total_sources": 0, "follow_ups_used": 0},
        )

    if llm is None:
        llm = _get_llm() if _get_llm else None

    all_learnings: List[WebLearning] = []
    all_sources: List[str] = []
    queries_used: List[str] = []
    follow_ups_used = 0

    initial_queries = generate_search_queries(user_intent, theme_output, payload, breadth, llm=llm)
    if not initial_queries:
        return WebResearchOutput(
            learnings=[],
            sources=[],
            queries_used=[],
            stats={"total_learnings": 0, "total_sources": 0, "follow_ups_used": 0},
        )

    for query in initial_queries:
        queries_used.append(query)
        try:
            results = serpapi_search(query, num_results=num_results_initial)
        except Exception:
            results = []
        urls = [r["url"] for r in results if r.get("url")]
        all_sources.extend(urls)
        analysis = analyze_search_results(query, results, llm=llm)
        for text in analysis.get("learnings") or []:
            if isinstance(text, str) and text.strip():
                all_learnings.append(WebLearning(
                    text=text.strip(),
                    query_used=query,
                    source_urls=urls[:5],
                ))
        follow_ups = (analysis.get("follow_up_questions") or [])[:max_follow_ups_per_query]
        if depth > 1 and follow_ups:
            for fq in follow_ups:
                if not isinstance(fq, str) or not fq.strip():
                    continue
                follow_ups_used += 1
                queries_used.append(fq)
                try:
                    fu_results = serpapi_search(fq, num_results=num_results_followup)
                except Exception:
                    fu_results = []
                fu_urls = [r["url"] for r in fu_results if r.get("url")]
                all_sources.extend(fu_urls)
                fu_analysis = analyze_search_results(fq, fu_results, llm=llm)
                for text in fu_analysis.get("learnings") or []:
                    if isinstance(text, str) and text.strip():
                        all_learnings.append(WebLearning(
                            text=text.strip(),
                            query_used=fq,
                            source_urls=fu_urls[:3],
                        ))

    # Dedupe learnings by text; keep first occurrence
    seen_texts: set = set()
    unique_learnings: List[WebLearning] = []
    for wl in all_learnings:
        t = wl.text.strip().lower()[:300]
        if t in seen_texts:
            continue
        seen_texts.add(t)
        unique_learnings.append(wl)
    all_sources = list(dict.fromkeys(s for s in all_sources if s))

    return WebResearchOutput(
        learnings=unique_learnings,
        sources=all_sources,
        queries_used=queries_used,
        stats={
            "total_learnings": len(unique_learnings),
            "total_sources": len(all_sources),
            "follow_ups_used": follow_ups_used,
        },
    )
