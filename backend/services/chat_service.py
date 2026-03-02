"""
Chat service: LLM-based stock market analyst chat with tool-calling.

Uses direct LLM.bind_tools() + manual tool execution loop for maximum
compatibility with Azure OpenAI (no AgentExecutor streaming issues).
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import requests
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


# Canonical report keys and their display labels
_REPORT_LABELS = {
    "market_report": "Market Analysis",
    "fundamentals_report": "Fundamentals Analysis",
    "technical_report": "Technical Analysis",
    "news_report": "News Analysis",
    "sec_report": "SEC Analysis",
    "investment_plan": "Investment Plan",
    "trader_investment_plan": "Trader Plan",
    "final_trade_decision": "Final Decision",
}
# Aliases the LLM might pass for report_type
_REPORT_ALIASES: dict[str, str] = {
    "market": "market_report",
    "fundamentals": "fundamentals_report",
    "fundamental": "fundamentals_report",
    "technical": "technical_report",
    "news": "news_report",
    "sec": "sec_report",
    "investment": "investment_plan",
    "plan": "investment_plan",
    "trader": "trader_investment_plan",
    "trader_plan": "trader_investment_plan",
    "final": "final_trade_decision",
    "decision": "final_trade_decision",
    "recommendation": "final_trade_decision",
}

def _tool_get_platform_reports(ticker: str, report_type: str | None = None, date: str | None = None) -> str:
    """Get FlowDeck AI analysis reports for a ticker, optionally filtered to a specific report and/or date."""
    try:
        from services.report_service import ReportService
        svc = ReportService()
        ticker_upper = ticker.strip().upper()

        if date:
            # Use the specified date (can be YYYY-MM-DD or full run_id YYYY-MM-DD_HH-MM-SS)
            target_date = date.strip()
            if not svc.has_report_for_date(ticker_upper, target_date):
                # List available dates to help the agent
                analyses = svc.get_historical_analyses(ticker_upper)
                if analyses:
                    available = ", ".join(a["date"] for a in analyses[:10])
                    return (
                        f"No reports found for {ticker_upper} on date '{target_date}'. "
                        f"Available report dates: {available}."
                    )
                return f"No AI analysis reports found for {ticker_upper} on this platform."
        else:
            target_date = svc.get_latest_report_date(ticker_upper)
            if not target_date:
                return f"No AI analysis reports found for {ticker_upper} on this platform."

        reports = svc.get_reports_with_scores(ticker_upper, target_date)
        if not reports:
            return f"No report content found for {ticker_upper}."

        # Resolve report_type alias → canonical key
        filter_key: str | None = None
        if report_type:
            rt = report_type.strip().lower()
            filter_key = _REPORT_ALIASES.get(rt, rt)  # try alias map, else use as-is
            if filter_key not in _REPORT_LABELS:
                # Try partial match
                matches = [k for k in _REPORT_LABELS if rt in k]
                filter_key = matches[0] if matches else None

        lines = [f"# FlowDeck AI Reports for {ticker_upper} ({target_date})", ""]

        # Recommendation summary (always shown)
        tip = reports.get("trader_investment_plan") or {}
        ftd = reports.get("final_trade_decision") or {}
        rec = tip.get("recommendation") or ftd.get("recommendation")
        conf = tip.get("confidence") or ftd.get("confidence")
        if rec:
            conf_str = f" ({conf*100:.0f}% confidence)" if conf else ""
            lines.append(f"**Recommendation: {rec}{conf_str}**")

        # Return scenarios (always shown)
        inv = reports.get("investment_plan") or {}
        exp = inv.get("expected_return_pct")
        bear_ret = inv.get("bear_case_return_pct")
        bull_ret = inv.get("bull_case_return_pct")
        if any(v is not None for v in [exp, bear_ret, bull_ret]):
            parts = []
            if exp is not None: parts.append(f"Expected: {exp:+.1f}%")
            if bear_ret is not None: parts.append(f"Bear: {bear_ret:+.1f}%")
            if bull_ret is not None: parts.append(f"Bull: {bull_ret:+.1f}%")
            lines.append("Return scenarios: " + " | ".join(parts))

        lines.append("")

        if filter_key:
            # Single-report mode
            if filter_key not in reports:
                available = ", ".join(_REPORT_LABELS.get(k, k) for k in reports)
                return (
                    f"Report '{report_type}' not found for {ticker_upper}. "
                    f"Available reports: {available}."
                )
            keys_to_render = [filter_key]
        else:
            # All reports
            REPORT_ORDER = ["final_trade_decision", "investment_plan", "trader_investment_plan",
                            "market_report", "fundamentals_report", "technical_report",
                            "news_report", "sec_report"]
            keys_to_render = [k for k in REPORT_ORDER if k in reports] + [k for k in reports if k not in REPORT_ORDER]

        for key in keys_to_render:
            data = reports.get(key)
            if not data:
                continue
            label = _REPORT_LABELS.get(key, key.replace("_", " ").title())
            score = data.get("score")
            takeaways = data.get("key_takeaways") or []
            content = (data.get("content") or "").strip()

            lines.append(f"## {label}" + (f" (Score: {score}/10)" if score is not None else ""))

            # Key takeaways (always shown)
            if takeaways:
                lines.append("**Key Takeaways:**")
                for t in takeaways:
                    lines.append(f"- {t}")

            # Researcher viewpoints (investment_plan)
            bull_vp = data.get("bull_viewpoint") or []
            bear_vp = data.get("bear_viewpoint") or []
            if bull_vp:
                lines.append("**Bull Viewpoint:**")
                for p in bull_vp:
                    lines.append(f"- {p}")
            if bear_vp:
                lines.append("**Bear Viewpoint:**")
                for p in bear_vp:
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

            # Full report content — only included when a specific report_type was requested
            if filter_key and content:
                if len(content) > 8000:
                    content = content[:8000] + " [...]"
                lines.append(content)
            lines.append("")

        return "\n".join(lines)
    except Exception as e:
        logger.exception("get_platform_reports error for %s: %s", ticker, e)
        return f"Error fetching platform reports for {ticker}: {e}"


def _tool_get_historical_report_dates(ticker: str) -> str:
    """List all historical AI analysis report dates available for a ticker on the platform."""
    try:
        from services.report_service import ReportService
        svc = ReportService()
        ticker_upper = ticker.strip().upper()
        analyses = svc.get_historical_analyses(ticker_upper)
        if not analyses:
            return f"No AI analysis reports found for {ticker_upper} on this platform."
        lines = [f"# Historical AI Report Dates for {ticker_upper}", ""]
        lines.append(f"Total analyses available: {len(analyses)}", )
        lines.append("")
        for a in analyses:
            run_id = a["date"]
            report_types = a.get("available_reports", [])
            labels = [_REPORT_LABELS.get(rt) or rt.replace("_", " ").title() for rt in report_types]
            lines.append(f"- **{run_id}**: {', '.join(labels)}")
        lines.append("")
        lines.append(
            "To read reports from a specific date, call get_platform_reports with "
            "the ticker and the desired date (e.g. '2025-01-15' or the full run_id)."
        )
        return "\n".join(lines)
    except Exception as e:
        logger.exception("get_historical_report_dates error for %s: %s", ticker, e)
        return f"Error fetching historical report dates for {ticker}: {e}"


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


def _tool_get_historical_prices(ticker: str, start_date: str, end_date: str) -> str:
    """
    Fetch daily OHLCV price history for a ticker over a custom date range (up to 5 years).
    Returns CSV data with columns: Date, Open, High, Low, Close, Volume.
    """
    try:
        import yfinance as yf
        import pandas as pd

        ticker_upper = ticker.strip().upper()

        # Parse and validate dates
        try:
            start_dt = datetime.date.fromisoformat(start_date)
            end_dt = datetime.date.fromisoformat(end_date)
        except ValueError:
            return f"Error: invalid date format. Use YYYY-MM-DD (e.g. 2024-01-01)."

        today = datetime.date.today()

        # Cap end date at today
        if end_dt > today:
            end_dt = today

        # Cap range at 5 years to avoid huge payloads
        max_start = today - datetime.timedelta(days=5 * 365)
        if start_dt < max_start:
            start_dt = max_start

        if start_dt >= end_dt:
            return "Error: start_date must be before end_date."

        data = yf.download(
            ticker_upper,
            start=start_dt.isoformat(),
            end=end_dt.isoformat(),
            multi_level_index=False,
            progress=False,
            auto_adjust=True,
        )

        if data is None or data.empty:
            return f"No price data found for {ticker_upper} between {start_dt} and {end_dt}."

        # Keep only the columns we need, reset index so Date is a column
        data = data.reset_index()[["Date", "Open", "High", "Low", "Close", "Volume"]]
        data["Date"] = [str(d)[:10] for d in pd.to_datetime(data["Date"])]
        data[["Open", "High", "Low", "Close"]] = data[["Open", "High", "Low", "Close"]].round(4)

        csv_out = data.to_csv(index=False)

        header = (
            f"# Historical daily prices for {ticker_upper}\n"
            f"# Period: {start_dt} to {end_dt} | Rows: {len(data)}\n"
            f"# Columns: Date, Open, High, Low, Close (adjusted), Volume\n\n"
        )
        return header + csv_out

    except Exception as e:
        return f"Error fetching historical prices for {ticker}: {e}"


def _tool_get_indicators(ticker: str) -> str:
    """Get technical indicators (RSI, MACD, SMA, Bollinger Bands) for a ticker."""
    try:
        from ai_engine.tradingagents.agents.utils.technical_indicators_tools import get_indicators
        today = datetime.date.today().isoformat()
        return get_indicators.invoke({"symbol": ticker.upper(), "indicator": "all", "curr_date": today, "look_back_days": 30})
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


def _tool_web_search(query: str) -> str:
    """Search the web using SerpAPI (serpapi.com) for any query."""
    import urllib.parse
    import urllib.request
    import json as _json

    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        return "Web search is unavailable: SERPAPI_KEY is not configured."
    try:
        params = {
            "engine": "google",
            "q": query,
            "num": 10,
            "api_key": api_key,
        }
        url = "https://serpapi.com/search?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode())

        error = data.get("error")
        if error:
            return f"Web search error: {error}"

        lines = [f"## Web Search Results for: {query}", ""]

        # Answer box (direct answer)
        answer_box = data.get("answer_box")
        if answer_box:
            title = answer_box.get("title", "")
            answer = answer_box.get("answer") or answer_box.get("snippet", "")
            if title:
                lines.append(f"**{title}**")
            if answer:
                lines.append(answer)
            lines.append("")

        # Knowledge graph
        kg = data.get("knowledge_graph")
        if kg:
            kg_title = kg.get("title", "")
            kg_desc = kg.get("description", "")
            if kg_title:
                lines.append(f"**{kg_title}**: {kg_desc}")
                lines.append("")

        # Organic results
        organic = data.get("organic_results", [])
        for i, result in enumerate(organic[:8], 1):
            title = result.get("title", "")
            link = result.get("link", "")
            snippet = result.get("snippet", "")
            date = result.get("date", "")
            date_str = f" ({date})" if date else ""
            lines.append(f"**{i}. {title}**{date_str}")
            if snippet:
                lines.append(snippet)
            if link:
                lines.append(f"Source: {link}")
            lines.append("")

        # Top stories
        top_stories = data.get("top_stories", [])
        if top_stories:
            lines.append("### Top Stories")
            for story in top_stories[:5]:
                title = story.get("title", "")
                source = story.get("source", "")
                date = story.get("date", "")
                link = story.get("link", "")
                date_str = f" ({date})" if date else ""
                source_str = f" — {source}" if source else ""
                lines.append(f"- **{title}**{source_str}{date_str}")
                if link:
                    lines.append(f"  {link}")
            lines.append("")

        if len(lines) <= 2:
            return f"No results found for: {query}"

        return "\n".join(lines)
    except Exception as e:
        logger.exception("web_search error for query '%s': %s", query, e)
        return f"Error performing web search: {e}"


# ---------------------------------------------------------------------------
# Code execution tool (sandboxed subprocess)
# ---------------------------------------------------------------------------

# Modules that are safe to import inside the sandbox.
# Any import NOT in this set will be blocked before execution.
_ALLOWED_MODULES = frozenset({
    # math / numerics
    "math", "cmath", "decimal", "fractions", "statistics", "random",
    # data structures / algorithms
    "collections", "heapq", "bisect", "array", "queue", "itertools",
    "functools", "operator", "copy", "pprint",
    # string / text
    "string", "re", "textwrap", "unicodedata", "difflib",
    # date / time (read-only)
    "datetime", "calendar", "time",
    # encoding / serialisation
    "json", "csv", "base64", "hashlib", "hmac", "struct",
    # third-party data/science (present in the venv)
    "numpy", "pandas", "scipy", "sklearn", "statsmodels",
    # typing helpers
    "typing", "dataclasses", "enum", "abc",
    # io helpers (StringIO / BytesIO only — no file paths)
    "io",
})

# Patterns that are always blocked regardless of the allowlist.
_BLOCKED_PATTERNS = [
    "import os",
    "import sys",
    "import subprocess",
    "import socket",
    "import requests",
    "import urllib",
    "import http",
    "import ftplib",
    "import smtplib",
    "import shutil",
    "import pathlib",
    "import glob",
    "import tempfile",
    "import pickle",
    "import shelve",
    "import sqlite3",
    "import ctypes",
    "import cffi",
    "import multiprocessing",
    "import threading",
    "import concurrent",
    "import asyncio",
    "__import__",
    "open(",
    "exec(",
    "eval(",
    "compile(",
    "globals(",
    "locals(",
    "vars(",
    "getattr(",
    "setattr(",
    "delattr(",
    "breakpoint(",
    "__builtins__",
    "__class__",
    "__subclasses__",
    "builtins",
]


def _tool_execute_python(code: str) -> str:
    """
    Execute a Python code snippet in a heavily restricted subprocess sandbox.

    Safety measures applied (in order):
      1. Static pattern scan — blocks dangerous imports and builtins before execution.
      2. Code length cap — rejects snippets over 4 KB.
      3. subprocess with shell=False — no shell injection possible.
      4. Stripped environment — no credentials, proxy settings, or PATH tricks.
      5. Isolated /tmp working directory — no access to the app source tree.
      6. Hard 10-second wall-clock timeout — kills infinite loops.
      7. Memory cap via resource.setrlimit (128 MB RSS, Unix only).
      8. stdout/stderr capped at 8 KB to prevent output flooding.
    """
    import subprocess
    import sys
    import textwrap
    import tempfile
    import os as _os

    # --- 1. Length cap ---
    MAX_CODE_BYTES = 4096
    if len(code.encode()) > MAX_CODE_BYTES:
        return f"Error: code exceeds the {MAX_CODE_BYTES}-byte limit ({len(code.encode())} bytes submitted)."

    # --- 2. Static pattern scan ---
    code_lower = code.lower()
    for pattern in _BLOCKED_PATTERNS:
        if pattern.lower() in code_lower:
            return (
                f"Error: code contains a blocked pattern: `{pattern}`. "
                "Only safe standard-library and data-science modules are permitted."
            )

    # --- 3. Build the wrapper script ---
    # The wrapper installs a restricted __builtins__ and then exec()s the user code.
    # We write it to a temp file so the subprocess argv never contains user code.
    wrapper = textwrap.dedent(f"""\
        import resource, sys

        # Memory cap: 128 MB RSS (soft), 256 MB (hard)
        try:
            resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 256 * 1024 * 1024))
        except Exception:
            pass  # Windows / non-Unix: skip silently

        # Allowed modules (runtime enforcement — mirrors the outer _ALLOWED_MODULES set)
        _ALLOWED = {{
            'math', 'cmath', 'decimal', 'fractions', 'statistics', 'random',
            'collections', 'heapq', 'bisect', 'array', 'queue', 'itertools',
            'functools', 'operator', 'copy', 'pprint',
            'string', 're', 'textwrap', 'unicodedata', 'difflib',
            'datetime', 'calendar', 'time',
            'json', 'csv', 'base64', 'hashlib', 'hmac', 'struct',
            'numpy', 'pandas', 'scipy', 'sklearn', 'statsmodels',
            'typing', 'dataclasses', 'enum', 'abc', 'io',
        }}

        import builtins as _builtins_mod

        # Custom __import__ that enforces the allowlist at runtime
        _real_import = _builtins_mod.__import__
        def _safe_import(name, *args, **kwargs):
            top = name.split('.')[0]
            if top not in _ALLOWED:
                raise ImportError(f"Module '{{name}}' is not allowed in the sandbox.")
            return _real_import(name, *args, **kwargs)

        # Restrict builtins — include __import__ so the import statement works,
        # but replace it with our allowlist-enforcing wrapper.
        _SAFE_BUILTINS = {{
            k: v for k, v in _builtins_mod.__dict__.items()
            if k in {{
                'print', 'len', 'range', 'enumerate', 'zip', 'map', 'filter',
                'sorted', 'reversed', 'sum', 'min', 'max', 'abs', 'round',
                'int', 'float', 'str', 'bool', 'list', 'dict', 'set', 'tuple',
                'type', 'isinstance', 'issubclass', 'hasattr',
                'repr', 'format', 'chr', 'ord', 'hex', 'oct', 'bin',
                'divmod', 'pow', 'hash', 'id', 'iter', 'next', 'callable',
                'all', 'any', 'staticmethod', 'classmethod', 'property',
                'NotImplemented', 'Ellipsis', 'None', 'True', 'False',
                '__name__', '__doc__', '__spec__', '__loader__', '__package__',
                # Exceptions
                'Exception', 'ValueError', 'TypeError', 'KeyError',
                'IndexError', 'AttributeError', 'RuntimeError',
                'StopIteration', 'ZeroDivisionError', 'OverflowError',
                'ArithmeticError', 'LookupError', 'AssertionError',
                'NotImplementedError', 'ImportError', 'NameError',
            }}
        }}
        # Inject the safe import wrapper (NOT the real __import__)
        _SAFE_BUILTINS['__import__'] = _safe_import

        _builtins_mod.open = None  # belt-and-suspenders

        _user_code = {repr(code)}
        exec(compile(_user_code, '<sandbox>', 'exec'), {{'__builtins__': _SAFE_BUILTINS}})
    """)

    # --- 4. Write wrapper to a temp file ---
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir="/tmp"
        ) as tf:
            tf.write(wrapper)
            tmp_path = tf.name
    except Exception as e:
        return f"Error: could not create sandbox script: {e}"

    # --- 5. Stripped environment (no credentials, no PATH tricks) ---
    safe_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/tmp",
        "LANG": "en_US.UTF-8",
        "PYTHONPATH": "",          # don't inherit app's PYTHONPATH
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }

    # --- 6. Execute ---
    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=10,
            cwd="/tmp",            # isolated working directory
            env=safe_env,
            shell=False,           # never use shell=True
        )
    except subprocess.TimeoutExpired:
        return "Error: code execution timed out (10-second limit)."
    except Exception as e:
        return f"Error: sandbox execution failed: {e}"
    finally:
        # Always clean up the temp file
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass

    # --- 7. Cap output size ---
    MAX_OUTPUT = 8192
    stdout = result.stdout or ""
    stderr = result.stderr or ""

    if len(stdout) > MAX_OUTPUT:
        stdout = stdout[:MAX_OUTPUT] + "\n... [output truncated]"
    if len(stderr) > MAX_OUTPUT:
        stderr = stderr[:MAX_OUTPUT] + "\n... [stderr truncated]"

    output = stdout
    if stderr:
        # Filter out the harmless "Traceback" header noise for cleaner display
        output += f"\n[stderr]:\n{stderr}"

    return output.strip() or "(no output)"


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
    import json as _json
    import re as _re

    charts: list[dict] = []

    # First pass: extract bare CHART_JSON: lines
    def _replace_bare(m: "_re.Match") -> str:
        payload = m.group(1).strip()
        try:
            spec = _json.loads(payload)
            charts.append(spec)
            return ""  # remove the line
        except Exception:
            return m.group(0)  # keep if malformed

    # Match a full line that starts with CHART_JSON: (possibly inside a code block)
    cleaned = _re.sub(r"(?m)^[ \t]*CHART_JSON:(.+)$", _replace_bare, text)

    # Second pass: remove orphaned empty code fences left after extraction
    # e.g. ```\n\n``` or ```python\n\n```
    cleaned = _re.sub(r"(?m)^```[^\n]*\n(\s*\n)*```\n?", "", cleaned)

    # Collapse runs of 3+ blank lines down to 2
    cleaned = _re.sub(r"\n{3,}", "\n\n", cleaned)

    return charts, cleaned


# ---------------------------------------------------------------------------
# User-context tool factories (require user_id + db session)
# ---------------------------------------------------------------------------

def _make_user_context_tools(user_id: int, db: Any) -> List[Dict[str, Any]]:
    """
    Build user-context tool definitions bound to a specific user_id and db session.
    Returns a list of tool dicts in the same format as the global TOOLS list.
    """

    def _tool_get_user_context(_: str = "") -> str:
        """Return the current user's profile information."""
        try:
            from models.db_models import User
            from services import token_service
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return "User not found."
            balance = token_service.get_balance(user_id, db)
            member_since = user.created_at.strftime("%B %d, %Y") if user.created_at else "Unknown"
            name_str = f"Name: {user.name}" if user.name else "Name: (not set)"
            lines = [
                "# Your FlowDeck Profile",
                f"Email: {user.email}",
                name_str,
                f"Token Balance: {balance:,} tokens",
                f"Member Since: {member_since}",
                f"Account Type: {'Admin' if user.is_admin else 'Standard'}",
            ]
            return "\n".join(lines)
        except Exception as e:
            logger.exception("get_user_context error: %s", e)
            return f"Error fetching user context: {e}"

    def _tool_get_user_subscriptions(_: str = "") -> str:
        """Return the list of tickers the user is subscribed to."""
        try:
            from models.db_models import Subscription
            subs = (
                db.query(Subscription)
                .filter(Subscription.user_id == user_id)
                .order_by(Subscription.created_at.desc())
                .all()
            )
            if not subs:
                return "You have no subscribed stocks yet. Visit the platform to subscribe to tickers."
            lines = ["# Your Subscribed Stocks", ""]
            for s in subs:
                date_str = s.created_at.strftime("%Y-%m-%d") if s.created_at else "Unknown"
                email_flag = " (email updates on)" if s.email_updates else " (email updates off)"
                lines.append(f"- **{s.ticker}** — subscribed {date_str}{email_flag}")
            lines.append("")
            lines.append(f"Total: {len(subs)} subscribed stock(s)")
            return "\n".join(lines)
        except Exception as e:
            logger.exception("get_user_subscriptions error: %s", e)
            return f"Error fetching subscriptions: {e}"

    def _tool_get_portfolio_overview(_: str = "") -> str:
        """
        Return a portfolio overview: current quotes + latest AI recommendation
        for every stock the user is subscribed to.
        """
        try:
            from models.db_models import Subscription
            from services.report_service import ReportService
            from ai_engine.tradingagents.agents.utils.core_stock_tools import get_stock_quote

            subs = (
                db.query(Subscription)
                .filter(Subscription.user_id == user_id)
                .order_by(Subscription.ticker)
                .all()
            )
            if not subs:
                return "You have no subscribed stocks. Subscribe to tickers on the platform to build your portfolio."

            svc = ReportService()
            lines = ["# Your Portfolio Overview", ""]

            for s in subs:
                ticker = s.ticker
                lines.append(f"## {ticker}")

                # Live quote
                try:
                    quote = get_stock_quote.invoke({"symbol": ticker})
                    lines.append(f"**Quote:** {quote}")
                except Exception as qe:
                    lines.append(f"**Quote:** unavailable ({qe})")

                # Latest AI recommendation
                try:
                    latest_date = svc.get_latest_report_date(ticker)
                    if latest_date:
                        reports = svc.get_reports_with_scores(ticker, latest_date)
                        tip = reports.get("trader_investment_plan") or {}
                        ftd = reports.get("final_trade_decision") or {}
                        rec = tip.get("recommendation") or ftd.get("recommendation")
                        conf = tip.get("confidence") or ftd.get("confidence")
                        inv = reports.get("investment_plan") or {}
                        exp = inv.get("expected_return_pct")
                        bear_ret = inv.get("bear_case_return_pct")
                        bull_ret = inv.get("bull_case_return_pct")

                        if rec:
                            conf_str = f" ({conf*100:.0f}% confidence)" if conf else ""
                            lines.append(f"**AI Recommendation:** {rec}{conf_str} (as of {latest_date})")
                        if any(v is not None for v in [exp, bear_ret, bull_ret]):
                            parts = []
                            if exp is not None: parts.append(f"Expected: {exp:+.1f}%")
                            if bear_ret is not None: parts.append(f"Bear: {bear_ret:+.1f}%")
                            if bull_ret is not None: parts.append(f"Bull: {bull_ret:+.1f}%")
                            lines.append("**Return Scenarios:** " + " | ".join(parts))
                    else:
                        lines.append("**AI Recommendation:** No report available yet")
                except Exception as re_:
                    lines.append(f"**AI Recommendation:** unavailable ({re_})")

                lines.append("")

            return "\n".join(lines)
        except Exception as e:
            logger.exception("get_portfolio_overview error: %s", e)
            return f"Error fetching portfolio overview: {e}"

    return [
        {
            "name": "get_user_context",
            "description": (
                "Get the current user's profile information: their email, display name, "
                "token balance, account type, and member-since date. "
                "Use when the user asks about their account, profile, token balance, or who they are."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
            "fn": lambda _="": _tool_get_user_context(),
        },
        {
            "name": "get_user_subscriptions",
            "description": (
                "Get the list of stock tickers the current user is subscribed to on FlowDeck, "
                "including subscription dates and email-update preferences. "
                "Use when the user asks about their watchlist, subscriptions, followed stocks, or portfolio tickers."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
            "fn": lambda _="": _tool_get_user_subscriptions(),
        },
        {
            "name": "get_portfolio_overview",
            "description": (
                "Get a full portfolio overview for the current user: live stock quotes AND the latest "
                "FlowDeck AI recommendation (BUY/SELL/HOLD with confidence and return scenarios) "
                "for every stock they are subscribed to. "
                "Use when the user asks about their portfolio, how their stocks are doing, "
                "portfolio performance, or wants a summary of all their subscribed stocks."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
            "fn": lambda _="": _tool_get_portfolio_overview(),
        },
    ]


# Tool registry: name -> (callable, description, parameters schema)
TOOLS = [
    {
        "name": "get_platform_reports",
        "description": (
            "ALWAYS call this first when the user asks about a stock's analysis, recommendation, outlook, "
            "investment thesis, bull/bear case, risk assessment, or any AI-generated insight. "
            "Retrieves FlowDeck's proprietary AI analysis reports from the platform database for a given ticker. "
            "Without report_type: returns a summary of ALL reports — recommendation, return scenarios, "
            "scores, and key takeaways for each report (no full text). "
            "With report_type: returns the full content of that specific report. "
            "Available reports: Final Trade Decision (risk-adjusted recommendation), "
            "Investment Plan (bull vs bear researcher debate), Trader Plan, Market Analysis, "
            "Fundamentals Analysis, Technical Analysis, News Analysis, SEC/Regulatory Analysis. "
            "Use report_type when the user asks to 'read', 'show', 'summarize', or 'deep dive' into a specific report. "
            "By default returns the LATEST report. Use the 'date' parameter to access historical reports — "
            "first call get_historical_report_dates to discover available dates, then pass the desired date here."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA, NVDA"},
                "report_type": {
                    "type": "string",
                    "description": (
                        "Optional. Fetch only a specific report instead of all reports. "
                        "Accepted values: 'final_trade_decision' (or 'final'/'decision'/'recommendation'), "
                        "'investment_plan' (or 'investment'/'plan'), "
                        "'trader_investment_plan' (or 'trader'/'trader_plan'), "
                        "'market_report' (or 'market'), "
                        "'fundamentals_report' (or 'fundamentals'/'fundamental'), "
                        "'technical_report' (or 'technical'), "
                        "'news_report' (or 'news'), "
                        "'sec_report' (or 'sec'). "
                        "Omit or leave null to fetch all available reports."
                    ),
                },
                "date": {
                    "type": "string",
                    "description": (
                        "Optional. Fetch reports from a specific historical analysis date instead of the latest. "
                        "Accepts YYYY-MM-DD (e.g. '2025-01-15') or a full run_id (e.g. '2025-01-15_10-30-00'). "
                        "Use get_historical_report_dates first to discover available dates for a ticker. "
                        "Omit or leave null to fetch the most recent reports."
                    ),
                },
            },
            "required": ["ticker"],
        },
        "fn": _tool_get_platform_reports,
    },
    {
        "name": "get_historical_report_dates",
        "description": (
            "List all historical AI analysis report dates available for a ticker on the FlowDeck platform. "
            "Returns a chronological list of run dates (newest first) with the report types available for each date. "
            "Use this tool when the user asks about: past analyses, historical recommendations, how the outlook "
            "has changed over time, previous reports, or any question involving a specific past date. "
            "After calling this, use get_platform_reports with the 'date' parameter to fetch reports from a specific date."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA, NVDA"},
            },
            "required": ["ticker"],
        },
        "fn": _tool_get_historical_report_dates,
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
        "name": "get_historical_prices",
        "description": (
            "Fetch daily OHLCV (Open, High, Low, Close, Volume) price history for a ticker over a custom date range "
            "(up to 5 years back). Returns CSV data with adjusted close prices. "
            "Use this — instead of get_stock_data — whenever the user asks about price history beyond the last 30 days: "
            "e.g. year-to-date performance, 1-year or multi-year returns, correlation between two stocks over a year, "
            "historical volatility, drawdown analysis, or any calculation that requires more than 30 days of price data. "
            "After fetching, pass the CSV to execute_python for calculations."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA",
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format, e.g. 2024-01-01",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format, e.g. 2025-01-01. Use today's date for the most recent data.",
                },
            },
            "required": ["ticker", "start_date", "end_date"],
        },
        "fn": _tool_get_historical_prices,
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
    {
        "name": "web_search",
        "description": (
            "Your ONLY gateway to live internet data. Use this tool whenever the information needed is NOT already "
            "provided by the other available tools (get_platform_reports, get_stock_quote, get_stock_data, "
            "get_indicators, get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement, "
            "get_news, get_global_news, get_insider_transactions, get_insider_sentiment). "
            "This covers ANY online content: breaking news, earnings call transcripts, analyst upgrades/downgrades, "
            "price target changes, SEC/regulatory filings, IPO details, M&A activity, product launches, "
            "macroeconomic data releases (CPI, GDP, jobs report), central bank decisions, geopolitical events, "
            "competitor analysis, industry trends, company background, executive changes, legal proceedings, "
            "social media sentiment, Reddit/Twitter discussions, blog posts, research papers, or ANY other "
            "topic that requires fetching current information from the web. "
            "When in doubt about whether another tool covers the question, use this tool to search online."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query, e.g. 'Apple Q1 2025 earnings results', 'Fed interest rate decision March 2025', 'NVDA analyst price target upgrade'"
                }
            },
            "required": ["query"],
        },
        "fn": _tool_web_search,
    },
    {
        "name": "execute_python",
        "description": (
            "Execute a Python code snippet in a secure sandbox and return the printed output. "
            "Use this tool for: mathematical calculations, statistical analysis, financial modelling, "
            "data transformations, sorting/filtering lists of numbers, computing returns or ratios, "
            "or any task where running code produces a more accurate answer than reasoning alone. "
            "Allowed modules: math, statistics, random, collections, itertools, functools, datetime, "
            "json, csv, decimal, fractions, re, string, numpy, pandas, scipy. "
            "NOT allowed: file I/O, network access, os/sys/subprocess, pickle, threading, or any "
            "module not in the allowlist. Keep code under 4 KB. Use print() to produce output."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": (
                        "Valid Python 3 code to execute. Must use print() to produce output. "
                        "Example: 'import math\\nprint(math.sqrt(144))'"
                    ),
                }
            },
            "required": ["code"],
        },
        "fn": _tool_execute_python,
    },
]

# OpenAI-format tool schemas for bind_tools
_TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
    for t in TOOLS
]

# Fast lookup: tool name -> callable
_TOOL_FN: Dict[str, Any] = {t["name"]: t["fn"] for t in TOOLS}


def _invoke_with_retry(fn, *args, max_retries: int = 3, **kwargs):
    """Invoke fn(*args, **kwargs) with exponential backoff on transient 500/503 errors."""
    import time
    last_exc = None
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            err_str = str(e)
            status = getattr(getattr(e, "response", None), "status_code", None) or 0
            is_transient = (
                "500" in err_str or "503" in err_str or
                status in (500, 503) or
                "internal server error" in err_str.lower() or
                "service unavailable" in err_str.lower()
            )
            if is_transient and attempt < max_retries - 1:
                wait = 2 ** attempt  # 1s, 2s
                logger.warning("Transient LLM error (attempt %d/%d), retrying in %ds: %s", attempt + 1, max_retries, wait, e)
                time.sleep(wait)
                last_exc = e
            else:
                raise
    raise last_exc  # type: ignore[misc]


def _build_llm():
    """Build and return the LLM for chat using the centralized llm_provider."""
    from ai_engine.llm_provider import get_llm, get_config_from_env
    config = get_config_from_env()
    return get_llm("deep", config, request_timeout=180)


class ChatService:
    """Service for running stock market chat via direct LLM + manual tool loop."""

    def __init__(self):
        self._llm = None

    def _get_llm(self):
        """Lazy-initialize the LLM."""
        if self._llm is None:
            self._llm = _build_llm()
        return self._llm

    def _build_tool_registry(
        self,
        user_id: Optional[int] = None,
        db: Optional[Any] = None,
    ) -> tuple:
        """
        Build the full tool list and fast-lookup dict for this request.
        If user_id and db are provided, user-context tools are included.
        Returns (schemas_list, fn_map_dict).
        """
        all_tools = list(TOOLS)
        if user_id is not None and db is not None:
            all_tools = all_tools + _make_user_context_tools(user_id, db)

        schemas = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
            for t in all_tools
        ]
        fn_map: Dict[str, Any] = {t["name"]: t["fn"] for t in all_tools}
        return schemas, fn_map

    def chat(
        self,
        messages: List[Dict[str, str]],
        user_id: Optional[int] = None,
        db: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run a chat turn with the LLM + tool-calling loop.

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

        last_user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg["content"]
                break

        if not last_user_msg:
            return {"reply": "Please send a message.", "tokens_used": 1}

        logger.info(
            "chat() started | user_id=%s | history_len=%d | query=%r",
            user_id,
            len(messages),
            last_user_msg[:200],
        )

        today = datetime.date.today().isoformat()
        has_user_ctx = user_id is not None and db is not None
        user_ctx_section = """
12. Call `get_user_context` to retrieve the current user's profile (email, name, token balance, member since).
13. Call `get_user_subscriptions` to see which stocks the user is subscribed/watching on FlowDeck.
14. Call `get_portfolio_overview` to get live quotes AND AI recommendations for ALL of the user's subscribed stocks at once — use this when the user asks about their portfolio or how their stocks are doing.""" if has_user_ctx else ""

        # Build watchlist context section if tickers are provided
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
9. Call `web_search` to find breaking news, recent earnings, analyst upgrades/downgrades, regulatory filings, macroeconomic data releases, or any information not covered by the other tools. Use it for general financial questions or when you need the latest web information.
10. Call `get_historical_prices` to fetch real daily OHLCV price data for any custom date range (up to 5 years). Use this — NOT simulation — whenever the user asks about year-to-date performance, 1-year returns, multi-year price history, correlation between stocks over a period, historical volatility, or any analysis requiring more than 30 days of price data. Always fetch real data first, then pass the CSV to `execute_python` for calculations.
11. Call `execute_python` to run calculations, financial modelling, statistical analysis, or data transformations where code gives a more precise answer than reasoning alone. Always use print() to output results. When working with price data from `get_historical_prices`, parse the CSV using the `csv` or `io` module (pandas is also available).
12. You may call multiple tools in sequence to build a comprehensive answer.{user_ctx_section}{watchlist_section}

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
            tool_schemas, tool_fn_map = self._build_tool_registry(user_id, db)
            llm_with_tools = llm.bind_tools(tool_schemas)  # type: ignore[attr-defined]

            tool_calls_made = 0
            max_tool_rounds = 5

            for round_num in range(max_tool_rounds):
                logger.debug(
                    "chat() LLM invoke | user_id=%s | round=%d | messages_in_context=%d",
                    user_id,
                    round_num + 1,
                    len(lc_messages),
                )
                response = _invoke_with_retry(llm_with_tools.invoke, lc_messages)

                # Check if the model wants to call tools
                tool_calls = getattr(response, "tool_calls", None)
                if not tool_calls:
                    # No tool calls — final answer
                    reply = response.content if hasattr(response, "content") else str(response)
                    logger.info(
                        "chat() finished | user_id=%s | rounds=%d | tools_called=%d | reply_len=%d",
                        user_id,
                        round_num + 1,
                        tool_calls_made,
                        len(reply),
                    )
                    return {"reply": reply, "tokens_used": max(1, 1 + tool_calls_made), "tools_called": tool_calls_made}

                logger.debug(
                    "chat() tool round %d | user_id=%s | num_tool_calls=%d | tools=%s",
                    round_num + 1,
                    user_id,
                    len(tool_calls),
                    [tc.get("name") or tc.get("function", {}).get("name", "?") for tc in tool_calls],
                )

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

                    logger.info(
                        "chat() tool call | user_id=%s | tool=%s | args=%s",
                        user_id,
                        tool_name,
                        {k: str(v)[:100] for k, v in tool_args.items()},
                    )

                    fn = tool_fn_map.get(tool_name)
                    if fn:
                        try:
                            tool_result = fn(**tool_args) if tool_args else fn()
                            logger.debug(
                                "chat() tool result | user_id=%s | tool=%s | result_len=%d",
                                user_id,
                                tool_name,
                                len(str(tool_result)),
                            )
                        except Exception as e:
                            logger.warning(
                                "chat() tool exception | user_id=%s | tool=%s | error=%s",
                                user_id,
                                tool_name,
                                e,
                            )
                            tool_result = f"Tool error: {e}"
                    else:
                        logger.warning(
                            "chat() unknown tool | user_id=%s | tool=%s",
                            user_id,
                            tool_name,
                        )
                        tool_result = f"Unknown tool: {tool_name}"

                    lc_messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_id))
                    tool_calls_made += 1

            # Max rounds reached — get final answer without tools
            logger.warning(
                "chat() max tool rounds reached | user_id=%s | max_rounds=%d | tools_called=%d",
                user_id,
                max_tool_rounds,
                tool_calls_made,
            )
            final_response = _invoke_with_retry(llm.invoke, lc_messages)
            reply = final_response.content if hasattr(final_response, "content") else str(final_response)
            logger.info(
                "chat() finished (max rounds) | user_id=%s | tools_called=%d | reply_len=%d",
                user_id,
                tool_calls_made,
                len(reply),
            )
            return {"reply": reply, "tokens_used": max(1, 1 + tool_calls_made), "tools_called": tool_calls_made}

        except Exception as e:
            logger.exception("chat() LLM error | user_id=%s | error=%s", user_id, e)
            return {
                "reply": f"I encountered an error while processing your request: {str(e)}. Please try again.",
                "tokens_used": 1,
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

        last_user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg["content"]
                break

        if not last_user_msg:
            yield 'data: {"type":"token","content":"Please send a message."}\n\n'
            yield 'data: {"type":"done","tokens_used":1,"tools_called":0}\n\n'
            return

        today = datetime.date.today().isoformat()
        has_user_ctx = user_id is not None and db is not None
        user_ctx_section = """
13. Call `get_user_context` to retrieve the current user's profile (email, name, token balance, member since).
14. Call `get_user_subscriptions` to see which stocks the user is subscribed/watching on FlowDeck.
15. Call `get_portfolio_overview` to get live quotes AND AI recommendations for ALL of the user's subscribed stocks at once — use this when the user asks about their portfolio or how their stocks are doing.""" if has_user_ctx else ""

        # Build watchlist context section if tickers are provided
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
9. Call `web_search` to find breaking news, recent earnings, analyst upgrades/downgrades, regulatory filings, macroeconomic data releases, or any information not covered by the other tools. Use it for general financial questions or when you need the latest web information.
10. Call `get_historical_prices` to fetch real daily OHLCV price data for any custom date range (up to 5 years). Use this — NOT simulation — whenever the user asks about year-to-date performance, 1-year returns, multi-year price history, correlation between stocks over a period, historical volatility, or any analysis requiring more than 30 days of price data. Always fetch real data first, then pass the CSV to `execute_python` for calculations.
11. Call `execute_python` to run calculations, financial modelling, statistical analysis, or data transformations where code gives a more precise answer than reasoning alone. Always use print() to output results. When working with price data from `get_historical_prices`, parse the CSV using the `csv` or `io` module (pandas is also available).
12. You may call multiple tools in sequence to build a comprehensive answer.{user_ctx_section}{watchlist_section}

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
            tool_schemas, tool_fn_map = self._build_tool_registry(user_id, db)
            llm_with_tools = llm.bind_tools(tool_schemas)  # type: ignore[attr-defined]

            tool_calls_made = 0
            max_tool_rounds = 5

            for round_num in range(max_tool_rounds):
                response = _invoke_with_retry(llm_with_tools.invoke, lc_messages)

                tool_calls = getattr(response, "tool_calls", None)
                if not tool_calls:
                    # No tool calls — final answer
                    reply = response.content if hasattr(response, "content") else str(response)
                    if reply:
                        # Extract any CHART_JSON lines the LLM wrote directly in its reply
                        chart_specs, reply = _extract_chart_specs(reply)
                        for spec in chart_specs:
                            yield f"data: {json.dumps({'type': 'chart', 'spec': spec})}\n\n"
                        reply = reply.strip()
                        if reply:
                            yield f"data: {json.dumps({'type': 'token', 'content': reply})}\n\n"
                    yield f"data: {json.dumps({'type': 'done', 'tokens_used': max(1, 1 + tool_calls_made), 'tools_called': tool_calls_made})}\n\n"
                    return

                # Execute each tool call and emit events
                lc_messages.append(response)
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

                    # Emit thinking status
                    thinking_label = tool_name.replace("_", " ").replace("get ", "").replace("tool ", "").strip().title()
                    yield f"data: {json.dumps({'type': 'thinking', 'content': thinking_label})}\n\n"

                    fn = tool_fn_map.get(tool_name)
                    if fn:
                        try:
                            tool_result = fn(**tool_args) if tool_args else fn()
                        except Exception as e:
                            logger.warning("chat_stream() tool exception | tool=%s | error=%s", tool_name, e)
                            tool_result = f"Tool error: {e}"
                    else:
                        tool_result = f"Unknown tool: {tool_name}"

                    # If execute_python was called, extract any CHART_JSON lines and
                    # emit them as chart events before the tool_call event.
                    tool_result_str = str(tool_result)
                    if tool_name == "execute_python":
                        chart_specs, tool_result_str = _extract_chart_specs(tool_result_str)
                        for spec in chart_specs:
                            yield f"data: {json.dumps({'type': 'chart', 'spec': spec})}\n\n"

                    # Emit tool_call event with input and truncated output
                    tool_input_str = json.dumps(tool_args) if tool_args else ""
                    tool_output_str = tool_result_str
                    # Truncate output to keep SSE events manageable (max 2000 chars)
                    if len(tool_output_str) > 2000:
                        tool_output_str = tool_output_str[:2000] + "…"
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': tool_name, 'input': tool_input_str, 'output': tool_output_str})}\n\n"

                    # Pass cleaned output (no CHART_JSON lines) back to the LLM
                    lc_messages.append(ToolMessage(content=tool_result_str, tool_call_id=tool_id))
                    tool_calls_made += 1

                # After all tools in this round complete, signal that the LLM is now reasoning
                yield f"data: {json.dumps({'type': 'thinking', 'content': 'Reasoning'})}\n\n"

            # Max rounds reached — get final answer without tools
            logger.warning("chat_stream() max tool rounds reached | user_id=%s | tools_called=%d", user_id, tool_calls_made)
            final_response = _invoke_with_retry(llm.invoke, lc_messages)
            reply = final_response.content if hasattr(final_response, "content") else str(final_response)
            if reply:
                chart_specs, reply = _extract_chart_specs(reply)
                for spec in chart_specs:
                    yield f"data: {json.dumps({'type': 'chart', 'spec': spec})}\n\n"
                reply = reply.strip()
                if reply:
                    yield f"data: {json.dumps({'type': 'token', 'content': reply})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'tokens_used': max(1, 1 + tool_calls_made), 'tools_called': tool_calls_made})}\n\n"

        except Exception as e:
            logger.exception("Chat stream error: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'content': f'I encountered an error: {str(e)}. Please try again.'})}\n\n"



# Module-level singleton
_chat_service: ChatService | None = None


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service

# Made with Bob
