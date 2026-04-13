"""JSON-safe serialization for persisted discovery metadata."""

from __future__ import annotations

from typing import Any, Dict


def serialize_event_summaries(raw: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for ticker, summary in raw.items():
        if hasattr(summary, "model_dump"):
            out[str(ticker)] = summary.model_dump(mode="json")
        elif isinstance(summary, dict):
            out[str(ticker)] = summary
        else:
            out[str(ticker)] = {"value": str(summary)}
    return out
