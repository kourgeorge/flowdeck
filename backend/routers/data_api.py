"""
Data API: canonical REST API for raw market data.

Single source of truth for all market/fundamental data. Used by:
- Dashboard UI (via /api/data/*)
- AI agents (via /api/data/*)

All data flows through InfoFetcher. No AI reports or UI-specific aggregations.
Blocking engine calls run in thread pool (non-blocking event loop).
"""

import asyncio

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from services.info_fetcher import get_info_fetcher
from services.edgar_service import get_edgar_service

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


@router.get("/stock-data/{ticker}")
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
    return await asyncio.to_thread(_engine().get_future_events, ticker)


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
):
    """Get extracted SEC EDGAR sections (risk factors, MD&A, competition) for a ticker. Requires LLM (OpenAI or Azure)."""
    engine = get_edgar_service()
    return await asyncio.to_thread(engine.get_filing_content, ticker, form, limit)
