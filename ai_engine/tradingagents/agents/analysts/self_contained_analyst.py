"""
Self-contained analyst implementation using proper ReAct pattern.

This module provides a complete analyst node that handles all tool calling
internally without requiring external graph loops.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

from langchain_core.messages import ToolMessage
from pydantic import BaseModel

from .helpers import _capture_usage, try_structured_response
from ..utils.resource_extraction import extract_resources_from_tool
from ..utils.trace_utils import make_agent_step


logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    """Convert arbitrary values into JSON-safe data for persistence."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


def _parse_tool_output_snapshot(tool_result: Any) -> Any:
    """Preserve the tool result as structured JSON when possible, otherwise as text."""
    if isinstance(tool_result, str):
        stripped = tool_result.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return json.loads(stripped)
            except Exception:
                return tool_result
        return tool_result
    return _json_safe(tool_result)


def _format_tool_output_preview(snapshot: Any, max_chars: int = 4500) -> str:
    """Create a compact preview for UI inspection while keeping the full snapshot separately."""
    try:
        if isinstance(snapshot, (dict, list)):
            text = json.dumps(snapshot, indent=2, sort_keys=True, default=str)
        else:
            text = str(snapshot)
    except Exception:
        text = str(snapshot)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[truncated preview]"


def build_tool_resource_snapshots(
    tool_name: str,
    tool_args: Dict[str, Any],
    tool_result: Any,
) -> List[Dict[str, Any]]:
    """Build persisted resource entries with the actual tool data snapshot."""
    tool_input = _json_safe(tool_args or {})
    tool_output = _parse_tool_output_snapshot(tool_result)
    tool_output_preview = _format_tool_output_preview(tool_output)
    tool_result_text = (
        tool_result if isinstance(tool_result, str) else json.dumps(_json_safe(tool_result), default=str)
    )
    captured_at = datetime.now(timezone.utc).isoformat()

    resource_entries = extract_resources_from_tool(tool_name, tool_args or {}, tool_result_text)
    if not resource_entries:
        ticker = str((tool_args or {}).get("ticker") or (tool_args or {}).get("symbol") or "").strip().upper()
        resource_entries = [{
            "type": "tool",
            "ticker": ticker or None,
            "description": tool_name,
        }]

    snapshots: List[Dict[str, Any]] = []
    for entry in resource_entries:
        snapshot_entry = dict(entry)
        snapshot_entry["tool_name"] = tool_name
        snapshot_entry["tool_input"] = tool_input
        snapshot_entry["tool_output"] = tool_output
        snapshot_entry["tool_output_preview"] = tool_output_preview
        snapshot_entry["captured_at"] = captured_at
        snapshots.append(snapshot_entry)
    return snapshots


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
        score_field: Name of the score field in structured output (e.g., "technical_score")
        report_field: Name of the report field in state (e.g., "technical_report")
        agent_name: Name of the analyst (for logging)
        max_iterations: Maximum number of tool-calling iterations
    
    Returns:
        Dictionary with report, score, usage metadata, and resources
    """
    # Validate that score_field exists in the structured output class
    # Use model_fields for Pydantic V2 compatibility
    model_fields = getattr(structured_output_class, 'model_fields', None) or getattr(structured_output_class, '__fields__', {})
    if score_field not in model_fields:
        raise ValueError(
            f"{agent_name}: score_field '{score_field}' not found in {structured_output_class.__name__}. "
            f"Available fields: {list(model_fields.keys())}"
        )
    current_date = state["trade_date"]
    ticker = state["company_of_interest"]
    
    # Build prompt. If a prior completed run seeded this aspect's report into state,
    # pass it through so the analyst updates it instead of starting from scratch.
    tool_names = [t.name if hasattr(t, 'name') else t.__name__ for t in tools]
    prior_report = (state.get("prior_reports") or {}).get(report_field) or None
    prior_analysis_date = state.get("prior_analysis_date") or None
    prompt = prompt_builder(
        tool_names=tool_names,
        current_date=current_date,
        ticker=ticker,
        prior_report=prior_report,
        prior_analysis_date=prior_analysis_date,
    )
    
    # Initialize local message context
    local_messages = []
    tool_map = {(t.name if hasattr(t, 'name') else t.__name__): t for t in tools}
    total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
    resources_used = []
    agent_steps = []
    
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
        agent_steps.append(
            make_agent_step(
                agent=agent_name,
                phase="analysis",
                kind="llm_decision",
                report_key=report_field,
                iteration=iteration + 1,
                status="tool_calls_requested" if tool_calls else "final_answer_ready",
                summary=(
                    f"{agent_name} requested {len(tool_calls)} tool call(s)"
                    if tool_calls
                    else f"{agent_name} completed tool gathering"
                ),
                message_preview=getattr(result, "content", ""),
                tool_calls=tool_calls,
                usage=usage,
            )
        )

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
                    resources_used.extend(
                        build_tool_resource_snapshots(tool_name, tool_args, tool_result)
                    )
                    # Create a single combined step with both input and output
                    agent_steps.append(
                        make_agent_step(
                            agent=agent_name,
                            phase="analysis",
                            kind="tool_result",
                            report_key=report_field,
                            iteration=iteration + 1,
                            status="completed",
                            summary=f"{tool_name} returned successfully",
                            tool_name=tool_name,
                            tool_args=tool_args,
                            observation_preview=_format_tool_output_preview(
                                _parse_tool_output_snapshot(tool_result)
                            ),
                        )
                    )
                except Exception as e:
                    logger.error(f"{agent_name} tool {tool_name} failed: {e}")
                    tool_results.append(
                        ToolMessage(
                            content=f"Error: {str(e)}",
                            tool_call_id=tool_id,
                            name=tool_name,
                        )
                    )
                    agent_steps.append(
                        make_agent_step(
                            agent=agent_name,
                            phase="analysis",
                            kind="tool_result",
                            report_key=report_field,
                            iteration=iteration + 1,
                            status="error",
                            summary=f"{tool_name} failed",
                            tool_name=tool_name,
                            tool_args=tool_args,
                            observation_preview=str(e),
                        )
                    )
        
        # Observe: Add tool results to context
        local_messages.extend(tool_results)
    
    # Generate final structured report
    structured_chain = prompt | llm.with_structured_output(structured_output_class)
    report, score, final_usage, key_takeaways, structured_result = try_structured_response(
        structured_chain,
        local_messages,
        report_field=report_field,
        score_field=score_field,
        logger=logger,
        agent_name=agent_name,
        llm=llm,
    )
    
    # Derive state keys from report_field
    # e.g., "technical_report" -> "technical_key_takeaways"
    takeaways_state_key = report_field.replace("_report", "_key_takeaways")
    # Use the explicit score_field instead of deriving it
    score_state_key = score_field
    
    # Track final usage
    if final_usage:
        for key in ["input_tokens", "output_tokens", "total_tokens", "cost_usd"]:
            total_usage[key] += final_usage.get(key, 0)
    
    if report is not None:
        extra_state = {}
        if structured_result is not None:
            try:
                extra_state = structured_result.model_dump()
            except Exception:
                extra_state = {}
            for key in ("report", report_field, score_field, "key_takeaways"):
                extra_state.pop(key, None)
        agent_steps.append(
            make_agent_step(
                agent=agent_name,
                phase="analysis",
                kind="report_synthesis",
                report_key=report_field,
                status="completed",
                summary=f"{agent_name} produced the final structured report",
                output_preview=report,
                usage=final_usage,
                extra={"score": score, "key_takeaways": key_takeaways},
            )
        )
        logger.info(f"{agent_name} completed successfully with score {score}")
        return {
            report_field: report,
            score_state_key: score,
            takeaways_state_key: key_takeaways,
            **extra_state,
            "report_usage": {report_field: total_usage},
            "report_resources": resources_used,
            "report_resources_by_report": {report_field: resources_used},
            "report_steps_by_report": {report_field: agent_steps},
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
    
    # Use explicit score_field instead of string manipulation
    score_state_key = score_field
    
    return {
        report_field: fallback_report,
        score_state_key: None,
        takeaways_state_key: [],
        "report_usage": {report_field: total_usage},
        "report_resources": resources_used,
        "report_resources_by_report": {report_field: resources_used},
        "report_steps_by_report": {
            report_field: agent_steps + [
                make_agent_step(
                    agent=agent_name,
                    phase="analysis",
                    kind="report_synthesis",
                    report_key=report_field,
                    status="fallback",
                    summary=f"{agent_name} fell back to an unstructured narrative report",
                    output_preview=fallback_report,
                    usage=fallback_usage,
                )
            ]
        },
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
