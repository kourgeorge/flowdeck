"""Configuration for Stock Deep Research (models, search, limits)."""

import os
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SearchAPI(str, Enum):
    TAVILY = "tavily"
    DUCKDUCKGO = "duckduckgo"
    NONE = "none"


class StockDeepResearchConfig(BaseModel):
    """Runtime config for the stock deep research graph."""

    # Models (use init_chat_model-style names: openai:gpt-4o, anthropic:claude-3-5-sonnet, etc.)
    research_model: str = Field(default="openai:gpt-4o", description="Model for supervisor and researchers")
    research_model_max_tokens: int = 8192
    compression_model: str = Field(default="openai:gpt-4o-mini", description="Model for compressing researcher output")
    compression_model_max_tokens: int = 8192
    final_report_model: str = Field(default="openai:gpt-4o", description="Model for final report generation")
    final_report_model_max_tokens: int = 16384

    # Search
    search_api: str = Field(default="duckduckgo", description="tavily | duckduckgo | none")
    max_content_length: int = Field(default=12000, description="Max chars per webpage for summarization (Tavily)")

    # Limits
    max_researcher_iterations: int = Field(default=15, description="Max supervisor loops (delegate → gather)")
    max_concurrent_research_units: int = Field(default=3, description="Max parallel researcher subgraphs")
    max_react_tool_calls: int = Field(default=12, description="Max tool-call rounds per researcher")
    max_structured_output_retries: int = 2

    # Optional: backend URL for SEC/EDGAR (same as tradingagents INFO_SERVICE_URL)
    info_service_url: Optional[str] = Field(default=None, description="Flowdeck backend URL for EDGAR filing content")

    # Optional clarification step (skip for headless/API)
    allow_clarification: bool = Field(default=False, description="Ask user clarifying questions before research")

    class Config:
        extra = "allow"

    @classmethod
    def from_runnable_config(cls, config: Optional[Dict[str, Any]] = None) -> "StockDeepResearchConfig":
        """Build config from LangGraph RunnableConfig or env."""
        config = config or {}
        conf = config.get("configurable") or {}
        return cls(
            research_model=conf.get("research_model") or os.getenv("STOCK_RESEARCH_MODEL", "openai:gpt-4o"),
            research_model_max_tokens=conf.get("research_model_max_tokens", 8192),
            compression_model=conf.get("compression_model") or os.getenv("STOCK_COMPRESSION_MODEL", "openai:gpt-4o-mini"),
            compression_model_max_tokens=conf.get("compression_model_max_tokens", 8192),
            final_report_model=conf.get("final_report_model") or os.getenv("STOCK_FINAL_REPORT_MODEL", "openai:gpt-4o"),
            final_report_model_max_tokens=conf.get("final_report_model_max_tokens", 16384),
            search_api=conf.get("search_api") or os.getenv("STOCK_SEARCH_API", "duckduckgo"),
            max_content_length=conf.get("max_content_length", 12000),
            max_researcher_iterations=conf.get("max_researcher_iterations", 15),
            max_concurrent_research_units=conf.get("max_concurrent_research_units", 3),
            max_react_tool_calls=conf.get("max_react_tool_calls", 12),
            max_structured_output_retries=conf.get("max_structured_output_retries", 2),
            info_service_url=conf.get("info_service_url") or os.getenv("INFO_SERVICE_URL"),
            allow_clarification=conf.get("allow_clarification", False),
        )
