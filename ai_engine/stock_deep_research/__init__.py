"""
Stock Deep Research — multi-agent system for comprehensive company/equity research.

Separate from the trading agent: produces deep research reports (industry, competition,
SEC, market share, legal, AI/ESG) with web search and optional SEC/EDGAR integration.
Inspired by Open Deep Research (LangChain) but specialized for stocks.
"""

from .graph import stock_researcher_graph

__all__ = ["stock_researcher_graph"]
