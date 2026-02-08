"""Structured LLM extraction for insights (key takeaways) from report content."""

from typing import List, Any, Optional
from pydantic import BaseModel, Field


class KeyTakeawaysOutput(BaseModel):
    """Structured output schema for extracting 3-5 key takeaways from a report."""

    key_takeaways: List[str] = Field(
        max_length=5,
        description="Three to five concise bullet-point takeaways from the report, each one sentence (or fewer if report is brief).",
    )


EXTRACT_TAKEAWAYS_PROMPT = """Extract exactly 3 to 5 key takeaways from the following analysis report. Each takeaway must be one clear, concise sentence. Return only the list of takeaways, no preamble.

Report:
---
{content}
---

Provide 3-5 key takeaways that a trader would care about."""


def extract_key_takeaways_structured(
    llm: Any,
    content: str,
    max_items: int = 5,
) -> List[str]:
    """
    Use the LLM with structured output to extract key takeaways from report markdown.
    Returns a list of 3-5 takeaways; on failure returns empty list (caller can fall back to heuristic).
    """
    if not content or not content.strip():
        return []
    try:
        # Truncate very long content to avoid token limits
        max_chars = 12000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[... report truncated ...]"
        structured_llm = llm.with_structured_output(KeyTakeawaysOutput)
        prompt = EXTRACT_TAKEAWAYS_PROMPT.format(content=content)
        out = structured_llm.invoke(prompt)
        if out and getattr(out, "key_takeaways", None):
            return list(out.key_takeaways)[:max_items]
    except Exception:
        pass
    return []
