"""
LangChain @tool wrappers for all FlowDeck agent tools.

LangGraph's ToolNode requires standard LangChain tools (decorated with @tool
or subclassing BaseTool from langchain_core).  This module wraps the existing
FlowDeck BaseTool implementations so we don't duplicate any business logic.

The ExecutionContext (user_id, db) is injected via LangGraph's RunnableConfig
using the ``configurable`` key — this is the standard LangGraph pattern for
passing request-scoped state to tools.

Usage:
    from ai_engine.agent.lc_tools import get_all_lc_tools
    tools = get_all_lc_tools(user_id=42, db=session)
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, List, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool

logger = logging.getLogger(__name__)

# Type alias: Optional RunnableConfig injected by LangGraph's ToolNode.
# InjectedToolArg tells LangGraph NOT to expose this as an LLM parameter.
# Optional satisfies strict type checkers (basedpyright).
_InjectedConfig = Annotated[Optional[RunnableConfig], InjectedToolArg]


def _ctx_from_config(config: Optional[RunnableConfig]) -> Any:
    """Extract ExecutionContext from LangGraph RunnableConfig configurable dict."""
    from ai_engine.agent.tool import ExecutionContext
    if config is None:
        return ExecutionContext()
    cfg = (config or {}).get("configurable", {})
    return cfg.get("execution_context") or ExecutionContext()


# ---------------------------------------------------------------------------
# Market data tools
# ---------------------------------------------------------------------------

@tool
def get_stock_quote(symbol: str, config: _InjectedConfig = None) -> str:
    """Get the real-time stock quote for a ticker: current price, daily change ($),
    daily change (%), bid/ask, day high/low, 52-week range, volume, and market status.
    Use when the user asks for the current price, today's performance, or live market data."""
    from ai_engine.agent.tools.stock_quote import StockQuoteTool
    ctx = _ctx_from_config(config)
    return StockQuoteTool().execute(ctx, symbol=symbol).to_str()


@tool
def get_stock_data(ticker: str, config: _InjectedConfig = None) -> str:
    """Get recent OHLCV price data and basic statistics for a stock ticker (last 30 days).
    Use for short-term price history, recent trading ranges, or quick technical context."""
    from ai_engine.agent.tools.market_data import StockDataTool
    ctx = _ctx_from_config(config)
    return StockDataTool().execute(ctx, ticker=ticker).to_str()


@tool
def get_historical_prices(
    ticker: str,
    start_date: str,
    end_date: str,
    config: _InjectedConfig = None,
) -> str:
    """Fetch real daily OHLCV price data for a single ticker over a custom date range (up to 5 years).
    Returns CSV with Date, Open, High, Low, Close, Volume columns.
    Use — NOT simulation — whenever the user asks about year-to-date performance, 1-year returns,
    multi-year price history, historical volatility, or any analysis requiring more than 30 days
    of price data for one ticker. Always fetch real data first, then pass the CSV to execute_python."""
    from ai_engine.agent.tools.market_data import HistoricalPricesTool
    ctx = _ctx_from_config(config)
    return HistoricalPricesTool().execute(ctx, ticker=ticker, start_date=start_date, end_date=end_date).to_str()


@tool
def get_multi_historical_prices(
    tickers: List[str],
    start_date: str,
    end_date: str,
    config: _InjectedConfig = None,
) -> str:
    """Fetch real closing prices for multiple tickers at once over a date range.
    Returns JSON with per-ticker CSV data. Use whenever the user asks about comparing two or more
    markets/stocks over a period, top gainers/losers in a portfolio, normalized performance charts,
    or any multi-ticker return calculation. Far more efficient than calling get_historical_prices
    repeatedly. After fetching, pass the JSON to execute_python for calculations."""
    from ai_engine.agent.tools.multi_market_data import MultiHistoricalPricesTool
    ctx = _ctx_from_config(config)
    return MultiHistoricalPricesTool().execute(ctx, tickers=tickers, start_date=start_date, end_date=end_date).to_str()


@tool
def get_indicators(ticker: str, config: _InjectedConfig = None) -> str:
    """Get all technical indicators for a stock in one call: RSI, MACD, Bollinger Bands (middle/upper/lower),
    50 SMA, 200 SMA, 10 EMA, ATR, VWMA, MFI. Pass only the ticker symbol — do NOT pass an 'indicator' argument.
    Use for technical analysis, overbought/oversold conditions, trend direction, or momentum assessment."""
    from ai_engine.agent.tools.market_data import IndicatorsTool
    ctx = _ctx_from_config(config)
    return IndicatorsTool().execute(ctx, ticker=ticker).to_str()


@tool
def get_specific_indicator(ticker: str, indicator: str, config: _InjectedConfig = None) -> str:
    """Get a specific technical indicator for a stock. Use when you need only one indicator
    instead of all indicators. Available indicators: rsi, macd, macds, macdh, boll, boll_ub,
    boll_lb, close_50_sma, close_200_sma, close_10_ema, atr, vwma, mfi.
    More efficient than get_indicators when analyzing a specific technical signal."""
    from ai_engine.agent.tools.market_data import SpecificIndicatorTool
    ctx = _ctx_from_config(config)
    return SpecificIndicatorTool().execute(ctx, ticker=ticker, indicator=indicator).to_str()


# ---------------------------------------------------------------------------
# Fundamental / financial statement tools
# ---------------------------------------------------------------------------

@tool
def get_fundamentals(ticker: str, config: _InjectedConfig = None) -> str:
    """Get key fundamental valuation metrics for a stock: P/E ratio, EPS, market cap, revenue,
    profit margins, dividend yield, beta, and analyst price targets.
    Use for valuation analysis, comparing stocks, or assessing financial health."""
    from ai_engine.agent.tools.financials import FundamentalsTool
    ctx = _ctx_from_config(config)
    return FundamentalsTool().execute(ctx, ticker=ticker).to_str()


@tool
def get_income_statement(ticker: str, config: _InjectedConfig = None) -> str:
    """Get the annual income statement for a stock: revenue, gross profit, operating income,
    net income, EPS, and year-over-year growth rates.
    Use for detailed revenue/profitability analysis or earnings trend assessment."""
    from ai_engine.agent.tools.financials import IncomeStatementTool
    ctx = _ctx_from_config(config)
    return IncomeStatementTool().execute(ctx, ticker=ticker).to_str()


@tool
def get_balance_sheet(ticker: str, config: _InjectedConfig = None) -> str:
    """Get the annual balance sheet for a stock: total assets, liabilities, equity,
    cash, debt levels, and key solvency ratios.
    Use for financial strength analysis, debt assessment, or liquidity evaluation."""
    from ai_engine.agent.tools.financials import BalanceSheetTool
    ctx = _ctx_from_config(config)
    return BalanceSheetTool().execute(ctx, ticker=ticker).to_str()


@tool
def get_cashflow(ticker: str, config: _InjectedConfig = None) -> str:
    """Get the annual cash flow statement for a stock: operating cash flow, free cash flow,
    capital expenditures, and financing activities.
    Use for cash generation analysis, FCF yield, or capital allocation assessment."""
    from ai_engine.agent.tools.financials import CashflowTool
    ctx = _ctx_from_config(config)
    return CashflowTool().execute(ctx, ticker=ticker).to_str()


# ---------------------------------------------------------------------------
# Platform reports
# ---------------------------------------------------------------------------

@tool
def get_platform_reports(ticker: str, config: _InjectedConfig = None) -> str:
    """Get FlowDeck's proprietary AI analysis reports for a stock: the latest BUY/SELL/HOLD
    recommendation with confidence score, bull/bear case, risk factors, return scenarios,
    technical analysis summary, and fundamental analysis summary.
    ALWAYS call this first when the user asks about a stock's analysis, recommendation,
    outlook, investment thesis, or any AI-generated insight. This is the primary source of truth."""
    from ai_engine.agent.tools.platform_reports import PlatformReportsTool
    ctx = _ctx_from_config(config)
    return PlatformReportsTool().execute(ctx, ticker=ticker).to_str()


@tool
def get_historical_report_dates(ticker: str, config: _InjectedConfig = None) -> str:
    """Get the list of dates for which FlowDeck AI reports are available for a stock.
    Use when the user asks about historical recommendations, past analysis, or report history."""
    from ai_engine.agent.tools.platform_reports import HistoricalReportDatesTool
    ctx = _ctx_from_config(config)
    return HistoricalReportDatesTool().execute(ctx, ticker=ticker).to_str()


# ---------------------------------------------------------------------------
# News tools
# ---------------------------------------------------------------------------

@tool
def get_news(ticker: str, config: _InjectedConfig = None) -> str:
    """Get recent news articles for a specific stock (last 7 days): headlines, sources,
    summaries, and sentiment signals.
    Use for company-specific news, earnings reactions, product launches, or regulatory events."""
    from ai_engine.agent.tools.news import NewsTool
    ctx = _ctx_from_config(config)
    return NewsTool().execute(ctx, ticker=ticker).to_str()


@tool
def get_global_news(query: str = "stock market", config: _InjectedConfig = None) -> str:
    """Get macro/market-wide news and trends: Fed decisions, economic data releases,
    sector rotations, geopolitical events, and broad market sentiment.
    Use for macro context, market-wide trends, or when the user asks about the overall market."""
    from ai_engine.agent.tools.news import GlobalNewsTool
    ctx = _ctx_from_config(config)
    return GlobalNewsTool().execute(ctx, query=query).to_str()


# ---------------------------------------------------------------------------
# Insider trading tools
# ---------------------------------------------------------------------------

@tool
def get_insider_transactions(ticker: str, config: _InjectedConfig = None) -> str:
    """Get recent insider buying and selling transactions for a stock: executive names,
    transaction types, share counts, prices, and dates.
    Use when the user asks about insider activity, management confidence, or insider buying/selling."""
    from ai_engine.agent.tools.insider import InsiderTransactionsTool
    ctx = _ctx_from_config(config)
    return InsiderTransactionsTool().execute(ctx, ticker=ticker).to_str()


@tool
def get_insider_sentiment(ticker: str, config: _InjectedConfig = None) -> str:
    """Get aggregated insider sentiment score for a stock based on recent insider transactions.
    Returns a bullish/bearish/neutral signal with supporting data.
    Use for a quick read on insider conviction or to complement fundamental analysis."""
    from ai_engine.agent.tools.insider import InsiderSentimentTool
    ctx = _ctx_from_config(config)
    return InsiderSentimentTool().execute(ctx, ticker=ticker).to_str()


# ---------------------------------------------------------------------------
# Web search
# ---------------------------------------------------------------------------

@tool
def web_search(query: str, config: _InjectedConfig = None) -> str:
    """Search the web for breaking news, recent earnings, analyst upgrades/downgrades,
    regulatory filings, macroeconomic data releases, or any information not covered by
    the other tools. Use for general financial questions or when you need the latest web information."""
    from ai_engine.agent.tools.web_search import WebSearchTool
    ctx = _ctx_from_config(config)
    return WebSearchTool().execute(ctx, query=query).to_str()


# ---------------------------------------------------------------------------
# Code execution
# ---------------------------------------------------------------------------

@tool
def execute_python(code: str, config: _InjectedConfig = None) -> str:
    """Execute Python code for calculations, financial modelling, statistical analysis,
    or data transformations where code gives a more precise answer than reasoning alone.
    Always use print() to output results. When working with price data from get_historical_prices,
    parse the CSV using the csv or io module (pandas is also available).
    When working with data from get_multi_historical_prices, parse the JSON using the json module.
    To produce a chart, print a line starting with CHART_JSON: followed by the chart spec JSON."""
    from ai_engine.agent.tools.execute_python import ExecutePythonTool
    ctx = _ctx_from_config(config)
    return ExecutePythonTool().execute(ctx, code=code).to_str()


# ---------------------------------------------------------------------------
# User-context tools (created per-request with bound user_id + db)
# ---------------------------------------------------------------------------

def make_user_lc_tools(user_id: int, db: Any) -> list:
    """
    Create LangChain @tool wrappers for user-context tools.
    These are created per-request because they are bound to a specific user + db session.
    """

    @tool
    def get_user_context() -> str:
        """Get the current user's profile information: their email, display name,
        token balance, account type, and member-since date.
        Use when the user asks about their account, profile, token balance, or who they are."""
        from ai_engine.agent.tools.user_context import UserContextTool
        from ai_engine.agent.tool import ExecutionContext
        ctx = ExecutionContext(user_id=user_id, db=db)
        return UserContextTool(user_id=user_id, db=db).execute(ctx).to_str()

    @tool
    def get_user_subscriptions() -> str:
        """Get the list of stock tickers the current user is subscribed to on FlowDeck,
        including subscription dates and email-update preferences.
        Use when the user asks about their watchlist, subscriptions, followed stocks, or portfolio tickers."""
        from ai_engine.agent.tools.user_context import UserSubscriptionsTool
        from ai_engine.agent.tool import ExecutionContext
        ctx = ExecutionContext(user_id=user_id, db=db)
        return UserSubscriptionsTool(user_id=user_id, db=db).execute(ctx).to_str()

    @tool
    def get_portfolio_overview() -> str:
        """Get a full portfolio overview for the current user: live stock quotes AND the latest
        FlowDeck AI recommendation (BUY/SELL/HOLD with confidence and return scenarios)
        for every stock they are subscribed to.
        Use when the user asks about their portfolio, how their stocks are doing,
        portfolio performance, or wants a summary of all their subscribed stocks."""
        from ai_engine.agent.tools.user_context import PortfolioOverviewTool
        from ai_engine.agent.tool import ExecutionContext
        ctx = ExecutionContext(user_id=user_id, db=db)
        return PortfolioOverviewTool(user_id=user_id, db=db).execute(ctx).to_str()

    return [get_user_context, get_user_subscriptions, get_portfolio_overview]


# ---------------------------------------------------------------------------
# Convenience aggregators
# ---------------------------------------------------------------------------

# All tools that are always available (no user context required)
ALL_LC_TOOLS = [
    get_stock_quote,
    get_stock_data,
    get_historical_prices,
    get_multi_historical_prices,
    get_indicators,
    get_specific_indicator,
    get_fundamentals,
    get_income_statement,
    get_balance_sheet,
    get_cashflow,
    get_platform_reports,
    get_historical_report_dates,
    get_news,
    get_global_news,
    get_insider_transactions,
    get_insider_sentiment,
    web_search,
    execute_python,
]


def get_all_lc_tools(user_id: Optional[int] = None, db: Any = None) -> list:
    """
    Return the full list of LangChain tools for a request.

    If user_id and db are provided, user-context tools are appended.
    """
    tools = list(ALL_LC_TOOLS)
    if user_id is not None and db is not None:
        tools.extend(make_user_lc_tools(user_id, db))
    return tools

# Made with Bob