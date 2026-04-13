"""
Standalone Stocks Discovery: digest-style context + deterministic candidates + LLM markdown report.

Lives outside ``ai_engine.briefing_agent``. The Brief page calls this via ``GET /api/digest?agent=stocks_discovery``.
"""

from .runner import StocksDiscoveryRunResult, run_stocks_discovery

__all__ = [
    "run_stocks_discovery",
    "StocksDiscoveryRunResult",
]
