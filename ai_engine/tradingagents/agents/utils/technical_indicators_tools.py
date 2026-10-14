from langchain_core.tools import tool
from typing import Annotated

from ...datasources.info_service_client import get_indicators as get_indicators_via_service, require_info_service

# Names the data vendors accept (backend/data_layer/vendors/y_finance.py). Models still guess
# generic names like "sma" despite the prompt listing these, and the backend answers a bad
# name with a bare HTTP 500, so the model never learned what to send instead.
SUPPORTED_INDICATORS = (
    "close_50_sma", "close_200_sma", "close_10_ema", "macd", "macds", "macdh",
    "rsi", "boll", "boll_ub", "boll_lb", "atr", "vwma", "mfi",
)


@tool
def get_indicators(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator name, exactly one of: " + ", ".join(SUPPORTED_INDICATORS)],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"] = 30,
) -> str:
    """
    Retrieve technical indicators for a given ticker symbol.
    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    Args:
        symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
        indicator (str): Technical indicator to get the analysis and report of
        curr_date (str): The current trading date you are trading on, YYYY-mm-dd
        look_back_days (int): How many days to look back, default is 30
    Returns:
        str: A formatted dataframe containing the technical indicators for the specified ticker symbol and indicator.
    """
    if indicator not in SUPPORTED_INDICATORS:
        return (
            f"Error: unsupported indicator '{indicator}'. "
            f"Use exactly one of: {', '.join(SUPPORTED_INDICATORS)}."
        )
    require_info_service()
    return get_indicators_via_service(symbol, indicator, curr_date, look_back_days)
