from typing import Any, List, Optional, Tuple

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import ToolMessage


class _UsageCaptureCallback(BaseCallbackHandler):
    """Callback that stores the last LLM response message for usage extraction."""

    def __init__(self) -> None:
        super().__init__()
        self.last_message: Any = None

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        generations = getattr(response, "generations", None) or []
        if generations and len(generations) > 0:
            gen0 = generations[0]
            if len(gen0) > 0:
                self.last_message = gen0[0].message


def _capture_usage(message: Any, llm: Any) -> Optional[dict]:
    """Extract LLM usage from AIMessage for report metadata."""
    try:
        from ai_engine.llm_usage import record_usage_from_message, usage_record_to_metadata
        r = record_usage_from_message(message, llm, None)
        return usage_record_to_metadata(r)
    except Exception:
        return None


def is_tool_result_message(message: Any) -> bool:
    if isinstance(message, ToolMessage):
        return True

    content = getattr(message, "content", None)
    if isinstance(content, list):
        return any(
            isinstance(item, dict) and item.get("type") == "tool" for item in content
        )
    return False


def _normalized_key_takeaways(structured_result: Any) -> List[str]:
    raw = getattr(structured_result, "key_takeaways", None) or []
    if not isinstance(raw, (list, tuple)):
        return []
    out: List[str] = []
    for x in raw:
        s = str(x).strip()
        if s:
            out.append(s)
    return out[:5]


def try_structured_response(
    structured_chain,
    messages,
    *,
    score_field: str,
    logger: Any,
    agent_name: str,
    llm: Any = None,
) -> Tuple[Optional[str], Optional[int], Optional[dict], List[str]]:
    """Invoke structured chain; return (report, score, usage_meta, key_takeaways)."""
    usage_cb = _UsageCaptureCallback()
    try:
        structured_result = structured_chain.invoke(
            messages, config={"callbacks": [usage_cb]}
        )
    except Exception:
        logger.exception("%s structured output failed; falling back.", agent_name)
        return None, None, None, []
    report = getattr(structured_result, "report", None)
    score = getattr(structured_result, score_field, None)
    usage_meta = None
    if llm is not None and usage_cb.last_message is not None:
        usage_meta = _capture_usage(usage_cb.last_message, llm)
    return report, score, usage_meta, _normalized_key_takeaways(structured_result)
