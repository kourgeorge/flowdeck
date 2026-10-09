from ai_engine.llm_provider import get_llm


def test_openai_key_trailing_newline_is_stripped(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key\n")
    llm = get_llm("quick", {"llm_provider": "openai", "quick_think_llm": "gpt-4o-mini"})
    assert llm.openai_api_key.get_secret_value() == "sk-test-key"


def test_azure_key_trailing_newline_is_stripped(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/\n")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-test-key\n")
    llm = get_llm("quick", {"llm_provider": "azure", "quick_think_llm": "gpt-4o-mini"})
    assert llm.openai_api_key.get_secret_value() == "azure-test-key"


def test_anthropic_key_trailing_newline_is_stripped(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test\n")
    llm = get_llm("quick", {"llm_provider": "anthropic", "quick_think_llm": "claude-haiku-4-5-20251001"})
    assert llm.anthropic_api_key.get_secret_value() == "sk-ant-test"
