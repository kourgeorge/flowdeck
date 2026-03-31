"""
Model provider for LLM-based workflows.

Supports deep-thinking and quick-thinking roles (and optional custom models)
across multiple backends: OpenAI, Ollama, OpenRouter, Anthropic, Google, Perplexity, Azure, Cerebras.
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


def get_config_from_env(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Build config dict for get_llm(role, config) from environment variables.
    Use this so all consumers (portfolio deep research, watchlist, etc.) share one place for provider/model resolution.
    overrides: optional dict (e.g. from RunnableConfig configurable) to override env; keys: llm_provider, deep_think_llm, quick_think_llm, backend_url.
    """
    overrides = overrides or {}
    cfg: Dict[str, Any] = {}
    provider = (
        overrides.get("llm_provider")
        or os.environ.get("LLM_PROVIDER")
        or ""
    ).strip().lower()
    azure_endpoint = (
        overrides.get("backend_url")
        or os.environ.get("AZURE_OPENAI_ENDPOINT")
        or ""
    ).strip()
    azure_key = (os.environ.get("AZURE_OPENAI_API_KEY") or "").strip()
    deep_default = "gpt-4o" if provider != "cerebras" else "gpt-oss-120b"
    quick_default = "gpt-4o-mini" if provider != "cerebras" else "gpt-oss-120b"
    if provider == "azure" or (not provider and azure_endpoint and azure_key):
        cfg["llm_provider"] = "azure"
        cfg["deep_think_llm"] = (
            overrides.get("deep_think_llm")
            or os.environ.get("DEEP_THINK_MODEL")
            or deep_default
        )
        cfg["quick_think_llm"] = (
            overrides.get("quick_think_llm")
            or os.environ.get("QUICK_THINK_MODEL")
            or quick_default
        )
    elif provider == "cerebras":
        cfg["llm_provider"] = "cerebras"
        cfg["deep_think_llm"] = (
            overrides.get("deep_think_llm")
            or os.environ.get("DEEP_THINK_MODEL")
            or "gpt-oss-120b"
        )
        cfg["quick_think_llm"] = (
            overrides.get("quick_think_llm")
            or os.environ.get("QUICK_THINK_MODEL")
            or "gpt-oss-120b"
        )
    else:
        cfg["llm_provider"] = provider or "openai"
        cfg["deep_think_llm"] = (
            overrides.get("deep_think_llm")
            or os.environ.get("DEEP_THINK_MODEL")
            or "gpt-4o"
        )
        cfg["quick_think_llm"] = (
            overrides.get("quick_think_llm")
            or os.environ.get("QUICK_THINK_MODEL")
            or "gpt-4o-mini"
        )
    # Set backend_url from overrides or LLM_BACKEND_URL environment variable
    if overrides.get("backend_url"):
        cfg["backend_url"] = overrides["backend_url"]
    elif os.environ.get("LLM_BACKEND_URL"):
        cfg["backend_url"] = os.environ.get("LLM_BACKEND_URL").strip()
    return cfg


def _model_for_role(role: LLMRole, config: Dict[str, Any]) -> str:
    """Resolve model name from config for the given role."""
    if role == "deep":
        return config.get(CONFIG_DEEP_THINK_LLM) or config.get("deep_think_llm") or "gpt-4o"
    return config.get(CONFIG_QUICK_THINK_LLM) or config.get("quick_think_llm") or "gpt-4o-mini"


# Models that reject the 'temperature' parameter (e.g. OpenAI o1/o3 reasoning models)
_MODELS_NO_TEMPERATURE = frozenset(
    {"o1", "o1-mini", "o1-preview", "o3", "o3-mini", "o4-mini"}
)


def _model_supports_temperature(model: str) -> bool:
    """Return False if this model is known to reject the temperature parameter."""
    base = (model or "").strip().lower()
    if not base:
        return True
    # Check exact and prefix (e.g. "o1-2024-..." or deployment names)
    if base in _MODELS_NO_TEMPERATURE:
        return False
    for no_temp in _MODELS_NO_TEMPERATURE:
        if base.startswith(no_temp + "-") or base.startswith(no_temp + "."):
            return False
    return True


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
    temp = temperature if temperature is not None else (0.0 if role == "deep" else 0.0)
    # Skip temperature if model doesn't support it, or config explicitly disables it
    use_temp = (
        config.get("use_temperature", True)
        and _model_supports_temperature(model)
    )

    if provider in ("openai", "ollama", "openrouter"):
        from langchain_openai import ChatOpenAI
        kwargs = dict(model=model, base_url=base_url, request_timeout=timeout)
        if use_temp:
            kwargs["temperature"] = temp
        return ChatOpenAI(**kwargs)
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        kwargs = dict(model=model, base_url=base_url, request_timeout=timeout)
        if use_temp:
            kwargs["temperature"] = temp
        return ChatAnthropic(**kwargs)
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
        kwargs = dict(
            azure_deployment=model,
            model=model,
            azure_endpoint=azure_endpoint,
            api_key=azure_api_key,
            api_version=azure_api_version,
            request_timeout=timeout,
        )
        if use_temp:
            kwargs["temperature"] = temp
        return AzureChatOpenAI(**kwargs)
    if provider == "cerebras":
        from langchain_cerebras import ChatCerebras
        api_key = (os.environ.get("CEREBRAS_API_KEY") or "").strip()
        if not api_key:
            raise ValueError(
                "CEREBRAS_API_KEY must be set for Cerebras provider. Set it in environment or backend/.env"
            )
        kwargs = dict(
            model=model,
            api_key=api_key,
            timeout=timeout,
            max_tokens=config.get("max_tokens") or 32768,
        )
        if use_temp:
            kwargs["temperature"] = temp
        if model and "gpt-oss-120b" in model.lower():
            reasoning = config.get("reasoning_effort") or os.environ.get("CEREBRAS_REASONING_EFFORT") or "medium"
            kwargs["reasoning_effort"] = reasoning
        return ChatCerebras(**kwargs)
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
