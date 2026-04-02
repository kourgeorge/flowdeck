"""Shared structured-output fields for analyst reports (single LLM pass, no post-hoc extraction)."""

from pydantic import Field


def analyst_key_takeaways_field():
    """New Field() per model attribute (do not share one FieldInfo across models)."""
    return Field(
        default_factory=list,
        description="Required: 3-5 one-sentence bullet takeaways for traders capturing the highest-signal conclusions from your report.",
    )
