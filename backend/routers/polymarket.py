"""
Polymarket API Router

REST API endpoints for accessing Polymarket prediction market data.
"""

import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from auth import get_current_user_optional
from data_layer import get_data_gateway
from models.db_models import User
from services.polymarket_service import get_polymarket_service

logger = logging.getLogger(__name__)


async def _fetch_company_info(ticker: str) -> Optional[dict]:
    """
    Fetch company profile (name, sector, industry, summary) for LLM keyword
    generation.  Runs the blocking gateway call off the event loop and never
    raises — returns None on failure so the endpoint degrades gracefully.
    """
    try:
        return await asyncio.to_thread(get_data_gateway().get_company_info, ticker)
    except Exception as e:
        logger.warning(f"Could not fetch company info for {ticker}: {e}")
        return None

router = APIRouter(prefix="/api/polymarket", tags=["polymarket"])


# Response models
class MarketResponse(BaseModel):
    """Single market response."""
    id: str
    question: str
    description: str
    probability: float = Field(ge=0, le=1)
    change_24h: float
    volume: int
    liquidity: int
    end_date: str
    category: str
    relevance_score: Optional[float] = None
    narrative: Optional[str] = None
    matched_keyword: Optional[str] = None
    url: str
    event_title: Optional[str] = None
    event_slug: Optional[str] = None
    event_description: Optional[str] = None


class NarrativeSentiment(BaseModel):
    """Sentiment for a narrative category."""
    sentiment: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    market_count: int
    trend: str


class TickerSentimentResponse(BaseModel):
    """Aggregated sentiment response for a ticker."""
    ticker: str
    overall_sentiment: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    trend: str
    narratives: dict[str, NarrativeSentiment]
    top_markets: list[MarketResponse]
    last_updated: str
    market_count: int
    error: Optional[str] = None


@router.get(
    "/ticker/{ticker}",
    response_model=TickerSentimentResponse,
    summary="Get Polymarket sentiment for a ticker"
)
async def get_ticker_predictions(
    ticker: str,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Get aggregated Polymarket prediction market sentiment for a stock ticker.
    
    This endpoint:
    1. Maps the ticker to relevant narrative categories
    2. Searches Polymarket for related markets
    3. Scores markets by relevance
    4. Aggregates sentiment across top markets
    5. Returns overall sentiment with confidence score
    
    **Sentiment Scale**: 0 (bearish) to 1 (bullish), 0.5 is neutral
    
    **Confidence**: Based on trading volume (higher volume = higher confidence)
    
    **Example**: For NVDA, finds markets about:
    - Direct mentions (NVDA stock, Nvidia earnings)
    - Industry (AI stocks, semiconductor sector)
    - Macro factors (Fed rates, tech sector outlook)
    """
    try:
        service = get_polymarket_service()

        # Company info drives LLM keyword generation; None is tolerated (falls
        # back to deterministic keywords).
        company_info = await _fetch_company_info(ticker)

        result = service.get_ticker_sentiment(
            ticker=ticker,
            company_info=company_info,
            max_markets=100,  # Increased from 50
            top_n=30  # Increased from 10 to show more markets
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching Polymarket data for {ticker}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching Polymarket data: {str(e)}"
        )


@router.get(
    "/markets/relevant/{ticker}",
    response_model=list[MarketResponse],
    summary="Get relevant markets for a ticker"
)
async def get_relevant_markets(
    ticker: str,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Get list of relevant Polymarket markets for a ticker without aggregation.
    
    Returns markets ranked by relevance score, useful for displaying
    individual markets to users.
    """
    try:
        service = get_polymarket_service()

        company_info = await _fetch_company_info(ticker)

        markets = service.get_relevant_markets(
            ticker=ticker,
            company_info=company_info,
            limit=limit
        )
        
        return markets
        
    except Exception as e:
        logger.error(f"Error fetching relevant markets for {ticker}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching markets: {str(e)}"
        )


@router.get(
    "/markets/trending",
    response_model=list[MarketResponse],
    summary="Get trending prediction markets"
)
async def get_trending_markets(
    category: str = Query(default="finance", description="Market category"),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Get trending prediction markets by trading volume.
    
    Categories:
    - finance: Financial markets (stocks, earnings, etc.)
    - crypto: Cryptocurrency markets
    - politics: Political prediction markets
    - economics: Economic indicators
    """
    try:
        service = get_polymarket_service()
        
        markets = service.get_trending_markets(
            category=category,
            limit=limit
        )
        
        return markets
        
    except Exception as e:
        logger.error(f"Error fetching trending markets: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching trending markets: {str(e)}"
        )


@router.get(
    "/health",
    summary="Check Polymarket service health"
)
async def health_check():
    """
    Check if Polymarket API is accessible and service is operational.
    
    Returns:
    - status: "healthy" or "unhealthy"
    - message: Description of status
    """
    try:
        service = get_polymarket_service()
        is_healthy = service.health_check()
        
        if is_healthy:
            return {
                "status": "healthy",
                "message": "Polymarket API is accessible"
            }
        else:
            return {
                "status": "unhealthy",
                "message": "Polymarket API is not accessible"
            }
            
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Error: {str(e)}"
        }


# Optional: Market details endpoint
@router.get(
    "/market/{market_id}",
    summary="Get detailed information about a specific market"
)
async def get_market_details(
    market_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Get detailed information about a specific Polymarket market.
    
    Includes:
    - Full question and description
    - Current probabilities for all outcomes
    - Trading volume and liquidity
    - Resolution criteria
    - Historical data (if available)
    """
    from backend.data_layer.vendors import polymarket_vendor
    
    try:
        market = polymarket_vendor.get_market_details(market_id)
        return polymarket_vendor.format_market_for_display(market)
        
    except polymarket_vendor.PolymarketAPIError as e:
        logger.error(f"Error fetching market {market_id}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Market not found: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching market {market_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching market: {str(e)}"
        )


# Optional: Market history endpoint
@router.get(
    "/market/{market_id}/history",
    summary="Get historical probability data for a market"
)
async def get_market_history(
    market_id: str,
    days: int = Query(default=30, ge=1, le=365),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Get historical probability data for a market.
    
    Useful for:
    - Tracking how sentiment evolved over time
    - Identifying trend changes
    - Analyzing prediction accuracy
    """
    from backend.data_layer.vendors import polymarket_vendor
    from datetime import datetime, timedelta
    
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        history = polymarket_vendor.get_market_history(
            market_id=market_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            "market_id": market_id,
            "start_date": start_date,
            "end_date": end_date,
            "history": history
        }
        
    except polymarket_vendor.PolymarketAPIError as e:
        logger.error(f"Error fetching history for market {market_id}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Market history not found: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching history for {market_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching market history: {str(e)}"
        )

# Made with Bob
