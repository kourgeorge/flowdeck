"""
Financial statement tools:
  - FundamentalsTool    — key valuation metrics (P/E, EPS, margins, etc.)
  - BalanceSheetTool    — assets, liabilities, equity, debt
  - CashflowTool        — operating/free cash flow, capex
  - IncomeStatementTool — revenue, gross profit, net income, EPS
"""

from __future__ import annotations

from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult, ToolSpec

# ---------------------------------------------------------------------------
# FundamentalsTool
# ---------------------------------------------------------------------------

_FUNDAMENTALS_SPEC = ToolSpec(
    name="get_fundamentals",
    version="1.0",
    description=(
        "Get key fundamental financial metrics for a ticker: P/E ratio, forward P/E, EPS (trailing/forward), "
        "market cap, enterprise value, revenue, gross margin, profit margin, operating margin, EBITDA, "
        "dividend yield, beta, and sector/industry. "
        "Use when the user asks about valuation, profitability, or financial health."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
        },
        "required": ["ticker"],
    },
    tags=["fundamentals", "valuation", "financials"],
)


class FundamentalsTool(BaseTool):
    spec = _FUNDAMENTALS_SPEC

    def execute(self, ctx: ExecutionContext, *, ticker: str, **_) -> ToolResult:
        try:
            from ai_engine.tradingagents.agents.utils.fundamental_data_tools import get_fundamentals
            data = get_fundamentals.invoke({"ticker": ticker.upper()})
            return ToolResult(ok=True, data=data)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


# ---------------------------------------------------------------------------
# BalanceSheetTool
# ---------------------------------------------------------------------------

_BALANCE_SHEET_SPEC = ToolSpec(
    name="get_balance_sheet",
    version="1.0",
    description=(
        "Get the balance sheet for a ticker: total assets, total liabilities, shareholders equity, "
        "cash and equivalents, total debt, and working capital. "
        "Use when the user asks about financial strength, debt levels, or liquidity."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
        },
        "required": ["ticker"],
    },
    tags=["fundamentals", "balance-sheet", "financials"],
)


class BalanceSheetTool(BaseTool):
    spec = _BALANCE_SHEET_SPEC

    def execute(self, ctx: ExecutionContext, *, ticker: str, **_) -> ToolResult:
        try:
            from ai_engine.tradingagents.agents.utils.fundamental_data_tools import get_balance_sheet
            data = get_balance_sheet.invoke({"ticker": ticker.upper()})
            return ToolResult(ok=True, data=data)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


# ---------------------------------------------------------------------------
# CashflowTool
# ---------------------------------------------------------------------------

_CASHFLOW_SPEC = ToolSpec(
    name="get_cashflow",
    version="1.0",
    description=(
        "Get the cash flow statement for a ticker: operating cash flow, free cash flow, "
        "capital expenditures, investing activities, and financing activities. "
        "Use when the user asks about cash generation, free cash flow, or capital allocation."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
        },
        "required": ["ticker"],
    },
    tags=["fundamentals", "cashflow", "financials"],
)


class CashflowTool(BaseTool):
    spec = _CASHFLOW_SPEC

    def execute(self, ctx: ExecutionContext, *, ticker: str, **_) -> ToolResult:
        try:
            from ai_engine.tradingagents.agents.utils.fundamental_data_tools import get_cashflow
            data = get_cashflow.invoke({"ticker": ticker.upper()})
            return ToolResult(ok=True, data=data)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


# ---------------------------------------------------------------------------
# IncomeStatementTool
# ---------------------------------------------------------------------------

_INCOME_STATEMENT_SPEC = ToolSpec(
    name="get_income_statement",
    version="1.0",
    description=(
        "Get the income statement for a ticker: revenue, cost of goods sold, gross profit, "
        "operating income, net income, and EPS. "
        "Use when the user asks about revenue growth, earnings, or profitability trends."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA"}
        },
        "required": ["ticker"],
    },
    tags=["fundamentals", "income", "financials"],
)


class IncomeStatementTool(BaseTool):
    spec = _INCOME_STATEMENT_SPEC

    def execute(self, ctx: ExecutionContext, *, ticker: str, **_) -> ToolResult:
        try:
            from ai_engine.tradingagents.agents.utils.fundamental_data_tools import get_income_statement
            data = get_income_statement.invoke({"ticker": ticker.upper()})
            return ToolResult(ok=True, data=data)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


