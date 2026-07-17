from langchain_core.tools import tool
from typing import Annotated, Optional

from ...datasources.info_service_client import (
    get_news as get_news_via_service,
    get_reddit_company_social as get_reddit_company_social_via_service,
    get_global_news as get_global_news_via_service,
    get_insider_sentiment as get_insider_sentiment_via_service,
    get_insider_transactions as get_insider_transactions_via_service,
    get_polymarket_sentiment as get_polymarket_sentiment_via_service,
    require_info_service,
)


def _format_polymarket_sentiment(ticker: str, data: Optional[dict]) -> str:
    """Format the aggregated Polymarket sentiment dict into a readable summary for the LLM."""
    if not data:
        return (
            f"No Polymarket prediction-market data available for {ticker.upper()} "
            "(service unavailable or no relevant markets)."
        )

    error = data.get("error")
    top_markets = data.get("top_markets") or []
    market_count = data.get("market_count", 0)

    if error and not top_markets:
        return (
            f"No relevant Polymarket prediction markets found for {ticker.upper()}: {error}. "
            "Treat prediction-market signal as neutral / unavailable."
        )

    overall = data.get("overall_sentiment", 0.5)
    confidence = data.get("confidence", 0.0)
    trend = data.get("trend", "neutral")

    lines = [
        f"# Polymarket prediction-market sentiment for {ticker.upper()}",
        "",
        f"- Overall sentiment: {overall:.2f} on a 0 (bearish) .. 0.5 (neutral) .. 1 (bullish) scale",
        f"- Trend: {trend}",
        f"- Confidence: {confidence:.2f} (0..1; driven by trading volume — low volume = weak signal)",
        f"- Relevant markets found: {market_count}",
        "",
        "Prediction markets aggregate real-money bets and are a forward-looking, "
        "crowd-sourced signal that complements social/Reddit chatter.",
        "",
    ]

    if top_markets:
        lines.append("## Top relevant markets")
        for m in top_markets[:15]:
            question = (m.get("question") or m.get("event_title") or "").strip()
            if not question:
                continue
            prob = m.get("probability")
            change = m.get("change_24h")
            volume = m.get("volume")
            end_date = m.get("end_date") or ""
            parts = []
            if isinstance(prob, (int, float)):
                parts.append(f"prob={prob * 100:.0f}%")
            if isinstance(change, (int, float)):
                parts.append(f"24h Δ={change * 100:+.1f}pp")
            if isinstance(volume, (int, float)) and volume:
                parts.append(f"vol=${volume:,.0f}")
            if end_date:
                parts.append(f"ends {str(end_date)[:10]}")
            meta = ", ".join(parts)
            lines.append(f"- {question}" + (f" ({meta})" if meta else ""))
    else:
        lines.append("No individual markets to display.")

    return "\n".join(lines)


@tool
def get_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve news data for a given ticker symbol.
    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    Args:
        ticker (str): Ticker symbol
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted string containing news data
    """
    require_info_service()
    return get_news_via_service(ticker, start_date, end_date)


@tool
def get_reddit_company_social(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    search_terms: Annotated[
        list[str],
        "Terms to search for in Reddit (e.g. company name and ticker). Get company name from get_quote or get_news first, then pass e.g. ['Apple', 'AAPL'].",
    ],
) -> str:
    """
    Retrieve Reddit social/discussion content for a company from finance subreddits
    (e.g. r/stocks, r/investing, r/wallstreetbets). You must provide search_terms: use get_quote(ticker)
    or get_news to get the company name, then pass a list of terms to look for (e.g. company name and ticker).
    Requires INFO_SERVICE_URL and backend REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET.
    """
    require_info_service()
    return get_reddit_company_social_via_service(ticker, start_date, end_date, search_terms)


@tool
def get_polymarket_sentiment(
    ticker: Annotated[str, "Ticker symbol"],
) -> str:
    """
    Retrieve aggregated Polymarket prediction-market sentiment for a company/ticker.

    Polymarket is a prediction market where people bet real money on future outcomes,
    so the implied probabilities are a forward-looking, crowd-sourced sentiment signal that
    complements social-media discussion. The backend maps the ticker to relevant market
    narratives (company events, sector/industry, macro factors), scores markets by relevance,
    and aggregates them into an overall sentiment.

    Returns a formatted summary with:
      - Overall sentiment on a 0 (bearish) .. 0.5 (neutral) .. 1 (bullish) scale
      - Trend (bullish / neutral / bearish) and confidence (volume-driven; low volume = weak signal)
      - The most relevant individual markets with implied probability, 24h change, and volume

    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    """
    require_info_service()
    data = get_polymarket_sentiment_via_service(ticker)
    return _format_polymarket_sentiment(ticker, data)


@tool
def get_global_news(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of articles to return"] = 5,
    query: Annotated[Optional[str], "Optional search focus (e.g. key risks, inflation)"] = None,
) -> str:
    """
    Retrieve global news data.
    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    Args:
        curr_date (str): Current date in yyyy-mm-dd format
        look_back_days (int): Number of days to look back (default 7)
        limit (int): Maximum number of articles to return (default 5)
        query (Optional[str]): Optional focus for the search; vendors may use it to narrow results
    Returns:
        str: A formatted string containing global news data
    """
    require_info_service()
    return get_global_news_via_service(curr_date, look_back_days, limit, query=query)


@tool
def get_insider_sentiment(
    ticker: Annotated[str, "ticker symbol for the company"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
) -> str:
    """
    Retrieve insider sentiment information about a company.
    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A report of insider sentiment data
    """
    require_info_service()
    return get_insider_sentiment_via_service(ticker, curr_date)


@tool
def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
) -> str:
    """
    Retrieve insider transaction information about a company.
    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A report of insider transaction data
    """
    require_info_service()
    return get_insider_transactions_via_service(ticker, limit=50)
