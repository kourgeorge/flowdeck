"""
Tests for report_resources: state reducer, resource extraction, and metadata persistence.
"""

import json
import pytest

# Reducer and extraction live in ai_engine; run from backend with repo root on path
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_merge_report_resources_dedupe():
    from ai_engine.tradingagents.agents.utils.agent_states import _merge_report_resources

    current = [
        {"type": "news", "url": "https://a.com", "title": "A"},
    ]
    update = [
        {"type": "news", "url": "https://a.com"},
        {"type": "sec_filing", "ticker": "AAPL", "title": "10-K filed 2024-01-15"},
    ]
    merged = _merge_report_resources(current, update)
    assert len(merged) == 2
    assert merged[0]["url"] == "https://a.com"
    assert merged[1]["type"] == "sec_filing" and merged[1]["ticker"] == "AAPL"


def test_merge_report_resources_empty_update():
    from ai_engine.tradingagents.agents.utils.agent_states import _merge_report_resources

    current = [{"type": "news", "url": "https://x.com"}]
    merged = _merge_report_resources(current, [])
    assert merged == current


def test_extract_resources_from_news():
    from ai_engine.tradingagents.agents.utils.resource_extraction import extract_resources_from_tool

    result = json.dumps({
        "articles": [
            {"link": "https://example.com/1", "title": "Article 1", "publisher": "Reuters"},
            {"link": "https://example.com/2", "title": "Article 2"},
        ],
    })
    resources = extract_resources_from_tool("get_news", {"ticker": "AAPL"}, result)
    assert len(resources) == 2
    assert resources[0]["type"] == "news"
    assert resources[0]["url"] == "https://example.com/1"
    assert resources[0]["title"] == "Article 1"
    assert resources[0]["ticker"] == "AAPL"
    assert resources[1]["url"] == "https://example.com/2"


def test_extract_resources_from_edgar():
    from ai_engine.tradingagents.agents.utils.resource_extraction import extract_resources_from_tool

    result = json.dumps({
        "filings": [
            {"form": "10-K", "filing_date": "2024-01-15", "accession_number": "0001234567-24-000001"},
        ],
    })
    resources = extract_resources_from_tool("get_edgar_filing_content", {"ticker": "AAPL"}, result)
    assert len(resources) == 1
    assert resources[0]["type"] == "sec_filing"
    assert resources[0]["ticker"] == "AAPL"
    assert "10-K" in (resources[0].get("title") or "")


def test_extract_resources_from_reddit():
    from ai_engine.tradingagents.agents.utils.resource_extraction import extract_resources_from_tool

    resources = extract_resources_from_tool(
        "get_reddit_company_social",
        {"ticker": "MSFT", "start_date": "2024-01-01", "end_date": "2024-01-07", "search_terms": ["Microsoft", "MSFT"]},
        "some text result",
    )
    assert len(resources) == 1
    assert resources[0]["type"] == "reddit"
    assert resources[0]["ticker"] == "MSFT"


def test_extract_resources_from_global_news_markdown():
    """Global news can return markdown; parser should extract links from 'Source: URL' and inline URLs."""
    from ai_engine.tradingagents.agents.utils.resource_extraction import extract_resources_from_tool

    # SerpAPI-style markdown with "Source: URL" lines
    markdown = """
## Global News (SerpAPI), from 2024-01-01 to 2024-01-08

**1. Fed signals rate hold** — Reuters (Jan 5)
Markets expect no change in March.
Source: https://example.com/fed-hold

**2. Oil prices rise** — Bloomberg
OPEC+ extends cuts.
Source: https://example.com/oil
"""
    resources = extract_resources_from_tool("get_global_news", {}, markdown)
    assert len(resources) == 2
    assert resources[0]["type"] == "global_news"
    assert resources[0]["url"] == "https://example.com/fed-hold"
    assert "Fed" in (resources[0].get("title") or "")
    assert resources[1]["url"] == "https://example.com/oil"

    # Fallback: no JSON, no Source: lines — single generic entry
    resources2 = extract_resources_from_tool("get_global_news", {}, "Plain text with https://one.com link inside.")
    assert len(resources2) >= 1
    assert resources2[0]["type"] == "global_news"
    assert resources2[0].get("url") == "https://one.com" or resources2[0].get("description")


def test_extract_resources_from_fundamentals():
    from ai_engine.tradingagents.agents.utils.resource_extraction import extract_resources_from_tool

    resources = extract_resources_from_tool("get_fundamentals", {"ticker": "GOOGL"}, "{}")
    assert len(resources) == 1
    assert resources[0]["type"] == "fundamentals"
    assert resources[0]["ticker"] == "GOOGL"


def test_report_row_to_dict_includes_resources():
    """_report_row_to_dict must expose resources from metadata_json."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from services.report_service import _report_row_to_dict

    class Row:
        content = ""
        metadata_json = json.dumps({
            "score": 4,
            "resources": [
                {"type": "news", "url": "https://example.com", "title": "Test"},
            ],
        })

    out = _report_row_to_dict(Row(), "2024-01-01")
    assert "resources" in out
    assert isinstance(out["resources"], list)
    assert len(out["resources"]) == 1
    assert out["resources"][0]["type"] == "news"
    assert out["resources"][0]["url"] == "https://example.com"


def test_build_tool_resource_snapshots_persists_actual_tool_output():
    from ai_engine.tradingagents.agents.analysts.self_contained_analyst import build_tool_resource_snapshots

    snapshots = build_tool_resource_snapshots(
        "get_ticker_quote",
        {"symbol": "AAPL"},
        '{"ticker":"AAPL","current_price":123.45,"currency":"USD"}',
    )

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot["type"] == "market_quote"
    assert snapshot["ticker"] == "AAPL"
    assert snapshot["tool_name"] == "get_ticker_quote"
    assert snapshot["tool_input"]["symbol"] == "AAPL"
    assert snapshot["tool_output"]["ticker"] == "AAPL"
    assert snapshot["tool_output"]["current_price"] == 123.45
    assert "current_price" in snapshot["tool_output_preview"]


def test_merge_report_resources_keeps_distinct_tool_snapshots_for_same_ticker():
    from ai_engine.tradingagents.agents.analysts.self_contained_analyst import build_tool_resource_snapshots
    from ai_engine.tradingagents.agents.utils.agent_states import _merge_report_resources

    quote_snapshot = build_tool_resource_snapshots(
        "get_ticker_quote",
        {"symbol": "AMZN"},
        '{"ticker":"AMZN","current_price":190.0}',
    )
    indicators_snapshot = build_tool_resource_snapshots(
        "get_indicators",
        {"ticker": "AMZN"},
        "# Technical Indicators for AMZN",
    )

    merged = _merge_report_resources(quote_snapshot, indicators_snapshot)
    assert len(merged) == 2
    assert {item["tool_name"] for item in merged} == {"get_ticker_quote", "get_indicators"}


def test_merge_report_resources_by_report_keeps_resources_scoped_to_report():
    from ai_engine.tradingagents.agents.analysts.self_contained_analyst import build_tool_resource_snapshots
    from ai_engine.tradingagents.agents.utils.agent_states import _merge_report_resources_by_report

    market_resources = build_tool_resource_snapshots(
        "get_ticker_quote",
        {"symbol": "AMZN"},
        '{"ticker":"AMZN","current_price":190.0}',
    )
    news_resources = build_tool_resource_snapshots(
        "get_news",
        {"ticker": "AMZN", "start_date": "2026-04-01", "end_date": "2026-04-06"},
        '{"articles":[{"link":"https://example.com/amzn","title":"AMZN headline"}]}',
    )

    merged = _merge_report_resources_by_report(
        {"market_report": market_resources},
        {"sentiment_report": news_resources},
    )

    assert set(merged.keys()) == {"market_report", "sentiment_report"}
    assert merged["market_report"][0]["tool_name"] == "get_ticker_quote"
    assert merged["sentiment_report"][0]["tool_name"] == "get_news"


def test_merge_report_steps_by_report_appends_steps():
    from ai_engine.tradingagents.agents.utils.agent_states import _merge_report_steps_by_report

    merged = _merge_report_steps_by_report(
        {"investment_plan": [{"agent": "Bull Researcher", "kind": "debate_turn", "captured_at": "2026-04-07T10:00:01+00:00"}]},
        {"investment_plan": [{"agent": "Bear Researcher", "kind": "debate_turn", "captured_at": "2026-04-07T10:00:02+00:00"}]},
    )

    assert list(merged.keys()) == ["investment_plan"]
    assert len(merged["investment_plan"]) == 2
    assert [step["agent"] for step in merged["investment_plan"]] == [
        "Bull Researcher",
        "Bear Researcher",
    ]


def test_merge_report_steps_by_report_sorts_out_of_order_updates():
    from ai_engine.tradingagents.agents.utils.agent_states import _merge_report_steps_by_report

    merged = _merge_report_steps_by_report(
        {
            "investment_plan": [
                {"agent": "Research Manager", "kind": "report_synthesis", "captured_at": "2026-04-07T10:00:03+00:00"},
            ]
        },
        {
            "investment_plan": [
                {"agent": "Bull Researcher", "kind": "debate_turn", "round_number": 1, "captured_at": "2026-04-07T10:00:01+00:00"},
                {"agent": "Bear Researcher", "kind": "debate_turn", "round_number": 2, "captured_at": "2026-04-07T10:00:02+00:00"},
            ]
        },
    )

    assert [step["agent"] for step in merged["investment_plan"]] == [
        "Bull Researcher",
        "Bear Researcher",
        "Research Manager",
    ]


def test_report_row_to_dict_includes_agent_steps():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from services.report_service import _report_row_to_dict

    class Row:
        content = ""
        metadata_json = json.dumps({
            "agent_steps": [
                {"agent": "Market Analyst", "kind": "tool_call", "tool_name": "get_ticker_quote"},
            ],
        })

    out = _report_row_to_dict(Row(), "2024-01-01")
    assert "agent_steps" in out
    assert isinstance(out["agent_steps"], list)
    assert len(out["agent_steps"]) == 1
    assert out["agent_steps"][0]["agent"] == "Market Analyst"


def test_report_row_to_dict_sorts_agent_steps_by_captured_at():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from services.report_service import _report_row_to_dict

    class Row:
        content = ""
        metadata_json = json.dumps({
            "agent_steps": [
                {"agent": "Research Manager", "kind": "report_synthesis", "captured_at": "2026-04-07T10:00:03+00:00"},
                {"agent": "Bull Researcher", "kind": "debate_turn", "captured_at": "2026-04-07T10:00:01+00:00"},
                {"agent": "Bear Researcher", "kind": "debate_turn", "captured_at": "2026-04-07T10:00:02+00:00"},
            ],
        })

    out = _report_row_to_dict(Row(), "2026-04-07")
    assert [step["agent"] for step in out["agent_steps"]] == [
        "Bull Researcher",
        "Bear Researcher",
        "Research Manager",
    ]


class _StubMemory:
    def get_memories(self, curr_situation, n_matches=2):
        return [{"recommendation": "Prior lesson"}]


class _StubResponse:
    def __init__(self, content: str):
        self.content = content


class _StubLLM:
    def __init__(self, content: str):
        self.content = content
        self.last_prompt = None

    def invoke(self, prompt):
        self.last_prompt = prompt
        return _StubResponse(self.content)


def test_research_debate_turn_persists_prompt_in_message_preview():
    from ai_engine.tradingagents.agents.researchers.bull_researcher import create_bull_researcher
    from ai_engine.tradingagents.agents.researchers.bear_researcher import create_bear_researcher

    state = {
        "investment_debate_state": {
            "history": "Prior debate history",
            "bull_history": "",
            "bear_history": "",
            "current_response": "Opponent response",
            "count": 0,
        },
        "market_report": "Market data",
        "sentiment_report": "News & sentiment data",
        "fundamentals_report": "Fundamentals data",
        "technical_report": "Technical data",
        "events_report": "Events data",
    }

    bull_llm = _StubLLM("Bull thesis")
    bull_out = create_bull_researcher(bull_llm, _StubMemory())(state)
    bull_step = bull_out["report_steps_by_report"]["investment_plan"][0]
    assert bull_step["message_preview"] == bull_llm.last_prompt.strip()
    assert bull_step["output_preview"] == "Bull Analyst: Bull thesis"

    bear_llm = _StubLLM("Bear thesis")
    bear_out = create_bear_researcher(bear_llm, _StubMemory())(state)
    bear_step = bear_out["report_steps_by_report"]["investment_plan"][0]
    assert bear_step["message_preview"] == bear_llm.last_prompt.strip()
    assert bear_step["output_preview"] == "Bear Analyst: Bear thesis"


def test_extract_resources_node():
    """Extract-resources node reads state with AIMessage + ToolMessages and returns report_resources."""
    pytest.importorskip("ai_engine.tradingagents.graph.tool_node_with_resources")
    from langchain_core.messages import AIMessage, ToolMessage
    from ai_engine.tradingagents.graph.tool_node_with_resources import make_extract_resources_node

    tool_call_id = "call_abc"
    tool_result = json.dumps({"articles": [{"link": "https://n.com/1", "title": "News 1"}]})

    extract_node = make_extract_resources_node()
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{
                    "id": tool_call_id,
                    "name": "get_news",
                    "args": {"ticker": "AAPL", "start_date": "2024-01-01", "end_date": "2024-01-07"},
                }],
            ),
            ToolMessage(content=tool_result, tool_call_id=tool_call_id),
        ],
        "report_resources": [],
    }
    update = extract_node(state)
    assert "report_resources" in update
    resources = update["report_resources"]
    assert len(resources) >= 1
    news_r = next(r for r in resources if r.get("type") == "news" and r.get("url") == "https://n.com/1")
    assert news_r is not None
    assert news_r.get("tool_name") == "get_news"
    assert "ticker" in (news_r.get("tool_input") or "")
    assert "News 1" in (news_r.get("tool_output_preview") or "")
