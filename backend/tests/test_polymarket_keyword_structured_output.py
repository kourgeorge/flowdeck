"""
The Polymarket keyword generator must bind its schema through structured_output()
so OpenAI-compatible models (the LiteLLM chatgpt/ route, which ignores
response_format) get a forced tool call, like the rest of the project.
"""

from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

import ai_engine.llm_provider as llm_provider
from services import polymarket_keyword_generator as gen


class _RecordingChatOpenAI(ChatOpenAI):
    """Records the structured-output method and returns a fixed keyword list."""

    def with_structured_output(self, schema, **kwargs):
        self.__dict__.setdefault("_methods", []).append(kwargs.get("method"))
        return RunnableLambda(
            lambda _input, **_kw: schema(keywords=["Nvidia", " GPU ", "", "Jensen Huang"])
        )


def test_keywords_parsed_via_function_calling(monkeypatch):
    llm = _RecordingChatOpenAI(model="chatgpt/gpt-6", api_key="test", base_url="http://localhost:1")
    monkeypatch.setattr(llm_provider, "get_config_from_env", lambda: {})
    monkeypatch.setattr(llm_provider, "get_llm", lambda *_a, **_kw: llm)

    keywords = gen._generate_via_llm("NVDA", {"name": "NVIDIA"}, limit=12)

    assert keywords == ["Nvidia", "GPU", "Jensen Huang"]
    assert llm.__dict__["_methods"] == ["function_calling"]
