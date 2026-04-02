"""
Extract token usage and cost from LLM responses (LangChain AIMessage).

Used by the agent graph to record tokens in/out and cost per LLM call,
and to return totals in run() / stream().
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Pricing USD per 1M tokens (input, output). Fill in for models you use.
# Sources: OpenAI pricing page, Azure same as OpenAI for same models.
_DEFAULT_PRICING: Dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-2024-08-06": (2.50, 10.00),
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "o1": (15.00, 60.00),
    "o1-mini": (1.10, 4.40),
    "o3-mini": (1.10, 4.40),
    "o3-mini-2025-01-31": (1.10, 4.40),
    "o4-mini": (1.10, 4.40),
}


def _normalize_model_for_pricing(model: Optional[str]) -> str:
    """Map deployment/model name to a pricing key (best effort)."""
    if not model:
        return "gpt-4o-mini"
    m = (model or "").strip().lower()
    for key in _DEFAULT_PRICING:
        if key in m or m in key:
            return key
    if "gpt-4o" in m:
        return "gpt-4o"
    if "gpt-4" in m:
        return "gpt-4-turbo"
    if "mini" in m or "gpt-3.5" in m:
        return "gpt-4o-mini"
    return "gpt-4o-mini"


@dataclass
class LLMUsageRecord:
    """One LLM call: token counts and cost."""
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: Optional[str] = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def parse_usage_from_message(message: Any) -> Optional[Dict[str, int]]:
    """
    Extract input_tokens and output_tokens from an AIMessage (or chunk).

    Handles OpenAI-style (token_usage.prompt_tokens/completion_tokens) and
    Anthropic-style (usage.input_tokens/output_tokens) in response_metadata
    or usage_metadata.
    """
    meta = getattr(message, "response_metadata", None) or {}
    if not isinstance(meta, dict):
        return None
    # OpenAI
    token_usage = meta.get("token_usage")
    if isinstance(token_usage, dict):
        pi = token_usage.get("prompt_tokens")
        po = token_usage.get("completion_tokens")
        if pi is not None and po is not None:
            return {"input_tokens": int(pi), "output_tokens": int(po)}
    # Anthropic / Azure (usage with input_tokens/output_tokens or prompt_tokens/completion_tokens)
    usage = meta.get("usage")
    if isinstance(usage, dict):
        pi = usage.get("input_tokens") or usage.get("prompt_tokens")
        po = usage.get("output_tokens") or usage.get("completion_tokens")
        if pi is not None and po is not None:
            return {"input_tokens": int(pi), "output_tokens": int(po)}
    # Some providers use usage_metadata
    usage_meta = getattr(message, "usage_metadata", None) or meta.get("usage_metadata")
    if isinstance(usage_meta, dict):
        pi = usage_meta.get("input_tokens") or usage_meta.get("prompt_token_count")
        po = usage_meta.get("output_tokens") or usage_meta.get("candidates_token_count")
        if pi is not None and po is not None:
            return {"input_tokens": int(pi), "output_tokens": int(po)}
    return None


def get_model_name_from_llm(llm: Any) -> Optional[str]:
    """Get model name from a LangChain chat model for pricing."""
    if llm is None:
        return None
    return getattr(llm, "model_name", None) or getattr(llm, "model", None)


def compute_cost_usd(
    model_name: Optional[str],
    input_tokens: int,
    output_tokens: int,
    pricing_overrides: Optional[Dict[str, tuple[float, float]]] = None,
) -> float:
    """Compute cost in USD from model name and token counts."""
    key = _normalize_model_for_pricing(model_name)
    table = (pricing_overrides or _DEFAULT_PRICING).copy()
    if key not in table:
        table[key] = _DEFAULT_PRICING.get("gpt-4o-mini", (0.15, 0.60))
    in_per_m, out_per_m = table[key]
    return (input_tokens / 1_000_000 * in_per_m) + (output_tokens / 1_000_000 * out_per_m)


def record_usage_from_message(
    message: Any,
    llm: Any,
    out_list: Optional[List[LLMUsageRecord]] = None,
    pricing_overrides: Optional[Dict[str, tuple[float, float]]] = None,
) -> Optional[LLMUsageRecord]:
    """
    Parse usage from an AIMessage, compute cost, optionally append to out_list.

    Returns one LLMUsageRecord if usage was parsed, else None.
    """
    usage = parse_usage_from_message(message)
    if not usage:
        return None
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    model = get_model_name_from_llm(llm)
    cost = compute_cost_usd(model, inp, out, pricing_overrides)
    record = LLMUsageRecord(
        input_tokens=inp,
        output_tokens=out,
        cost_usd=cost,
        model=model,
    )
    if out_list is not None:
        out_list.append(record)
    return record


def usage_record_to_metadata(record: Optional[LLMUsageRecord]) -> Optional[Dict[str, Any]]:
    """Convert an LLMUsageRecord to a dict suitable for report metadata."""
    if record is None:
        return None
    return {
        "input_tokens": record.input_tokens,
        "output_tokens": record.output_tokens,
        "total_tokens": record.total_tokens,
        "cost_usd": round(record.cost_usd, 6),
    }


def sum_usage(records: List[LLMUsageRecord]) -> Dict[str, Any]:
    """Aggregate a list of usage records into totals."""
    total_in = sum(r.input_tokens for r in records)
    total_out = sum(r.output_tokens for r in records)
    total_cost = sum(r.cost_usd for r in records)
    return {
        "input_tokens": total_in,
        "output_tokens": total_out,
        "total_tokens": total_in + total_out,
        "cost_usd": round(total_cost, 6),
        "calls": len(records),
        "per_call": [
            {
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_usd": round(r.cost_usd, 6),
                "model": r.model,
            }
            for r in records
        ],
    }
