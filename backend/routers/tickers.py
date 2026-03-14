"""Ticker widgets, ticker page, and historical reports by run."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth import get_current_user_optional
from config import MAJOR_TICKERS
from database import get_db
from models.schemas import (
    ReportData,
    ReportScoreSummary,
    TickerPageData,
    TickerQuote,
    TickerWidget,
    WidgetsResponse,
    Recommendation,
    HistoricalAnalysis,
)
from data_layer import get_data_gateway
from services import token_service
from services.share_service import get_share_url

router = APIRouter(prefix="/api/tickers", tags=["tickers"])


def _normalize_confidence(value: object) -> Optional[float]:
    """Return normalized confidence only when it is a valid 0-1 numeric value."""
    if not isinstance(value, (int, float)):
        return None
    confidence = float(value)
    if 0.0 <= confidence <= 1.0:
        return confidence
    return None


def _normalize_score_confidence(value: object) -> Optional[float]:
    """Convert a 0-10 score to normalized confidence (0-1)."""
    if not isinstance(value, (int, float)):
        return None
    score = float(value)
    if 0.0 <= score <= 10.0:
        return score / 10.0
    return None


def _extract_confidence(*metas: object) -> Optional[float]:
    """Pick first available confidence from metadata, with score/10 fallback."""
    for meta in metas:
        if not isinstance(meta, dict):
            continue
        confidence = _normalize_confidence(meta.get("confidence"))
        if confidence is not None:
            return confidence
        confidence_from_score = _normalize_score_confidence(meta.get("score"))
        if confidence_from_score is not None:
            return confidence_from_score
    return None


def _get_ticker_widgets_sync(
    tickers: Optional[str],
    date: Optional[str],
    only_date: bool = False,
    limit: Optional[int] = None,
    offset: int = 0,
    recent_days: Optional[int] = None,
) -> WidgetsResponse:
    """Sync implementation of widget data (runs in thread pool to avoid blocking event loop)."""
    gw = get_data_gateway()
    use_major_split = False
    major_set: set[str] = set()
    total_count: Optional[int] = None
    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
    else:
        report_date = date or datetime.now().strftime("%Y-%m-%d")
        recent_window_days = recent_days if recent_days and recent_days > 1 else None
        if only_date and limit is not None:
            if recent_window_days:
                ticker_list, total_count = gw.get_tickers_with_reports_for_recent_days_paginated(
                    report_date, recent_window_days, limit, offset
                )
            else:
                ticker_list, total_count = gw.get_tickers_with_reports_for_date_paginated(
                    report_date, limit, offset
                )
        else:
            if only_date:
                if recent_window_days:
                    tickers_for_date = gw.get_tickers_with_reports_for_recent_days(
                        report_date, recent_window_days
                    )
                else:
                    tickers_for_date = gw.get_tickers_with_reports_for_date(report_date)
                ticker_list = [t.upper() for t in tickers_for_date]
            else:
                major_set = {t.upper() for t in MAJOR_TICKERS}
                ticker_list = list(MAJOR_TICKERS)
                use_major_split = True

    widgets = []
    quotes_dict = {}
    try:
        quotes_dict = gw.get_quotes_batch(ticker_list)
    except Exception as e:
        print(f"Warning: Failed to fetch market quotes: {e}")

    company_names: dict[str, Optional[str]] = {}
    try:
        company_infos = gw.get_company_info_batch(ticker_list)
        company_names = {
            t: (company_infos.get(t) or {}).get("name") or None
            for t in ticker_list
        }
    except Exception:
        company_names = {t: None for t in ticker_list}

    for ticker in ticker_list:
        quote_data = quotes_dict.get(ticker) if quotes_dict else None
        quote = None
        if quote_data and isinstance(quote_data, dict):
            try:
                quote = TickerQuote(**quote_data)
            except Exception:
                quote = None
        if quote is None:
            try:
                quote_data = gw.get_quote(ticker)
                if quote_data and isinstance(quote_data, dict):
                    quote = TickerQuote(**quote_data)
            except Exception:
                pass

        latest_date = None
        recommendation = None
        confidence = None
        report_scores = None

        try:
            latest_run = gw.get_latest_execution_for_ticker(ticker)
            if latest_run:
                latest_ar_id, latest_date = latest_run
                scores_raw = gw.get_reports_with_scores(latest_ar_id)
                if scores_raw:
                    report_scores = {
                        k: ReportScoreSummary(score=v.get("score"), score_label=v.get("score_label"))
                        for k, v in scores_raw.items()
                        if v.get("score") is not None or v.get("score_label")
                    }
                    if not report_scores:
                        report_scores = None
                    tip = scores_raw.get("trader_investment_plan") or {}
                    ftd = scores_raw.get("final_trade_decision") or {}
                    if ftd.get("recommendation"):
                        recommendation = ftd["recommendation"]
                    elif tip.get("recommendation"):
                        recommendation = tip.get("recommendation")
                    confidence = _extract_confidence(tip, ftd)
        except Exception as e:
            print(f"Warning: Failed to get reports for {ticker}: {e}")

        is_major = (ticker.upper() in major_set) if use_major_split else None
        company_name = company_names.get(ticker)
        if quote:
            widget = TickerWidget(
                ticker=ticker,
                name=company_name,
                current_price=quote.current_price,
                daily_change=quote.daily_change,
                daily_change_percent=quote.daily_change_percent,
                recommendation=recommendation if latest_date else None,
                confidence=confidence,
                report_date=latest_date,
                has_report=latest_date is not None,
                market_status=quote.market_status,
                report_scores=report_scores,
                is_major=is_major,
                currency=getattr(quote, "currency", None),
            )
        else:
            widget = TickerWidget(
                ticker=ticker,
                name=company_name,
                current_price=0.0,
                daily_change=0.0,
                daily_change_percent=0.0,
                recommendation=recommendation if latest_date else None,
                confidence=confidence,
                report_date=latest_date,
                has_report=latest_date is not None,
                market_status="UNKNOWN",
                report_scores=report_scores,
                is_major=is_major,
            )
        widgets.append(widget)

    return WidgetsResponse(widgets=widgets, total=total_count)


def _get_ticker_page_sync(ticker: str) -> TickerPageData:
    """Sync implementation of ticker page data (runs in thread pool to avoid blocking event loop)."""
    gw = get_data_gateway()

    quote_data = gw.get_quote(ticker)
    if not quote_data or not isinstance(quote_data, dict):
        raise HTTPException(
            status_code=404,
            detail=f"Ticker '{ticker}' not found. Check the symbol and try again.",
        )
    quote = TickerQuote(**quote_data)

    is_generating = False
    generation_analysis_run_id = None
    try:
        from services.data_cache import get_running_analysis_run_id_for_ticker
        generation_analysis_run_id = get_running_analysis_run_id_for_ticker("ticker", ticker)
        if generation_analysis_run_id is not None:
            is_generating = True
    except Exception as e:
        logging.getLogger(__name__).warning("Error checking cache for running analysis: %s", e)

    latest_run = gw.get_latest_execution_for_ticker(ticker)
    if is_generating and generation_analysis_run_id is not None:
        latest_analysis_run_id = generation_analysis_run_id
        latest_date = latest_run[1] if latest_run else None
        if latest_date is None:
            latest_date = "Generating..."
    elif latest_run:
        latest_analysis_run_id, latest_date = latest_run
    else:
        latest_analysis_run_id = None
        latest_date = None
    latest_reports = {}
    latest_reports_with_scores = {}
    latest_reports_with_scores_raw = {}
    latest_recommendation = None
    report_days_ago = None

    if latest_analysis_run_id is not None:
        latest_reports = gw.get_reports_for_run(latest_analysis_run_id)
        latest_reports_with_scores_raw = gw.get_reports_with_scores(latest_analysis_run_id)
        latest_reports_with_scores = {
            k: ReportData(
                content=v.get('content'),
                score=v.get('score'),
                score_label=v.get('score_label'),
                key_takeaways=v.get('key_takeaways') or [],
                analysis_date=v.get('analysis_date'),
                generated_at=v.get('generated_at'),
                days_ago=v.get('days_ago'),
                models_used=v.get('models_used'),
                bull_viewpoint=v.get('bull_viewpoint'),
                bear_viewpoint=v.get('bear_viewpoint'),
                risky_viewpoint=v.get('risky_viewpoint'),
                safe_viewpoint=v.get('safe_viewpoint'),
                neutral_viewpoint=v.get('neutral_viewpoint'),
                tps_plan=v.get('tps_plan'),
            )
            for k, v in latest_reports_with_scores_raw.items()
        }
        first_report = next(iter(latest_reports_with_scores_raw.values()), {})
        report_days_ago = first_report.get('days_ago')
        tip_meta = latest_reports_with_scores_raw.get("trader_investment_plan") or {}
        final_meta = latest_reports_with_scores_raw.get("final_trade_decision") or {}
        confidence = _extract_confidence(tip_meta, final_meta)
        if final_meta.get("recommendation"):
            latest_recommendation = Recommendation(
                recommendation=final_meta["recommendation"],
                confidence=confidence,
                source="final_trade_decision",
                date=latest_date or ""
            )
        elif tip_meta.get("recommendation"):
            latest_recommendation = Recommendation(
                recommendation=tip_meta["recommendation"],
                confidence=confidence,
                source="trader_investment_plan",
                date=latest_date or ""
            )

    historical = gw.get_historical_analyses(ticker)
    historical_analyses = []
    for h in historical:
        reports_with_scores = gw.get_reports_with_scores(h["analysis_run_id"])
        rec = None
        if (reports_with_scores.get("final_trade_decision") or {}).get("recommendation"):
            rec = reports_with_scores["final_trade_decision"]["recommendation"]
        elif (reports_with_scores.get("trader_investment_plan") or {}).get("recommendation"):
            rec = reports_with_scores["trader_investment_plan"]["recommendation"]
        historical_analyses.append(HistoricalAnalysis(
            analysis_run_id=h["analysis_run_id"],
            date=h["date"],
            available_reports=h["available_reports"],
            recommendation=rec
        ))

    investment_plan_meta = latest_reports_with_scores_raw.get("investment_plan") or {}
    expected_return_pct = investment_plan_meta.get("expected_return_pct")
    bear_case_return_pct = investment_plan_meta.get("bear_case_return_pct")
    bull_case_return_pct = investment_plan_meta.get("bull_case_return_pct")

    share_url = get_share_url(latest_analysis_run_id) if latest_analysis_run_id else None

    return TickerPageData(
        ticker=ticker,
        quote=quote,
        recommendation=latest_recommendation,
        report_run_id=latest_analysis_run_id,
        report_date=latest_date,
        report_days_ago=report_days_ago,
        reports=latest_reports,
        reports_with_scores=latest_reports_with_scores,
        historical_analyses=historical_analyses,
        has_reports=latest_analysis_run_id is not None,
        is_generating=is_generating,
        generation_analysis_run_id=generation_analysis_run_id,
        expected_return_pct=expected_return_pct,
        bear_case_return_pct=bear_case_return_pct,
        bull_case_return_pct=bull_case_return_pct,
        share_url=share_url,
    )


@router.get("/widgets", response_model=WidgetsResponse)
async def get_ticker_widgets(
    tickers: Optional[str] = Query(None, description="Comma-separated list of tickers"),
    date: Optional[str] = Query(None, description="Date (YYYY-MM-DD) for report filter; default today"),
    only_date: bool = Query(False, description="When set with no tickers: return only tickers with reports for the given date (no major-stocks list)"),
    recent_days: Optional[int] = Query(None, ge=1, le=30, description="When only_date: include reports from the last N days ending at date"),
    limit: Optional[int] = Query(None, description="When only_date: max number of widgets to return (paginated)"),
    offset: int = Query(0, description="When only_date and limit: pagination offset"),
):
    """Get widget data for tickers. Uses cached batch quote fetch for speed. Runs in thread pool (non-blocking)."""
    try:
        return await asyncio.to_thread(_get_ticker_widgets_sync, tickers, date, only_date, limit, offset, recent_days)
    except Exception as e:
        print(f"Error in get_ticker_widgets: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load widget data: {str(e)}")


@router.get("/{ticker}/reports/{analysis_run_id}")
async def get_ticker_reports_for_run(
    ticker: str,
    analysis_run_id: int,
    _current_user=Depends(get_current_user_optional),
):
    """Get reports_with_scores for a specific historical run by analysis_run_id. Experimental."""
    ticker = ticker.upper()
    gw = get_data_gateway()

    def _fetch():
        scores_raw = gw.get_reports_with_scores(analysis_run_id)
        if not scores_raw:
            return None
        return {
            k: ReportData(
                content=v.get("content"),
                score=v.get("score"),
                score_label=v.get("score_label"),
                key_takeaways=v.get("key_takeaways") or [],
                analysis_date=v.get("analysis_date"),
                generated_at=v.get("generated_at"),
                days_ago=v.get("days_ago"),
                models_used=v.get("models_used"),
                bull_viewpoint=v.get("bull_viewpoint"),
                bear_viewpoint=v.get("bear_viewpoint"),
                risky_viewpoint=v.get("risky_viewpoint"),
                safe_viewpoint=v.get("safe_viewpoint"),
                neutral_viewpoint=v.get("neutral_viewpoint"),
                tps_plan=v.get("tps_plan"),
                expected_return_pct=v.get("expected_return_pct"),
                bear_case_return_pct=v.get("bear_case_return_pct"),
                bull_case_return_pct=v.get("bull_case_return_pct"),
            )
            for k, v in scores_raw.items()
        }

    try:
        result = await asyncio.to_thread(_fetch)
        if result is None:
            raise HTTPException(status_code=404, detail="No reports found for this run")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load reports: {str(e)}")


@router.get("/{ticker}", response_model=TickerPageData)
async def get_ticker_page(
    ticker: str,
    current_user=Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Get complete ticker page data. Accessible without authentication. Runs in thread pool (non-blocking). Views are recorded for creator rewards when user is logged in."""
    ticker = ticker.upper()
    try:
        result = await asyncio.to_thread(_get_ticker_page_sync, ticker)
        if result.report_run_id is not None and current_user is not None:
            try:
                token_service.record_view(result.report_run_id, current_user.id, db)
            except Exception:
                pass
        if result.report_run_id is not None and current_user is not None:
            try:
                result = result.model_copy(
                    update={
                        "report_view_count": token_service.get_view_count(result.report_run_id, db),
                        "report_earned_tokens": token_service.get_run_earned_tokens(result.report_run_id, db),
                    }
                )
            except Exception:
                pass
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_ticker_page: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load ticker page: {str(e)}")
