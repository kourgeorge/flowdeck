from typing import Any, Optional, Tuple

from langchain_core.messages import ToolMessage


def is_tool_result_message(message: Any) -> bool:
    if isinstance(message, ToolMessage):
        return True

    content = getattr(message, "content", None)
    if isinstance(content, list):
        return any(
            isinstance(item, dict) and item.get("type") == "tool" for item in content
        )
    return False


def try_structured_response(
    structured_chain,
    messages,
    *,
    score_field: str,
    logger,
    agent_name: str,
) -> Tuple[Optional[str], Optional[int]]:
    try:
        structured_result = structured_chain.invoke(messages)
        report = getattr(structured_result, "report")
        score = getattr(structured_result, score_field)
        return report, score
    except Exception:
        logger.exception("%s structured output failed; falling back.", agent_name)
        return None, None
