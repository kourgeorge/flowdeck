"""
Portfolio Deep Research: evidence-backed multi-step research for a set of tickers.

Uses planner, retrieval (data tools + SerpAPI + existing reports), synthesis,
and report delivery with fast vs deep model routing. Final report includes
figures (Vega-Lite) and HTML output.

API keys (SERPAPI_KEY, LLM provider keys, INFO_SERVICE_URL) are read from backend/.env
when this package is imported.
"""

from pathlib import Path

# Load backend/.env so API keys (SERPAPI_KEY, Azure/OpenAI, INFO_SERVICE_URL) are available
def _load_backend_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    _repo_root = Path(__file__).resolve().parent.parent.parent
    load_dotenv(_repo_root / "backend" / ".env")
    load_dotenv(_repo_root / ".env")


_load_backend_env()

from .config import PortfolioDeepResearchConfig
from .state import (
    Claim,
    ResearchState,
)
from .tools import get_all_tools, get_latest_reports, serpapi_search

try:
    from .graph import portfolio_research_graph
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(
        "portfolio_research_graph could not be loaded: %s. Install optional deps (e.g. langchain) if needed.",
        e,
    )
    portfolio_research_graph = None  # type: ignore[assignment]

__all__ = [
    "ResearchState",
    "Claim",
    "PortfolioDeepResearchConfig",
    "get_all_tools",
    "get_latest_reports",
    "serpapi_search",
    "portfolio_research_graph",
]
