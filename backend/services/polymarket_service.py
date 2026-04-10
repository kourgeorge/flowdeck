"""
Polymarket Service

Main service layer that orchestrates Polymarket data fetching, market relevance scoring,
and sentiment aggregation. This is the primary interface for other parts of the application.
"""

import math
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from functools import lru_cache

from backend.data_layer.vendors import polymarket_vendor
from backend.services import polymarket_narrative_mapper
from backend.services import polymarket_relevance_scorer

logger = logging.getLogger(__name__)


class PolymarketService:
    """
    Service for fetching and analyzing Polymarket prediction market data.
    """
    
    def __init__(self):
        self.vendor = polymarket_vendor
        self.mapper = polymarket_narrative_mapper
        self.scorer = polymarket_relevance_scorer
    
    def get_ticker_sentiment(
        self,
        ticker: str,
        company_info: Optional[Dict] = None,
        max_markets: int = 50,
        top_n: int = 10
    ) -> Dict:
        """
        Get aggregated Polymarket sentiment for a ticker.
        
        This is the main entry point for getting prediction market sentiment.
        
        Args:
            ticker: Stock ticker symbol
            company_info: Optional dict with keys: name, sector, industry
            max_markets: Maximum markets to fetch per narrative
            top_n: Number of top markets to return
            
        Returns:
            Dictionary with:
            - overall_sentiment: 0-1 scale (0=bearish, 0.5=neutral, 1=bullish)
            - confidence: 0-1 scale based on volume
            - trend: "bullish", "neutral", or "bearish"
            - narratives: Dict of narrative categories with sentiment
            - top_markets: List of most relevant markets
            - last_updated: ISO timestamp
            - error: Optional error message if data unavailable
        """
        try:
            logger.info(f"Fetching Polymarket sentiment for {ticker}")
            
            # Step 1: Map ticker to narratives
            narratives = self.mapper.map_ticker_to_narratives(ticker, company_info)
            logger.info(f"Generated {len(narratives)} narratives for {ticker}")
            
            # Step 2: Fetch markets for each narrative
            all_markets = self._fetch_markets_for_narratives(
                narratives[:10],  # Limit to top 10 narratives to avoid too many API calls
                max_per_narrative=max_markets // 10
            )
            logger.info(f"Fetched {len(all_markets)} total markets")
            
            if not all_markets:
                return self._create_neutral_response(
                    ticker,
                    error="No relevant markets found"
                )
            
            # Step 3: Score and rank markets by relevance
            # Use higher threshold to filter out weakly related markets
            scored_markets = self.scorer.rank_markets_by_relevance(
                all_markets,
                ticker,
                narratives,
                company_info,
                min_score=0.15  # Increased from 0.1 to filter out generic tech markets
            )
            logger.info(f"Scored {len(scored_markets)} relevant markets")
            
            if not scored_markets:
                return self._create_neutral_response(
                    ticker,
                    error="No markets met relevance threshold"
                )
            
            # Step 4: Select top diverse markets
            top_markets = self.scorer.filter_top_markets(
                scored_markets,
                top_n=top_n,
                diversity_factor=0.3
            )
            
            # Step 5: Aggregate sentiment
            sentiment_data = self._aggregate_sentiment(top_markets, narratives)
            
            # Step 6: Format response
            response = {
                "ticker": ticker.upper(),
                "overall_sentiment": sentiment_data["overall_sentiment"],
                "confidence": sentiment_data["confidence"],
                "trend": sentiment_data["trend"],
                "narratives": sentiment_data["narratives"],
                "top_markets": [
                    self._format_market_for_response(m)
                    for m in top_markets
                ],
                "last_updated": datetime.utcnow().isoformat() + "Z",
                "market_count": len(scored_markets)
            }
            
            logger.info(
                f"Polymarket sentiment for {ticker}: "
                f"{sentiment_data['overall_sentiment']:.2f} ({sentiment_data['trend']})"
            )
            
            return response
            
        except polymarket_vendor.PolymarketUnavailableError as e:
            logger.error(f"Polymarket API unavailable: {e}")
            return self._create_neutral_response(
                ticker,
                error="Polymarket data temporarily unavailable"
            )
        except Exception as e:
            import traceback
            logger.error(f"Error fetching Polymarket sentiment for {ticker}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return self._create_neutral_response(
                ticker,
                error=f"Error: {str(e)}"
            )
    
    def _fetch_markets_for_narratives(
        self,
        narratives: List[str],
        max_per_narrative: int = 5
    ) -> List[Dict]:
        """
        Fetch markets for multiple narratives.
        
        Args:
            narratives: List of search queries
            max_per_narrative: Max markets per narrative
            
        Returns:
            Deduplicated list of markets
        """
        try:
            markets = self.vendor.search_markets_by_keywords(
                keywords=narratives,
                category=None,  # Don't filter by category - too restrictive
                active=True,
                limit_per_keyword=max_per_narrative
            )
            return markets
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []
    
    def _aggregate_sentiment(
        self,
        markets: List[Dict],
        narratives: List[str],
        include_narrative_breakdown: bool = True
    ) -> Dict:
        """
        Aggregate sentiment from multiple markets.
        
        Args:
            markets: List of scored markets
            narratives: List of narrative queries
            
        Returns:
            Dict with overall_sentiment, confidence, trend, and narratives
        """
        if not markets:
            return {
                "overall_sentiment": 0.5,
                "confidence": 0.0,
                "trend": "neutral",
                "narratives": {}
            }
        
        # Validate markets is a list of dicts
        if not isinstance(markets, list):
            logger.error(f"markets is not a list: {type(markets)}")
            raise TypeError(f"markets must be a list, got {type(markets)}")
        
        # Calculate weighted sentiment
        total_weight = 0
        weighted_sum = 0
        
        logger.info(f"Aggregating sentiment from {len(markets)} markets")
        
        for idx, market in enumerate(markets):
            # Validate each market is a dict
            if not isinstance(market, dict):
                logger.error(f"Market at index {idx} is not a dict: {type(market)}, value: {market}")
                raise TypeError(f"Market at index {idx} must be a dict, got {type(market)}")
            
            # Extract probability (0-1 scale)
            probability = self.vendor.extract_probability(market)
            
            # Calculate weight based on volume, liquidity, and relevance
            try:
                volume = float(market.get('volume', 0)) if market.get('volume') else 0
            except (ValueError, TypeError):
                volume = 0
            
            relevance = market.get('relevance_score', 0.5)
            time_decay = self._time_decay_factor(market.get('end_date'))
            
            weight = (
                math.log10(volume + 1) *  # Log scale for volume
                relevance *  # Relevance score
                time_decay  # Time decay
            )
            
            weighted_sum += probability * weight
            total_weight += weight
            
            # Log first 5 markets for debugging
            if idx < 5:
                question = market.get('question', market.get('event_title', 'N/A'))[:60]
                logger.info(
                    f"  Market {idx+1}: '{question}' - "
                    f"prob={probability:.3f} ({probability*100:.1f}%), "
                    f"vol=${volume:,.0f}, "
                    f"relevance={relevance:.2f}, "
                    f"time_decay={time_decay:.2f}, "
                    f"weight={weight:.2f}"
                )
        
        # Calculate overall sentiment
        overall_sentiment = weighted_sum / total_weight if total_weight > 0 else 0.5
        
        # Calculate confidence based on total volume
        total_volume = 0
        for m in markets:
            try:
                vol = float(m.get('volume', 0)) if m.get('volume') else 0
                total_volume += vol
            except (ValueError, TypeError):
                continue
        confidence = min(math.log10(total_volume + 1) / 6, 1.0)  # Normalize to 0-1
        
        # Determine trend
        if overall_sentiment >= 0.6:
            trend = "bullish"
        elif overall_sentiment <= 0.4:
            trend = "bearish"
        else:
            trend = "neutral"
        
        logger.info(
            f"Aggregation complete: overall_sentiment={overall_sentiment:.3f} ({overall_sentiment*100:.1f}%), "
            f"confidence={confidence:.3f}, trend={trend}, "
            f"total_volume=${total_volume:,.0f}, total_weight={total_weight:.2f}"
        )
        
        # Return sentiment without narrative breakdown to avoid recursion
        return {
            "overall_sentiment": overall_sentiment,
            "confidence": confidence,
            "trend": trend,
            "narratives": {}  # Empty dict to maintain API compatibility
        }
    
    def _group_by_narrative(
        self,
        markets: List[Dict],
        narratives: List[str]
    ) -> Dict[str, Dict]:
        """
        Group markets by narrative category and calculate per-narrative sentiment.
        
        Args:
            markets: List of markets
            narratives: List of narrative queries
            
        Returns:
            Dict mapping narrative category to sentiment data
        """
        narrative_groups: Dict[str, List[Dict]] = {}
        
        for market in markets:
            category = self.scorer.get_market_narrative_category(market, narratives)
            if category not in narrative_groups:
                narrative_groups[category] = []
            narrative_groups[category].append(market)
        
        # Calculate sentiment for each narrative (without recursive breakdown)
        result = {}
        for category, category_markets in narrative_groups.items():
            category_sentiment = self._aggregate_sentiment(
                category_markets,
                narratives,
                include_narrative_breakdown=False
            )
            result[category] = {
                "sentiment": category_sentiment["overall_sentiment"],
                "confidence": category_sentiment["confidence"],
                "market_count": len(category_markets),
                "trend": category_sentiment["trend"]
            }
        
        return result
    
    def _time_decay_factor(self, end_date: Optional[str]) -> float:
        """
        Calculate time decay factor for market weight.
        
        Args:
            end_date: Market end date (ISO format)
            
        Returns:
            Decay factor (0-1)
        """
        if not end_date:
            return 0.5
        
        try:
            if 'T' in end_date:
                end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            else:
                end = datetime.strptime(end_date, '%Y-%m-%d')
            
            now = datetime.now(end.tzinfo) if end.tzinfo else datetime.now()
            days_until = (end - now).days
            
            if days_until <= 0:
                return 0.1  # Resolved markets
            elif days_until <= 30:
                return 1.0  # Near-term
            elif days_until <= 90:
                return 0.8  # Medium-term
            elif days_until <= 180:
                return 0.6  # Long-term
            else:
                return 0.4  # Very long-term
        except Exception:
            return 0.5
    
    def _format_market_for_response(self, market: Dict) -> Dict:
        """
        Format market data for API response.
        
        Args:
            market: Raw market data
            
        Returns:
            Formatted market dict
        """
        # Convert volume and liquidity to integers
        try:
            volume = int(float(market.get('volume', 0)))
        except (ValueError, TypeError):
            volume = 0
        
        try:
            liquidity = int(float(market.get('liquidity', 0)))
        except (ValueError, TypeError):
            liquidity = 0
        
        # Extract probability - try multiple fields
        probability = self.vendor.extract_probability(market)
        
        # Build proper URL using event slug if available
        event_slug = market.get('event_slug', '')
        if event_slug:
            url = f"https://polymarket.com/event/{event_slug}"
        else:
            url = market.get('url', f"https://polymarket.com/event/{market.get('id')}")
        
        return {
            "id": market.get('id'),
            "question": market.get('question', ''),
            "description": market.get('description', ''),
            "probability": probability,
            "change_24h": self.vendor.calculate_24h_change(market),
            "volume": volume,
            "liquidity": liquidity,
            "end_date": market.get('end_date', ''),
            "category": market.get('category', ''),
            "relevance_score": market.get('relevance_score', 0),
            "narrative": self.scorer.get_market_narrative_category(
                market,
                [str(market.get('matched_keyword'))] if market.get('matched_keyword') else []
            ),
            "matched_keyword": market.get('matched_keyword', ''),
            "url": url,
            "event_title": market.get('event_title', ''),
            "event_slug": market.get('event_slug', ''),
            "event_description": market.get('event_description', '')
        }
    
    def _create_neutral_response(
        self,
        ticker: str,
        error: Optional[str] = None
    ) -> Dict:
        """
        Create neutral response when data is unavailable.
        
        Args:
            ticker: Stock ticker
            error: Optional error message
            
        Returns:
            Neutral sentiment response
        """
        response = {
            "ticker": ticker.upper(),
            "overall_sentiment": 0.5,
            "confidence": 0.0,
            "trend": "neutral",
            "narratives": {},
            "top_markets": [],
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "market_count": 0
        }
        
        if error:
            response["error"] = error
        
        return response
    
    def get_relevant_markets(
        self,
        ticker: str,
        company_info: Optional[Dict] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get list of relevant markets for a ticker without aggregation.
        
        Args:
            ticker: Stock ticker
            company_info: Optional company info
            limit: Max markets to return
            
        Returns:
            List of formatted markets
        """
        try:
            # Get narratives
            narratives = self.mapper.map_ticker_to_narratives(ticker, company_info)
            
            # Fetch markets
            markets = self._fetch_markets_for_narratives(narratives[:10])
            
            # Score and rank
            scored_markets = self.scorer.rank_markets_by_relevance(
                markets,
                ticker,
                narratives,
                company_info
            )
            
            # Return top N
            return [
                self._format_market_for_response(m)
                for m in scored_markets[:limit]
            ]
            
        except Exception as e:
            logger.error(f"Error getting relevant markets for {ticker}: {e}")
            return []
    
    def get_trending_markets(
        self,
        category: str = "finance",
        limit: int = 20
    ) -> List[Dict]:
        """
        Get trending markets by volume.
        
        Args:
            category: Market category
            limit: Number of markets
            
        Returns:
            List of trending markets
        """
        try:
            markets = self.vendor.get_trending_markets(
                category=category,
                limit=limit
            )
            
            return [
                self.vendor.format_market_for_display(m)
                for m in markets
            ]
            
        except Exception as e:
            logger.error(f"Error getting trending markets: {e}")
            return []
    
    def health_check(self) -> bool:
        """
        Check if Polymarket service is operational.
        
        Returns:
            True if healthy, False otherwise
        """
        return self.vendor.health_check()


# Singleton instance
_service_instance: Optional[PolymarketService] = None


def get_polymarket_service() -> PolymarketService:
    """
    Get singleton instance of PolymarketService.
    
    Returns:
        PolymarketService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = PolymarketService()
    return _service_instance

# Made with Bob
