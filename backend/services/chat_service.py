"""
Chat service: LLM-based stock market analyst chat with tool-calling.

Uses direct LLM.bind_tools() + manual tool execution loop for maximum
compatibility with Azure OpenAI (no AgentExecutor streaming issues).
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Generator, List

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load env from backend/.env and repo root .env
_backend_dir = Path(__file__).parent.parent
load_dotenv(dotenv_path=_backend_dir / ".env")
load_dotenv(dotenv_path=_backend_dir.parent / ".env")


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

def _tool_get_stock_quote(symbol: str) -> str:
    """Get current stock quote for a ticker symbol."""
    try:
        from ai_engine.tradingagents.agents.utils.core_stock_tools import get_stock_quote
        return get_stock_quote.invoke({"symbol": symbol.upper()})
    except Exception as e:
        return f"Error fetching quote for {symbol}: {e}"


def _tool_get_platform_reports(ticker: str) -> str:
    """Get FlowDeck AI analysis reports for a ticker."""
    try:
        from services.report_service import ReportService
        svc = ReportService()
        ticker_upper = ticker.strip().upper()
        latest_date = svc.get_latest_report_date(ticker_upper)
        if not latest_date:
            return f"No AI analysis reports found for {ticker_upper} on this platform."

        reports = svc.get_reports_with_scores(ticker_upper, latest_date)
        if not reports:
            return f"No report content found for {ticker_upper}."

        REPORT_LABELS = {
            "market_report": "Market Analysis",
            "fundamentals_report": "Fundamentals Analysis",
            "technical_report": "Technical Analysis",
            "news_report": "News Analysis",
            "sec_report": "SEC Analysis",
            "investment_plan": "Investment Plan",
            "trader_investment_plan": "Trader Plan",
            "final_trade_decision": "Final Decision",
        }

        lines = [f"# FlowDeck AI Reports for {ticker_upper} ({latest_date})", ""]

        # Recommendation summary
        tip = reports.get("trader_investment_plan") or {}
        ftd = reports.get("final_trade_decision") or {}
        rec = tip.get("recommendation") or ftd.get("recommendation")
        conf = tip.get("confidence") or ftd.get("confidence")
        if rec:
            conf_str = f" ({conf*100:.0f}% confidence)" if conf else ""
            lines.append(f"**Recommendation: {rec}{conf_str}**")

        # Return scenarios
        inv = reports.get("investment_plan") or {}
        exp = inv.get("expected_return_pct")
        bear = inv.get("bear_case_return_pct")
        bull = inv.get("bull_case_return_pct")
        if any(v is not None for v in [exp, bear, bull]):
            parts = []
            if exp is not None: parts.append(f"Expected: {exp:+.1f}%")
            if bear is not None: parts.append(f"Bear: {bear:+.1f}%")
            if bull is not None: parts.append(f"Bull: {bull:+.1f}%")
            lines.append("Return scenarios: " + " | ".join(parts))

        lines.append("")

        # Each report: label + score + key takeaways + truncated content
        REPORT_ORDER = ["final_trade_decision", "investment_plan", "trader_investment_plan",
                        "market_report", "fundamentals_report", "technical_report",
                        "news_report", "sec_report"]
        ordered = [k for k in REPORT_ORDER if k in reports] + [k for k in reports if k not in REPORT_ORDER]

        for key in ordered:
            data = reports.get(key)
            if not data:
                continue
            label = REPORT_LABELS.get(key, key.replace("_", " ").title())
            score = data.get("score")
            takeaways = data.get("key_takeaways") or []
            content = (data.get("content") or "").strip()

            lines.append(f"## {label}" + (f" (Score: {score}/10)" if score is not None else ""))

            # Key takeaways
            if takeaways:
                lines.append("**Key Takeaways:**")
                for t in takeaways:
                    lines.append(f"- {t}")

            # Researcher viewpoints (investment_plan)
            bull = data.get("bull_viewpoint") or []
            bear = data.get("bear_viewpoint") or []
            if bull:
                lines.append("**Bull Viewpoint:**")
                for p in bull:
                    lines.append(f"- {p}")
            if bear:
                lines.append("**Bear Viewpoint:**")
                for p in bear:
                    lines.append(f"- {p}")

            # Risk analyst viewpoints (final_trade_decision)
            risky = data.get("risky_viewpoint") or []
            neutral = data.get("neutral_viewpoint") or []
            safe = data.get("safe_viewpoint") or []
            if risky:
                lines.append("**Risky Analyst:**")
                for p in risky:
                    lines.append(f"- {p}")
            if neutral:
                lines.append("**Neutral Analyst:**")
                for p in neutral:
                    lines.append(f"- {p}")
            if safe:
                lines.append("**Safe Analyst:**")
                for p in safe:
                    lines.append(f"- {p}")

            # Report content (truncated to 2000 chars)
            if content:
                if len(content) > 2000:
                    content = content[:2000] + " [...]"
                lines.append(content)
            lines.append("")

        return "\n".join(lines)
    except Exception as e:
        logger.exception("get_platform_reports error for %s: %s", ticker, e)
        return f"Error fetching platform reports for {ticker}: {e}"


def _tool_get_news(ticker: str) -> str:
    """Get recent news for a ticker symbol."""
    try:
        from ai_engine.tradingagents.agents.utils.news_data_tools import get_news
        today = datetime.date.today()
        start = (today - datetime.timedelta(days=7)).isoformat()
        end = today.isoformat()
        return get_news.invoke({"ticker": ticker.upper(), "start_date": start, "end_date": end})
    except Exception as e:
        return f"Error fetching news for {ticker}: {e}"


def _tool_get_fundamentals(ticker: str) -> str:
    """Get fundamental financial data for a ticker symbol."""
    try:
        from ai_engine.tradingagents.agents.utils.fundamental_data_tools import get_fundamentals
        return get_fundamentals.invoke({"ticker": ticker.upper()})
    except Exception as e:
        return f"Error fetching fundamentals for {ticker}: {e}"


def _tool_get_balance_sheet(ticker: str) -> str:
    """Get balance sheet data for a ticker symbol."""
    try:
        from ai_engine.tradingagents.agents.utils.fundamental_data_tools import get_balance_sheet
        return get_balance_sheet.invoke({"ticker": ticker.upper()})
    except Exception as e:
        return f"Error fetching balance sheet for {ticker}: {e}"


def _tool_get_cashflow(ticker: str) -> str:
    """Get cash flow statement for a ticker symbol."""
    try:
        from ai_engine.tradingagents.agents.utils.fundamental_data_tools import get_cashflow
        return get_cashflow.invoke({"ticker": ticker.upper()})
    except Exception as e:
        return f"Error fetching cash flow for {ticker}: {e}"


def _tool_get_income_statement(ticker: str) -> str:
    """Get income statement for a ticker symbol."""
    try:
        from ai_engine.tradingagents.agents.utils.fundamental_data_tools import get_income_statement
        return get_income_statement.invoke({"ticker": ticker.upper()})
    except Exception as e:
        return f"Error fetching income statement for {ticker}: {e}"


def _tool_get_stock_data(ticker: str) -> str:
    """Get historical OHLCV price data for a ticker (last 30 days)."""
    try:
        from ai_engine.tradingagents.agents.utils.core_stock_tools import get_stock_data
        today = datetime.date.today()
        start = (today - datetime.timedelta(days=30)).isoformat()
        end = today.isoformat()
        return get_stock_data.invoke({"symbol": ticker.upper(), "start_date": start, "end_date": end})
    except Exception as e:
        return f"Error fetching stock data for {ticker}: {e}"


def _tool_get_indicators(ticker: str) -> str:
    """Get technical indicators (RSI, MACD, SMA, Bollinger Bands) for a ticker."""
    try:
        from ai_engine.tradingagents.agents.utils.technical_indicators_tools import get_indicators
        today = datetime.date.today().isoformat()
        return get_indicators.invoke({"ticker": ticker.upper(), "curr_date": today, "look_back_days": 30})
    except Exception as e:
        return f"Error fetching indicators for {ticker}: {e}"


def _tool_get_insider_transactions(ticker: str) -> str:
    """Get recent insider buy/sell transactions for a ticker symbol."""
    try:
        from ai_engine.tradingagents.agents.utils.news_data_tools import get_insider_transactions
        today = datetime.date.today().isoformat()
        return get_insider_transactions.invoke({"ticker": ticker.upper(), "curr_date": today})
    except Exception as e:
        return f"Error fetching insider transactions for {ticker}: {e}"


def _tool_get_insider_sentiment(ticker: str) -> str:
    """Get insider sentiment summary for a ticker symbol."""
    try:
        from ai_engine.tradingagents.agents.utils.news_data_tools import get_insider_sentiment
        today = datetime.date.today().isoformat()
        return get_insider_sentiment.invoke({"ticker": ticker.upper(), "curr_date": today})
    except Exception as e:
        return f"Error fetching insider sentiment for {ticker}: {e}"


def _tool_get_global_news() -> str:
    """Get current global market and macroeconomic news."""
    try:
        from ai_engine.tradingagents.agents.utils.news_data_tools import get_global_news
        today = datetime.date.today().isoformat()
        return get_global_news.invoke({"curr_date": today, "look_back_days": 7, "limit": 10})
    except Exception as e:
        return f"Error fetching global news: {e}"


# Tool registry: name -> (callable, description, parameters schema)
TOOLS = [
    {
        "name": "get_platform_reports",
        "description": (
            "ALWAYS call this first when the user asks about a stock's analysis, recommendation, outlook, "
            "investment thesis, bull/bear case, risk assessment, or any AI-generated insight. "
            "Retrieves FlowDeck's proprietary AI analysis reports from the platform database for a given ticker. "
            "Returns: BUY/SELL/HOLD recommendation with confidence score, expected/bull/bear return scenarios, "
            "and the full content of all available reports: Final Trade Decision (risk-adjusted), "
            "Investment Plan (bull vs bear researcher debate), Trader Plan, Market Analysis, "
            "Fundamentals Analysis, Technical Analysis, News Analysis, and SEC/Regulatory Analysis. "
            "Each report includes a quality score (0-10) and key takeaways."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA, NVDA"}
            },
            "required": ["ticker"],
        },
        "fn": _tool_get_platform_reports,
    },
    {
        "name": "get_stock_quote",
        "description": (
            "Get the real-time stock quote for a ticker: current price, daily change ($), "
            "daily change (%), bid/ask, day high/low, 52-week range, volume, and market status. "
            "Use when the user asks for the current price, today's performance, or live market data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
            },
            "required": ["symbol"],
        },
        "fn": _tool_get_stock_quote,
    },
    {
        "name": "get_stock_data",
        "description": (
            "Get historical OHLCV (Open, High, Low, Close, Volume) price data for a ticker over the last 30 days. "
            "Use when the user asks about price history, recent price movement, or wants to see a price trend."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
            },
            "required": ["ticker"],
        },
        "fn": _tool_get_stock_data,
    },
    {
        "name": "get_indicators",
        "description": (
            "Get technical analysis indicators for a ticker over the last 30 days: "
            "RSI (momentum/overbought-oversold), MACD (trend/momentum), SMA/EMA (moving averages), "
            "Bollinger Bands (volatility), ATR (average true range), VWMA (volume-weighted). "
            "Use when the user asks about technical analysis, chart patterns, momentum, or support/resistance."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
            },
            "required": ["ticker"],
        },
        "fn": _tool_get_indicators,
    },
    {
        "name": "get_fundamentals",
        "description": (
            "Get key fundamental financial metrics for a ticker: P/E ratio, forward P/E, EPS (trailing/forward), "
            "market cap, enterprise value, revenue, gross margin, profit margin, operating margin, EBITDA, "
            "dividend yield, beta, and sector/industry. "
            "Use when the user asks about valuation, profitability, or financial health."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
            },
            "required": ["ticker"],
        },
        "fn": _tool_get_fundamentals,
    },
    {
        "name": "get_balance_sheet",
        "description": (
            "Get the balance sheet for a ticker: total assets, total liabilities, shareholders equity, "
            "cash and equivalents, total debt, and working capital. "
            "Use when the user asks about financial strength, debt levels, or liquidity."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
            },
            "required": ["ticker"],
        },
        "fn": _tool_get_balance_sheet,
    },
    {
        "name": "get_cashflow",
        "description": (
            "Get the cash flow statement for a ticker: operating cash flow, free cash flow, "
            "capital expenditures, investing activities, and financing activities. "
            "Use when the user asks about cash generation, free cash flow, or capital allocation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
            },
            "required": ["ticker"],
        },
        "fn": _tool_get_cashflow,
    },
    {
        "name": "get_income_statement",
        "description": (
            "Get the income statement for a ticker: revenue, cost of goods sold, gross profit, "
            "operating income, net income, and EPS. "
            "Use when the user asks about revenue growth, earnings, or profitability trends."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
            },
            "required": ["ticker"],
        },
        "fn": _tool_get_income_statement,
    },
    {
        "name": "get_news",
        "description": (
            "Get recent news articles for a specific ticker from the last 7 days. "
            "Use when the user asks about recent news, events, announcements, or catalysts for a specific company."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
            },
            "required": ["ticker"],
        },
        "fn": _tool_get_news,
    },
    {
        "name": "get_global_news",
        "description": (
            "Get global market and macroeconomic news from the last 7 days (no ticker needed). "
            "Use when the user asks about market conditions, macro trends, Fed policy, interest rates, "
            "sector trends, or general market news not specific to one company."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "fn": lambda _="": _tool_get_global_news(),
    },
    {
        "name": "get_insider_transactions",
        "description": (
            "Get recent insider trading transactions for a ticker: who bought or sold, "
            "how many shares, at what price, and their role (CEO, CFO, Director, etc.). "
            "Use when the user asks about insider activity, insider buying/selling, or management confidence."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
            },
            "required": ["ticker"],
        },
        "fn": _tool_get_insider_transactions,
    },
    {
        "name": "get_insider_sentiment",
        "description": (
            "Get an aggregated insider sentiment score for a ticker: net insider buying vs selling trend, "
            "ratio of buyers to sellers, and overall sentiment direction. "
            "Use when the user asks about insider sentiment, whether insiders are bullish or bearish."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
            },
            "required": ["ticker"],
        },
        "fn": _tool_get_insider_sentiment,
    },
]

# OpenAI-format tool schemas for bind_tools
_TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
    for t in TOOLS
]

# Fast lookup: tool name -> callable
_TOOL_FN: Dict[str, Any] = {t["name"]: t["fn"] for t in TOOLS}


def _build_llm(streaming: bool = False):
    """Build and return the LLM for chat."""
    from ai_engine.llm_provider import get_llm, get_config_from_env
    config = get_config_from_env()
    provider = config.get("llm_provider", "openai").lower()

    if provider == "azure":
        from langchain_openai import AzureChatOpenAI
        from pydantic import SecretStr
        import os as _os
        azure_endpoint = _os.getenv("AZURE_OPENAI_ENDPOINT", "")
        azure_api_key = _os.getenv("AZURE_OPENAI_API_KEY", "")
        azure_api_version = _os.getenv("OPENAI_API_VERSION", "2024-08-01-preview")
        model = config.get("deep_think_llm") or "gpt-4o"
        return AzureChatOpenAI(
            azure_deployment=model,
            model=model,
            azure_endpoint=azure_endpoint,
            api_key=SecretStr(azure_api_key),
            api_version=azure_api_version,
            timeout=180,
            streaming=streaming,
        )
    else:
        return get_llm("deep", config, request_timeout=180)


class ChatService:
    """Service for running stock market chat via direct LLM + manual tool loop."""

    def __init__(self):
        self._llm = None
        self._llm_streaming = None

    def _get_llm(self):
        """Lazy-initialize the non-streaming LLM."""
        if self._llm is None:
            self._llm = _build_llm(streaming=False)
        return self._llm

    def _get_llm_streaming(self):
        """Lazy-initialize the streaming LLM."""
        if self._llm_streaming is None:
            self._llm_streaming = _build_llm(streaming=True)
        return self._llm_streaming

    def chat(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Run a chat turn with the LLM + tool-calling loop.

        Args:
            messages: List of {role: "user"|"assistant", content: str} dicts.

        Returns:
            dict with reply (str) and tokens_used (int).
        """
        if not messages:
            return {
                "reply": "Hello! I'm your FlowDeck Stock Market Analyst. Ask me anything about stocks, markets, or financial data.",
                "tokens_used": 1,
            }

        last_user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg["content"]
                break

        if not last_user_msg:
            return {"reply": "Please send a message.", "tokens_used": 1}

        today = datetime.date.today().isoformat()
        system_content = f"""You are FlowDeck's Stock Market Analyst AI — an expert in equity analysis, trading strategy, and financial markets. Today is {today}.

## Your Role
You help users understand stocks, markets, and investment opportunities using real-time data and FlowDeck's proprietary AI analysis. You are knowledgeable, precise, and data-driven.

## Tool Usage Rules
1. **ALWAYS call `get_platform_reports` first** when the user asks about a stock's analysis, recommendation, outlook, investment thesis, bull/bear case, risks, or any AI-generated insight. This is your primary source of truth.
2. Call `get_stock_quote` for current price and today's performance.
3. Call `get_indicators` for technical analysis (RSI, MACD, Bollinger Bands, etc.).
4. Call `get_fundamentals` for valuation metrics (P/E, EPS, margins, market cap).
5. Call `get_income_statement`, `get_balance_sheet`, or `get_cashflow` for detailed financial statements.
6. Call `get_news` for recent company-specific news and catalysts.
7. Call `get_global_news` for macro/market-wide news and trends.
8. Call `get_insider_transactions` or `get_insider_sentiment` for insider trading activity.
9. You may call multiple tools in sequence to build a comprehensive answer.

## Response Style
- Be concise and data-driven. Lead with the most important insight.
- Format numbers clearly: prices as $182.50, changes as +2.3%, large numbers as $2.1B or $450M.
- Use markdown formatting: **bold** for key metrics, bullet points for lists.
- When citing FlowDeck reports, reference the report type (e.g., "According to FlowDeck's Technical Analysis...").
- If data is unavailable, say so clearly and offer what you can provide.

## Disclaimer
This is for informational and educational purposes only. Not personalized investment advice. Always do your own research."""

        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage, ToolMessage

        lc_messages: List[BaseMessage] = [SystemMessage(content=system_content)]
        for msg in messages[-20:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            else:
                lc_messages.append(AIMessage(content=content))

        try:
            llm = self._get_llm()
            llm_with_tools = llm.bind_tools(_TOOL_SCHEMAS)  # type: ignore[attr-defined]

            tool_calls_made = 0
            max_tool_rounds = 5

            for _ in range(max_tool_rounds):
                response = llm_with_tools.invoke(lc_messages)

                # Check if the model wants to call tools
                tool_calls = getattr(response, "tool_calls", None)
                if not tool_calls:
                    # No tool calls — final answer
                    reply = response.content if hasattr(response, "content") else str(response)
                    return {"reply": reply, "tokens_used": max(1, 1 + tool_calls_made)}

                # Execute each tool call
                lc_messages.append(response)  # add assistant message with tool_calls
                for tc in tool_calls:
                    tool_name = tc.get("name") or tc.get("function", {}).get("name", "")
                    tool_args_raw = tc.get("args") or tc.get("function", {}).get("arguments", "{}")
                    tool_id = tc.get("id", tool_name)

                    if isinstance(tool_args_raw, str):
                        try:
                            tool_args = json.loads(tool_args_raw)
                        except Exception:
                            tool_args = {}
                    else:
                        tool_args = tool_args_raw or {}

                    fn = _TOOL_FN.get(tool_name)
                    if fn:
                        try:
                            # All our tools take a single string argument
                            arg_val = next(iter(tool_args.values()), "") if tool_args else ""
                            tool_result = fn(str(arg_val))
                        except Exception as e:
                            tool_result = f"Tool error: {e}"
                    else:
                        tool_result = f"Unknown tool: {tool_name}"

                    lc_messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_id))
                    tool_calls_made += 1

            # Max rounds reached — get final answer without tools
            final_response = llm.invoke(lc_messages)
            reply = final_response.content if hasattr(final_response, "content") else str(final_response)
            return {"reply": reply, "tokens_used": max(1, 1 + tool_calls_made)}

        except Exception as e:
            logger.exception("Chat LLM error: %s", e)
            return {
                "reply": f"I encountered an error while processing your request: {str(e)}. Please try again.",
                "tokens_used": 1,
            }

    def chat_stream(self, messages: List[Dict[str, str]]) -> Generator[str, None, None]:
        """
        Stream a chat turn: run the tool-calling loop (blocking), then stream
        the final LLM response token-by-token as SSE lines.

        Yields SSE-formatted strings:
          - ``data: {"type":"token","content":"..."}\\n\\n``  for each text chunk
          - ``data: {"type":"done","tokens_used":N}\\n\\n``   when finished
          - ``data: {"type":"error","content":"..."}\\n\\n``  on error
        """
        if not messages:
            yield 'data: {"type":"token","content":"Hello! I\'m your FlowDeck Stock Market Analyst. Ask me anything about stocks, markets, or financial data."}\n\n'
            yield 'data: {"type":"done","tokens_used":1}\n\n'
            return

        last_user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg["content"]
                break

        if not last_user_msg:
            yield 'data: {"type":"token","content":"Please send a message."}\n\n'
            yield 'data: {"type":"done","tokens_used":1}\n\n'
            return

        today = datetime.date.today().isoformat()
        system_content = f"""You are FlowDeck's Stock Market Analyst AI — an expert in equity analysis, trading strategy, and financial markets. Today is {today}.

## Your Role
You help users understand stocks, markets, and investment opportunities using real-time data and FlowDeck's proprietary AI analysis. You are knowledgeable, precise, and data-driven.

## Tool Usage Rules
1. **ALWAYS call `get_platform_reports` first** when the user asks about a stock's analysis, recommendation, outlook, investment thesis, bull/bear case, risks, or any AI-generated insight. This is your primary source of truth.
2. Call `get_stock_quote` for current price and today's performance.
3. Call `get_indicators` for technical analysis (RSI, MACD, Bollinger Bands, etc.).
4. Call `get_fundamentals` for valuation metrics (P/E, EPS, margins, market cap).
5. Call `get_income_statement`, `get_balance_sheet`, or `get_cashflow` for detailed financial statements.
6. Call `get_news` for recent company-specific news and catalysts.
7. Call `get_global_news` for macro/market-wide news and trends.
8. Call `get_insider_transactions` or `get_insider_sentiment` for insider trading activity.
9. You may call multiple tools in sequence to build a comprehensive answer.

## Response Style
- Be concise and data-driven. Lead with the most important insight.
- Format numbers clearly: prices as $182.50, changes as +2.3%, large numbers as $2.1B or $450M.
- Use markdown formatting: **bold** for key metrics, bullet points for lists.
- When citing FlowDeck reports, reference the report type (e.g., "According to FlowDeck's Technical Analysis...").
- If data is unavailable, say so clearly and offer what you can provide.

## Disclaimer
This is for informational and educational purposes only. Not personalized investment advice. Always do your own research."""

        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage, ToolMessage

        lc_messages: List[BaseMessage] = [SystemMessage(content=system_content)]
        for msg in messages[-20:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            else:
                lc_messages.append(AIMessage(content=content))

        try:
            llm = self._get_llm()
            llm_with_tools = llm.bind_tools(_TOOL_SCHEMAS)  # type: ignore[attr-defined]
            llm_stream = self._get_llm_streaming()

            tool_calls_made = 0
            max_tool_rounds = 5

            # Human-readable labels for tool progress messages
            _TOOL_THINKING_LABELS = {
                "get_platform_reports": "Fetching AI analysis reports",
                "get_stock_quote": "Fetching live stock quote",
                "get_stock_data": "Fetching price history",
                "get_indicators": "Fetching technical indicators",
                "get_fundamentals": "Fetching fundamental data",
                "get_balance_sheet": "Fetching balance sheet",
                "get_cashflow": "Fetching cash flow statement",
                "get_income_statement": "Fetching income statement",
                "get_news": "Fetching recent news",
                "get_global_news": "Fetching global market news",
                "get_insider_transactions": "Fetching insider transactions",
                "get_insider_sentiment": "Fetching insider sentiment",
            }

            # --- Tool-calling loop (non-streaming) ---
            for _ in range(max_tool_rounds):
                response = llm_with_tools.invoke(lc_messages)

                tool_calls = getattr(response, "tool_calls", None)
                if not tool_calls:
                    # No more tool calls — re-invoke with the streaming LLM for real token-by-token output
                    for chunk in llm_stream.stream(lc_messages):
                        raw = chunk.content if hasattr(chunk, "content") else ""
                        delta = raw if isinstance(raw, str) else ""
                        if delta:
                            yield f"data: {json.dumps({'type': 'token', 'content': delta})}\n\n"
                    yield f"data: {json.dumps({'type': 'done', 'tokens_used': max(1, 1 + tool_calls_made), 'tools_called': tool_calls_made})}\n\n"
                    return

                # Execute tool calls
                lc_messages.append(response)
                for tc in tool_calls:
                    tool_name = tc.get("name") or tc.get("function", {}).get("name", "")
                    tool_args_raw = tc.get("args") or tc.get("function", {}).get("arguments", "{}")
                    tool_id = tc.get("id", tool_name)

                    # Emit a thinking event so the frontend can show progress
                    thinking_label = _TOOL_THINKING_LABELS.get(tool_name, f"Running {tool_name.replace('_', ' ')}")
                    yield f"data: {json.dumps({'type': 'thinking', 'content': thinking_label})}\n\n"

                    if isinstance(tool_args_raw, str):
                        try:
                            tool_args = json.loads(tool_args_raw)
                        except Exception:
                            tool_args = {}
                    else:
                        tool_args = tool_args_raw or {}

                    fn = _TOOL_FN.get(tool_name)
                    if fn:
                        try:
                            arg_val = next(iter(tool_args.values()), "") if tool_args else ""
                            tool_result = fn(str(arg_val))
                        except Exception as e:
                            tool_result = f"Tool error: {e}"
                    else:
                        tool_result = f"Unknown tool: {tool_name}"

                    lc_messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_id))
                    tool_calls_made += 1

            # Max rounds reached — stream final answer without tools
            for chunk in llm_stream.stream(lc_messages):
                raw = chunk.content if hasattr(chunk, "content") else ""
                delta = raw if isinstance(raw, str) else ""
                if delta:
                    yield f"data: {json.dumps({'type': 'token', 'content': delta})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'tokens_used': max(1, 1 + tool_calls_made), 'tools_called': tool_calls_made})}\n\n"

        except Exception as e:
            logger.exception("Chat stream LLM error: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'content': f'I encountered an error: {str(e)}. Please try again.'})}\n\n"



# Module-level singleton
_chat_service: ChatService | None = None


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service

# Made with Bob
