"""
Data API: canonical REST API for raw market data and report access.

Single source of truth for all market/fundamental data. Used by:
- Dashboard UI (via /api/data/*)
- AI agents (via /api/data/*)

All data flows through DataGateway (market, reports, EDGAR sources).
Blocking engine calls run in thread pool (non-blocking event loop).
"""

import asyncio
import json
import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

from auth import get_current_user
from data_layer import get_data_gateway
from services.share_service import get_share_url

logger = logging.getLogger(__name__)


class ReportsBatchBody(BaseModel):
    tickers: List[str] = []


router = APIRouter(prefix="/api/data", tags=["Data API"])


def _gateway():
    return get_data_gateway()


def _ticker_not_found_detail(ticker: str) -> str:
    """Standard 404 detail when a ticker does not exist (quote/data not found)."""
    return f"Ticker '{ticker}' not found. Check the symbol and try again."


async def _ensure_ticker_exists(ticker: str) -> None:
    """Raise 404 with standard detail if the ticker has no quote (does not exist)."""
    t = ticker.upper()
    quote = await asyncio.to_thread(_gateway().get_quote, t)
    if quote is None:
        raise HTTPException(status_code=404, detail=_ticker_not_found_detail(t))


@router.get("/quote/{ticker}")
async def data_quote(ticker: str):
    """Get current market quote for a ticker."""
    result = await asyncio.to_thread(_gateway().get_quote, ticker)
    if result is None:
        raise HTTPException(status_code=404, detail=_ticker_not_found_detail(ticker))
    return result


@router.get("/market-rates")
async def data_market_rates():
    """
    Get current market rates including treasury yields and risk-free rate from FRED.
    
    Returns treasury rates used for valuation models (WACC, DCF).
    Data is cached for 24 hours to minimize API calls.
    """
    return await asyncio.to_thread(_gateway().get_market_rates)


@router.get("/market-movers")
async def data_market_movers(
    count: int = Query(8, ge=1, le=100, description="Number of gainers and losers to return (each)"),
):
    """Get daily top gainers and losers (US market) from Yahoo Finance via yahooquery Screener."""
    return await asyncio.to_thread(_gateway().get_daily_market_movers, count)


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
    range_: str = Query("1d", alias="range", description="1d, 1w, 1mo, 3mo, 6mo, ytd"),
) -> Dict[str, Any]:
    """Get market overview: US indices, sectors, regional ETFs, and commodities with price and change. Pagination per group. range: 1d, 1w, 1mo, 3mo, 6mo, ytd."""
    gw = _gateway()
    return await asyncio.to_thread(
        gw.get_market_overview,
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


# Max time for section overview (regions/1w with many tickers can be slow or hang on Yahoo).
MARKET_OVERVIEW_SECTION_TIMEOUT_SEC = 90


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
    logger.info("Market overview section requested: section=%s range=%s limit=%s offset=%s", section, range_, limit, offset)
    gw = _gateway()
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                gw.get_market_overview_section,
                section,
                limit,
                offset,
                range_,
            ),
            timeout=MARKET_OVERVIEW_SECTION_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Market overview section request timed out after {MARKET_OVERVIEW_SECTION_TIMEOUT_SEC}s. Try a different range or retry.",
        )


@router.get("/news")
async def data_news(
    ticker: str = Query(..., description="Ticker symbol"),
    vendor: Optional[str] = Query(None, description="News vendor (e.g. yfinance, alpha_vantage)"),
    lookback_days: int = Query(7, ge=1, le=90, description="Days to look back"),
):
    """Get news articles for a ticker."""
    await _ensure_ticker_exists(ticker)
    gw = _gateway()
    return await asyncio.to_thread(
        lambda: gw.get_news(ticker, vendor=vendor, lookback_days=lookback_days)
    )


@router.get("/news/batch")
async def data_news_batch(
    tickers: str = Query(..., description="Comma-separated ticker symbols (max 50)"),
    vendor: Optional[str] = Query(None, description="News vendor"),
    lookback_days: int = Query(7, ge=1, le=90, description="Days to look back"),
):
    """Get merged, deduped news for multiple tickers in one request. Each article has a 'tickers' list."""
    raw = [s.strip().upper() for s in tickers.split(",") if s.strip()]
    if not raw:
        return {"articles": [], "count": 0}
    tickers_list = raw[:50]
    gw = _gateway()
    return await asyncio.to_thread(
        lambda: gw.get_news_batch(tickers_list, vendor=vendor, lookback_days=lookback_days)
    )


@router.get("/news/batch/stream")
async def data_news_batch_stream(
    tickers: str = Query(..., description="Comma-separated ticker symbols (max 50)"),
    vendor: Optional[str] = Query(None, description="News vendor"),
    lookback_days: int = Query(7, ge=1, le=90, description="Days to look back"),
):
    """
    Stream news for multiple tickers as they become available.
    Returns newline-delimited JSON (NDJSON) with progressive updates.
    Each line is a JSON object with articles from completed tickers.
    """
    raw = [s.strip().upper() for s in tickers.split(",") if s.strip()]
    if not raw:
        async def empty_stream():
            yield json.dumps({"articles": [], "count": 0, "completed": True}) + "\n"
        return StreamingResponse(empty_stream(), media_type="application/x-ndjson")
    
    tickers_list = raw[:50]
    
    async def news_stream():
        """Stream news as each ticker completes."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        gw = _gateway()
        all_articles = []
        seen_uuids = set()
        completed_count = 0
        
        def fetch_one_ticker(ticker: str):
            try:
                return gw.get_news(ticker, vendor=vendor, lookback_days=lookback_days)
            except Exception as e:
                logger.warning(f"Failed to fetch news for {ticker}: {e}")
                return {"ticker": ticker, "articles": [], "count": 0, "error": str(e)}
        
        # Use ThreadPoolExecutor to fetch in parallel (increased from 8 to 16 workers)
        max_workers = min(16, len(tickers_list))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {
                executor.submit(fetch_one_ticker, ticker): ticker
                for ticker in tickers_list
            }
            
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    result = await asyncio.get_event_loop().run_in_executor(None, future.result)
                    completed_count += 1
                    
                    # Add new articles (dedupe by UUID)
                    new_articles = []
                    for article in result.get("articles", []):
                        uuid = article.get("uuid")
                        if uuid and uuid not in seen_uuids:
                            seen_uuids.add(uuid)
                            # Add ticker to article
                            article_with_ticker = {**article, "tickers": [ticker]}
                            new_articles.append(article_with_ticker)
                            all_articles.append(article_with_ticker)
                    
                    # Stream this batch immediately
                    if new_articles:
                        chunk = {
                            "articles": new_articles,
                            "count": len(new_articles),
                            "total_articles": len(all_articles),
                            "completed_tickers": completed_count,
                            "total_tickers": len(tickers_list),
                            "completed": completed_count == len(tickers_list)
                        }
                        yield json.dumps(chunk) + "\n"
                
                except Exception as e:
                    logger.error(f"Error processing news for {ticker}: {e}", exc_info=True)
        
        # Send final summary if no articles were streamed
        if completed_count == len(tickers_list) and not all_articles:
            yield json.dumps({
                "articles": [],
                "count": 0,
                "total_articles": 0,
                "completed_tickers": completed_count,
                "total_tickers": len(tickers_list),
                "completed": True
            }) + "\n"
    
    return StreamingResponse(news_stream(), media_type="application/x-ndjson")


@router.get("/insider-transactions/{ticker}")
async def data_insider_transactions(
    ticker: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of insider transactions to return"),
):
    """Get latest insider transactions for a ticker."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_gateway().get_insider_transactions, ticker, limit)


@router.get("/company/{ticker}")
async def data_company(ticker: str):
    """Get company profile (name, sector, industry, exchange, country, website)."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_gateway().get_company_info, ticker)


@router.get("/extended-info/{ticker}")
async def data_extended(ticker: str):
    """Get extended metrics (beta, market cap, margins, PE, etc.)."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_gateway().get_extended_info, ticker)


@router.get("/fund-info/{ticker}")
async def data_fund_info(ticker: str):
    """Get ETF/fund-specific data (AUM, expense ratio, category, holdings, sector weightings)."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_gateway().get_fund_info, ticker)


@router.get("/fundamentals/{ticker}")
async def data_fundamentals(ticker: str):
    """Get fundamental data for a ticker."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_gateway().get_fundamentals, ticker)


@router.get("/financial-statements/{ticker}")
async def data_financial_statements(
    ticker: str,
    statement_type: str = Query("all", description="all | balance_sheet | cashflow | income_statement"),
    freq: str = Query("quarterly", description="quarterly | annual"),
):
    """Get balance sheet, cashflow, and/or income statement."""
    await _ensure_ticker_exists(ticker)
    gw = _gateway()
    return await asyncio.to_thread(
        lambda: gw.get_financial_statements(ticker, statement_type=statement_type, freq=freq)
    )


@router.get("/financial-charts/{ticker}")
async def data_financial_charts(
    ticker: str,
    freq: str = Query("annual", description="annual | quarterly"),
):
    """Get chart-ready time series for fundamentals (Revenue, EPS, Debt, FCF, etc.)."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_gateway().get_financial_charts, ticker, freq)


@router.get("/historical/{ticker}")
async def data_historical(
    ticker: str,
    period: str = Query("6mo", description="1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max"),
    interval: str = Query("1d", description="1m, 2m, 5m, 15m, 30m, 60m, 1d, 5d, 1wk, 1mo, 3mo"),
):
    """Get historical OHLCV price data."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_gateway().get_historical, ticker, period, interval)


@router.get("/ticker-data/{ticker}")
async def data_ticker_data(
    ticker: str,
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD"),
):
    """Get OHLCV time series as text (for agents). Returns CSV-like string."""
    await _ensure_ticker_exists(ticker)
    data = await asyncio.to_thread(_gateway().get_ticker_data, ticker, start_date, end_date)
    return {"ticker": ticker.upper(), "start_date": start_date, "end_date": end_date, "data": data}


@router.get("/indicators/{ticker}")
async def data_indicators(
    ticker: str,
    indicator: str = Query(..., description="Indicator name (rsi, macd, macdh, etc.)"),
    curr_date: str = Query(..., description="Current date YYYY-MM-DD"),
    look_back_days: int = Query(30, ge=1, le=365, description="Days to look back"),
):
    """Get technical indicators (RSI, MACD, Bollinger Bands, etc.) for agents."""
    await _ensure_ticker_exists(ticker)
    data = await asyncio.to_thread(
        _gateway().get_indicators,
        ticker.upper(),
        indicator,
        curr_date,
        look_back_days,
    )
    return {"ticker": ticker.upper(), "indicator": indicator, "data": data}


@router.get("/global-news")
async def data_global_news(
    curr_date: str = Query(..., description="Current date YYYY-MM-DD"),
    lookback_days: int = Query(7, ge=1, le=90, description="Days to look back"),
    limit: int = Query(10, ge=1, le=50, description="Max articles to return"),
    query: Optional[str] = Query(None, description="Optional search focus"),
):
    """Get global/macro news for agents."""
    data = await asyncio.to_thread(
        _gateway().get_global_news,
        curr_date,
        lookback_days,
        limit,
        query,
    )
    return {"data": data}


@router.get("/insider-sentiment/{ticker}")
async def data_insider_sentiment(
    ticker: str,
    curr_date: str = Query(..., description="Current date YYYY-MM-DD"),
):
    """Get insider sentiment for a ticker (Finnhub)."""
    await _ensure_ticker_exists(ticker)
    data = await asyncio.to_thread(_gateway().get_insider_sentiment, ticker.upper(), curr_date)
    return {"ticker": ticker.upper(), "data": data}


@router.get("/reddit-company-social/{ticker}")
async def data_reddit_company_social(
    ticker: str,
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD"),
    search_terms: str = Query(..., description="Comma-separated terms to match (e.g. Apple,AAPL). Agent provides from get_quote/get_news."),
):
    """Get Reddit company social/discussion feed from finance subreddits. search_terms required (agent-provided)."""
    await _ensure_ticker_exists(ticker)
    terms = [t.strip() for t in search_terms.split(",") if t.strip()]
    if not terms:
        raise HTTPException(400, "search_terms must contain at least one non-empty term")
    data = await asyncio.to_thread(
        _gateway().get_reddit_company_social,
        ticker.upper(),
        start_date,
        end_date,
        terms,
    )
    return {"ticker": ticker.upper(), "data": data}


@router.get("/analyst-recommendations/{ticker}")
async def data_analyst_recommendations(ticker: str):
    """Get analyst recommendations from YahooQuery."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_gateway().get_analyst_recommendations, ticker)


@router.get("/events/{ticker}")
async def data_deterministic_events(
    ticker: str,
    lookback_days: int = Query(10, ge=1, le=365, description="Trailing days for price/technical event detection."),
):
    """Get deterministic technical and fundamental events for a ticker."""
    await _ensure_ticker_exists(ticker)
    try:
        from datetime import datetime, timezone

        from backend.processing import get_ticker_event_summary

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        result = await asyncio.to_thread(
            get_ticker_event_summary,
            _gateway(),
            ticker,
            as_of_date=today,
            price_technical_lookback_days=lookback_days,
        )
        return result.model_dump()
    except Exception as e:
        return {
            "ticker": ticker.upper(),
            "event_score": 0.0,
            "events": [],
            "dominant_events": [],
            "event_count": 0,
            "error": str(e),
        }

@router.get("/future-events/{ticker}")
async def data_future_events(ticker: str):
    """Get upcoming earnings and ex-dividend dates (Yahoo Finance)."""
    await _ensure_ticker_exists(ticker)
    try:
        return await asyncio.to_thread(_gateway().get_future_events, ticker)
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
    return await asyncio.to_thread(_gateway().get_similar_tickers, ticker, limit, offset)

@router.get("/company-officers/{ticker}")
async def data_company_officers(ticker: str):
    """Get company officers/management team from Yahoo Finance."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_gateway().get_company_officers, ticker)




@router.get("/edgar-filings/{ticker}")
async def data_edgar_filings(ticker: str):
    """Get recent 10-K and 10-Q SEC EDGAR filings for a ticker. Returns empty filings if not in EDGAR or on error."""
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_gateway().get_edgar_filings, ticker)


@router.get("/edgar-filing-content/{ticker}")
async def data_edgar_filing_content(
    ticker: str,
    form: Optional[str] = Query(None, description="10-K or 10-Q"),
    limit: int = Query(1, ge=1, le=5, description="Max number of filings"),
    raw: bool = Query(False, description="If true, return raw text for exploration instead of LLM-extracted sections"),
):
    """
    Get SEC EDGAR filing content.
    
    Args:
        ticker: Stock ticker symbol
        form: Optional form type filter (10-K or 10-Q)
        limit: Number of filings to return (default 1)
        raw: If true, return full filing text for agent exploration.
             If false, return LLM-extracted sections (current behavior, default).
    
    Returns:
        - raw=false: Extracted sections (risk_factors, mda, competition, etc.) via LLM
        - raw=true: Full filing text for agent-side exploration
    """
    await _ensure_ticker_exists(ticker)
    return await asyncio.to_thread(_gateway().get_edgar_filing_content, ticker, form, limit, raw)


# --- Report access for AI agents (portfolio deep research, etc.) ---


@router.get("/reports/{ticker}")
async def data_reports_ticker(
    ticker: str,
    date: Optional[str] = Query(
        None,
        description="Optional. YYYY-MM-DD or analysis_run_id to fetch a specific run. Omit for latest.",
    ),
    _current_user=Depends(get_current_user),
):
    """Get reports for one ticker. Requires authentication. Use ?date= to fetch a specific run (YYYY-MM-DD or run_id). Omit for latest."""
    await _ensure_ticker_exists(ticker)
    gw = _gateway()
    t = ticker.upper()
    ar_id: Optional[int] = None
    date_display: str = ""
    if date and date.strip():
        resolved = await asyncio.to_thread(gw.get_analysis_run_for_date, t, date.strip())
        if resolved:
            ar_id, date_display = resolved
    if ar_id is None:
        latest = await asyncio.to_thread(gw.get_latest_execution_for_ticker, t)
        if latest:
            ar_id, date_display = latest
    if ar_id is None:
        return {"report_run_id": None, "report_date": None, "reports": {}, "share_url": None}
    reports = await asyncio.to_thread(gw.get_reports_with_scores, ar_id)
    share_url = get_share_url(ar_id)
    return {"report_run_id": ar_id, "report_date": date_display, "reports": reports, "share_url": share_url}


@router.get("/reports/{ticker}/dates")
async def data_reports_ticker_dates(
    ticker: str,
    _current_user=Depends(get_current_user),
):
    """List available report dates for a ticker (newest first). Requires authentication."""
    await _ensure_ticker_exists(ticker)
    dates = await asyncio.to_thread(_gateway().list_report_dates, ticker.upper())
    return {"ticker": ticker.upper(), "dates": dates}


@router.post("/reports/batch")
async def data_reports_batch(
    body: ReportsBatchBody,
    _current_user=Depends(get_current_user),
):
    """Get latest reports for multiple tickers. Requires authentication. Body: { \"tickers\": [\"AAPL\", \"MSFT\", ...] }. Returns tickers -> { report_date, reports }."""
    tickers = [str(t).upper() for t in (body.tickers or []) if t][:50]
    gw = _gateway()
    for t in tickers:
        await _ensure_ticker_exists(t)
    result = {}
    for t in tickers:
        latest = await asyncio.to_thread(gw.get_latest_execution_for_ticker, t)
        if not latest:
            result[t] = {"report_run_id": None, "report_date": None, "reports": {}, "share_url": None}
        else:
            ar_id, date_display = latest
            reports = await asyncio.to_thread(gw.get_reports_with_scores, ar_id)
            share_url = get_share_url(ar_id)
            result[t] = {"report_run_id": ar_id, "report_date": date_display, "reports": reports, "share_url": share_url}
    return {"tickers": result}
