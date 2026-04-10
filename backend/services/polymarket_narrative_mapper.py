"""
Polymarket Narrative Mapper

Maps stock tickers to relevant narrative categories and search queries for Polymarket.
This enables finding markets that indirectly affect a stock (e.g., "Fed rates" affects NVDA).
"""

import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Narrative templates organized by category
NARRATIVE_TEMPLATES = {
    "macro_liquidity": [
        "Fed rate decision",
        "interest rates",
        "rate cuts",
        "rate hikes",
        "monetary policy",
        "inflation",
        "CPI",
        "Federal Reserve"
    ],
    "economic_indicators": [
        "GDP growth",
        "unemployment rate",
        "recession probability",
        "economic growth",
        "consumer spending",
        "retail sales",
        "jobless claims"
    ],
    "geopolitical": [
        "China economy",
        "trade war",
        "tariffs",
        "sanctions",
        "geopolitical tensions",
        "supply chain disruptions"
    ],
    "market_sentiment": [
        "stock market crash",
        "bull market",
        "bear market",
        "market volatility",
        "VIX",
        "investor sentiment"
    ]
}

# Sector-specific narratives
SECTOR_NARRATIVES = {
    "Technology": [
        "AI stocks",
        "artificial intelligence",
        "tech sector",
        "semiconductor industry",
        "cloud computing",
        "software stocks",
        "tech earnings",
        "NASDAQ performance"
    ],
    "Energy": [
        "oil prices",
        "crude oil",
        "renewable energy",
        "EV adoption",
        "electric vehicles",
        "energy sector",
        "OPEC",
        "natural gas"
    ],
    "Financial Services": [
        "banking sector",
        "interest rates",
        "financial stocks",
        "bank earnings",
        "fintech",
        "crypto regulation",
        "lending rates"
    ],
    "Healthcare": [
        "healthcare stocks",
        "pharma sector",
        "drug approval",
        "Medicare",
        "biotech",
        "FDA approval"
    ],
    "Consumer Cyclical": [
        "consumer spending",
        "retail sales",
        "e-commerce",
        "consumer confidence",
        "holiday shopping"
    ],
    "Consumer Defensive": [
        "consumer staples",
        "inflation impact",
        "food prices",
        "retail sector"
    ],
    "Industrials": [
        "manufacturing",
        "industrial production",
        "supply chain",
        "infrastructure spending"
    ],
    "Real Estate": [
        "housing market",
        "real estate",
        "mortgage rates",
        "commercial real estate"
    ],
    "Communication Services": [
        "media stocks",
        "streaming",
        "advertising spending",
        "social media"
    ],
    "Utilities": [
        "utility stocks",
        "energy prices",
        "renewable energy"
    ],
    "Basic Materials": [
        "commodity prices",
        "metals",
        "mining",
        "raw materials"
    ]
}

# Industry-specific narratives (more granular)
INDUSTRY_NARRATIVES = {
    "Semiconductors": [
        "chip shortage",
        "semiconductor demand",
        "GPU market",
        "AI chips",
        "Taiwan semiconductor"
    ],
    "Software": [
        "SaaS growth",
        "cloud adoption",
        "enterprise software",
        "software spending"
    ],
    "Internet Content & Information": [
        "digital advertising",
        "online traffic",
        "search engine",
        "social media users"
    ],
    "Auto Manufacturers": [
        "EV sales",
        "auto sales",
        "vehicle production",
        "autonomous driving"
    ],
    "Banks": [
        "bank deposits",
        "loan growth",
        "banking crisis",
        "interest margins"
    ],
    "Oil & Gas": [
        "oil production",
        "energy demand",
        "drilling activity"
    ],
    "Biotechnology": [
        "drug trials",
        "FDA decisions",
        "biotech funding"
    ],
    "Aerospace & Defense": [
        "defense spending",
        "aircraft orders",
        "space industry"
    ]
}

# Company-specific keywords (for major companies)
COMPANY_SPECIFIC_KEYWORDS = {
    "AAPL": ["Apple", "iPhone", "iOS", "Mac", "iPad", "App Store"],
    "MSFT": ["Microsoft", "Windows", "Azure", "Office", "Xbox"],
    "GOOGL": ["Google", "Alphabet", "search", "YouTube", "Android"],
    "AMZN": ["Amazon", "AWS", "e-commerce", "Prime"],
    "NVDA": [
        "Nvidia", "GPU", "AI chips", "graphics cards",
        "NVDA price", "NVDA Week", "Nvidia stock price"  # Added price-specific terms
    ],
    "TSLA": ["Tesla", "EV", "electric vehicles", "Elon Musk", "TSLA price"],
    "META": ["Meta", "Facebook", "Instagram", "WhatsApp", "metaverse"],
    "NFLX": ["Netflix", "streaming", "subscribers"],
    "AMD": ["AMD", "Ryzen", "EPYC", "graphics cards"],
    "INTC": ["Intel", "processors", "chips"],
    "JPM": ["JPMorgan", "JP Morgan", "Chase"],
    "BAC": ["Bank of America", "BofA"],
    "WMT": ["Walmart", "retail"],
    "DIS": ["Disney", "Disney+", "theme parks"],
    "V": ["Visa", "payment processing"],
    "MA": ["Mastercard", "payment processing"],
    "PYPL": ["PayPal", "digital payments"],
    "CRM": ["Salesforce", "CRM software"],
    "ORCL": ["Oracle", "database", "cloud"],
    "CSCO": ["Cisco", "networking"],
    "BA": ["Boeing", "aircraft"],
    "GE": ["General Electric", "GE"],
    "XOM": ["Exxon", "ExxonMobil"],
    "CVX": ["Chevron"],
    "PFE": ["Pfizer", "vaccine"],
    "JNJ": ["Johnson & Johnson", "J&J"],
    "UNH": ["UnitedHealth", "health insurance"],
}


def map_ticker_to_narratives(
    ticker: str,
    company_info: Optional[Dict] = None
) -> List[str]:
    """
    Generate prioritized list of search queries for Polymarket based on ticker context.
    
    Args:
        ticker: Stock ticker symbol (e.g., "NVDA")
        company_info: Optional dict with keys: name, sector, industry
        
    Returns:
        Ordered list of search queries, most relevant first
    """
    narratives: List[str] = []
    seen: Set[str] = set()
    
    ticker_upper = ticker.upper()
    
    # Helper to add unique narratives
    def add_narrative(query: str) -> None:
        query_lower = query.lower()
        if query_lower not in seen:
            seen.add(query_lower)
            narratives.append(query)
    
    # 1. Direct company mentions (highest priority) - EXPANDED
    add_narrative(ticker_upper)
    add_narrative(f"{ticker_upper} stock")
    add_narrative(f"{ticker_upper} price")
    add_narrative(f"{ticker_upper} earnings")
    add_narrative(f"{ticker_upper} Week")  # Catches "INTC Week of..." markets
    add_narrative(f"${ticker_upper}")
    add_narrative(f"({ticker_upper})")
    
    # Add company-specific keywords if available
    if ticker_upper in COMPANY_SPECIFIC_KEYWORDS:
        for keyword in COMPANY_SPECIFIC_KEYWORDS[ticker_upper]:
            add_narrative(keyword)
            add_narrative(f"{keyword} stock")
            add_narrative(f"{keyword} price")
    
    # Add company name if provided
    if company_info and company_info.get('name'):
        company_name = company_info['name']
        add_narrative(company_name)
        add_narrative(f"{company_name} stock")
        add_narrative(f"{company_name} earnings")
        add_narrative(f"{company_name} price")
    
    # 2. Industry-specific narratives (high priority) - LIMITED
    if company_info and company_info.get('industry'):
        industry = company_info['industry']
        if industry in INDUSTRY_NARRATIVES:
            # Only add top 3 industry narratives to avoid too broad matches
            for narrative in INDUSTRY_NARRATIVES[industry][:3]:
                add_narrative(narrative)
    
    # 3. Sector-specific narratives (medium priority) - VERY LIMITED
    # Reduce sector narratives as they're too broad and match other companies
    if company_info and company_info.get('sector'):
        sector = company_info['sector']
        if sector in SECTOR_NARRATIVES:
            # Only add top 2 sector narratives, skip generic ones
            sector_narratives = SECTOR_NARRATIVES[sector]
            # Filter out overly generic narratives
            specific_narratives = [n for n in sector_narratives
                                  if 'sector' not in n.lower() and 'stocks' not in n.lower()]
            for narrative in specific_narratives[:2]:
                add_narrative(narrative)
    
    # 4. Macro economic drivers (lower priority) - REDUCED
    # Only add if we have few direct matches
    if len(narratives) < 15:
        for narrative in NARRATIVE_TEMPLATES["macro_liquidity"][:2]:  # Reduced from 4 to 2
            add_narrative(narrative)
    
    # Skip economic indicators and market sentiment for now - too generic
    # These can be added back if needed, but they dilute relevance
    
    logger.info(f"Generated {len(narratives)} narratives for {ticker_upper}")
    
    return narratives


def get_narrative_category(query: str) -> str:
    """
    Categorize a search query into a narrative category.
    
    Args:
        query: Search query string
        
    Returns:
        Category name (e.g., "macro_liquidity", "sector_specific", "company_specific")
    """
    query_lower = query.lower()
    
    # Check company-specific
    for ticker, keywords in COMPANY_SPECIFIC_KEYWORDS.items():
        if any(keyword.lower() in query_lower for keyword in keywords):
            return "company_specific"
        if ticker.lower() in query_lower:
            return "company_specific"
    
    # Check narrative templates
    for category, narratives in NARRATIVE_TEMPLATES.items():
        if any(narrative.lower() in query_lower for narrative in narratives):
            return category
    
    # Check sector narratives
    for sector, narratives in SECTOR_NARRATIVES.items():
        if any(narrative.lower() in query_lower for narrative in narratives):
            return "sector_specific"
    
    # Check industry narratives
    for industry, narratives in INDUSTRY_NARRATIVES.items():
        if any(narrative.lower() in query_lower for narrative in narratives):
            return "industry_specific"
    
    return "general"


def prioritize_narratives(
    narratives: List[str],
    max_queries: int = 10
) -> List[str]:
    """
    Reduce and prioritize narrative list to avoid excessive API calls.
    
    Args:
        narratives: Full list of narratives
        max_queries: Maximum number of queries to return
        
    Returns:
        Prioritized subset of narratives
    """
    if len(narratives) <= max_queries:
        return narratives
    
    # Keep first max_queries (already prioritized by map_ticker_to_narratives)
    return narratives[:max_queries]


def get_related_tickers(ticker: str) -> List[str]:
    """
    Get related tickers that might have relevant Polymarket markets.
    
    Args:
        ticker: Stock ticker
        
    Returns:
        List of related ticker symbols
    """
    # Mapping of tickers to related tickers
    RELATED_TICKERS = {
        "NVDA": ["AMD", "INTC", "TSM"],
        "AMD": ["NVDA", "INTC"],
        "TSLA": ["F", "GM", "RIVN", "LCID"],
        "AAPL": ["MSFT", "GOOGL", "AMZN"],
        "MSFT": ["AAPL", "GOOGL", "AMZN"],
        "GOOGL": ["AAPL", "MSFT", "META"],
        "META": ["GOOGL", "SNAP", "PINS"],
        "AMZN": ["WMT", "SHOP"],
        "JPM": ["BAC", "WFC", "C"],
        "BAC": ["JPM", "WFC", "C"],
    }
    
    return RELATED_TICKERS.get(ticker.upper(), [])


def expand_narratives_with_related(
    ticker: str,
    company_info: Optional[Dict] = None,
    include_related: bool = False
) -> List[str]:
    """
    Generate narratives including related companies if requested.
    
    Args:
        ticker: Stock ticker
        company_info: Company information
        include_related: Whether to include related ticker narratives
        
    Returns:
        Expanded list of narratives
    """
    narratives = map_ticker_to_narratives(ticker, company_info)
    
    if include_related:
        related_tickers = get_related_tickers(ticker)
        for related_ticker in related_tickers:
            narratives.append(related_ticker)
            narratives.append(f"{related_ticker} stock")
    
    return narratives


# Example usage and testing
if __name__ == "__main__":
    # Test with NVDA
    nvda_info = {
        "name": "NVIDIA Corporation",
        "sector": "Technology",
        "industry": "Semiconductors"
    }
    
    narratives = map_ticker_to_narratives("NVDA", nvda_info)
    print(f"NVDA Narratives ({len(narratives)}):")
    for i, narrative in enumerate(narratives[:15], 1):
        category = get_narrative_category(narrative)
        print(f"  {i}. {narrative} [{category}]")
    
    print("\n" + "="*50 + "\n")
    
    # Test with TSLA
    tsla_info = {
        "name": "Tesla, Inc.",
        "sector": "Consumer Cyclical",
        "industry": "Auto Manufacturers"
    }
    
    narratives = map_ticker_to_narratives("TSLA", tsla_info)
    print(f"TSLA Narratives ({len(narratives)}):")
    for i, narrative in enumerate(narratives[:15], 1):
        category = get_narrative_category(narrative)
        print(f"  {i}. {narrative} [{category}]")

# Made with Bob
