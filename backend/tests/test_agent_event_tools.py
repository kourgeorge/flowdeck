from __future__ import annotations

from pathlib import Path
import sys
import unittest

repo_root = Path(__file__).resolve().parents[2]
backend_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(backend_root))

from ai_engine.agent.lc_tools import ALL_LC_TOOLS
from ai_engine.agent.tools import ALL_TOOLS
from ai_engine.agent.tools.events import _format_events_payload


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


if __name__ == "__main__":
    unittest.main()
