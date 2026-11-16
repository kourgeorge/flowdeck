"""A watchlist ticker without a platform report must not be shown as a HOLD.

report_payload.py lists every ticker with recommendation=None until a report
exists; the chart, stage 6 data and the heuristic evidence extractor used to
turn that None into HOLD.
"""

import sys
from pathlib import Path

_WC = Path(__file__).resolve().parents[2] / "ai_engine" / "watchlist_consulting"
if str(_WC) not in sys.path:
    sys.path.insert(0, str(_WC))

from pipeline_schemas import NO_REPORT_LABEL  # noqa: E402
from stage2_evidence_extractor import _extract_one_heuristic  # noqa: E402
from stage6_data_builder import run_data_builder  # noqa: E402
from vega_specs import recommendation_bar_spec  # noqa: E402


def _counts(spec):
    return {d["recommendation"]: d["count"] for d in spec["data"]["values"]}


def test_bar_spec_does_not_count_missing_recommendation_as_hold():
    spec = recommendation_bar_spec([
        {"ticker": "AAA", "recommendation": None},
        {"ticker": "BBB", "recommendation": "BUY"},
        {"ticker": "CCC", "recommendation": "weird"},
    ])
    counts = _counts(spec)
    assert "HOLD" not in counts
    assert counts == {"BUY": 1, NO_REPORT_LABEL: 2}


def test_bar_spec_real_recommendations_unchanged():
    spec = recommendation_bar_spec([
        {"ticker": "A", "recommendation": "BUY"},
        {"ticker": "B", "recommendation": "sell"},
        {"ticker": "C", "recommendation": "HOLD"},
        {"ticker": "D", "recommendation": "HOLD"},
    ])
    assert _counts(spec) == {"BUY": 1, "SELL": 1, "HOLD": 2}


def test_heuristic_extractor_gives_no_hold_for_missing_recommendation():
    packet = _extract_one_heuristic({"ticker": "AAA", "recommendation": None})
    assert packet.action_candidate is None
    assert any("no platform report" in b.lower() for b in packet.thesis_bullets)


def test_heuristic_extractor_real_recommendations_unchanged():
    for rec in ("BUY", "SELL", "HOLD"):
        packet = _extract_one_heuristic({"ticker": "AAA", "recommendation": rec})
        assert packet.action_candidate is not None
        assert packet.action_candidate.action == rec.lower()
        assert packet.action_candidate.rationale == f"Recommendation: {rec}"
        assert not any("no platform report" in b.lower() for b in packet.thesis_bullets)


def test_stage6_recommendation_dist_matches_chart():
    entries = [
        {"ticker": "AAA", "recommendation": None},
        {"ticker": "BBB", "recommendation": "BUY"},
    ]
    figure_data, _ = run_data_builder([], [], {"entries": entries}, fetcher=None)
    dist = {d["recommendation"]: d["count"] for d in figure_data["recommendation_dist"]["values"]}
    assert dist == {"BUY": 1, NO_REPORT_LABEL: 1}
