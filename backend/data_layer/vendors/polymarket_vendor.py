"""
Polymarket API Client

This module provides functions to interact with the Polymarket prediction market API.
It handles fetching markets, prices, and historical data with caching and error handling.

API Documentation: https://docs.polymarket.com/
"""

import os
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from functools import lru_cache
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# API Configuration
POLYMARKET_API_BASE_URL = os.getenv(
    "POLYMARKET_API_BASE_URL",
    "https://gamma-api.polymarket.com"
)
POLYMARKET_CLOB_API_URL = os.getenv(
    "POLYMARKET_CLOB_API_URL", 
    "https://clob.polymarket.com"
)

# Cache configuration
CACHE_TTL_PRICES = int(os.getenv("POLYMARKET_CACHE_TTL", "300"))  # 5 minutes
CACHE_TTL_MARKETS = 3600  # 1 hour for market lists

# Filtering thresholds - lowered to capture more markets
# These can be overridden via environment variables
MIN_VOLUME = int(os.getenv("POLYMARKET_MIN_VOLUME", "10"))  # Lowered from 100 to 10
MIN_LIQUIDITY = int(os.getenv("POLYMARKET_MIN_LIQUIDITY", "10"))  # Lowered from 50 to 10

# Request timeout
REQUEST_TIMEOUT = 30


class PolymarketAPIError(Exception):
    """Base exception for Polymarket API errors."""
    pass


class PolymarketRateLimitError(PolymarketAPIError):
    """Rate limit exceeded."""
    pass


class PolymarketUnavailableError(PolymarketAPIError):
    """API temporarily unavailable."""
    pass


def _get_session() -> requests.Session:
    """
    Create a requests session with retry logic.
    
    Returns:
        Configured requests.Session with exponential backoff
    """
    session = requests.Session()
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def _make_request(
    url: str,
    params: Optional[Dict] = None,
    timeout: int = REQUEST_TIMEOUT
) -> Dict:
    """
    Make HTTP request with error handling.
    
    Args:
        url: Full URL to request
        params: Query parameters
        timeout: Request timeout in seconds
        
    Returns:
        JSON response as dictionary
        
    Raises:
        PolymarketAPIError: On API errors
        PolymarketRateLimitError: On rate limit
        PolymarketUnavailableError: On timeout/unavailable
    """
    session = _get_session()
    
    try:
        response = session.get(url, params=params, timeout=timeout)
        
        # Handle rate limiting
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            logger.warning(f"Polymarket rate limit hit, retry after {retry_after}s")
            raise PolymarketRateLimitError(f"Rate limit exceeded, retry after {retry_after}s")
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.Timeout:
        logger.error(f"Polymarket API timeout: {url}")
        raise PolymarketUnavailableError("API request timeout")
        
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Polymarket API connection error: {e}")
        raise PolymarketUnavailableError("Cannot connect to Polymarket API")
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"Polymarket API HTTP error: {e}")
        raise PolymarketAPIError(f"HTTP error: {e}")
        
    except Exception as e:
        logger.error(f"Unexpected error calling Polymarket API: {e}")
        raise PolymarketAPIError(f"Unexpected error: {e}")


def _is_market_open(market: Dict) -> bool:
    """
    Return True if the market is currently open/unresolved.

    Checks the per-market active/closed/archived flags and, crucially,
    the end_date field — a market whose end_date is in the past is resolved
    even if the API still returns it with active=true in a keyword search.
    """
    # Explicit closed/archived flags take priority
    if market.get('closed') is True or market.get('archived') is True:
        return False
    if market.get('active') is False:
        return False

    # Check end_date: reject markets that ended before today
    from datetime import timezone as _tz
    now_naive = datetime.now(_tz.utc).replace(tzinfo=None)
    for key in ('endDate', 'end_date', 'end_date_iso', 'endDateIso'):
        raw = market.get(key)
        if not raw:
            continue
        try:
            # Strip trailing Z / timezone info for naive UTC comparison
            clean = str(raw).replace('Z', '').split('+')[0].strip()
            # Support "2025-07-01T00:00:00" and "2025-07-01" formats
            if 'T' in clean:
                end_dt = datetime.strptime(clean[:19], '%Y-%m-%dT%H:%M:%S')
            else:
                end_dt = datetime.strptime(clean[:10], '%Y-%m-%d')
            if end_dt < now_naive:
                return False
        except (ValueError, TypeError):
            pass  # Unparseable date — don't reject on that alone

    return True


def fetch_markets(
    query: Optional[str] = None,
    category: Optional[str] = None,
    active: bool = True,
    limit: int = 100,
    offset: int = 0
) -> List[Dict]:
    """
    Fetch markets from Polymarket API.
    
    Uses /events for browsing/searching markets.  Returns only open,
    unresolved markets by checking both server-side active/closed flags
    and per-market end_date so that old resolved markets never appear.
    
    Args:
        query: Search query string
        category: Filter by category (not used)
        active: If True, only return active (unresolved) markets
        limit: Maximum number of markets to return
        offset: Pagination offset
        
    Returns:
        List of market dictionaries extracted from events
        
    Raises:
        PolymarketAPIError: On API errors
    """
    params: Dict[str, Any] = {}

    # /events is the stable public endpoint — /public-search returns 403
    url = f"{POLYMARKET_API_BASE_URL}/events"
    params["limit"] = limit
    params["offset"] = offset
    if active:
        params["active"] = "true"
        params["closed"] = "false"
        # Request newest events first so keyword matches return recent results
        params["order"] = "startDate"
        params["ascending"] = "false"
    if query:
        params["title"] = query  # server-side keyword filter

    try:
        logger.info(f"Fetching Polymarket data: query={query}, url={url}")
        data = _make_request(url, params=params)

        # /events returns a list directly or wrapped in 'data'
        events = data if isinstance(data, list) else data.get('data', [])
        logger.info(f"Found {len(events)} events from /events for query '{query}'")
        
        # Extract markets from events and flatten
        all_markets = []
        for event in events:
            # Skip if event is not a dict
            if not isinstance(event, dict):
                logger.warning(f"Skipping non-dict event: {type(event)}")
                continue
                
            # Each event contains a 'markets' array
            event_markets = event.get('markets', [])
            if not isinstance(event_markets, list):
                logger.warning(f"Event markets is not a list: {type(event_markets)}")
                continue
                
            for idx, market in enumerate(event_markets):
                # Skip if market is not a dict
                if not isinstance(market, dict):
                    logger.warning(f"Skipping non-dict market: {type(market)}")
                    continue

                # Add event-level data to market for context
                market['event_title'] = event.get('title', '')
                market['event_slug'] = event.get('slug', '')
                market['event_description'] = event.get('description', '')
                # Use event end date as fallback for per-market end date
                for date_key in ('endDate', 'end_date'):
                    if not market.get(date_key) and event.get(date_key):
                        market[date_key] = event[date_key]
                # Use event volume if market volume not available
                if not market.get('volume'):
                    market['volume'] = event.get('volume', 0)
                if not market.get('liquidity'):
                    market['liquidity'] = event.get('liquidity', 0)

                # Skip resolved/closed markets — check per-market flags and end_date
                if active and not _is_market_open(market):
                    continue

                # Debug: Log first accepted market structure
                if idx == 0 and len(all_markets) == 0:
                    logger.info(f"Sample market keys: {list(market.keys())}")

                all_markets.append(market)
        
        # Filter by volume and liquidity thresholds
        filtered_markets = []
        filtered_count = 0
        for market in all_markets:
            try:
                volume = float(market.get('volume', 0)) if market.get('volume') else 0
                liquidity = float(market.get('liquidity', 0)) if market.get('liquidity') else 0
                if volume >= MIN_VOLUME and liquidity >= MIN_LIQUIDITY:
                    filtered_markets.append(market)
                else:
                    filtered_count += 1
                    if filtered_count <= 3:  # Log first 3 filtered markets for debugging
                        logger.info(
                            f"Filtered market '{market.get('question', market.get('event_title', 'N/A'))[:50]}...': "
                            f"volume={volume:.2f} (min={MIN_VOLUME}), "
                            f"liquidity={liquidity:.2f} (min={MIN_LIQUIDITY})"
                        )
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid volume/liquidity data for market {market.get('id')}: {e}")
                continue
        
        logger.info(f"Fetched {len(filtered_markets)} markets from {len(events)} events (filtered from {len(all_markets)} total markets)")
        return filtered_markets
        
    except PolymarketAPIError:
        raise
    except Exception as e:
        logger.error(f"Error fetching markets: {e}")
        raise PolymarketAPIError(f"Failed to fetch markets: {e}")


def get_market_details(market_id: str) -> Dict:
    """
    Get detailed information about a specific market.
    
    Args:
        market_id: Market ID (Ethereum address)
        
    Returns:
        Market details dictionary with all available information
        
    Raises:
        PolymarketAPIError: On API errors
    """
    url = f"{POLYMARKET_API_BASE_URL}/markets/{market_id}"
    
    try:
        logger.info(f"Fetching market details: {market_id}")
        data = _make_request(url)
        return data
        
    except PolymarketAPIError:
        raise
    except Exception as e:
        logger.error(f"Error fetching market details: {e}")
        raise PolymarketAPIError(f"Failed to fetch market details: {e}")


def get_market_prices(market_id: str) -> Dict:
    """
    Get current prices and implied probabilities for a market.
    
    Args:
        market_id: Market ID
        
    Returns:
        Dictionary with:
        - outcomes: List of outcomes with current prices
        - last_updated: Timestamp of last price update
        
    Raises:
        PolymarketAPIError: On API errors
    """
    url = f"{POLYMARKET_CLOB_API_URL}/prices/{market_id}"
    
    try:
        logger.info(f"Fetching market prices: {market_id}")
        data = _make_request(url)
        return data
        
    except PolymarketAPIError:
        raise
    except Exception as e:
        logger.error(f"Error fetching market prices: {e}")
        raise PolymarketAPIError(f"Failed to fetch market prices: {e}")


def search_markets_by_keywords(
    keywords: List[str],
    category: Optional[str] = None,
    active: bool = True,
    limit_per_keyword: int = 20
) -> List[Dict]:
    """
    Search for markets matching any of the provided keywords.
    
    Args:
        keywords: List of search terms
        category: Optional category filter
        active: Only return active markets
        limit_per_keyword: Max results per keyword
        
    Returns:
        Deduplicated list of markets sorted by relevance
    """
    all_markets = []
    seen_ids = set()
    
    for keyword in keywords:
        try:
            markets = fetch_markets(
                query=keyword,
                category=category,
                active=active,
                limit=limit_per_keyword
            )
            
            # Deduplicate by market ID
            for market in markets:
                market_id = market.get('id')
                if market_id and market_id not in seen_ids:
                    seen_ids.add(market_id)
                    # Add search keyword for relevance tracking
                    market['matched_keyword'] = keyword
                    all_markets.append(market)
                    
        except PolymarketAPIError as e:
            logger.warning(f"Error searching for keyword '{keyword}': {e}")
            continue
    
    logger.info(f"Found {len(all_markets)} unique markets across {len(keywords)} keywords")
    return all_markets


def get_market_history(
    market_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    interval: str = "1d"
) -> List[Dict]:
    """
    Get historical price data for a market.
    
    Args:
        market_id: Market ID
        start_date: Start date in YYYY-MM-DD format (default: 30 days ago)
        end_date: End date in YYYY-MM-DD format (default: today)
        interval: Data interval ('1h', '1d', '1w')
        
    Returns:
        List of historical data points with:
        - timestamp: ISO timestamp
        - probability: Implied probability at that time
        - volume_24h: 24-hour trading volume
        
    Raises:
        PolymarketAPIError: On API errors
    """
    # Default to last 30 days if not specified
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_dt = datetime.now() - timedelta(days=30)
        start_date = start_dt.strftime("%Y-%m-%d")
    
    url = f"{POLYMARKET_API_BASE_URL}/markets/{market_id}/history"
    params = {
        "start": start_date,
        "end": end_date,
        "interval": interval
    }
    
    try:
        logger.info(f"Fetching market history: {market_id} ({start_date} to {end_date})")
        data = _make_request(url, params=params)
        
        # API may return list directly or wrapped
        history = data if isinstance(data, list) else data.get('history', [])
        return history
        
    except PolymarketAPIError:
        raise
    except Exception as e:
        logger.error(f"Error fetching market history: {e}")
        raise PolymarketAPIError(f"Failed to fetch market history: {e}")


def get_trending_markets(
    category: Optional[str] = None,
    limit: int = 20,
    time_window: str = "24h"
) -> List[Dict]:
    """
    Get trending markets by volume.
    
    Args:
        category: Optional category filter
        limit: Number of markets to return
        time_window: Time window for volume calculation ('24h', '7d', '30d')
        
    Returns:
        List of markets sorted by recent volume
    """
    try:
        # Fetch active markets
        markets = fetch_markets(
            category=category,
            active=True,
            limit=limit * 2  # Fetch more to account for filtering
        )
        
        # Sort by volume (descending)
        markets.sort(key=lambda m: m.get('volume', 0), reverse=True)
        
        # Return top N
        return markets[:limit]
        
    except PolymarketAPIError:
        raise
    except Exception as e:
        logger.error(f"Error fetching trending markets: {e}")
        raise PolymarketAPIError(f"Failed to fetch trending markets: {e}")


@lru_cache(maxsize=100)
def get_market_categories() -> List[str]:
    """
    Get list of available market categories.
    
    Returns:
        List of category names
    """
    # Common categories based on Polymarket structure
    return [
        "finance",
        "crypto",
        "politics",
        "sports",
        "economics",
        "technology",
        "entertainment"
    ]


def health_check() -> bool:
    """
    Check if Polymarket API is accessible.
    
    Returns:
        True if API is healthy, False otherwise
    """
    try:
        url = f"{POLYMARKET_API_BASE_URL}/markets"
        params = {"limit": 1}
        _make_request(url, params=params, timeout=5)
        return True
    except Exception as e:
        logger.error(f"Polymarket API health check failed: {e}")
        return False


# Utility functions for data processing

def extract_probability(market: Dict, outcome_index: int = 0) -> float:
    """
    Extract implied probability from market data.
    
    Args:
        market: Market dictionary
        outcome_index: Index of outcome to get probability for (default: 0 for "Yes")
        
    Returns:
        Probability as float between 0 and 1
    """
    market_id = market.get('id', 'unknown')
    question = market.get('question', market.get('event_title', 'N/A'))[:50]
    
    # Try lastTradePrice first (most recent actual price)
    if 'lastTradePrice' in market:
        try:
            price = float(market['lastTradePrice'])
            # lastTradePrice is already in 0-1 range
            prob = max(0.0, min(1.0, price))
            logger.debug(f"Market {market_id} '{question}': Using lastTradePrice={price:.4f} -> {prob:.4f}")
            return prob
        except (ValueError, TypeError) as e:
            logger.warning(f"Market {market_id}: Invalid lastTradePrice: {market.get('lastTradePrice')} - {e}")
    
    # Try outcomePrices array (string values that need conversion)
    outcome_prices = market.get('outcomePrices', [])
    if outcome_prices and outcome_index < len(outcome_prices):
        try:
            price_str = outcome_prices[outcome_index]
            price = float(price_str)
            # outcomePrices are already in 0-1 range (e.g., "0.055" = 5.5%)
            prob = max(0.0, min(1.0, price))
            logger.debug(f"Market {market_id} '{question}': Using outcomePrices[{outcome_index}]={price_str} -> {prob:.4f}")
            return prob
        except (ValueError, TypeError, IndexError) as e:
            logger.warning(f"Market {market_id}: Invalid outcomePrices: {outcome_prices} - {e}")
    
    # Try bestBid/bestAsk for current market price
    if 'bestBid' in market:
        try:
            price = float(market['bestBid'])
            prob = max(0.0, min(1.0, price))
            logger.debug(f"Market {market_id} '{question}': Using bestBid={price:.4f} -> {prob:.4f}")
            return prob
        except (ValueError, TypeError) as e:
            logger.warning(f"Market {market_id}: Invalid bestBid: {market.get('bestBid')} - {e}")
    
    # Try direct price field
    if 'price' in market:
        try:
            price = float(market['price'])
            if price > 1:
                price = price / 100
            prob = max(0.0, min(1.0, price))
            logger.debug(f"Market {market_id} '{question}': Using price={market.get('price')} -> {prob:.4f}")
            return prob
        except (ValueError, TypeError) as e:
            logger.warning(f"Market {market_id}: Invalid price: {market.get('price')} - {e}")
    
    # Try outcomes array
    outcomes = market.get('outcomes', [])
    if outcomes and outcome_index < len(outcomes):
        outcome = outcomes[outcome_index]
        
        # Handle case where outcome is a dict
        if isinstance(outcome, dict):
            price = outcome.get('price', 0.5)
            try:
                price = float(price)
                if price > 1:
                    price = price / 100
                prob = max(0.0, min(1.0, price))
                logger.debug(f"Market {market_id} '{question}': Using outcomes[{outcome_index}].price={outcome.get('price')} -> {prob:.4f}")
                return prob
            except (ValueError, TypeError) as e:
                logger.warning(f"Market {market_id}: Invalid outcome price: {outcome.get('price')} - {e}")
    
    # Log all available price fields for debugging
    logger.warning(
        f"Market {market_id} '{question}': No valid probability found. "
        f"Available fields: lastTradePrice={market.get('lastTradePrice')}, "
        f"outcomePrices={market.get('outcomePrices')}, "
        f"bestBid={market.get('bestBid')}, "
        f"price={market.get('price')}, "
        f"outcomes={len(outcomes)} items"
    )
    
    # Fallback to neutral
    return 0.5


def calculate_24h_change(market: Dict) -> float:
    """
    Calculate 24-hour probability change.
    
    Args:
        market: Market dictionary with price history
        
    Returns:
        Change in probability (e.g., 0.03 for +3%)
    """
    try:
        # Try to get from market data if available
        if 'change_24h' in market:
            return market['change_24h']
        
        # Otherwise would need to fetch history
        # For now, return 0 as placeholder
        return 0.0
        
    except Exception:
        return 0.0


def format_market_for_display(market: Dict) -> Dict:
    """
    Format market data for frontend display.
    
    Args:
        market: Raw market data from API
        
    Returns:
        Formatted market dictionary
    """
    return {
        "id": market.get('id'),
        "question": market.get('question', ''),
        "description": market.get('description', ''),
        "probability": extract_probability(market),
        "change_24h": calculate_24h_change(market),
        "volume": market.get('volume', 0),
        "liquidity": market.get('liquidity', 0),
        "end_date": market.get('end_date', ''),
        "category": market.get('category', ''),
        "tags": market.get('tags', []),
        "active": market.get('active', True),
        "url": f"https://polymarket.com/event/{market.get('slug', market.get('id'))}"
    }

# Made with Bob
