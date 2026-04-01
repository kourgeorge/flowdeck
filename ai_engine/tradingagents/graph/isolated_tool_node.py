"""
Custom tool node that works with isolated message contexts.

This replaces LangGraph's built-in ToolNode which expects messages in state.
Our isolated contexts store messages in temporary keys like _market_context.
"""

import logging
from typing import Any, Callable, Dict, List

from langchain_core.messages import ToolMessage


logger = logging.getLogger(__name__)


def make_isolated_tool_node(tools: List[Callable], context_key: str):
    """
    Create a tool execution node that works with isolated message contexts.
    
    Args:
        tools: List of tool functions to make available
        context_key: State key where the isolated context is stored (e.g., "_market_context")
    
    Returns:
        A node function that executes tools and updates the isolated context
    """
    tool_map = {tool.name: tool for tool in tools}
    
    def tool_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tools from the isolated context and return updated context."""
        local_messages = state.get(context_key, [])
        
        if not local_messages:
            logger.warning(f"No messages in {context_key}")
            return {context_key: []}
        
        # Get the last message which should have tool calls
        last_message = local_messages[-1]
        tool_calls = getattr(last_message, "tool_calls", [])
        
        if not tool_calls:
            logger.warning(f"No tool calls in last message of {context_key}")
            return {context_key: local_messages}
        
        # Execute each tool call
        tool_results = []
        for tool_call in tool_calls:
            tool_name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", None)
            tool_args = tool_call.get("args") if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
            tool_id = tool_call.get("id") if isinstance(tool_call, dict) else getattr(tool_call, "id", None)
            
            if tool_name not in tool_map:
                logger.error(f"Tool {tool_name} not found in tool map")
                tool_results.append(
                    ToolMessage(
                        content=f"Error: Tool {tool_name} not found",
                        tool_call_id=tool_id or "unknown",
                        name=tool_name or "unknown",
                    )
                )
                continue
            
            try:
                # Execute the tool
                result = tool_map[tool_name].invoke(tool_args)
                tool_results.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=tool_id or "unknown",
                        name=tool_name,
                    )
                )
            except Exception as e:
                logger.error(f"Tool {tool_name} execution failed: {e}")
                tool_results.append(
                    ToolMessage(
                        content=f"Error executing {tool_name}: {str(e)}",
                        tool_call_id=tool_id or "unknown",
                        name=tool_name,
                    )
                )
        
        # Update the isolated context with tool results
        updated_messages = list(local_messages) + tool_results
        return {context_key: updated_messages}
    
    return tool_node
