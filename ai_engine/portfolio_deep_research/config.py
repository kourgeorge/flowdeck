"""Configuration for Portfolio Deep Research (LLM provider, search, limits)."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from ai_engine.llm_provider import get_config_from_env


class PortfolioDeepResearchConfig(BaseModel):
    """Runtime config for portfolio deep research graph."""

    # LLM: use with llm_provider.get_llm(role, self.llm_config())
    llm_provider: str = Field(default="openai", description="openai | anthropic | azure | ollama | openrouter | google | perplexity | cerebras")
    deep_think_llm: str = Field(default="gpt-4o", description="Model for deep nodes")
    quick_think_llm: str = Field(default="gpt-4o-mini", description="Model for fast nodes")

    # Data and search
    info_service_url: Optional[str] = Field(default=None, description="Backend URL for /api/data and /api/data/reports")
    serpapi_key: Optional[str] = Field(default=None, description="SerpAPI key; fallback SERPAPI_KEY env")

    # Limits
    max_search_results: int = Field(default=8, description="Results per SerpAPI query")
    request_timeout: int = Field(default=120, description="LLM request timeout (seconds)")

    class Config:
        extra = "allow"

    def llm_config(self) -> Dict[str, Any]:
        """Dict for ai_engine.llm_provider.get_llm(role, config)."""
        return {
            "llm_provider": self.llm_provider,
            "deep_think_llm": self.deep_think_llm,
            "quick_think_llm": self.quick_think_llm,
        }

    @classmethod
    def from_runnable_config(cls, config: Optional[Dict[str, Any]] = None) -> "PortfolioDeepResearchConfig":
        """Build from LangGraph RunnableConfig or env. Uses ai_engine.llm_provider.get_config_from_env for LLM config."""
        config = config or {}
        conf = config.get("configurable") or {}
        # LLM config from llm_provider (env + overrides from configurable)
        llm_cfg = get_config_from_env(conf)
        # Backend uses port 8002; default so agent can reach reports and figure data when run locally
        info_url = (
            conf.get("info_service_url")
            or os.environ.get("INFO_SERVICE_URL")
            or "http://localhost:8002"
        )
        info_url = (info_url or "").strip().rstrip("/") or "http://localhost:8002"
        return cls(
            llm_provider=llm_cfg.get("llm_provider", "openai"),
            deep_think_llm=llm_cfg.get("deep_think_llm", "gpt-4o"),
            quick_think_llm=llm_cfg.get("quick_think_llm", "gpt-4o-mini"),
            info_service_url=info_url,
            serpapi_key=conf.get("serpapi_key") or os.environ.get("SERPAPI_KEY"),
            max_search_results=int(conf.get("max_search_results", 8)),
            request_timeout=int(conf.get("request_timeout", 120)),
        )
