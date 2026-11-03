"""
Regression tests for the final-report step of run_self_contained_analyst.

NVDA runs 2617 (gpt-6-luna) and 2618 (gpt-6.1-sol) on the LiteLLM chatgpt/ route
lost every analyst score: the route ignores response_format json_schema, so the
structured call failed for all six analysts. On sol the narrative fallback then
came back empty too, and five reports were never persisted. These tests pin the
two fixes: OpenAI-compatible models use a forced tool call for the schema, and
an empty narrative reply gets one retry with an explicit closing instruction.
"""

from typing import List

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from ai_engine.llm_provider import structured_output
from ai_engine.tradingagents.agents.analysts.self_contained_analyst import (
    _FINAL_REPORT_INSTRUCTION,
    run_self_contained_analyst,
)


class _Output(BaseModel):
    report: str = Field(description="report")
    other_score: int = Field(ge=1, le=5, description="score")


class _FailingStructuredLLM(Runnable):
    """Tool loop ends immediately, structured output raises, narrative replies are canned."""

    def __init__(self, narrative_replies: List[AIMessage]):
        self._narrative_replies = list(narrative_replies)
        self.narrative_inputs = []

    def bind_tools(self, tools):
        return RunnableLambda(lambda _input, **kwargs: AIMessage(content="", tool_calls=[]))

    def with_structured_output(self, cls):
        def _raise(_input, **kwargs):
            raise ValueError("Structured Output response does not have a 'parsed' field")
        return RunnableLambda(_raise)

    def invoke(self, prompt_value, config=None, **kwargs):
        self.narrative_inputs.append(prompt_value.to_messages())
        return self._narrative_replies.pop(0)


def _build_prompt(**kwargs):
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

    return ChatPromptTemplate.from_messages([
        ("system", "You are a test analyst for {ticker} on {current_date}."),
        MessagesPlaceholder(variable_name="messages"),
    ]).partial(ticker=kwargs["ticker"], current_date=kwargs["current_date"])


def _other_tool(ticker: str) -> str:
    return "{}"


def _run(llm):
    return run_self_contained_analyst(
        state={"trade_date": "2026-10-26", "company_of_interest": "NVDA"},
        llm=llm,
        tools=[_other_tool],
        prompt_builder=_build_prompt,
        structured_output_class=_Output,
        score_field="other_score",
        report_field="other_report",
        agent_name="Other Analyst",
        max_iterations=1,
    )


def test_empty_narrative_reply_is_retried_with_closing_instruction():
    llm = _FailingStructuredLLM([
        AIMessage(content=""),
        AIMessage(content="## NVDA report\nReal content."),
    ])

    result = _run(llm)

    assert result["other_report"] == "## NVDA report\nReal content."
    assert result["other_score"] is None
    assert len(llm.narrative_inputs) == 2
    retry_last = llm.narrative_inputs[1][-1]
    assert isinstance(retry_last, HumanMessage)
    assert retry_last.content == _FINAL_REPORT_INSTRUCTION


def test_nonempty_narrative_reply_is_not_retried():
    llm = _FailingStructuredLLM([AIMessage(content="First try worked.")])

    result = _run(llm)

    assert result["other_report"] == "First try worked."
    assert len(llm.narrative_inputs) == 1


def test_list_of_blocks_content_is_read_as_text():
    llm = _FailingStructuredLLM([
        AIMessage(content=[{"type": "text", "text": "Block "}, {"type": "text", "text": "content."}]),
    ])

    result = _run(llm)

    assert result["other_report"] == "Block content."
    assert len(llm.narrative_inputs) == 1


def test_openai_compatible_models_use_function_calling():
    llm = ChatOpenAI(model="chatgpt/gpt-6.1-sol", api_key="test", base_url="http://localhost:1")

    bound = structured_output(llm, _Output)

    # with_structured_output returns model.bind(...) | parser; the binding carries
    # a forced tool choice for function_calling and a response_format for json_schema.
    binding = bound.first
    assert "tools" in binding.kwargs
    assert "response_format" not in binding.kwargs


def test_non_openai_models_keep_their_default_method():
    calls = []

    class _OtherProvider:
        def with_structured_output(self, schema, **kwargs):
            calls.append(kwargs)
            return "bound"

    assert structured_output(_OtherProvider(), _Output) == "bound"
    assert calls == [{}]
