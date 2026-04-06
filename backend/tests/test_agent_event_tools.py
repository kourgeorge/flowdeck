from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

repo_root = Path(__file__).resolve().parents[2]
backend_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(backend_root))

from ai_engine.agent.lc_tools import ALL_LC_TOOLS
from ai_engine.agent.tools import ALL_TOOLS
from ai_engine.agent.tools.events import _format_events_payload
from ai_engine.tradingagents.agents.utils.events_tools import (
    fetch_events_report,
    _format_events_payload as _format_tradingagent_events_payload,
)
from ai_engine.tradingagents.agents.utils.resource_extraction import extract_resources_from_tool


class TestAgentEventToolRegistration(unittest.TestCase):
    def test_events_tool_is_registered_for_both_chat_agent_paths(self) -> None:
        base_tool_names = [tool.name for tool in ALL_TOOLS]
        lc_tool_names = [tool.name for tool in ALL_LC_TOOLS]

        self.assertIn("get_events", base_tool_names)
        self.assertIn("get_events", lc_tool_names)
        self.assertLess(base_tool_names.index("get_events"), 15)
        self.assertLess(lc_tool_names.index("get_events"), 15)


class TestAgentEventToolFormatting(unittest.TestCase):
    def test_formatting_includes_summary_and_event_details(self) -> None:
        formatted = _format_events_payload(
            "AAPL",
            {
                "event_score": 6.5,
                "event_count": 2,
                "dominant_events": ["new_52w_high", "volume_spike"],
                "events": [
                    {
                        "event_type": "new_52w_high",
                        "domain": "price_technical",
                        "strength": "high",
                        "detected_on": "2026-03-19",
                        "description": "The stock reached or exceeded its highest price level of the past 52 weeks.",
                        "metric_value": 225.12,
                        "threshold_value": 220.0,
                        "metadata": {"close": 225.12, "prior_52w_high": 220.0},
                    },
                    {
                        "event_type": "volume_spike",
                        "domain": "price_technical",
                        "strength": "medium",
                        "detected_on": "2026-03-19",
                        "description": "Trading volume rose materially above the recent average.",
                        "metric_value": 1850000,
                        "threshold_value": 1200000,
                        "metadata": {"volume": 1850000, "avg_volume_20d": 1200000},
                    },
                ],
            },
        )

        self.assertIn("# Events for AAPL", formatted)
        self.assertIn("Event score: 6.5", formatted)
        self.assertIn("Dominant events: new_52w_high, volume_spike", formatted)
        self.assertIn("new_52w_high | domain=price_technical | strength=high | detected_on=2026-03-19", formatted)
        self.assertIn("Trigger: metric=225.12, threshold=220", formatted)
        self.assertIn("Metadata: close=225.12, prior_52w_high=220", formatted)

    def test_tradingagents_formatter_matches_expected_sections(self) -> None:
        formatted = _format_tradingagent_events_payload(
            "MSFT",
            {
                "event_score": 4.25,
                "event_count": 1,
                "dominant_events": ["earnings_upcoming"],
                "events": [
                    {
                        "event_type": "earnings_upcoming",
                        "domain": "fundamental",
                        "strength": "medium",
                        "detected_on": "2026-03-20",
                        "description": "Quarterly earnings are approaching.",
                        "metadata": {"days_until": 5},
                    }
                ],
            },
        )

        self.assertIn("# Events for MSFT", formatted)
        self.assertIn("Event score: 4.25", formatted)
        self.assertIn("Dominant events: earnings_upcoming", formatted)
        self.assertIn("earnings_upcoming | domain=fundamental | strength=medium | detected_on=2026-03-20", formatted)
        self.assertIn("Metadata: days_until=5", formatted)


class TestTradingAgentsEventTool(unittest.TestCase):
    def test_fetch_events_report_forwards_lookback_days_and_formats_output(self) -> None:
        with patch(
            "ai_engine.tradingagents.agents.utils.events_tools.require_info_service"
        ), patch(
            "ai_engine.tradingagents.agents.utils.events_tools.get_events_via_service",
            return_value={
                "event_score": 3.0,
                "event_count": 1,
                "dominant_events": ["volume_spike"],
                "events": [
                    {
                        "event_type": "volume_spike",
                        "domain": "price_technical",
                        "strength": "high",
                        "detected_on": "2026-03-19",
                        "description": "Trading volume rose materially above the recent average.",
                    }
                ],
            },
        ) as mock_get_events:
            formatted = fetch_events_report("nvda", lookback_days=21)

        mock_get_events.assert_called_once_with("NVDA", lookback_days=21)
        self.assertIn("# Events for NVDA", formatted)
        self.assertIn("Dominant events: volume_spike", formatted)

    def test_get_events_resource_is_captured_as_deterministic_events(self) -> None:
        resources = extract_resources_from_tool(
            "get_events",
            {"ticker": "AAPL"},
            "ignored",
        )

        self.assertEqual(
            resources,
            [
                {
                    "type": "deterministic_events",
                    "ticker": "AAPL",
                    "description": "Deterministic event summary for AAPL",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
