from typing import Annotated, Optional
from datetime import datetime
from dateutil.relativedelta import relativedelta
from .googlenews_utils import getNewsData


def get_google_news(
    query: Annotated[str, "Query to search with or ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Get Google News for a query/ticker between start_date and end_date."""
    query = query.replace(" ", "+")

    news_results = getNewsData(query, start_date, end_date)

    news_str = ""

    for news in news_results:
        news_str += (
            f"### {news['title']} (source: {news['source']}) \n\n{news['snippet']}\n\n"
        )

    if len(news_results) == 0:
        return ""

    return f"## {query} Google News, from {start_date} to {end_date}:\n\n{news_str}"


def get_global_news_google(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of articles to return"] = 5,
    query: Annotated[Optional[str], "Optional search focus"] = None,
) -> str:
    """Get global/macroeconomic news from Google News for trading purposes."""
    # Calculate start_date from curr_date and look_back_days
    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_date_dt = curr_date_dt - relativedelta(days=look_back_days)
    start_date = start_date_dt.strftime("%Y-%m-%d")
    
    # Use user query if provided, else general macro query
    search_query = (
        query.strip().replace(" ", "+") if query and query.strip()
        else "global+economics+OR+macroeconomics+OR+financial+markets+OR+trading+news"
    )
    
    news_results = getNewsData(search_query, start_date, curr_date)
    
    # Limit results to the specified number
    news_results = news_results[:limit]
    
    news_str = ""
    for news in news_results:
        news_str += (
            f"### {news['title']} (source: {news['source']}) \n\n{news['snippet']}\n\n"
        )
    
    if len(news_results) == 0:
        return ""
    
    return f"## Global News (Google), from {start_date} to {curr_date}:\n\n{news_str}"