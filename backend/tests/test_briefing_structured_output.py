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


# A brief whose writer failed used to be saved as "completed" and charged, with
# a narrative of "Digest unavailable: <raw error incl. internal LiteLLM URL>" or
# an empty string when the model skipped the tool call. The writer must raise so
# digest_service marks the run failed and refunds it.


class _FakeLLM:
    """Non-OpenAI fake: structured_output() calls with_structured_output(schema)."""

    def __init__(self, invoke):
        self._invoke = invoke

    def with_structured_output(self, schema, **kwargs):
        return RunnableLambda(lambda _input, **_kw: self._invoke())


def _raise_timeout():
    raise TimeoutError("Request timed out: http://litellm.internal:4000/v1/chat/completions")


def test_narrative_writer_raises_on_llm_error():
    import pytest

    from ai_engine.briefing_agent.agents import NarrativeWriterError

    with pytest.raises(NarrativeWriterError) as excinfo:
        run_narrative_writer(_state(), _FakeLLM(_raise_timeout))

    message = str(excinfo.value)
    assert "Digest unavailable:" not in message
    assert "litellm.internal" not in message
    assert isinstance(excinfo.value.__cause__, TimeoutError)


def test_narrative_writer_raises_when_llm_returns_none():
    import pytest

    from ai_engine.briefing_agent.agents import NarrativeWriterError

    with pytest.raises(NarrativeWriterError):
        run_narrative_writer(_state(), _FakeLLM(lambda: None))


def test_narrative_writer_structured_style_raises_when_llm_returns_none(monkeypatch):
    import pytest

    from ai_engine.briefing_agent import prompts
    from ai_engine.briefing_agent.agents import NarrativeWriterError

    monkeypatch.setattr(prompts, "style_uses_structured_output", lambda _style: True)

    with pytest.raises(NarrativeWriterError):
        run_narrative_writer(_state(), _FakeLLM(lambda: None))


def test_digest_service_fails_and_refunds_when_narrative_writer_errors(monkeypatch):
    import asyncio

    import pytest
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import ai_engine.briefing_agent as briefing_agent
    from ai_engine.briefing_agent.agents import NarrativeWriterError
    from database import Base
    from models.db_models import Execution, Report, Usage, User
    from services import digest_service, report_service

    # StaticPool: update_execution_status opens its own session, which must see
    # the same in-memory database as the session passed to the service.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr(report_service, "SessionLocal", TestSession)

    db = TestSession()
    db.add(User(id=1, email="brief@example.com", hashed_password="x"))
    db.commit()

    def _fake_run_digest(**_kwargs):
        run_narrative_writer(_state(), _FakeLLM(_raise_timeout))

    monkeypatch.setattr(briefing_agent, "run_digest", _fake_run_digest)

    try:
        with pytest.raises(NarrativeWriterError):
            asyncio.run(
                digest_service.run_and_store_digest(
                    db, 1, digest_date="2026-11-02", span_type="daily"
                )
            )

        db.expire_all()
        execution = db.query(Execution).one()
        assert execution.status == "failed"
        assert "litellm.internal" not in (execution.error_message or "")
        assert db.query(Report).count() == 0
        refunds = (
            db.query(Usage)
            .filter(
                Usage.related_entity_type == "execution",
                Usage.related_entity_id == execution.id,
                Usage.transaction_type == "refund",
            )
            .all()
        )
        assert len(refunds) == 1
        assert refunds[0].amount > 0
    finally:
        db.close()
        engine.dispose()
