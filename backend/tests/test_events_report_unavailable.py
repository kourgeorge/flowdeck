"""The analysis events report must say "unavailable", never "no active events", when nothing was checked.

T-101 fixed this only in the chat tool; fetch_events_report (used to fill events_report
and by the analysts' get_events) still rendered an unavailable payload as a quiet ticker.
"""

from __future__ import annotations

from unittest.mock import patch

from ai_engine.agent.tools import events as chat_events
from ai_engine.tradingagents.agents.utils import events_tools

_UNAVAILABLE = {
    "ticker": "AAPL",
    "available": False,
    "event_score": None,
    "event_count": 0,
    "dominant_events": [],
    "events": [],
    "error": "Price history could not be loaded: TimeoutError: timed out",
}

_QUIET = {
    "ticker": "AAPL",
    "available": True,
    "event_score": 0.0,
    "event_count": 0,
    "dominant_events": [],
    "events": [],
}

_EXPECTED_UNAVAILABLE = (
    "Events unavailable for AAPL: Price history could not be loaded: TimeoutError: timed out. "
    "No event score was computed; do not read this as a quiet ticker."
)


def _analysis_report(payload):
    with patch.object(events_tools, "require_info_service"), patch.object(
        events_tools, "get_events_via_service", return_value=dict(payload)
    ):
        return events_tools.fetch_events_report("aapl")


def _chat_output(payload):
    class _Summary:
        def model_dump(self, mode="json"):
            return dict(payload)

    with patch("data_layer.get_data_gateway", return_value=object()), patch(
        "ai_engine.processing.get_ticker_event_summary", return_value=_Summary()
    ):
        return chat_events._fetch_events("AAPL")


def test_analysis_report_says_unavailable_not_quiet():
    text = _analysis_report(_UNAVAILABLE)
    assert "unavailable" in text.lower()
    assert "TimeoutError" in text
    assert "No active events" not in text


def test_analysis_report_unavailable_when_only_score_missing():
    payload = {**_UNAVAILABLE}
    payload.pop("available")
    text = _analysis_report(payload)
    assert "unavailable" in text.lower()
    assert "No active events" not in text


def test_analysis_report_quiet_ticker_keeps_no_active_events():
    text = _analysis_report(_QUIET)
    assert "No active events were detected for AAPL." in text
    assert "unavailable" not in text.lower()


def test_chat_tool_output_unchanged_for_unavailable():
    assert _chat_output(_UNAVAILABLE) == _EXPECTED_UNAVAILABLE


def test_chat_tool_output_unchanged_for_quiet():
    assert _chat_output(_QUIET) == (
        "# Events for AAPL\n"
        "Event score: 0\n"
        "Event count: 0\n"
        "Dominant events: none\n"
        "\n"
        "No active events were detected for AAPL."
    )
