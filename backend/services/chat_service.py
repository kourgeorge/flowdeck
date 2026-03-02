"""
Chat service: LLM-based stock market analyst chat with tool-calling.

Delegates to the FlowDeckAgent LangGraph runtime (ai_engine/agent/graph.py) which manages:
  - 17 LangChain tools (stock data, financials, news, web search, code execution)
  - 4 skills (deep dive, portfolio health, stock comparison, portfolio performance)
  - LangGraph ReAct tool-calling loop with ToolNode
  - SSE streaming with thinking/tool_call/token/done events
"""

from __future__ import annotations

import datetime
import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional

if TYPE_CHECKING:
    from ai_engine.agent.graph import FlowDeckAgent

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load env from backend/.env and repo root .env
_backend_dir = Path(__file__).parent.parent
load_dotenv(dotenv_path=_backend_dir / ".env")
load_dotenv(dotenv_path=_backend_dir.parent / ".env")


# ---------------------------------------------------------------------------
# Chart extraction helper
# ---------------------------------------------------------------------------

def _extract_chart_specs(text: str) -> tuple[list[dict], str]:
    """
    Scan text for ``CHART_JSON:`` markers and extract chart specs.

    Handles two forms:
      1. Bare line:  ``CHART_JSON:{...}``
      2. Code-fenced: a line inside a ``` block that starts with CHART_JSON:

    Returns:
        (chart_specs, cleaned_text) where chart_specs is a list of parsed
        chart dicts and cleaned_text has the CHART_JSON lines (and any
        surrounding empty code-fence lines) removed.
    """
    charts: list[dict] = []

    def _replace_bare(m: re.Match) -> str:
        payload = m.group(1).strip()
        try:
            spec = json.loads(payload)
            charts.append(spec)
            return ""
        except Exception:
            return m.group(0)

    cleaned = re.sub(r"(?m)^[ \t]*CHART_JSON:(.+)$", _replace_bare, text)
    cleaned = re.sub(r"(?m)^```[^\n]*\n(\s*\n)*```\n?", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return charts, cleaned


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

def _build_llm():
    """Build and return the LLM for chat using the centralized llm_provider."""
    from ai_engine.llm_provider import get_llm, get_config_from_env
    config = get_config_from_env()
    return get_llm("deep", config, request_timeout=180)


# ---------------------------------------------------------------------------
# System prompt builder (shared by chat + chat_stream)
# ---------------------------------------------------------------------------

def _build_system_prompt(
    user_id: Optional[int],
    db: Optional[Any],
    context: Optional[Dict[str, Any]],
) -> str:
    """Build the FlowDeck system prompt for a given request."""
    today = datetime.date.today().isoformat()
    has_user_ctx = user_id is not None and db is not None

    user_ctx_section = """
12. Call `get_user_context` to retrieve the current user's profile (email, name, token balance, member since).
13. Call `get_user_subscriptions` to see which stocks the user is subscribed/watching on FlowDeck.
14. Call `get_portfolio_overview` to get live quotes AND AI recommendations for ALL of the user's subscribed stocks at once — use this when the user asks about their portfolio or how their stocks are doing.""" if has_user_ctx else ""

    watchlist_tickers: List[str] = (context or {}).get("tickers", [])
    watchlist_section = ""
    if watchlist_tickers:
        tickers_str = ", ".join(watchlist_tickers)
        watchlist_section = f"""

## User's Current Watchlist
The user is currently viewing the Vibe Trading page with the following tickers in their list: **{tickers_str}**
- When the user says "my stocks", "my list", "these stocks", or asks about their watchlist without specifying tickers, they are referring to these tickers.
- When asked for a comparison, overview, or analysis of their portfolio/watchlist, cover ALL of these tickers: {tickers_str}
- You may proactively mention relevant insights across all watchlist tickers when appropriate."""

    return f"""You are FlowDeck's Stock Market Analyst AI — an expert in equity analysis, trading strategy, and financial markets. Today is {today}.

## Your Role
You help users understand stocks, markets, and investment opportunities using real-time data and FlowDeck's proprietary AI analysis. You are knowledgeable, precise, and data-driven.

## ⚠️ CRITICAL: NEVER Simulate or Estimate Data
**You MUST NEVER fabricate, simulate, estimate, or hallucinate financial data.**
- If the user asks for price performance, returns, or comparisons — you MUST call the appropriate tool to fetch REAL data first.
- Do NOT say "here are simulated results" or "based on typical performance" or provide example numbers.
- Do NOT provide percentage returns, price changes, or rankings without first calling a data tool.
- If a tool call fails or returns no data, say so clearly — do NOT substitute with made-up numbers.
- **Every number you present must come from a tool call result, not from your training data.**

## Ticker Symbol Convention
Always use **Yahoo Finance ticker symbols** when calling any tool that accepts a ticker (e.g. `AAPL`, `MSFT`, `BRK-B`, `BTC-USD`, `^GSPC`). If the user provides a company name or an alternative symbol, resolve it to the correct Yahoo Finance ticker before making tool calls.

**Common index/market tickers:**
- US S&P 500: `SPY` (ETF) or `^GSPC` (index)
- US Nasdaq: `QQQ` (ETF) or `^IXIC` (index)
- Israeli TA-35: `TA35.TA`
- Israeli TA-125: `TA125.TA`

## Tool Usage Rules
1. **ALWAYS call `get_platform_reports` first** when the user asks about a stock's analysis, recommendation, outlook, investment thesis, bull/bear case, risks, or any AI-generated insight. This is your primary source of truth.
2. Call `get_stock_quote` for current price and today's performance.
3. Call `get_indicators` for technical analysis (RSI, MACD, Bollinger Bands, etc.).
4. Call `get_fundamentals` for valuation metrics (P/E, EPS, margins, market cap).
5. Call `get_income_statement`, `get_balance_sheet`, or `get_cashflow` for detailed financial statements.
6. Call `get_news` for recent company-specific news and catalysts.
7. Call `get_global_news` for macro/market-wide news and trends.
8. Call `get_insider_transactions` or `get_insider_sentiment` for insider trading activity.
9. Call `web_search` to find breaking news, recent earnings, analyst upgrades/downgrades, regulatory filings, macroeconomic data releases, or any information not covered by the other tools. Use it for general financial questions or when you need the latest web information.
10. Call `get_historical_prices` to fetch real daily OHLCV price data for a **single ticker** over a custom date range (up to 5 years). Use this — NOT simulation — whenever the user asks about year-to-date performance, 1-year returns, multi-year price history, historical volatility, or any analysis requiring more than 30 days of price data for one ticker. Always fetch real data first, then pass the CSV to `execute_python` for calculations.
11. **Call `get_multi_historical_prices`** to fetch real closing prices for **multiple tickers at once** — use this whenever the user asks about: comparing two or more markets/stocks over a period (e.g. US vs Israeli market), top gainers/losers in a portfolio, normalized performance charts, or any multi-ticker return calculation. This is far more efficient than calling `get_historical_prices` repeatedly. After fetching, pass the JSON to `execute_python` for calculations and chart generation.
12. Call `execute_python` to run calculations, financial modelling, statistical analysis, or data transformations where code gives a more precise answer than reasoning alone. Always use print() to output results. When working with price data from `get_historical_prices`, parse the CSV using the `csv` or `io` module (pandas is also available). When working with data from `get_multi_historical_prices`, parse the JSON using the `json` module.
13. You may call multiple tools in sequence to build a comprehensive answer.{user_ctx_section}{watchlist_section}

## Producing Charts
When the user asks for a chart, graph, or visual, include a chart spec **directly in your reply** on its own line using this exact format (one line, no line breaks inside the JSON, no code fences around it):

CHART_JSON:{{"title":"...","type":"line|bar|area|scatter","xKey":"...","yKeys":["..."],"data":[{{"xKey_value":"...","yKey_value":0}}],"colors":["#60a5fa"]}}

Schema:
- `title` (string): chart title shown above the chart
- `type` (string): one of `line`, `bar`, `area`, `scatter`
- `xKey` (string): the key in each data object used for the X axis
- `yKeys` (array of strings): one or more keys used for Y series (one per series)
- `data` (array of objects): each object has the xKey field plus all yKey fields as numbers
- `colors` (optional array of hex strings): one colour per yKey series

Rules:
- Output the CHART_JSON line **bare** — not inside a code block, not wrapped in backticks.
- You may write explanatory text before or after the CHART_JSON line.
- When you already have the data (e.g. from get_historical_prices), output CHART_JSON directly — do NOT call execute_python just to produce a chart.
- When you need to compute derived data first (e.g. rolling averages, correlations), call execute_python and have it print the CHART_JSON line.

Example — monthly price comparison:
CHART_JSON:{{"title":"META vs IBM (1Y)","type":"line","xKey":"date","yKeys":["META","IBM"],"data":[{{"date":"2025-03","META":650,"IBM":245}},{{"date":"2025-04","META":670,"IBM":250}}],"colors":["#60a5fa","#f97316"]}}

## Execution Style
- **Execute tool calls IMMEDIATELY without announcing your intent first.**
- Do NOT say "I'll fetch...", "Let me get...", "I'll retrieve...", or "One moment while I..." before calling tools.
- Call the necessary tools directly, then present the results.
- Provide context and explanations AFTER you have the data, not before.
- Exception: If a task requires multiple complex steps (5+), you may briefly outline the approach, but still execute the first step immediately.

## Response Style
- Be concise and data-driven. Lead with the most important insight.
- Format numbers clearly: prices as $182.50, changes as +2.3%, large numbers as $2.1B or $450M.
- Use markdown formatting: **bold** for key metrics, bullet points for lists.
- When citing FlowDeck reports, reference the report type (e.g., "According to FlowDeck's Technical Analysis...").
- If data is unavailable, say so clearly and offer what you can provide.

## Disclaimer
This is for informational and educational purposes only. Not personalized investment advice. Always do your own research."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _last_user_message(messages: List[Dict[str, Any]]) -> str:
    """Return the content of the last user message, or empty string."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return ""


# ---------------------------------------------------------------------------
# ChatService
# ---------------------------------------------------------------------------

class ChatService:
    """
    Service for running stock market chat via the FlowDeckAgent LangGraph runtime.

    Wraps FlowDeckAgent with the FlowDeck system prompt, chart extraction,
    and token accounting.  The public interface (chat / chat_stream) is
    unchanged so the router requires no modifications.
    """

    def __init__(self):
        self._llm = None
        self._agent = None

    def _get_llm(self):
        """Lazy-initialize the LLM."""
        if self._llm is None:
            self._llm = _build_llm()
        return self._llm

    def _get_agent(self) -> "FlowDeckAgent":
        """Lazy-initialize the FlowDeckAgent (graph is compiled once per process)."""
        if self._agent is None:
            from ai_engine.agent.graph import FlowDeckAgent
            self._agent = FlowDeckAgent(llm=self._get_llm())
        return self._agent  # type: ignore[return-value]

    def chat(
        self,
        messages: List[Dict[str, str]],
        user_id: Optional[int] = None,
        db: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run a chat turn (blocking).

        Args:
            messages: List of {role: "user"|"assistant", content: str} dicts.
            user_id:  Optional user ID for user-context tools.
            db:       Optional SQLAlchemy session for user-context tools.
            context:  Optional context dict (e.g. {"tickers": ["AAPL", "MSFT"]}).

        Returns:
            dict with reply (str) and tokens_used (int).
        """
        if not messages:
            return {
                "reply": "Hello! I'm your FlowDeck Stock Market Analyst. Ask me anything about stocks, markets, or financial data.",
                "tokens_used": 1,
            }

        last_user_msg = _last_user_message(messages)
        if not last_user_msg:
            return {"reply": "Please send a message.", "tokens_used": 1}

        logger.info(
            "chat() started | user_id=%s | history_len=%d | query=%r",
            user_id,
            len(messages),
            last_user_msg[:200],
        )

        system_prompt = _build_system_prompt(user_id, db, context)
        result = self._get_agent().run(
            messages,
            user_id=user_id,
            db=db,
            system_prompt=system_prompt,
            max_tool_calls=15,
        )
        return {
            "reply": result.get("reply", ""),
            "tokens_used": result.get("tokens_used", 1),
            "tools_called": result.get("tools_called", 0),
        }

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        user_id: Optional[int] = None,
        db: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Generator[str, None, None]:
        """
        Run the tool-calling loop and yield SSE events as tools execute.

        Yields SSE-formatted strings:
          - ``data: {"type":"thinking","content":"..."}\\n\\n``           while tools are running
          - ``data: {"type":"tool_call","name":"...","input":"...","output":"..."}\\n\\n``  per tool
          - ``data: {"type":"token","content":"..."}\\n\\n``               the final reply (single chunk)
          - ``data: {"type":"done","tokens_used":N,"tools_called":M}\\n\\n`` when finished
          - ``data: {"type":"error","content":"..."}\\n\\n``               on error
        """
        if not messages:
            yield 'data: {"type":"token","content":"Hello! I\'m your FlowDeck Stock Market Analyst. Ask me anything about stocks, markets, or financial data."}\n\n'
            yield 'data: {"type":"done","tokens_used":1,"tools_called":0}\n\n'
            return

        last_user_msg = _last_user_message(messages)
        if not last_user_msg:
            yield 'data: {"type":"token","content":"Please send a message."}\n\n'
            yield 'data: {"type":"done","tokens_used":1,"tools_called":0}\n\n'
            return

        system_prompt = _build_system_prompt(user_id, db, context)

        try:
            for event in self._get_agent().stream(
                messages,
                user_id=user_id,
                db=db,
                system_prompt=system_prompt,
                max_tool_calls=15,
            ):
                # For token events, extract any CHART_JSON lines the LLM embedded
                if '"type":"token"' in event or '"type": "token"' in event:
                    try:
                        payload = json.loads(event.removeprefix("data: ").strip())
                        raw_content = payload.get("content", "")
                        chart_specs, cleaned = _extract_chart_specs(raw_content)
                        for spec in chart_specs:
                            yield f"data: {json.dumps({'type': 'chart', 'spec': spec})}\n\n"
                        cleaned = cleaned.strip()
                        if cleaned:
                            yield f"data: {json.dumps({'type': 'token', 'content': cleaned})}\n\n"
                    except Exception:
                        yield event  # fallback: yield as-is
                elif '"type":"tool_call"' in event or '"type": "tool_call"' in event:
                    # For execute_python, extract CHART_JSON from output
                    try:
                        payload = json.loads(event.removeprefix("data: ").strip())
                        if payload.get("name") == "execute_python":
                            raw_output = payload.get("output", "")
                            chart_specs, cleaned_output = _extract_chart_specs(raw_output)
                            for spec in chart_specs:
                                yield f"data: {json.dumps({'type': 'chart', 'spec': spec})}\n\n"
                            payload["output"] = cleaned_output[:2000]
                            yield f"data: {json.dumps(payload)}\n\n"
                        else:
                            output = payload.get("output", "")
                            if len(output) > 2000:
                                payload["output"] = output[:2000] + "…"
                            yield f"data: {json.dumps(payload)}\n\n"
                    except Exception:
                        yield event
                else:
                    yield event
        except Exception as e:
            logger.exception("chat_stream() error | user_id=%s | %s", user_id, e)
            yield f"data: {json.dumps({'type': 'error', 'content': f'I encountered an error: {str(e)}. Please try again.'})}\n\n"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_chat_service: ChatService | None = None


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service

# Made with Bob
