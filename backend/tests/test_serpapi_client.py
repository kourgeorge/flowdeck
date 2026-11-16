"""Deep research and watchlist web research share ai_engine.serpapi_client (T-79).

They used to carry line-for-line copies of the SerpAPI call, and the deep research tool
ignored PortfolioDeepResearchConfig.serpapi_key. urlopen is faked so nothing hits the network.
"""

import io
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

_WC = Path(__file__).resolve().parents[2] / "ai_engine" / "watchlist_consulting"
if str(_WC) not in sys.path:
    sys.path.insert(0, str(_WC))

from ai_engine import serpapi_client  # noqa: E402
from ai_engine.portfolio_deep_research.config import PortfolioDeepResearchConfig  # noqa: E402
from ai_engine.portfolio_deep_research import tools as pdr_tools  # noqa: E402
import web_research  # noqa: E402

_BODY = {
    "organic_results": [
        {"title": "Apple beats", "snippet": "Revenue up.", "link": "https://a.example/1",
         "displayed_link": "a.example › markets › apple"},
        {"title": "Apple guidance", "snippet": "Soft Q4.", "link": "https://b.example/2",
         "source": "B News"},
        {"title": "Third", "snippet": "x", "link": "https://c.example/3"},
    ]
}

_EXPECTED = [
    {"title": "Apple beats", "snippet": "Revenue up.", "url": "https://a.example/1", "domain": "a.example"},
    {"title": "Apple guidance", "snippet": "Soft Q4.", "url": "https://b.example/2", "domain": "B News"},
]


def _fake_urlopen(monkeypatch, body):
    calls = []

    def fake(req, timeout=None):
        calls.append({"url": req.full_url, "timeout": timeout})
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return calls


def _key_of(call):
    return urllib.parse.parse_qs(urllib.parse.urlparse(call["url"]).query)["api_key"][0]


def test_watchlist_search_returns_result_dicts(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "env-key")
    calls = _fake_urlopen(monkeypatch, _BODY)
    assert web_research.serpapi_search("apple", num_results=2) == _EXPECTED
    assert _key_of(calls[0]) == "env-key"
    assert calls[0]["timeout"] == 30


def test_deep_research_tool_formats_results(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "env-key")
    _fake_urlopen(monkeypatch, _BODY)
    out = pdr_tools.serpapi_search.invoke({"query": "apple", "num_results": 2})
    assert out == (
        "[1] Apple beats\nURL: https://a.example/1\nRevenue up.\n\n"
        "[2] Apple guidance\nURL: https://b.example/2\nSoft Q4.\n"
    )


def test_deep_research_tool_empty_results(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "env-key")
    _fake_urlopen(monkeypatch, {"organic_results": []})
    assert pdr_tools.serpapi_search.invoke({"query": "nothing"}) == "No results found. Try a different query."


def test_config_key_is_used_over_env(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "env-key")
    calls = _fake_urlopen(monkeypatch, _BODY)
    monkeypatch.setattr(pdr_tools, "get_data_tools", lambda: [])
    tools = pdr_tools.get_all_tools(PortfolioDeepResearchConfig(serpapi_key="cfg-key"))
    search_tool = next(t for t in tools if t.name == "serpapi_search")
    search_tool.invoke({"query": "apple"})
    assert _key_of(calls[0]) == "cfg-key"


def test_no_config_key_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "env-key")
    calls = _fake_urlopen(monkeypatch, _BODY)
    monkeypatch.setattr(pdr_tools, "get_data_tools", lambda: [])
    for cfg in (None, PortfolioDeepResearchConfig()):
        search_tool = next(t for t in pdr_tools.get_all_tools(cfg) if t.name == "serpapi_search")
        search_tool.invoke({"query": "apple"})
    assert [_key_of(c) for c in calls] == ["env-key", "env-key"]


def test_missing_key_and_api_error_are_unchanged(monkeypatch):
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    with pytest.raises(ValueError, match="SERPAPI_KEY not set"):
        web_research.serpapi_search("apple")
    with pytest.raises(ValueError, match="SERPAPI_KEY not set"):
        pdr_tools.serpapi_search.invoke({"query": "apple"})

    _fake_urlopen(monkeypatch, {"error": "Invalid API key."})
    with pytest.raises(RuntimeError, match="SerpAPI error: Invalid API key."):
        serpapi_client.search("apple", num_results=5, api_key="bad")
