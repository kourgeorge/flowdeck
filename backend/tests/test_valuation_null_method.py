"""
A valuation method the tool leaves out (EV/EBITDA when EBITDA is missing, see
T-58) is sent as null. These tests make sure null flows through the analyst
schema, the stored report payload and the plain-text formatting without
turning into a $0 fair value.
"""

import json

import pytest
from pydantic import ValidationError

from ai_engine.tradingagents.agents.analysts.valuation_analyst import (
    ValuationAnalysisOutput,
    ValuationMethodScenario,
)
from ai_engine.tradingagents.agents.utils.valuation_tools import (
    calculate_valuation_summary,
    format_method_scenarios_text,
)

NULL_METHOD = {"bear": None, "base": None, "bull": None}


def test_schema_accepts_null_scenario_values():
    scenario = ValuationMethodScenario(bear=None, base=None, bull=None)
    assert scenario.model_dump() == NULL_METHOD


def test_schema_still_requires_the_fields_to_be_present():
    # Null is allowed, but the model must say so explicitly rather than skip it.
    with pytest.raises(ValidationError):
        ValuationMethodScenario()


def test_json_schema_allows_null_and_tells_the_model_not_to_write_zero():
    schema = ValuationAnalysisOutput.model_json_schema()
    base_field = schema["$defs"]["ValuationMethodScenario"]["properties"]["base"]
    assert {"type": "null"} in base_field["anyOf"]
    assert "not 0" in base_field["description"]
    assert "never 0" in schema["properties"]["ev_ebitda"]["description"]


def test_report_payload_with_null_ev_ebitda_builds():
    from services.report_service import _report_row_to_dict

    class Row:
        content = "Valuation report"
        metadata_json = json.dumps({
            "score": 3,
            "fair_value_base": 150.0,
            "dcf": {"bear": 110.0, "base": 150.0, "bull": 190.0},
            "pe_comps": {"bear": 115.0, "base": 155.0, "bull": 195.0},
            "ev_ebitda": NULL_METHOD,
        })

    out = _report_row_to_dict(Row(), "2026-11-16")
    assert out["ev_ebitda"] == NULL_METHOD
    assert out["dcf"]["base"] == 150.0


def test_summary_table_hides_null_method():
    summary = calculate_valuation_summary(
        dcf={"bear": 110.0, "base": 150.0, "bull": 190.0},
        pe_comps={"bear": 115.0, "base": 155.0, "bull": 195.0},
        ev_ebitda=dict(NULL_METHOD),
        method_weights={"DCF": 0.6, "P/E Comps": 0.4, "EV/EBITDA": 0.0},
    )
    assert [row["method"] for row in summary["rows"]] == ["DCF", "P/E Comps"]


def test_formatted_text_shows_na_not_zero():
    text = format_method_scenarios_text(
        {"bear": 110.0, "base": 150.0, "bull": 190.0},
        {"bear": 115.0, "base": 155.0, "bull": 195.0},
        dict(NULL_METHOD),
    )
    ev_line = next(line for line in text.splitlines() if line.startswith("EV/EBITDA"))
    assert "n/a" in ev_line
    assert "0.00" not in ev_line
    assert "$0" not in ev_line
    assert "DCF: bear $110.00, base $150.00, bull $190.00" in text


def test_formatted_text_shows_na_for_a_single_missing_value():
    text = format_method_scenarios_text(
        {"bear": None, "base": 150.0, "bull": 190.0}, None, None,
    )
    assert text.splitlines()[0] == "DCF: bear n/a, base $150.00, bull $190.00"
