"""
Self-contained analyst implementation using proper ReAct pattern.

This module provides a complete analyst node that handles all tool calling
internally without requiring external graph loops.
"""

import logging
from typing import Any, Callable, Dict, List

from langchain_core.messages import ToolMessage
from pydantic import BaseModel

from .helpers import _capture_usage, try_structured_response


logger = logging.getLogger(__name__)


def run_self_contained_analyst(
    state: Dict[str, Any],
    llm: Any,
    tools: List[Callable],
    prompt_builder: Callable,
    structured_output_class: type[BaseModel],
    score_field: str,
    report_field: str,
    agent_name: str,
    max_iterations: int = 5,
) -> Dict[str, Any]:
    """
    Run a self-contained analyst that handles all tool calling internally.
    
    This implements the ReAct pattern properly:
    1. Think (LLM decides what to do)
    2. Act (Execute tools if needed)
    3. Observe (Get tool results)
    4. Repeat until done
    5. Return final report
    
    All of this happens in ONE graph node execution, eliminating external loops.
    
    Args:
        state: Current agent state
        llm: Language model to use
        tools: List of tools available to the analyst
        prompt_builder: Function to build the analyst prompt
        structured_output_class: Pydantic model for structured output
        score_field: Name of the score field in structured output
        report_field: Name of the report field in state
        agent_name: Name of the analyst (for logging)
        max_iterations: Maximum number of tool-calling iterations
    
    Returns:
        Dictionary with report, score, usage metadata, and resources
    """
    current_date = state["trade_date"]
    ticker = state["company_of_interest"]
    
    # Build prompt
    tool_names = [t.name if hasattr(t, 'name') else t.__name__ for t in tools]
    prompt = prompt_builder(
        tool_names=tool_names,
        current_date=current_date,
        ticker=ticker,
    )
    
    # Initialize local message context
    local_messages = []
    tool_map = {(t.name if hasattr(t, 'name') else t.__name__): t for t in tools}
    total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
    resources_used = []
    
    # ReAct loop - all happens internally
    for iteration in range(max_iterations):
        logger.info(f"{agent_name} iteration {iteration + 1}/{max_iterations}")
        
        # Think: Ask LLM what to do next
        chain_with_tools = prompt | llm.bind_tools(tools)
        result = chain_with_tools.invoke(local_messages)
        
        # Track usage
        usage = _capture_usage(result, llm)
        if usage:
            for key in ["input_tokens", "output_tokens", "total_tokens", "cost_usd"]:
                total_usage[key] += usage.get(key, 0)
        
        local_messages.append(result)
        
        # Check if LLM wants to use tools
        tool_calls = getattr(result, "tool_calls", [])
        
        if not tool_calls:
            # No more tools needed - generate final report
            logger.info(f"{agent_name} completed tool calling, generating final report")
            break
        
        # Act: Execute the tools
        logger.info(f"{agent_name} executing {len(tool_calls)} tool(s)")
        tool_results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]
            
            if tool_name in tool_map:
                try:
                    tool_func = tool_map[tool_name]
                    # Call tool - handle both callable and LangChain tool objects
                    if hasattr(tool_func, 'invoke'):
                        tool_result = tool_func.invoke(tool_args)
                    else:
                        tool_result = tool_func(**tool_args)
                    
                    tool_results.append(
                        ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_id,
                            name=tool_name,
                        )
                    )
                    # Track resources
                    resources_used.append({
                        "tool": tool_name,
                        "args": tool_args,
                    })
                except Exception as e:
                    logger.error(f"{agent_name} tool {tool_name} failed: {e}")
                    tool_results.append(
                        ToolMessage(
                            content=f"Error: {str(e)}",
                            tool_call_id=tool_id,
                            name=tool_name,
                        )
                    )
        
        # Observe: Add tool results to context
        local_messages.extend(tool_results)
    
    # Generate final structured report
    structured_chain = prompt | llm.with_structured_output(structured_output_class)
    report, score, final_usage, key_takeaways = try_structured_response(
        structured_chain,
        local_messages,
        score_field=score_field,
        logger=logger,
        agent_name=agent_name,
        llm=llm,
    )
    takeaways_state_key = report_field.replace("_report", "_key_takeaways")
    
    # Track final usage
    if final_usage:
        for key in ["input_tokens", "output_tokens", "total_tokens", "cost_usd"]:
            total_usage[key] += final_usage.get(key, 0)
    
    if report is not None:
        logger.info(f"{agent_name} completed successfully with score {score}")
        return {
            report_field: report,
            f"{report_field.replace('_report', '_score')}": score,
            takeaways_state_key: key_takeaways,
            "report_usage": {report_field: total_usage},
            "report_resources": resources_used,
        }
    
    # Fallback: generate narrative response
    logger.warning(f"{agent_name} falling back to narrative response")
    fallback_result = (prompt | llm).invoke(local_messages)
    fallback_report = (
        fallback_result.content
        if hasattr(fallback_result, "content")
        else str(fallback_result)
    )
    fallback_usage = _capture_usage(fallback_result, llm)
    if fallback_usage:
        for key in ["input_tokens", "output_tokens", "total_tokens", "cost_usd"]:
            total_usage[key] += fallback_usage.get(key, 0)
    
    return {
        report_field: fallback_report,
        f"{report_field.replace('_report', '_score')}": None,
        takeaways_state_key: [],
        "report_usage": {report_field: total_usage},
        "report_resources": resources_used,
    }


def create_self_contained_analyst(
    llm: Any,
    tools: List[Callable],
    prompt_builder: Callable,
    structured_output_class: type[BaseModel],
    score_field: str,
    report_field: str,
    agent_name: str,
    max_iterations: int = 5,
) -> Callable:
    """
    Factory function to create a self-contained analyst node.
    
    Returns a function that can be used directly as a LangGraph node.
    """
    def analyst_node(state: Dict[str, Any]) -> Dict[str, Any]:
        return run_self_contained_analyst(
            state=state,
            llm=llm,
            tools=tools,
            prompt_builder=prompt_builder,
            structured_output_class=structured_output_class,
            score_field=score_field,
            report_field=report_field,
            agent_name=agent_name,
            max_iterations=max_iterations,
        )
    
    return analyst_node

# Made with Bob
