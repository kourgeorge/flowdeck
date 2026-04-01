"""
Helper module for analysts using isolated message contexts.

This module provides utilities for running analysts with local message contexts
instead of shared state messages, eliminating the need for message clearing.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel

from .helpers import _capture_usage, try_structured_response


logger = logging.getLogger(__name__)


def run_analyst_with_isolated_context(
    state: Dict[str, Any],
    llm: Any,
    tools: List[Callable],
    prompt_builder: Callable,
    structured_output_class: type[BaseModel],
    score_field: str,
    report_field: str,
    agent_name: str,
    temp_state_key: str,
) -> Dict[str, Any]:
    """
    Run an analyst with isolated message context for tool calling.
    
    This function manages the complete lifecycle of an analyst:
    1. Creates isolated local messages
    2. Handles tool calling loop
    3. Extracts structured output
    4. Returns results without polluting shared state
    
    Args:
        state: Current agent state
        llm: Language model to use
        tools: List of tools available to the analyst
        prompt_builder: Function to build the analyst prompt
        structured_output_class: Pydantic model for structured output
        score_field: Name of the score field in structured output
        report_field: Name of the report field in state
        agent_name: Name of the analyst (for logging)
        temp_state_key: Key for temporary state storage (e.g., "_market_context")
    
    Returns:
        Dictionary with report, score, and usage metadata
    """
    current_date = state["trade_date"]
    ticker = state["company_of_interest"]
    
    # Build prompt
    prompt = prompt_builder(
        tool_names=[tool.name for tool in tools],
        current_date=current_date,
        ticker=ticker,
    )
    
    # Check if we have a stored context from previous iteration
    local_messages = state.get(temp_state_key, [])
    
    # If we have messages with tool results, generate final report
    if local_messages and any(isinstance(m, ToolMessage) for m in local_messages):
        structured_chain = prompt | llm.with_structured_output(structured_output_class)
        report, score, usage_meta = try_structured_response(
            structured_chain,
            local_messages,
            score_field=score_field,
            logger=logger,
            agent_name=agent_name,
            llm=llm,
        )
        
        if report is not None:
            result = {
                report_field: report,
                f"{report_field.replace('_report', '_score')}": score,
                temp_state_key: None,  # Clear temporary state
            }
            if usage_meta:
                result["report_usage"] = {report_field: usage_meta}
            return result
        
        # Fallback: generate narrative response
        fallback_result = (prompt | llm).invoke(local_messages)
        fallback_report = (
            fallback_result.content
            if hasattr(fallback_result, "content")
            else str(fallback_result)
        )
        usage_meta = _capture_usage(fallback_result, llm)
        result = {
            report_field: fallback_report,
            f"{report_field.replace('_report', '_score')}": None,
            temp_state_key: None,
        }
        if usage_meta:
            result["report_usage"] = {report_field: usage_meta}
        return result
    
    # Initial call or continuation: request tools
    chain_with_tools = prompt | llm.bind_tools(tools)
    result = chain_with_tools.invoke(local_messages)
    
    # Check if we got tool calls
    if not getattr(result, "tool_calls", []):
        # No tool calls - try to extract final report
        local_messages.append(result)
        structured_chain = prompt | llm.with_structured_output(structured_output_class)
        report, score, usage_meta = try_structured_response(
            structured_chain,
            local_messages,
            score_field=score_field,
            logger=logger,
            agent_name=agent_name,
            llm=llm,
        )
        
        if report is not None:
            result_dict = {
                report_field: report,
                f"{report_field.replace('_report', '_score')}": score,
                temp_state_key: None,
            }
            if usage_meta:
                result_dict["report_usage"] = {report_field: usage_meta}
            return result_dict
        
        # Fallback
        report = result.content if hasattr(result, "content") else str(result)
        usage_meta = _capture_usage(result, llm)
        result_dict = {
            report_field: report,
            f"{report_field.replace('_report', '_score')}": None,
            temp_state_key: None,
        }
        if usage_meta:
            result_dict["report_usage"] = {report_field: usage_meta}
        return result_dict
    
    # Has tool calls - store context and signal need for tool execution
    local_messages.append(result)
    return {
        temp_state_key: local_messages,
        f"_{agent_name.lower().replace(' ', '_')}_needs_tools": True,
        report_field: "",
        f"{report_field.replace('_report', '_score')}": None,
    }


def execute_tools_for_analyst(
    state: Dict[str, Any],
    tools: List[Callable],
    temp_state_key: str,
) -> Dict[str, Any]:
    """
    Execute tools for an analyst and update the isolated context.
    
    Args:
        state: Current agent state
        tools: List of available tools
        temp_state_key: Key for temporary state storage
    
    Returns:
        Dictionary with updated context including tool results
    """
    local_messages = state.get(temp_state_key, [])
    if not local_messages:
        return {temp_state_key: []}
    
    last_message = local_messages[-1]
    tool_calls = getattr(last_message, "tool_calls", [])
    
    if not tool_calls:
        return {temp_state_key: local_messages}
    
    # Execute tools
    tool_results = []
    tool_map = {tool.name: tool for tool in tools}
    
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        
        if tool_name in tool_map:
            try:
                result = tool_map[tool_name].invoke(tool_args)
                tool_results.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=tool_id,
                        name=tool_name,
                    )
                )
            except Exception as e:
                logger.error(f"Tool {tool_name} failed: {e}")
                tool_results.append(
                    ToolMessage(
                        content=f"Error: {str(e)}",
                        tool_call_id=tool_id,
                        name=tool_name,
                    )
                )
    
    # Update context with tool results
    local_messages.extend(tool_results)
    return {temp_state_key: local_messages}
