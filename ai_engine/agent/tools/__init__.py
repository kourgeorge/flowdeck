"""
Hardcoded tool implementations for the FlowDeck agent.

Each tool wraps an existing backend/ai_engine function as a BaseTool subclass.
Import ALL_TOOLS to get the full list ready for ToolRegistry.register_many().
"""

from ai_engine.agent.tools.stock_quote import StockQuoteTool
from ai_engine.agent.tools.platform_reports import PlatformReportsTool, HistoricalReportDatesTool
from ai_engine.agent.tools.market_data import StockDataTool, HistoricalPricesTool, IndicatorsTool
from ai_engine.agent.tools.multi_market_data import MultiHistoricalPricesTool
from ai_engine.agent.tools.financials import (
    FundamentalsTool,
    BalanceSheetTool,
    CashflowTool,
    IncomeStatementTool,
)
from ai_engine.agent.tools.news import NewsTool, GlobalNewsTool
from ai_engine.agent.tools.insider import InsiderTransactionsTool, InsiderSentimentTool
from ai_engine.agent.tools.web_search import WebSearchTool
from ai_engine.agent.tools.execute_python import ExecutePythonTool

# All tools that are always available (no user context required)
ALL_TOOLS = [
    StockQuoteTool(),
    PlatformReportsTool(),
    HistoricalReportDatesTool(),
    StockDataTool(),
    HistoricalPricesTool(),
    MultiHistoricalPricesTool(),
    IndicatorsTool(),
    FundamentalsTool(),
    BalanceSheetTool(),
    CashflowTool(),
    IncomeStatementTool(),
    NewsTool(),
    GlobalNewsTool(),
    InsiderTransactionsTool(),
    InsiderSentimentTool(),
    WebSearchTool(),
    ExecutePythonTool(),
]

__all__ = [
    "StockQuoteTool",
    "PlatformReportsTool",
    "HistoricalReportDatesTool",
    "StockDataTool",
    "HistoricalPricesTool",
    "MultiHistoricalPricesTool",
    "IndicatorsTool",
    "FundamentalsTool",
    "BalanceSheetTool",
    "CashflowTool",
    "IncomeStatementTool",
    "NewsTool",
    "GlobalNewsTool",
    "InsiderTransactionsTool",
    "InsiderSentimentTool",
    "WebSearchTool",
    "ExecutePythonTool",
    "ALL_TOOLS",
]

# Made with Bob
