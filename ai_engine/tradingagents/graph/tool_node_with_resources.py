"""
Extract report_resources from tool calls after a ToolNode has run.

We use a separate node that runs after each tools_X node (state already has
new ToolMessages merged). This avoids wrapping ToolNode.invoke which requires
LangGraph runtime config.
"""

import json
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, ToolMessage

from ..agents.utils.resource_extraction import extract_resources_from_tool

_TOOL_INPUT_MAX = 400
_TOOL_OUTPUT_PREVIEW_MAX = 500


def make_extract_resources_node():
    """
    Return a node function that reads isolated context keys, finds the last
    AIMessage with tool_calls and the following ToolMessages, extracts
    resources, and returns {"report_resources": new_entries} (reducer merges).
    Run this node after the tool node so state already has the new messages.
    """
    def node(state: Dict[str, Any]) -> Dict[str, Any]:
        new_resources: List[Dict[str, Any]] = []
        
        # Check all possible isolated context keys
        context_keys = [
            "_market_context", "_social_context", "_news_context",
            "_fundamentals_context", "_technical_context", "_sec_context"
        ]
        
        messages = []
        for key in context_keys:
            ctx = state.get(key)
            if ctx:
                messages = ctx
                break
        
        if not messages:
            return {}
        # Find the last AIMessage with tool_calls and collect following ToolMessages
        last_ai_idx = None
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], AIMessage) and getattr(messages[i], "tool_calls", None):
                last_ai_idx = i
                break
        if last_ai_idx is None:
            return {}
        last_ai = messages[last_ai_idx]
        id_to_call: Dict[str, Dict[str, Any]] = {}
        for tc in last_ai.tool_calls:
            tid = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", None)
            if tid and name is not None:
                id_to_call[tid] = {"name": name, "args": args or {}}
        for j in range(last_ai_idx + 1, len(messages)):
            msg = messages[j]
            if not isinstance(msg, ToolMessage):
                break
            tid = getattr(msg, "tool_call_id", None) or getattr(msg, "id", None)
            content = getattr(msg, "content", None) or ""
            if isinstance(content, list):
                content = str(content)
            call_info = id_to_call.get(tid) if tid else None
            if call_info:
                name = call_info.get("name") or ""
                args = call_info.get("args")
                if not isinstance(args, dict):
                    args = {}
                entries = extract_resources_from_tool(name, args, content)
                # Attach tool invocation context for UI
                tool_input_str = json.dumps(args, default=str)[:_TOOL_INPUT_MAX]
                if len(json.dumps(args, default=str)) > _TOOL_INPUT_MAX:
                    tool_input_str += "..."
                tool_output_preview = (content[:_TOOL_OUTPUT_PREVIEW_MAX] + "...") if len(content) > _TOOL_OUTPUT_PREVIEW_MAX else content
                for e in entries:
                    if isinstance(e, dict):
                        e["tool_name"] = name
                        e["tool_input"] = tool_input_str
                        e["tool_output_preview"] = tool_output_preview
                new_resources.extend(entries)
        if new_resources:
            return {"report_resources": new_resources}
        return {}
    return node
