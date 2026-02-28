"""
Data API: canonical REST API for raw market data and report access.

Single source of truth for all market/fundamental data. Used by:
- Dashboard UI (via /api/data/*)
- AI agents (via /api/data/*)

All data flows through InfoFetcher. Report endpoints expose ReportService for agents.
Blocking engine calls run in thread pool (non-blocking event loop).
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from services.edgar_service import get_edgar_service
from services.info_fetcher import get_info_fetcher
from services.report_service import ReportService


class ReportsBatchBody(BaseModel):
    tickers: List[str] = []


router = APIRouter(tags=["Data API"])


def _engine():
    return get_info_fetcher()


@router.get("/quote/{ticker}")
async def data_quote(ticker: str):
    """Get current market quote for a ticker."""
    result = await asyncio.to_thread(_engine().get_quote, ticker)
    if result is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    return result


@router.get("/news")
async def data_news(
    ticker: str = Query(..., description="Ticker symbol"),
    vendor: Optional[str] = Query(None, description="News vendor (e.g. yfinance, alpha_vantage)"),
    lookback_days: int = Query(7, ge=1, le=90, description="Days to look back"),
):
    """Get news articles for a ticker."""
    engine = _engine()
    return await asyncio.to_thread(
        lambda: engine.get_news(ticker, vendor=vendor, lookback_days=lookback_days)
    )


@router.get("/insider-transactions/{ticker}")
async def data_insider_transactions(
    ticker: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of insider transactions to return"),
):
    """Get latest insider transactions for a ticker."""
    return await asyncio.to_thread(_engine().get_insider_transactions, ticker, limit)


@router.get("/company/{ticker}")
async def data_company(ticker: str):
    """Get company profile (name, sector, industry, exchange, country, website)."""
    return await asyncio.to_thread(_engine().get_company_info, ticker)


@router.get("/extended-info/{ticker}")
async def data_extended(ticker: str):
    """Get extended metrics (beta, market cap, margins, PE, etc.)."""
    return await asyncio.to_thread(_engine().get_extended_info, ticker)


@router.get("/fund-info/{ticker}")
async def data_fund_info(ticker: str):
    """Get ETF/fund-specific data (AUM, expense ratio, category, holdings, sector weightings)."""
    return await asyncio.to_thread(_engine().get_fund_info, ticker)


@router.get("/fundamentals/{ticker}")
async def data_fundamentals(ticker: str):
    """Get fundamental data for a ticker."""
    return await asyncio.to_thread(_engine().get_fundamentals, ticker)


@router.get("/financial-statements/{ticker}")
async def data_financial_statements(
    ticker: str,
    statement_type: str = Query("all", description="all | balance_sheet | cashflow | income_statement"),
    freq: str = Query("quarterly", description="quarterly | annual"),
):
    """Get balance sheet, cashflow, and/or income statement."""
    engine = _engine()
    return await asyncio.to_thread(
        lambda: engine.get_financial_statements(ticker, statement_type=statement_type, freq=freq)
    )


@router.get("/financial-charts/{ticker}")
async def data_financial_charts(
    ticker: str,
    freq: str = Query("annual", description="annual | quarterly"),
):
    """Get chart-ready time series for fundamentals (Revenue, EPS, Debt, FCF, etc.)."""
    return await asyncio.to_thread(_engine().get_financial_charts, ticker, freq)


@router.get("/historical/{ticker}")
async def data_historical(
    ticker: str,
    period: str = Query("6mo", description="1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max"),
    interval: str = Query("1d", description="1m, 2m, 5m, 15m, 30m, 60m, 1d, 5d, 1wk, 1mo, 3mo"),
):
    """Get historical OHLCV price data."""
    return await asyncio.to_thread(_engine().get_historical, ticker, period, interval)


@router.get("/ticker-data/{ticker}")
async def data_stock_data(
    ticker: str,
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD"),
):
    """Get OHLCV time series as text (for agents). Returns CSV-like string."""
    data = await asyncio.to_thread(_engine().get_stock_data, ticker, start_date, end_date)
    return {"ticker": ticker.upper(), "start_date": start_date, "end_date": end_date, "data": data}


@router.get("/analyst-recommendations/{ticker}")
async def data_analyst_recommendations(ticker: str):
    """Get analyst recommendations from Yahoo Finance."""
    return await asyncio.to_thread(_engine().get_analyst_recommendations, ticker)


@router.get("/future-events/{ticker}")
async def data_future_events(ticker: str):
    """Get upcoming earnings and ex-dividend dates (Yahoo Finance)."""
    try:
        return await asyncio.to_thread(_engine().get_future_events, ticker)
    except Exception as e:
        return {"ticker": ticker.upper(), "events": [], "count": 0, "error": str(e)}


@router.get("/edgar-filings/{ticker}")
async def data_edgar_filings(ticker: str):
    """Get recent 10-K and 10-Q SEC EDGAR filings for a ticker. Returns empty filings if not in EDGAR or on error."""
    engine = get_edgar_service()
    return await asyncio.to_thread(engine.get_filings, ticker)


@router.get("/edgar-filing-content/{ticker}")
async def data_edgar_filing_content(
    ticker: str,
    form: Optional[str] = Query(None, description="10-K or 10-Q"),
    limit: int = Query(1, ge=1, le=5, description="Max number of filings"),
    _current_user=Depends(get_current_user),
):
    """Get extracted SEC EDGAR sections (risk factors, MD&A, competition) for a ticker. Requires authentication and LLM (OpenAI or Azure)."""
    engine = get_edgar_service()
    return await asyncio.to_thread(engine.get_filing_content, ticker, form, limit)


# --- Report access for AI agents (portfolio deep research, etc.) ---

_report_service: Optional[ReportService] = None


def _get_report_service() -> ReportService:
    global _report_service
    if _report_service is None:
        _report_service = ReportService()
    return _report_service


@router.get("/reports/{ticker}")
async def data_reports_ticker(
    ticker: str,
    _current_user=Depends(get_current_user),
):
    """Get latest reports for one ticker. Requires authentication. Returns report_date and reports dict (report_type -> content, score, key_takeaways, etc.)."""
    svc = _get_report_service()
    report_date = await asyncio.to_thread(svc.get_latest_report_date, ticker.upper())
    if not report_date:
        return {"report_date": None, "reports": {}}
    reports = await asyncio.to_thread(svc.get_reports_with_scores, ticker.upper(), report_date)
    return {"report_date": report_date, "reports": reports}


@router.post("/reports/batch")
async def data_reports_batch(
    body: ReportsBatchBody,
    _current_user=Depends(get_current_user),
):
    """Get latest reports for multiple tickers. Requires authentication. Body: { \"tickers\": [\"AAPL\", \"MSFT\", ...] }. Returns tickers -> { report_date, reports }."""
    tickers = [str(t).upper() for t in (body.tickers or []) if t][:50]
    svc = _get_report_service()
    result = {}
    for t in tickers:
        report_date = await asyncio.to_thread(svc.get_latest_report_date, t)
        if not report_date:
            result[t] = {"report_date": None, "reports": {}}
        else:
            reports = await asyncio.to_thread(svc.get_reports_with_scores, t, report_date)
            result[t] = {"report_date": report_date, "reports": reports}
    return {"tickers": result}
