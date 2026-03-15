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
            "score": 7,
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


def test_extract_resources_node():
    """Extract-resources node reads state with AIMessage + ToolMessages and returns report_resources."""
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
