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

# Supported roles: deep = heavier model for reasoning; quick = faster model for tools/routing; chat = conversational model
LLMRole = Literal["deep", "quick", "chat"]

# Config keys used by the provider
CONFIG_LLM_PROVIDER = "llm_provider"
CONFIG_DEEP_THINK_LLM = "deep_think_llm"
CONFIG_QUICK_THINK_LLM = "quick_think_llm"
CONFIG_CHAT_MODEL = "chat_model"
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
        cfg["chat_model"] = (
            overrides.get("chat_model")
            or os.environ.get("CHAT_MODEL")
            or cfg["deep_think_llm"]  # fallback to deep_think_llm if CHAT_MODEL not set
        )
    # Optional reasoning effort for OpenAI/Azure reasoning models (none, low, medium, high, ...)
    reasoning_effort = (
        overrides.get("reasoning_effort")
        or os.environ.get("LLM_REASONING_EFFORT")
        or ""
    ).strip().lower()
    if reasoning_effort:
        cfg["reasoning_effort"] = reasoning_effort
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
    elif role == "chat":
        return config.get(CONFIG_CHAT_MODEL) or config.get("chat_model") or config.get(CONFIG_DEEP_THINK_LLM) or config.get("deep_think_llm") or "gpt-4o"
    return config.get(CONFIG_QUICK_THINK_LLM) or config.get("quick_think_llm") or "gpt-4o-mini"


# Models that reject the 'temperature' parameter (e.g. OpenAI o1/o3 reasoning models)
_MODELS_NO_TEMPERATURE = frozenset(
    {"o1", "o1-mini", "o1-preview", "o3", "o3-mini", "o4-mini"}
)

# Model families that reject 'temperature' while reasoning is on (their default),
# and accept it only with reasoning_effort="none" (e.g. gpt-6-luna)
_REASONING_FAMILIES = ("gpt-5", "gpt-6")


def _model_supports_temperature(model: str, reasoning_effort: Optional[str] = None) -> bool:
    """Return False if this model is known to reject the temperature parameter."""
    base = (model or "").strip().lower()
    if not base:
        return True
    # Ignore proxy/provider prefixes such as "azure/" or "openai/" (LiteLLM)
    base = base.rsplit("/", 1)[-1]
    # Check exact and prefix (e.g. "o1-2024-..." or deployment names)
    if base in _MODELS_NO_TEMPERATURE:
        return False
    for no_temp in _MODELS_NO_TEMPERATURE:
        if base.startswith(no_temp + "-") or base.startswith(no_temp + "."):
            return False
    if base.startswith(_REASONING_FAMILIES):
        return (reasoning_effort or "").strip().lower() == "none"
    return True


def get_llm(
    role: LLMRole,
    config: Dict[str, Any],
    *,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    request_timeout: Optional[int] = 600,
    http_client: Optional[Any] = None,
) -> BaseChatModel:
    """
    Return a chat model for the given role (or explicit model name) using config.

    Args:
        role: "deep" (reasoning / judge) or "quick" (analysts, tools, routing).
        config: Must contain llm_provider and optionally deep_think_llm, quick_think_llm, backend_url.
        model_name: If set, overrides the model for this role (still uses same provider).
        temperature: Optional override (e.g. 0.0 for deterministic).
        max_tokens: Optional cap on output tokens. Anthropic defaults to 1024 if unset, which
            silently truncates long output, so callers generating long-form content should set this.
        request_timeout: Request timeout in seconds (default 600).
        http_client: Optional httpx.Client for the OpenAI-SDK-based providers (openai, ollama,
            openrouter, azure, cerebras). Pass one when the caller wants to close the model's
            connections: without it ChatOpenAI falls back to langchain-openai's process-wide
            lru_cached httpx client, which must never be closed. Other providers ignore it.

    Returns:
        A LangChain-compatible chat model (BaseChatModel).

    Raises:
        ValueError: If llm_provider is unsupported or required env vars are missing (e.g. Azure).
    """
    provider = (config.get(CONFIG_LLM_PROVIDER) or config.get("llm_provider") or "openai").lower()
    model = model_name or _model_for_role(role, config)
    base_url = config.get(CONFIG_BACKEND_URL) or config.get("backend_url")
    timeout = request_timeout if request_timeout is not None else 600
    temp = temperature if temperature is not None else (0.0 if role == "deep" else 0.0)
    reasoning_effort = config.get("reasoning_effort")
    # Skip temperature if model doesn't support it, or config explicitly disables it
    use_temp = (
        config.get("use_temperature", True)
        and _model_supports_temperature(model, reasoning_effort)
    )

    if provider in ("openai", "ollama", "openrouter"):
        from langchain_openai import ChatOpenAI
        kwargs = dict(model=model, base_url=base_url, request_timeout=timeout)
        # Pass the key explicitly so it gets stripped. Left to itself, ChatOpenAI reads
        # OPENAI_API_KEY raw, and a trailing newline from a .env/secret file ends up in
        # the Authorization header; httpx then rejects it as an illegal header value,
        # which the OpenAI SDK reports only as a vague "APIConnectionError".
        openai_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
        if openai_key:
            kwargs["api_key"] = openai_key
        if use_temp:
            kwargs["temperature"] = temp
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        if http_client is not None:
            kwargs["http_client"] = http_client
        return ChatOpenAI(**kwargs)
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        kwargs = dict(model=model, base_url=base_url, request_timeout=timeout)
        # Same trailing-newline trap as OPENAI_API_KEY above.
        anthropic_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        if anthropic_key:
            kwargs["api_key"] = anthropic_key
        if use_temp:
            kwargs["temperature"] = temp
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        return ChatAnthropic(**kwargs)
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        kwargs = dict(model=model, temperature=temp)
        if max_tokens is not None:
            kwargs["max_output_tokens"] = max_tokens
        return ChatGoogleGenerativeAI(**kwargs)
    if provider == "perplexity":
        from langchain_perplexity import ChatPerplexity
        kwargs = dict(model=model, temperature=temp)
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        return ChatPerplexity(**kwargs)
    if provider == "azure":
        from langchain_openai import AzureChatOpenAI
        azure_endpoint = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip()
        azure_api_key = (os.getenv("AZURE_OPENAI_API_KEY") or "").strip()
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
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        if http_client is not None:
            kwargs["http_client"] = http_client
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
            max_tokens=max_tokens or config.get("max_tokens") or 32768,
        )
        if use_temp:
            kwargs["temperature"] = temp
        if model and "gpt-oss-120b" in model.lower():
            reasoning = config.get("reasoning_effort") or os.environ.get("CEREBRAS_REASONING_EFFORT") or "medium"
            kwargs["reasoning_effort"] = reasoning
        if http_client is not None:
            kwargs["http_client"] = http_client
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
        request_timeout: Optional[int] = 300,
        http_client: Optional[Any] = None,
    ) -> BaseChatModel:
        """Return the chat model for the given role."""
        return get_llm(
            role,
            self.config,
            model_name=model_name,
            temperature=temperature,
            request_timeout=request_timeout,
            http_client=http_client,
        )

    def get_deep_llm(
        self,
        *,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        request_timeout: Optional[int] = 300,
        http_client: Optional[Any] = None,
    ) -> BaseChatModel:
        """Return the deep-thinking model (reasoning, judge, complex tasks)."""
        return self.get_llm(
            "deep",
            model_name=model_name,
            temperature=temperature,
            request_timeout=request_timeout,
            http_client=http_client,
        )

    def get_quick_llm(
        self,
        *,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        request_timeout: Optional[int] = 300,
        http_client: Optional[Any] = None,
    ) -> BaseChatModel:
        """Return the quick-thinking model (analysts, tools, routing)."""
        return self.get_llm(
            "quick",
            model_name=model_name,
            temperature=temperature,
            request_timeout=request_timeout,
            http_client=http_client,
        )
