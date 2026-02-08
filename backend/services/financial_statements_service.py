"""
Single source of financial statements for the app.

Uses Yahoo Finance (yfinance) only. Served to both the dashboard UI and AI agents
via /api/data/financial-statements/{ticker}.
No dependency on tradingagents for this data.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import yfinance as yf

logger = logging.getLogger(__name__)


def _row_to_key(name: str) -> str:
    """Convert yfinance row label to camelCase key for API/UI (e.g. 'Long Term Debt' -> 'longTermDebt')."""
    if not name or not isinstance(name, str):
        return ""
    parts = name.strip().split()
    if not parts:
        return ""
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])


def _dataframe_to_reports(df) -> List[Dict[str, Any]]:
    """Convert a yfinance statement DataFrame to list of report dicts (one per date column)."""
    if df is None or df.empty:
        return []
    reports = []
    for col in df.columns:
        try:
            date_str = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)[:10]
        except Exception:
            date_str = str(col)[:10]
        report: Dict[str, Any] = {"fiscalDateEnding": date_str}
        for idx in df.index:
            key = _row_to_key(str(idx))
            if not key:
                continue
            val = df.loc[idx, col]
            if val is None or (isinstance(val, float) and (val != val)):
                report[key] = None
            else:
                try:
                    report[key] = int(val) if isinstance(val, (int, float)) and float(val) == int(val) else float(val)
                except (TypeError, ValueError):
                    report[key] = val
        reports.append(report)
    return reports


def get_financial_statements(
    ticker: str,
    statement_type: str = "all",
    freq: str = "quarterly",
) -> Dict[str, Any]:
    """
    Fetch balance sheet, cash flow, and income statement from Yahoo Finance.
    Returns the same shape expected by the UI and agents: statements with
    annualReports and quarterlyReports (both always included so UI can toggle).
    """
    ticker = ticker.upper()
    from datetime import datetime
    curr_date = datetime.now().strftime("%Y-%m-%d")
    result = {
        "ticker": ticker,
        "date": curr_date,
        "frequency": freq,
        "statements": {},
    }
    try:
        t = yf.Ticker(ticker)
        bs_ann = t.balance_sheet
        bs_qtr = t.quarterly_balance_sheet
        cf_ann = t.cashflow
        cf_qtr = t.quarterly_cashflow
        inc_ann = t.income_stmt
        inc_qtr = t.quarterly_income_stmt
    except Exception as e:
        logger.warning("Failed to fetch financial statements for %s: %s", ticker, e)
        for key in ["balance_sheet", "cashflow", "income_statement"]:
            if statement_type in ("all", key):
                result["statements"][key] = {"format": "error", "data": str(e)}
        return result

    def add_statement(key: str, df_annual, df_quarterly) -> None:
        if statement_type not in ("all", key):
            return
        annual = _dataframe_to_reports(df_annual)
        quarterly = _dataframe_to_reports(df_quarterly)
        result["statements"][key] = {
            "format": "json",
            "data": {"annualReports": annual, "quarterlyReports": quarterly},
        }

    add_statement("balance_sheet", bs_ann, bs_qtr)
    add_statement("cashflow", cf_ann, cf_qtr)
    add_statement("income_statement", inc_ann, inc_qtr)

    return result
