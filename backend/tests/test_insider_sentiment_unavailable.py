"""Insider sentiment has no data source, so it must refuse honestly.

Before: the vendor map had `"get_insider_sentiment": {}`, so routing raised
"Attempted 0 vendor(s)" and the endpoint always returned 500, while every agent
tool list still offered the tool and wasted a call on that error.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.data_api import router as data_router

app = FastAPI()
app.include_router(data_router)


def _tool_name(t) -> str:
    return getattr(t, "name", None) or getattr(t, "__name__", "") or str(t)


def test_insider_sentiment_endpoint_returns_503_not_500():
    gateway = MagicMock()
    with patch("routers.data_api.get_data_gateway", return_value=gateway):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/data/insider-sentiment/AAPL", params={"curr_date": "2026-11-16"})

    assert response.status_code == 503, response.text
    assert response.json()["detail"] == "Insider sentiment is not available (no data source configured)"
    gateway.get_insider_sentiment.assert_not_called()


def test_lc_tool_list_has_no_insider_sentiment():
    from ai_engine.agent.lc_tools import ALL_LC_TOOLS, get_all_lc_tools

    names = {_tool_name(t) for t in ALL_LC_TOOLS} | {_tool_name(t) for t in get_all_lc_tools()}
    assert "get_insider_transactions" in names
    assert not any("insider_sentiment" in n for n in names), names


def test_registered_tools_have_no_insider_sentiment():
    import ai_engine.agent.tools as tools_pkg

    names = {t.spec.name for t in tools_pkg.ALL_TOOLS}
    assert "get_insider_transactions" in names
    assert not any("insider_sentiment" in n for n in names), names
    assert not hasattr(tools_pkg, "InsiderSentimentTool")


def test_agent_prompts_and_tool_lists_do_not_mention_insider_sentiment():
    # Prompts and name-based tool lists are plain strings, so check the source text:
    # any mention would point the LLM at a tool it can no longer call.
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    for rel in (
        "ai_engine/agent/lc_tools.py",
        "ai_engine/agent/tools/__init__.py",
        "ai_engine/agent/tools/web_search.py",
        "ai_engine/briefing_agent/agents.py",
        "ai_engine/portfolio_deep_research/tools.py",
        "ai_engine/tradingagents/graph/trading_graph.py",
        "backend/services/chat_service.py",
    ):
        assert "get_insider_sentiment" not in (root / rel).read_text(), rel
