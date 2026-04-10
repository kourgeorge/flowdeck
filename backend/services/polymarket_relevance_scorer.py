"""
Polymarket Market Relevance Scorer

Scores and ranks Polymarket markets by their relevance to a specific stock ticker.
Uses multi-factor scoring including keyword matching, narrative alignment, liquidity, and time relevance.
"""

import math
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def score_market_relevance(
    market: Dict,
    ticker: str,
    narratives: List[str],
    company_info: Optional[Dict] = None
) -> float:
    """
    Calculate relevance score for a market (0-1 scale).
    
    Scoring factors:
    - Keyword match (0-0.3): Direct ticker/company mentions
    - Narrative alignment (0-0.3): Matches narrative categories
    - Liquidity weight (0-0.2): log(volume) normalized
    - Time relevance (0-0.1): Near-term markets preferred
    - Resolution clarity (0-0.1): Clear, measurable outcomes
    
    Args:
        market: Market dictionary from Polymarket API
        ticker: Stock ticker symbol
        narratives: List of relevant narrative queries
        company_info: Optional company information dict
        
    Returns:
        Relevance score between 0 and 1
    """
    score = 0.0
    
    # Extract market text
    question = market.get('question', '').lower()
    description = market.get('description', '').lower()
    combined_text = f"{question} {description}"
    
    # Get company name if available
    company_name = ""
    if company_info and company_info.get('name'):
        company_name = company_info['name'].lower()
    
    ticker_lower = ticker.lower()
    
    # 1. Keyword matching (0-0.3)
    keyword_score = calculate_keyword_score(
        combined_text,
        ticker_lower,
        company_name
    )
    score += keyword_score
    
    # 2. Narrative alignment (0-0.3)
    narrative_score = calculate_narrative_score(
        combined_text,
        narratives
    )
    score += narrative_score
    
    # 3. Liquidity weight (0-0.2)
    liquidity_score = calculate_liquidity_score(market)
    score += liquidity_score
    
    # 4. Time relevance (0-0.1)
    time_score = calculate_time_relevance_score(market)
    score += time_score
    
    # 5. Resolution clarity (0-0.1)
    clarity_score = calculate_clarity_score(question)
    score += clarity_score
    
    # Ensure score is in valid range
    final_score = max(0.0, min(1.0, score))
    
    logger.debug(
        f"Market relevance: {final_score:.3f} "
        f"(keyword={keyword_score:.3f}, narrative={narrative_score:.3f}, "
        f"liquidity={liquidity_score:.3f}, time={time_score:.3f}, clarity={clarity_score:.3f})"
    )
    
    return final_score


def calculate_keyword_score(
    text: str,
    ticker: str,
    company_name: str
) -> float:
    """
    Score based on direct keyword matches (0-0.3).
    
    Args:
        text: Combined question and description text
        ticker: Ticker symbol (lowercase)
        company_name: Company name (lowercase)
        
    Returns:
        Keyword match score
    """
    score = 0.0
    
    # Exact ticker match (highest weight)
    if f" {ticker} " in f" {text} " or f"${ticker}" in text:
        score = 0.3
    # Company name match
    elif company_name and company_name in text:
        score = 0.25
    # Partial ticker match (e.g., in a longer word)
    elif ticker in text:
        score = 0.15
    # Partial company name match
    elif company_name and any(word in text for word in company_name.split() if len(word) > 3):
        score = 0.1
    
    return score


def calculate_narrative_score(
    text: str,
    narratives: List[str]
) -> float:
    """
    Score based on narrative alignment (0-0.3).
    
    Args:
        text: Combined question and description text
        narratives: List of narrative queries
        
    Returns:
        Narrative alignment score
    """
    if not narratives:
        return 0.0
    
    # Count how many narratives match
    matches = 0
    for narrative in narratives:
        narrative_lower = narrative.lower()
        # Check for substring match
        if narrative_lower in text:
            matches += 1
        # Check for word-level match (more lenient)
        elif any(word in text for word in narrative_lower.split() if len(word) > 3):
            matches += 0.5
    
    # Normalize by number of narratives, cap at 0.3
    score = min(matches * 0.1, 0.3)
    
    return score


def calculate_liquidity_score(market: Dict) -> float:
    """
    Score based on market liquidity (0-0.2).
    
    Higher volume = stronger signal (more money backing the prediction).
    
    Args:
        market: Market dictionary
        
    Returns:
        Liquidity score
    """
    # Convert to float to handle string values from API
    try:
        volume = float(market.get('volume', 0)) if market.get('volume') else 0
        liquidity = float(market.get('liquidity', 0)) if market.get('liquidity') else 0
    except (ValueError, TypeError):
        volume = 0
        liquidity = 0
    
    # Use volume as primary metric
    if volume >= 100000:
        score = 0.2
    elif volume >= 50000:
        score = 0.18
    elif volume >= 10000:
        score = 0.15
    elif volume >= 5000:
        score = 0.12
    elif volume >= 1000:
        score = 0.1
    else:
        score = 0.05
    
    # Boost if liquidity is also high
    if liquidity >= 10000:
        score = min(score + 0.02, 0.2)
    
    return score


def calculate_time_relevance_score(market: Dict) -> float:
    """
    Score based on time until resolution (0-0.1).
    
    Near-term markets are more relevant for current trading decisions.
    
    Args:
        market: Market dictionary
        
    Returns:
        Time relevance score
    """
    end_date_str = market.get('end_date')
    if not end_date_str:
        return 0.05  # Default for markets without end date
    
    try:
        # Parse end date
        if 'T' in end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        else:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        # Calculate days until resolution
        now = datetime.now(end_date.tzinfo) if end_date.tzinfo else datetime.now()
        days_until = (end_date - now).days
        
        # Score based on time horizon
        if days_until <= 0:
            score = 0.02  # Resolved markets have low relevance
        elif days_until <= 7:
            score = 0.1  # Very near-term: highest relevance
        elif days_until <= 30:
            score = 0.09  # Near-term: high relevance
        elif days_until <= 90:
            score = 0.07  # Medium-term: good relevance
        elif days_until <= 180:
            score = 0.05  # Long-term: moderate relevance
        else:
            score = 0.03  # Very long-term: low relevance
        
        return score
        
    except Exception as e:
        logger.warning(f"Error parsing end date '{end_date_str}': {e}")
        return 0.05


def calculate_clarity_score(question: str) -> float:
    """
    Score based on resolution clarity (0-0.1).
    
    Markets with clear, measurable outcomes are preferred.
    
    Args:
        question: Market question text
        
    Returns:
        Clarity score
    """
    question_lower = question.lower()
    
    # Keywords indicating clear, measurable outcomes
    clarity_keywords = [
        'price', 'above', 'below', 'reach', 'exceed',
        'beat', 'miss', 'earnings', 'revenue',
        'will', 'by', 'before', 'after',
        'percentage', 'percent', '%', '$'
    ]
    
    # Count clarity indicators
    clarity_count = sum(1 for keyword in clarity_keywords if keyword in question_lower)
    
    # Score based on clarity indicators
    if clarity_count >= 3:
        score = 0.1
    elif clarity_count >= 2:
        score = 0.08
    elif clarity_count >= 1:
        score = 0.06
    else:
        score = 0.04
    
    # Penalize vague questions
    vague_keywords = ['might', 'could', 'possibly', 'maybe', 'uncertain']
    if any(keyword in question_lower for keyword in vague_keywords):
        score *= 0.5
    
    return score


def rank_markets_by_relevance(
    markets: List[Dict],
    ticker: str,
    narratives: List[str],
    company_info: Optional[Dict] = None,
    min_score: float = 0.1
) -> List[Dict]:
    """
    Score and rank markets by relevance to ticker.
    
    Args:
        markets: List of market dictionaries
        ticker: Stock ticker symbol
        narratives: List of relevant narratives
        company_info: Optional company information
        min_score: Minimum relevance score to include
        
    Returns:
        List of markets with relevance_score added, sorted by score (descending)
    """
    scored_markets = []
    
    for market in markets:
        score = score_market_relevance(
            market,
            ticker,
            narratives,
            company_info
        )
        
        # Only include markets above minimum threshold
        if score >= min_score:
            market_copy = market.copy()
            market_copy['relevance_score'] = score
            scored_markets.append(market_copy)
    
    # Sort by relevance score (descending)
    scored_markets.sort(key=lambda m: m['relevance_score'], reverse=True)
    
    logger.info(
        f"Ranked {len(scored_markets)} markets for {ticker} "
        f"(filtered from {len(markets)} total)"
    )
    
    return scored_markets


def filter_top_markets(
    markets: List[Dict],
    top_n: int = 10,
    diversity_factor: float = 0.3
) -> List[Dict]:
    """
    Select top N markets with diversity consideration.
    
    Ensures we don't just get multiple markets about the same topic.
    
    Args:
        markets: List of scored markets (sorted by relevance)
        top_n: Number of markets to return
        diversity_factor: Weight for diversity (0-1, higher = more diverse)
        
    Returns:
        Top N diverse markets
    """
    if len(markets) <= top_n:
        return markets
    
    selected = []
    remaining = markets.copy()
    
    # Always include the top market
    if remaining:
        selected.append(remaining.pop(0))
    
    # Select remaining markets with diversity consideration
    while len(selected) < top_n and remaining:
        best_score = -1
        best_idx = 0
        
        for idx, market in enumerate(remaining):
            # Base score is relevance
            score = market.get('relevance_score', 0)
            
            # Apply diversity penalty if too similar to selected markets
            if diversity_factor > 0:
                similarity_penalty = calculate_similarity_penalty(
                    market,
                    selected
                )
                score = score * (1 - diversity_factor * similarity_penalty)
            
            if score > best_score:
                best_score = score
                best_idx = idx
        
        selected.append(remaining.pop(best_idx))
    
    return selected


def calculate_similarity_penalty(
    market: Dict,
    selected_markets: List[Dict]
) -> float:
    """
    Calculate similarity penalty for diversity filtering.
    
    Args:
        market: Market to evaluate
        selected_markets: Already selected markets
        
    Returns:
        Penalty factor (0-1, higher = more similar)
    """
    if not selected_markets:
        return 0.0
    
    question = market.get('question', '').lower()
    question_words = set(question.split())
    
    max_similarity = 0.0
    
    for selected in selected_markets:
        selected_question = selected.get('question', '').lower()
        selected_words = set(selected_question.split())
        
        # Calculate Jaccard similarity
        if question_words and selected_words:
            intersection = len(question_words & selected_words)
            union = len(question_words | selected_words)
            similarity = intersection / union if union > 0 else 0
            max_similarity = max(max_similarity, similarity)
    
    return max_similarity


def get_market_narrative_category(
    market: Dict,
    narratives: List[str]
) -> str:
    """
    Determine which narrative category a market belongs to.
    
    Args:
        market: Market dictionary
        narratives: List of narrative queries
        
    Returns:
        Narrative category name
    """
    question = market.get('question', '').lower()
    description = market.get('description', '').lower()
    combined_text = f"{question} {description}"
    
    # Check which narrative matches best
    best_match = "general"
    best_match_count = 0
    
    for narrative in narratives:
        narrative_lower = narrative.lower()
        words = narrative_lower.split()
        match_count = sum(1 for word in words if len(word) > 3 and word in combined_text)
        
        if match_count > best_match_count:
            best_match_count = match_count
            best_match = narrative
    
    # Categorize based on content
    if any(term in combined_text for term in ['fed', 'rate', 'interest', 'inflation']):
        return "macro_liquidity"
    elif any(term in combined_text for term in ['recession', 'gdp', 'unemployment']):
        return "economic_indicators"
    elif any(term in combined_text for term in ['china', 'trade', 'tariff', 'geopolitical']):
        return "geopolitical"
    elif best_match != "general":
        return best_match
    
    return "general"


# Example usage and testing
if __name__ == "__main__":
    # Test market scoring
    test_market = {
        "id": "0x123",
        "question": "Will NVDA stock reach $1000 by end of Q2 2026?",
        "description": "Resolves YES if Nvidia closes above $1000",
        "volume": 85000,
        "liquidity": 32000,
        "end_date": "2026-06-30T23:59:59Z"
    }
    
    test_narratives = [
        "NVDA", "Nvidia", "AI stocks", "semiconductor", "Fed rate cuts"
    ]
    
    test_company_info = {
        "name": "NVIDIA Corporation",
        "sector": "Technology",
        "industry": "Semiconductors"
    }
    
    score = score_market_relevance(
        test_market,
        "NVDA",
        test_narratives,
        test_company_info
    )
    
    print(f"Market: {test_market['question']}")
    print(f"Relevance Score: {score:.3f}")
    print(f"Category: {get_market_narrative_category(test_market, test_narratives)}")

# Made with Bob
