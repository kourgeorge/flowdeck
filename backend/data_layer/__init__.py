"""
Data layer: unified gateway for internal and external data sources.

Single entry point for REST API, AI agents, and other app components.
Supports pluggable sources (market, reports, user, EDGAR) with caching where configured.
"""

from data_layer.gateway import DataGateway, get_data_gateway, init_data_gateway

__all__ = ["DataGateway", "get_data_gateway", "init_data_gateway"]
