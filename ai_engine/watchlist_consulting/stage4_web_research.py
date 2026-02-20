"""
Stage 4: Web Research.
Input: UserIntent, ThemeOutput, watchlist payload.
Output: WebResearchOutput (learnings, sources, queries_used, stats).
Runs after Stage 3 (Theme miner). Optional: skipped when breadth=0 or SERPAPI_KEY not set.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pipeline_schemas import ThemeOutput, UserIntent, WebResearchOutput
from web_research import run_web_research_sync


def run_web_research(
    user_intent: UserIntent,
    theme_output: ThemeOutput,
    payload: Dict[str, Any],
    *,
    breadth: int = 3,
    depth: int = 2,
    num_results_initial: int = 5,
    num_results_followup: int = 3,
    max_follow_ups_per_query: int = 2,
    llm: Optional[Any] = None,
) -> WebResearchOutput:
    """
    Run web research stage: generate queries from intent/themes/tickers,
    search via SerpAPI, analyze results, optional follow-up depth, aggregate into WebResearchOutput.
    """
    return run_web_research_sync(
        user_intent,
        theme_output,
        payload,
        breadth=breadth,
        depth=depth,
        num_results_initial=num_results_initial,
        num_results_followup=num_results_followup,
        max_follow_ups_per_query=max_follow_ups_per_query,
        llm=llm,
    )
