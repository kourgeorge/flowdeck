"""
Shared AI utilities for Flowdeck: LLM provider, model roles, etc.
Reused by backend services, tradingagents, watchlist report, and other AI features.
"""

from .llm_provider import (
    CONFIG_BACKEND_URL,
    CONFIG_DEEP_THINK_LLM,
    CONFIG_LLM_PROVIDER,
    CONFIG_QUICK_THINK_LLM,
    LLMRole,
    LLMProvider,
    get_llm,
)

__all__ = [
    "get_llm",
    "LLMProvider",
    "LLMRole",
    "CONFIG_LLM_PROVIDER",
    "CONFIG_DEEP_THINK_LLM",
    "CONFIG_QUICK_THINK_LLM",
    "CONFIG_BACKEND_URL",
]
