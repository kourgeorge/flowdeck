"""
Regression test for the 2026-11-02 daily brief, run on gpt-6 through the LiteLLM
chatgpt/ route. Every brief step called llm.with_structured_output(schema) with
the default json_schema method; that route ignores response_format, so the model
answered in markdown ('## narrative ...') and each step failed with json_invalid.
The brief must ask OpenAI-compatible models for a forced tool call instead, the
same fix the trading analysts got in ae1e4cc.
"""

from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

from ai_engine.briefing_agent.agents import run_narrative_writer, run_ticker_interpreter
from ai_engine.briefing_agent.state import DigestContext, DigestWorkflowState


class _RecordingChatOpenAI(ChatOpenAI):
    """Records the structured-output method and returns a filled-in schema instance."""

    def with_structured_output(self, schema, **kwargs):
        self.__dict__.setdefault("_methods", []).append(kwargs.get("method"))
        fields = {
            name: ("company" if name == "driver" else "text")
            for name, field in schema.model_fields.items()
            if field.is_required()
        }
        return RunnableLambda(lambda _input, **_kw: schema(**fields))


def _llm():
    return _RecordingChatOpenAI(model="chatgpt/gpt-6", api_key="test", base_url="http://localhost:1")


def _state():
    return DigestWorkflowState(
        user_id=1,
        digest_date="2026-11-02",
        digest_context=DigestContext(tickers=["QCOM"], priority_tickers=["QCOM"]),
    )


def test_ticker_interpreter_uses_function_calling():
    llm = _llm()

    result = run_ticker_interpreter(_state(), llm)

    assert llm.__dict__["_methods"] == ["function_calling"]
    assert result["QCOM"].explanation == "text"


def test_narrative_writer_uses_function_calling():
    llm = _llm()

    narrative, what_to_watch = run_narrative_writer(_state(), llm)

    assert llm.__dict__["_methods"] == ["function_calling"]
    assert what_to_watch == "text"
    assert narrative
