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


def _ticker_not_found_detail(ticker: str) -> str:
    """Standard 404 detail when a ticker does not exist (quote/data not found)."""
    return f"Ticker '{ticker}' not found. Check the symbol and try again."


async def _ensure_ticker_exists(ticker: str) -> None:
    """Raise 404 with standard detail if the ticker has no quote (does not exist)."""
    t = ticker.upper()
    quote = await asyncio.to_thread(_engine().get_quote, t)
    if quote is None:
        raise HTTPException(status_code=404, detail=_ticker_not_found_detail(t))


@router.get("/quote/{ticker}")
async def data_quote(ticker: str):
    """Get current market quote for a ticker."""
    result = await asyncio.to_thread(_engine().get_quote, ticker)
    if result is None:
        raise HTTPException(status_code=404, detail=_ticker_not_found_detail(ticker))
    return result


@router.get("/market-movers")
async def data_market_movers(
    count: int = Query(25, ge=1, le=100, description="Number of gainers and losers to return (each)"),
):
    """Get daily top gainers and losers (US market) from Yahoo Finance via yahooquery Screener."""
    return await asyncio.to_thread(_engine().get_daily_market_movers, count)


@router.get("/market-overview")
async def data_market_overview(
    limit_indices: int = Query(6, ge=1, le=100),
    offset_indices: int = Query(0, ge=0),
    limit_sectors: int = Query(10, ge=1, le=100),
    offset_sectors: int = Query(0, ge=0),
    limit_regions: int = Query(8, ge=1, le=100),
    offset_regions: int = Query(0, ge=0),
    limit_commodities: int = Query(12, ge=1, le=100),
    offset_commodities: int = Query(0, ge=0),
    range_: str = Query("1d", alias="range", description="1d, 1w, 1mo, 3mo, ytd"),
):
    """Get market overview: US indices, sectors, regional ETFs, and commodities with price and change. Pagination per group. range: 1d, 1w, 1mo, 3mo, ytd."""
    engine = _engine()
    return await asyncio.to_thread(
        engine.get_market_overview,
        limit_indices,
        offset_indices,
        limit_sectors,
        offset_sectors,
        limit_regions,
        offset_regions,
        limit_commodities,
        offset_commodities,
        range_,
    )


@router.get("/market-overview/section")
async def data_market_overview_section(
    section: str = Query(
        ...,
        description="Section to fetch: indices | sectors | regions | commodities",
    ),
    limit: int = Query(6, ge=1, le=100),
    offset: int = Query(0, ge=0),
    range_: str = Query("1d", alias="range", description="1d, 1w, 1mo, 3mo, ytd"),
):
    """
    Get a single section of the market overview (indices, sectors, regions, commodities).

    Returns a compact payload:
    {
      \"section\": \"indices\" | \"sectors\" | \"regions\" | \"commodities\",
      \"items\": [...],
      \"total\": int
    }
    """
    engine = _engine()
    return await asyncio.to_thread(
        engine.get_market_overview_section,
        section,
        limit,
        offset,
        range_,
    )


@router.get("/news")
async def data_news(
    ticker: str = Query(..., description="Ticker symbol"),
    vendor: Optional[str] = Query(None, description="News vendor (e.g. yfinance, alpha_vantage)"),
    lookback_days: int = Query(7, ge=1, le=90, description="Days to look back"),
):
    """Get news articles for a ticker."""
    await _ensure_ticker_exists(ticker)
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
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_engine().get_insider_transactions, ticker, limit)


@router.get("/company/{ticker}")
async def data_company(ticker: str):
    """Get company profile (name, sector, industry, exchange, country, website)."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_engine().get_company_info, ticker)


@router.get("/extended-info/{ticker}")
async def data_extended(ticker: str):
    """Get extended metrics (beta, market cap, margins, PE, etc.)."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_engine().get_extended_info, ticker)


@router.get("/fund-info/{ticker}")
async def data_fund_info(ticker: str):
    """Get ETF/fund-specific data (AUM, expense ratio, category, holdings, sector weightings)."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_engine().get_fund_info, ticker)


@router.get("/fundamentals/{ticker}")
async def data_fundamentals(ticker: str):
    """Get fundamental data for a ticker."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_engine().get_fundamentals, ticker)


@router.get("/financial-statements/{ticker}")
async def data_financial_statements(
    ticker: str,
    statement_type: str = Query("all", description="all | balance_sheet | cashflow | income_statement"),
    freq: str = Query("quarterly", description="quarterly | annual"),
):
    """Get balance sheet, cashflow, and/or income statement."""
    await _ensure_ticker_exists(ticker)
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
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_engine().get_financial_charts, ticker, freq)


@router.get("/historical/{ticker}")
async def data_historical(
    ticker: str,
    period: str = Query("6mo", description="1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max"),
    interval: str = Query("1d", description="1m, 2m, 5m, 15m, 30m, 60m, 1d, 5d, 1wk, 1mo, 3mo"),
):
    """Get historical OHLCV price data."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_engine().get_historical, ticker, period, interval)


@router.get("/ticker-data/{ticker}")
async def data_ticker_data(
    ticker: str,
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD"),
):
    """Get OHLCV time series as text (for agents). Returns CSV-like string."""
    await _ensure_ticker_exists(ticker)
    data = await asyncio.to_thread(_engine().get_ticker_data, ticker, start_date, end_date)
    return {"ticker": ticker.upper(), "start_date": start_date, "end_date": end_date, "data": data}


@router.get("/analyst-recommendations/{ticker}")
async def data_analyst_recommendations(ticker: str):
    """Get analyst recommendations from YahooQuery."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_engine().get_analyst_recommendations, ticker)


@router.get("/future-events/{ticker}")
async def data_future_events(ticker: str):
    """Get upcoming earnings and ex-dividend dates (Yahoo Finance)."""
    await _ensure_ticker_exists(ticker)
    try:
        return await asyncio.to_thread(_engine().get_future_events, ticker)
    except Exception as e:
        return {"ticker": ticker.upper(), "events": [], "count": 0, "error": str(e)}

@router.get("/similar-tickers/{ticker}")
async def data_similar_tickers(
    ticker: str,
    limit: int = Query(10, ge=1, le=50, description="Maximum number of similar tickers to return"),
    offset: int = Query(0, ge=0, description="Result offset for pagination"),
):
    """Get similar tickers based on sector/industry matching."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_engine().get_similar_tickers, ticker, limit, offset)

@router.get("/company-officers/{ticker}")
async def data_company_officers(ticker: str):
    """Get company officers/management team from Yahoo Finance."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_engine().get_company_officers, ticker)




@router.get("/edgar-filings/{ticker}")
async def data_edgar_filings(ticker: str):
    """Get recent 10-K and 10-Q SEC EDGAR filings for a ticker. Returns empty filings if not in EDGAR or on error."""
    await _ensure_ticker_exists(ticker)
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
    await _ensure_ticker_exists(ticker)
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
    await _ensure_ticker_exists(ticker)
    svc = _get_report_service()
    latest = await asyncio.to_thread(svc.get_latest_analysis_run, ticker.upper())
    if not latest:
        return {"report_run_id": None, "report_date": None, "reports": {}}
    ar_id, date_display = latest
    reports = await asyncio.to_thread(svc.get_reports_with_scores, ticker.upper(), ar_id)
    return {"report_run_id": ar_id, "report_date": date_display, "reports": reports}


@router.post("/reports/batch")
async def data_reports_batch(
    body: ReportsBatchBody,
    _current_user=Depends(get_current_user),
):
    """Get latest reports for multiple tickers. Requires authentication. Body: { \"tickers\": [\"AAPL\", \"MSFT\", ...] }. Returns tickers -> { report_date, reports }."""
    tickers = [str(t).upper() for t in (body.tickers or []) if t][:50]
    for t in tickers:
        await _ensure_ticker_exists(t)
    svc = _get_report_service()
    result = {}
    for t in tickers:
        latest = await asyncio.to_thread(svc.get_latest_analysis_run, t)
        if not latest:
            result[t] = {"report_run_id": None, "report_date": None, "reports": {}}
        else:
            ar_id, date_display = latest
            reports = await asyncio.to_thread(svc.get_reports_with_scores, t, ar_id)
            result[t] = {"report_run_id": ar_id, "report_date": date_display, "reports": reports}
    return {"tickers": result}
