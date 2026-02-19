"""
Model provider for LLM-based workflows.

Supports deep-thinking and quick-thinking roles (and optional custom models)
across multiple backends: OpenAI, Ollama, OpenRouter, Anthropic, Google, Perplexity, Azure.
Use in the trading graph, watchlist report, analysis service, or any other AI feature
that needs a consistent way to obtain chat models.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Literal, Optional

# LangChain chat model base type (optional for typing)
try:
    from langchain_core.language_models.chat_models import BaseChatModel
except ImportError:
    BaseChatModel = Any  # type: ignore[misc, assignment]

# Supported roles: deep = heavier model for reasoning; quick = faster model for tools/routing
LLMRole = Literal["deep", "quick"]

# Config keys used by the provider
CONFIG_LLM_PROVIDER = "llm_provider"
CONFIG_DEEP_THINK_LLM = "deep_think_llm"
CONFIG_QUICK_THINK_LLM = "quick_think_llm"
CONFIG_BACKEND_URL = "backend_url"


def _model_for_role(role: LLMRole, config: Dict[str, Any]) -> str:
    """Resolve model name from config for the given role."""
    if role == "deep":
        return config.get(CONFIG_DEEP_THINK_LLM) or config.get("deep_think_llm") or "gpt-4o"
    return config.get(CONFIG_QUICK_THINK_LLM) or config.get("quick_think_llm") or "gpt-4o-mini"


def get_llm(
    role: LLMRole,
    config: Dict[str, Any],
    *,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    request_timeout: Optional[int] = 120,
) -> BaseChatModel:
    """
    Return a chat model for the given role (or explicit model name) using config.

    Args:
        role: "deep" (reasoning / judge) or "quick" (analysts, tools, routing).
        config: Must contain llm_provider and optionally deep_think_llm, quick_think_llm, backend_url.
        model_name: If set, overrides the model for this role (still uses same provider).
        temperature: Optional override (e.g. 0.0 for deterministic).
        request_timeout: Request timeout in seconds (default 120).

    Returns:
        A LangChain-compatible chat model (BaseChatModel).

    Raises:
        ValueError: If llm_provider is unsupported or required env vars are missing (e.g. Azure).
    """
    provider = (config.get(CONFIG_LLM_PROVIDER) or config.get("llm_provider") or "openai").lower()
    model = model_name or _model_for_role(role, config)
    base_url = config.get(CONFIG_BACKEND_URL) or config.get("backend_url")
    timeout = request_timeout if request_timeout is not None else 120
    temp = temperature if temperature is not None else (0.0 if role == "deep" else 0.3)

    if provider in ("openai", "ollama", "openrouter"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            base_url=base_url,
            temperature=temp,
            request_timeout=timeout,
        )
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            base_url=base_url,
            temperature=temp,
            request_timeout=timeout,
        )
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, temperature=temp)
    if provider == "perplexity":
        from langchain_perplexity import ChatPerplexity
        return ChatPerplexity(model=model, temperature=temp)
    if provider == "azure":
        from langchain_openai import AzureChatOpenAI
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_api_version = os.getenv("OPENAI_API_VERSION", "2024-08-01-preview")
        if not azure_endpoint or not azure_api_key:
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY environment variables must be set for Azure provider"
            )
        return AzureChatOpenAI(
            azure_deployment=model,
            model=model,
            azure_endpoint=azure_endpoint,
            api_key=azure_api_key,
            api_version=azure_api_version,
            request_timeout=timeout,
            temperature=temp,
        )
    raise ValueError(f"Unsupported LLM provider: {config.get(CONFIG_LLM_PROVIDER)}")


class LLMProvider:
    """
    Holds config and exposes deep/quick chat models for any LLM-based workflow.

    Usage:
        provider = LLMProvider(config)
        deep_llm = provider.get_deep_llm()
        quick_llm = provider.get_quick_llm()
        # or
        llm = provider.get_llm("deep")
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}

    def get_llm(
        self,
        role: LLMRole,
        *,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        request_timeout: Optional[int] = 120,
    ) -> BaseChatModel:
        """Return the chat model for the given role."""
        return get_llm(
            role,
            self.config,
            model_name=model_name,
            temperature=temperature,
            request_timeout=request_timeout,
        )

    def get_deep_llm(
        self,
        *,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        request_timeout: Optional[int] = 120,
    ) -> BaseChatModel:
        """Return the deep-thinking model (reasoning, judge, complex tasks)."""
        return self.get_llm(
            "deep",
            model_name=model_name,
            temperature=temperature,
            request_timeout=request_timeout,
        )

    def get_quick_llm(
        self,
        *,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        request_timeout: Optional[int] = 120,
    ) -> BaseChatModel:
        """Return the quick-thinking model (analysts, tools, routing)."""
        return self.get_llm(
            "quick",
            model_name=model_name,
            temperature=temperature,
            request_timeout=request_timeout,
        )
