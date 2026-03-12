"""
SkillAgent — the central agent runtime.

The agent supports two capability layers:

  Tools  (atomic)  — exposed to the LLM as function-calling schemas.
                     The LLM decides when to call them; the ToolExecutor
                     runs them safely with timeout + validation.

  Skills (workflow) — multi-step recipes NOT exposed to the LLM directly.
                     The agent checks intent BEFORE the LLM loop; if a skill
                     matches, it runs the skill workflow and feeds the result
                     back into the LLM for a final polished answer.

Flow:
  1. Check SkillRegistry for intent match → run skill → feed result to LLM
  2. Otherwise: LLM tool-calling loop (up to max_tool_rounds)
  3. Return final reply + metrics

The agent is stateless — create one instance and call run() / run_stream()
per request.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Generator, List, Optional

from ai_engine.agent.executor import SkillExecutor, ToolExecutor
from ai_engine.agent.registry import SkillRegistry, ToolRegistry
from ai_engine.agent.tool import ExecutionContext

logger = logging.getLogger(__name__)


class SkillAgent:
    """
    Modular agent runtime with Tools + Skills support.

    Args:
        tool_registry:   Registry of all available atomic tools.
        skill_registry:  Registry of all available multi-step skills.
        llm:             LangChain-compatible chat model (must support bind_tools).
        tool_executor:   Optional ToolExecutor (created with defaults if not provided).
        skill_executor:  Optional SkillExecutor (created with defaults if not provided).
        max_tool_rounds: Max LLM → tool call rounds before forcing a final answer.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        skill_registry: SkillRegistry,
        llm: Any,
        tool_executor: Optional[ToolExecutor] = None,
        skill_executor: Optional[SkillExecutor] = None,
        max_tool_rounds: int = 5,
    ) -> None:
        self.tool_registry = tool_registry
        self.skill_registry = skill_registry
        self.llm = llm
        self.tool_executor = tool_executor or ToolExecutor()
        # Give the tool_executor a reference to the registry so skills can call tools
        self.tool_executor.tool_registry = self.tool_registry  # type: ignore[attr-defined]
        self.skill_executor = skill_executor or SkillExecutor(tool_executor=self.tool_executor)
        self.max_tool_rounds = max_tool_rounds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        messages: List[Dict[str, str]],
        ctx: ExecutionContext,
        system_prompt: str,
    ) -> Dict[str, Any]:
        """
        Run a full agent turn (blocking).

        Returns:
            {
                "reply": str,
                "tokens_used": int,
                "tools_called": int,
                "skill_used": str | None,
            }
        """
        from langchain_core.messages import (
            AIMessage, HumanMessage, SystemMessage, ToolMessage,
        )

        if not messages:
            return {"reply": "", "tokens_used": 1, "tools_called": 0, "skill_used": None}

        last_user_msg = _last_user_message(messages)
        if not last_user_msg:
            return {"reply": "Please send a message.", "tokens_used": 1, "tools_called": 0, "skill_used": None}

        logger.info(
            "agent.run | user_id=%s | query=%r",
            ctx.user_id,
            last_user_msg[:200],
        )

        # ----------------------------------------------------------------
        # 1. Skill intent check — run workflow before LLM loop
        # ----------------------------------------------------------------
        skill_used: Optional[str] = None
        skill_context_block = ""

        matched_skill = self.skill_registry.match_intent(last_user_msg)
        if matched_skill:
            skill_name = matched_skill.spec.name  # type: ignore[attr-defined]
            logger.info("agent.run | skill_matched=%s | user_id=%s", skill_name, ctx.user_id)

            # Extract args from the message for the skill
            skill_args = _extract_skill_args(last_user_msg, matched_skill)
            skill_result = self.skill_executor.run(matched_skill, ctx, **skill_args)

            if skill_result.ok:
                skill_used = skill_name
                skill_context_block = (
                    f"\n\n## Skill Workflow Result ({skill_name})\n"
                    f"The following data was gathered by running the '{skill_name}' workflow:\n\n"
                    f"{skill_result.to_str()}\n\n"
                    f"Use this data to answer the user's question. Do NOT call tools to re-fetch "
                    f"data already present above."
                )
                logger.info(
                    "agent.run | skill=%s ok=True | steps=%d | user_id=%s",
                    skill_name,
                    len(skill_result.steps),
                    ctx.user_id,
                )
            else:
                logger.warning(
                    "agent.run | skill=%s failed | error=%s | falling back to tool loop",
                    skill_name,
                    skill_result.error,
                )

        # ----------------------------------------------------------------
        # 2. Build LangChain message list
        # ----------------------------------------------------------------
        full_system = system_prompt + skill_context_block
        lc_messages: List[Any] = [SystemMessage(content=full_system)]
        for msg in messages[-20:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            else:
                lc_messages.append(AIMessage(content=content))

        # ----------------------------------------------------------------
        # 3. LLM tool-calling loop
        # ----------------------------------------------------------------
        tool_schemas = self.tool_registry.to_openai_schemas()
        llm_with_tools = self.llm.bind_tools(tool_schemas)  # type: ignore[attr-defined]
        tool_calls_made = 0

        try:
            for round_num in range(self.max_tool_rounds):
                logger.debug(
                    "agent.run | round=%d | messages=%d | user_id=%s",
                    round_num + 1,
                    len(lc_messages),
                    ctx.user_id,
                )
                response = _invoke_with_retry(llm_with_tools.invoke, lc_messages)

                tool_calls = getattr(response, "tool_calls", None)
                if not tool_calls:
                    # Final answer
                    reply = response.content if hasattr(response, "content") else str(response)
                    logger.info(
                        "agent.run | done | rounds=%d | tools=%d | skill=%s | reply_len=%d | user_id=%s",
                        round_num + 1,
                        tool_calls_made,
                        skill_used,
                        len(reply),
                        ctx.user_id,
                    )
                    return {
                        "reply": reply,
                        "tokens_used": max(1, 1 + tool_calls_made),
                        "tools_called": tool_calls_made,
                        "skill_used": skill_used,
                    }

                logger.debug(
                    "agent.run | tool_round=%d | tools=%s | user_id=%s",
                    round_num + 1,
                    [tc.get("name") or tc.get("function", {}).get("name", "?") for tc in tool_calls],
                    ctx.user_id,
                )

                lc_messages.append(response)
                for tc in tool_calls:
                    tool_name, tool_args, tool_id, tool_output = _dispatch_tool_call(
                        tc, self.tool_registry, self.tool_executor, ctx
                    )
                    logger.info(
                        "agent.run | tool_call | tool=%s | args=%s | user_id=%s",
                        tool_name,
                        {k: str(v)[:100] for k, v in tool_args.items()},
                        ctx.user_id,
                    )
                    lc_messages.append(ToolMessage(content=tool_output, tool_call_id=tool_id))
                    tool_calls_made += 1

                    # Respect max_tool_calls budget
                    if tool_calls_made >= ctx.max_tool_calls:
                        logger.warning(
                            "agent.run | max_tool_calls=%d reached | user_id=%s",
                            ctx.max_tool_calls,
                            ctx.user_id,
                        )
                        break

            # Max rounds reached — get final answer without tools
            logger.warning(
                "agent.run | max_rounds=%d reached | tools=%d | user_id=%s",
                self.max_tool_rounds,
                tool_calls_made,
                ctx.user_id,
            )
            final_response = _invoke_with_retry(self.llm.invoke, lc_messages)
            reply = final_response.content if hasattr(final_response, "content") else str(final_response)
            return {
                "reply": reply,
                "tokens_used": max(1, 1 + tool_calls_made),
                "tools_called": tool_calls_made,
                "skill_used": skill_used,
            }

        except Exception as exc:
            logger.exception("agent.run | error | user_id=%s | %s", ctx.user_id, exc)
            return {
                "reply": f"I encountered an error while processing your request: {exc}. Please try again.",
                "tokens_used": 1,
                "tools_called": tool_calls_made,
                "skill_used": skill_used,
            }

    def run_stream(
        self,
        messages: List[Dict[str, str]],
        ctx: ExecutionContext,
        system_prompt: str,
    ) -> Generator[str, None, None]:
        """
        Run a full agent turn and yield SSE events.

        Yields SSE-formatted strings:
          - ``data: {"type":"thinking","content":"..."}\\n\\n``
          - ``data: {"type":"skill_start","name":"..."}\\n\\n``
          - ``data: {"type":"skill_done","name":"...","steps":N}\\n\\n``
          - ``data: {"type":"tool_call","name":"...","input":"...","output":"..."}\\n\\n``
          - ``data: {"type":"token","content":"..."}\\n\\n``
          - ``data: {"type":"done","tokens_used":N,"tools_called":M,"skill_used":"..."}\\n\\n``
          - ``data: {"type":"error","content":"..."}\\n\\n``
        """
        from langchain_core.messages import (
            AIMessage, HumanMessage, SystemMessage, ToolMessage,
        )

        if not messages:
            yield 'data: {"type":"token","content":"Hello! How can I help you today?"}\n\n'
            yield 'data: {"type":"done","tokens_used":1,"tools_called":0,"skill_used":null}\n\n'
            return

        last_user_msg = _last_user_message(messages)
        if not last_user_msg:
            yield 'data: {"type":"token","content":"Please send a message."}\n\n'
            yield 'data: {"type":"done","tokens_used":1,"tools_called":0,"skill_used":null}\n\n'
            return

        skill_used: Optional[str] = None
        skill_context_block = ""
        tool_calls_made = 0

        try:
            # ----------------------------------------------------------------
            # 1. Skill intent check
            # ----------------------------------------------------------------
            matched_skill = self.skill_registry.match_intent(last_user_msg)
            if matched_skill:
                skill_name = matched_skill.spec.name  # type: ignore[attr-defined]
                yield f"data: {json.dumps({'type': 'skill_start', 'name': skill_name})}\n\n"
                yield f"data: {json.dumps({'type': 'thinking', 'content': f'Running {skill_name} workflow...'})}\n\n"

                skill_args = _extract_skill_args(last_user_msg, matched_skill)
                skill_result = self.skill_executor.run(matched_skill, ctx, **skill_args)

                if skill_result.ok:
                    skill_used = skill_name
                    skill_context_block = (
                        f"\n\n## Skill Workflow Result ({skill_name})\n"
                        f"The following data was gathered by running the '{skill_name}' workflow:\n\n"
                        f"{skill_result.to_str()}\n\n"
                        f"Use this data to answer the user's question. Do NOT call tools to re-fetch "
                        f"data already present above."
                    )
                    yield f"data: {json.dumps({'type': 'skill_done', 'name': skill_name, 'steps': len(skill_result.steps)})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'thinking', 'content': f'Skill {skill_name} failed, falling back to tools...'})}\n\n"

            # ----------------------------------------------------------------
            # 2. Build LangChain message list
            # ----------------------------------------------------------------
            full_system = system_prompt + skill_context_block
            lc_messages: List[Any] = [SystemMessage(content=full_system)]
            for msg in messages[-20:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    lc_messages.append(HumanMessage(content=content))
                else:
                    lc_messages.append(AIMessage(content=content))

            # ----------------------------------------------------------------
            # 3. LLM tool-calling loop
            # ----------------------------------------------------------------
            tool_schemas = self.tool_registry.to_openai_schemas()
            llm_with_tools = self.llm.bind_tools(tool_schemas)  # type: ignore[attr-defined]

            for round_num in range(self.max_tool_rounds):
                response = _invoke_with_retry(llm_with_tools.invoke, lc_messages)

                tool_calls = getattr(response, "tool_calls", None)
                if not tool_calls:
                    reply = response.content if hasattr(response, "content") else str(response)
                    yield f"data: {json.dumps({'type': 'token', 'content': reply})}\n\n"
                    yield f"data: {json.dumps({'type': 'done', 'tokens_used': max(1, 1 + tool_calls_made), 'tools_called': tool_calls_made, 'skill_used': skill_used})}\n\n"
                    return

                lc_messages.append(response)
                for tc in tool_calls:
                    tool_name, tool_args, tool_id, tool_output = _dispatch_tool_call(
                        tc, self.tool_registry, self.tool_executor, ctx
                    )
                    yield f"data: {json.dumps({'type': 'thinking', 'content': f'Calling {tool_name}...'})}\n\n"
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': tool_name, 'input': str(tool_args)[:200], 'output': tool_output[:500]})}\n\n"
                    lc_messages.append(ToolMessage(content=tool_output, tool_call_id=tool_id))
                    tool_calls_made += 1

                    if tool_calls_made >= ctx.max_tool_calls:
                        break

            # Max rounds — force final answer
            final_response = _invoke_with_retry(self.llm.invoke, lc_messages)
            reply = final_response.content if hasattr(final_response, "content") else str(final_response)
            yield f"data: {json.dumps({'type': 'token', 'content': reply})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'tokens_used': max(1, 1 + tool_calls_made), 'tools_called': tool_calls_made, 'skill_used': skill_used})}\n\n"

        except Exception as exc:
            logger.exception("agent.run_stream | error | user_id=%s | %s", ctx.user_id, exc)
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _last_user_message(messages: List[Dict[str, str]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return ""


def _dispatch_tool_call(
    tc: dict,
    tool_registry: Any,
    tool_executor: Any,
    ctx: Any,
) -> tuple[str, dict, str, str]:
    """
    Parse a single tool-call dict, look up the tool, execute it, and return
    (tool_name, tool_args, tool_id, tool_output).

    Shared by run() and run_stream() to avoid duplicating the dispatch logic.
    """
    tool_name = tc.get("name") or tc.get("function", {}).get("name", "")
    tool_args_raw = tc.get("args") or tc.get("function", {}).get("arguments", "{}")
    tool_id = tc.get("id", tool_name)

    if isinstance(tool_args_raw, str):
        try:
            tool_args = json.loads(tool_args_raw)
        except Exception:
            tool_args = {}
    else:
        tool_args = tool_args_raw or {}

    tool = tool_registry.get(tool_name)
    if tool:
        tool_output = tool_executor.run(tool, ctx, **tool_args).to_str()
    else:
        logger.warning("agent | unknown_tool=%s | user_id=%s", tool_name, ctx.user_id)
        tool_output = f"Unknown tool: {tool_name}"

    return tool_name, tool_args, tool_id, tool_output


def _invoke_with_retry(fn, *args, max_retries: int = 3, **kwargs):
    """Retry an LLM call up to max_retries times on transient errors."""
    import time as _time
    last_exc = None
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning("LLM call failed (attempt %d/%d), retrying in %ds: %s", attempt + 1, max_retries, wait, exc)
                _time.sleep(wait)
    raise last_exc  # type: ignore[misc]


def _extract_skill_args(message: str, skill: Any) -> dict:
    """
    Extract arguments for a skill from the user message.

    For skills that need a ticker, try to extract it from the message.
    For skills that need a list of tickers (compare), extract multiple.
    Falls back to empty dict if nothing can be extracted.
    """
    import re
    spec = skill.spec  # type: ignore[attr-defined]
    schema = spec.input_schema
    props = schema.get("properties", {})

    args: dict = {}

    if "ticker" in props:
        # Extract single ticker: 2-5 uppercase letters (or with - for BRK-B etc.)
        match = re.search(r"\b([A-Z]{2,5}(?:-[A-Z])?)\b", message.upper())
        if match:
            args["ticker"] = match.group(1)

    if "tickers" in props:
        # Extract multiple tickers
        found = re.findall(r"\b([A-Z]{2,5}(?:-[A-Z])?)\b", message.upper())
        # Filter out common English words that look like tickers
        _STOP = {"AND", "THE", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "HER",
                 "WAS", "ONE", "OUR", "OUT", "DAY", "GET", "HAS", "HIM", "HIS", "HOW",
                 "ITS", "MAY", "NEW", "NOW", "OLD", "SEE", "TWO", "WAY", "WHO", "BOY",
                 "DID", "ITS", "LET", "PUT", "SAY", "SHE", "TOO", "USE", "VS", "OR"}
        tickers = [t for t in dict.fromkeys(found) if t not in _STOP]
        if len(tickers) >= 2:
            args["tickers"] = tickers[:6]

    return args


