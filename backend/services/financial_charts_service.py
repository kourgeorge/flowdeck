"""
Build chart-ready time series from Yahoo Finance financial statements.

All data is from yfinance (balance_sheet, cashflow, income_stmt). Used by the
fundamentals tab to show Historical Financials, Balance Sheet & Cash Flow trends,
and performance metrics.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import yfinance as yf

from data_layer.vendors.yf_session import get_yf_session

logger = logging.getLogger(__name__)


def _find_row(df, *candidates: str):
    """Return first row label that exists in df.index (case-insensitive partial match)."""
    if df is None or df.empty:
        return None
    idx_str = [str(i).lower() for i in df.index]
    for c in candidates:
        c_lower = c.lower()
        for i, s in enumerate(idx_str):
            if c_lower in s:
                return df.index[i]
    return None


def _series_for_row(df, row_label) -> List[Optional[float]]:
    """Extract values for a row across all date columns. Returns list of floats (or None)."""
    if df is None or df.empty or row_label is None:
        return []
    if row_label not in df.index:
        return []
    row = df.loc[row_label]
    out = []
    for _, v in row.items():
        try:
            if v is None or (isinstance(v, float) and (v != v)):  # NaN
                out.append(None)
            else:
                out.append(float(v))
        except (TypeError, ValueError):
            out.append(None)
    return out


def _period_to_key(p: str) -> str:
    """Normalize period string for alignment (YYYY or YYYY-MM)."""
    return p[:7] if len(p) >= 7 else p


def _align_series_to_periods(
    periods: List[str], df, row_label
) -> List[Optional[float]]:
    """Get values from df row, aligned to the given period list by date key."""
    if df is None or df.empty or row_label is None or row_label not in df.index:
        return [None] * len(periods)
    row = df.loc[row_label]
    key_to_val = {}
    for col, v in row.items():
        try:
            pk = _period_to_key(
                col.strftime("%Y-%m-%d")[:7] if hasattr(col, "strftime") else str(col)[:10]
            )
            key_to_val[pk] = float(v) if v is not None and not (isinstance(v, float) and (v != v)) else None
        except (TypeError, ValueError):
            pass
    return [key_to_val.get(_period_to_key(p)) for p in periods]


def _periods_from_df(df) -> List[str]:
    """Return list of period strings (YYYY or YYYY-MM) from dataframe columns."""
    if df is None or df.empty:
        return []
    out = []
    for c in df.columns:
        try:
            if hasattr(c, "strftime"):
                out.append(c.strftime("%Y-%m-%d")[:7] if hasattr(c, "month") else c.strftime("%Y"))
            else:
                out.append(str(c)[:10])
        except Exception:
            out.append(str(c))
    return out


def get_financial_charts(ticker: str, freq: str = "annual") -> Dict[str, Any]:
    """
    Fetch balance sheet, cashflow, and income statement from yfinance and return
    chart-ready series for the fundamentals tab.

    Returns:
        Dict with ticker, frequency, and chart data: historical_financials,
        shares_outstanding, long_term_debt_vs_fcf, retained_earnings,
        total_cash_vs_long_term_debt, accounts_receivable_vs_revenue,
        dividend_sustainability, performance_metrics.
    """
    ticker = ticker.upper()
    try:
        t = yf.Ticker(ticker, session=get_yf_session())
        if freq.lower() == "quarterly":
            bs = t.quarterly_balance_sheet
            cf = t.quarterly_cashflow
            inc = t.quarterly_income_stmt
        else:
            bs = t.balance_sheet
            cf = t.cashflow
            inc = t.income_stmt
    except Exception as e:
        logger.warning("Failed to fetch financials for %s: %s", ticker, e)
        return {
            "ticker": ticker,
            "frequency": freq,
            "error": str(e),
            "historical_financials": None,
            "shares_outstanding": None,
            "long_term_debt_vs_fcf": None,
            "retained_earnings": None,
            "total_cash_vs_long_term_debt": None,
            "accounts_receivable_vs_revenue": None,
            "dividend_sustainability": None,
            "performance_metrics": None,
        }

    def _align(periods: List[str], *value_lists: List[Optional[float]]):
        """All series share the same period list; ensure value lists match length."""
        n = len(periods)
        out = []
        for vl in value_lists:
            if len(vl) >= n:
                out.append(vl[:n])
            else:
                out.append(vl + [None] * (n - len(vl)))
        return out

    # Prefer income statement for period axis (usually has most dates)
    if not inc.empty:
        periods = _periods_from_df(inc)
    elif not bs.empty:
        periods = _periods_from_df(bs)
    elif not cf.empty:
        periods = _periods_from_df(cf)
    else:
        periods = []

    if not periods:
        return {
            "ticker": ticker,
            "frequency": freq,
            "error": "No financial statement data",
            "historical_financials": None,
            "shares_outstanding": None,
            "long_term_debt_vs_fcf": None,
            "retained_earnings": None,
            "total_cash_vs_long_term_debt": None,
            "accounts_receivable_vs_revenue": None,
            "dividend_sustainability": None,
            "performance_metrics": None,
        }

    # ---- Historical Financials (Revenue, Operating Income, EPS) ----
    rev_row = _find_row(inc, "Total Revenue", "Operating Revenue", "Revenue")
    op_inc_row = _find_row(inc, "Total Operating Income As Reported", "Operating Income", "EBIT")
    eps_row = _find_row(inc, "Diluted EPS", "Basic EPS")
    revenue = _align_series_to_periods(periods, inc, rev_row) if rev_row else [None] * len(periods)
    operating_income = _align_series_to_periods(periods, inc, op_inc_row) if op_inc_row else [None] * len(periods)
    eps = _align_series_to_periods(periods, inc, eps_row) if eps_row else [None] * len(periods)
    historical_financials = {
        "periods": periods,
        "revenue": revenue,
        "operating_income": operating_income,
        "eps": eps,
    }

    # ---- Shares Outstanding ----
    shares_row = _find_row(bs, "Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding")
    if not shares_row and not inc.empty:
        shares_row = _find_row(inc, "Diluted Average Shares", "Basic Average Shares")
    if shares_row and bs is not None and not bs.empty:
        shares_vals = _align_series_to_periods(periods, bs, shares_row)
    elif shares_row and inc is not None and not inc.empty:
        shares_vals = _align_series_to_periods(periods, inc, shares_row)
    else:
        shares_vals = [None] * len(periods)
    shares_outstanding = {"periods": periods, "values": shares_vals}

    # ---- Long Term Debt vs Free Cash Flow ----
    ltd_row = _find_row(bs, "Long Term Debt And Capital Lease Obligation", "Long Term Debt", "Total Debt")
    fcf_row = _find_row(cf, "Free Cash Flow")
    ltd_vals = _align_series_to_periods(periods, bs, ltd_row) if ltd_row else [None] * len(periods)
    fcf_vals = _align_series_to_periods(periods, cf, fcf_row) if fcf_row else [None] * len(periods)
    long_term_debt_vs_fcf = {
        "periods": periods,
        "long_term_debt": ltd_vals,
        "free_cash_flow": fcf_vals,
    }

    # ---- Retained Earnings ----
    re_row = _find_row(bs, "Retained Earnings")
    re_vals = _align_series_to_periods(periods, bs, re_row) if re_row else [None] * len(periods)
    retained_earnings = {"periods": periods, "values": re_vals}

    # ---- Total Cash vs Long Term Debt ----
    cash_row = _find_row(bs, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")
    cash_vals = _align_series_to_periods(periods, bs, cash_row) if cash_row else [None] * len(periods)
    ltd_vals2 = _align_series_to_periods(periods, bs, ltd_row) if ltd_row else [None] * len(periods)
    total_cash_vs_long_term_debt = {
        "periods": periods,
        "total_cash": cash_vals,
        "long_term_debt": ltd_vals2,
    }

    # ---- Accounts Receivable vs Revenue ----
    ar_row = _find_row(bs, "Accounts Receivable", "Receivables", "Current Net Receivables")
    ar_vals = _align_series_to_periods(periods, bs, ar_row) if ar_row else [None] * len(periods)
    rev_vals = _align_series_to_periods(periods, inc, rev_row) if rev_row else [None] * len(periods)
    accounts_receivable_vs_revenue = {
        "periods": periods,
        "accounts_receivable": ar_vals,
        "revenue": rev_vals,
    }

    # ---- Dividend Sustainability (Dividends Paid vs Free Cash Flow) ----
    div_row = _find_row(cf, "Cash Dividends Paid", "Common Stock Dividend Paid", "Dividend Payout")
    div_vals = _align_series_to_periods(periods, cf, div_row) if div_row else [None] * len(periods)
    fcf_vals2 = _align_series_to_periods(periods, cf, fcf_row) if fcf_row else [None] * len(periods)
    dividend_sustainability = {
        "periods": periods,
        "dividends_paid": div_vals,
        "free_cash_flow": fcf_vals2,
    }

    # ---- Performance Metrics (Gross Margin %, Pretax Margin %, ROIC-like) ----
    gross_row = _find_row(inc, "Gross Profit")
    pretax_row = _find_row(inc, "Pretax Income", "Tax Provision")
    net_income_row = _find_row(inc, "Net Income Common Stockholders", "Net Income From Continuing Operation Net Minority Interest", "Net Income")
    gross_vals = _align_series_to_periods(periods, inc, gross_row) if gross_row else [None] * len(periods)
    pretax_vals = _align_series_to_periods(periods, inc, pretax_row) if pretax_row else [None] * len(periods)
    rev_for_margin = _align_series_to_periods(periods, inc, rev_row) if rev_row else [None] * len(periods)
    invested_row = _find_row(bs, "Invested Capital", "Total Capitalization")
    invested_vals = _align_series_to_periods(periods, bs, invested_row) if invested_row else [None] * len(periods)
    ni_vals = _align_series_to_periods(periods, inc, net_income_row) if net_income_row else [None] * len(periods)
    gross_pct = []
    pretax_pct = []
    roic_pct = []
    for i in range(len(periods)):
        r = rev_for_margin[i] if i < len(rev_for_margin) and rev_for_margin[i] else None
        g = gross_vals[i] if i < len(gross_vals) else None
        p = pretax_vals[i] if i < len(pretax_vals) else None
        inv = invested_vals[i] if i < len(invested_vals) else None
        ni = ni_vals[i] if i < len(ni_vals) else None
        gross_pct.append(round(100 * g / r, 2) if r and g and r != 0 else None)
        pretax_pct.append(round(100 * p / r, 2) if r and p and r != 0 else None)
        roic_pct.append(round(100 * ni / inv, 2) if inv and ni and inv != 0 else None)
    performance_metrics = {
        "periods": periods,
        "gross_margin_pct": gross_pct,
        "pretax_margin_pct": pretax_pct,
        "roic_pct": roic_pct,
    }

    return {
        "ticker": ticker,
        "frequency": freq,
        "historical_financials": historical_financials,
        "shares_outstanding": shares_outstanding,
        "long_term_debt_vs_fcf": long_term_debt_vs_fcf,
        "retained_earnings": retained_earnings,
        "total_cash_vs_long_term_debt": total_cash_vs_long_term_debt,
        "accounts_receivable_vs_revenue": accounts_receivable_vs_revenue,
        "dividend_sustainability": dividend_sustainability,
        "performance_metrics": performance_metrics,
    }
