"""Data source implementations."""

from data_layer.sources.base import (
    EdgarSourceProtocol,
    MarketDataSourceProtocol,
    ReportDataSourceProtocol,
    UserPortfolioSourceProtocol,
)
from data_layer.sources.market import CachedMarketSource
from data_layer.sources.reports import ReportDataSource
from data_layer.sources.user import UserPortfolioSource
from data_layer.sources.edgar import EdgarDataSource

__all__ = [
    "MarketDataSourceProtocol",
    "ReportDataSourceProtocol",
    "UserPortfolioSourceProtocol",
    "EdgarSourceProtocol",
    "CachedMarketSource",
    "ReportDataSource",
    "UserPortfolioSource",
    "EdgarDataSource",
]
