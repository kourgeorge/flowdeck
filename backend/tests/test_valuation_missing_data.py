"""
Refuse-to-guess tests for calculate_multi_method_valuation (T-58).

Covers three gaps: a missing EBITDA being defaulted to $1 and then getting the
largest method weight, missing statements producing an invented FCF / EBITDA /
14x multiple labelled "reported", and the analyst target price being used as
the current price when the quote call fails.
"""
import json

import pytest

from ai_engine.tradingagents.agents.utils import valuation_tools as vt


@pytest.fixture(autouse=True)
def _fixed_market_rates(monkeypatch):
    monkeypatch.setattr(vt, "_fetch_market_rates", lambda: None)


def _statements(fcf=None, operating_cf=None, capex=None):
    cashflow = {}
    if fcf is not None:
        cashflow["freeCashFlow"] = fcf
    if operating_cf is not None:
        cashflow["operatingCashFlow"] = operating_cf
    if capex is not None:
        cashflow["capitalExpenditure"] = capex
    cashflow["fiscalDateEnding"] = "2025-12-31"
    return {"statements": {
        "balance_sheet": {"data": {"annualReports": [
            {"fiscalDateEnding": "2025-12-31", "totalDebt": 1_000_000_000,
             "cashAndCashEquivalents": 500_000_000},
        ], "quarterlyReports": []}},
        "cashflow": {"data": {"annualReports": [cashflow], "quarterlyReports": []}},
        "income_statement": {"data": {"annualReports": [
            {"fiscalDateEnding": "2025-12-31", "totalRevenue": 10_000_000_000,
             "netIncome": 200_000_000},
        ]}},
    }}


def _all_assumptions(result):
    return "\n".join(result["valuation_key_assumptions"])


def test_missing_ebitda_gets_no_weight():
    # The scout's repro: negative FCF, EPS 2 / P/E 20, no EBITDA.
    result = vt.calculate_multi_method_valuation_data(
        ticker="NOEB",
        current_price=40.0,
        fundamentals={
            "SharesOutstanding": 100_000_000,
            "EPS": 2.0,
            "TrailingPE": 20.0,
            "RevenueTTM": 10_000_000_000,
        },
        statements_payload=_statements(fcf=-50_000_000, operating_cf=100_000_000, capex=-150_000_000),
    )

    assert result["valuation_available"] is True
    weights = result["valuation_summary"]["method_weights"]
    assert weights["EV/EBITDA"] == 0.0
    assert max(weights, key=weights.get) != "EV/EBITDA"
    assert result["ev_ebitda"] == {"bear": None, "base": None, "bull": None}
    assert result["inputs"]["ebitda"] is None
    assert "EV/EBITDA" not in [row["method"] for row in result["valuation_summary"]["rows"]]
    assert "EV/EBITDA excluded" in _all_assumptions(result)


def test_no_statements_and_no_profit_margin_refuses():
    result = vt.calculate_multi_method_valuation_data(
        ticker="NOSTM",
        current_price=40.0,
        fundamentals={"SharesOutstanding": 100_000_000, "EPS": 2.0, "RevenueTTM": 10_000_000_000},
        statements_payload={},
    )

    assert result["valuation_available"] is False
    assert "ProfitMargin" in result["valuation_unavailable_reason"]
    assert result["fair_value_base"] is None


def test_no_statements_with_real_profit_margin_flags_estimates():
    result = vt.calculate_multi_method_valuation_data(
        ticker="MARGIN",
        current_price=40.0,
        fundamentals={
            "SharesOutstanding": 100_000_000,
            "EPS": 2.0,
            "TrailingPE": 20.0,
            "RevenueTTM": 10_000_000_000,
            "ProfitMargin": 0.10,
            "EBITDA": 1_500_000_000,
        },
        statements_payload={},
    )

    assert result["valuation_available"] is True
    text = _all_assumptions(result)
    assert "ESTIMATED FCF" in text
    assert "FCF estimated" in text
    assert "FCF reported" not in text
    assert "default 14.0x" in text
    assert result["inputs"]["fcf_estimated"] is True
    assert result["inputs"]["ev_ebitda_multiple_defaulted"] is True
    assert result["inputs"]["current_fcf"] == pytest.approx(10_000_000_000 * 0.10 * 0.9)
    # Data-quality component reflects the estimates (all-actual data scores 2).
    assert result["valuation_score_breakdown"]["data_quality"] < 2.0


def test_quote_down_refuses_instead_of_using_analyst_target(monkeypatch):
    monkeypatch.setattr(vt, "require_info_service", lambda: None)
    monkeypatch.setattr(vt, "get_quote", lambda ticker: None)
    monkeypatch.setattr(vt, "get_fundamentals_via_service", lambda ticker: {
        "fundamentals": {
            "SharesOutstanding": 100_000_000,
            "EPS": 2.0,
            "AnalystTargetPrice": 55.0,
            "ProfitMargin": 0.10,
            "RevenueTTM": 10_000_000_000,
        }
    })
    monkeypatch.setattr(vt, "get_financial_statements", lambda *a, **k: _statements(fcf=500_000_000))
    monkeypatch.setattr(vt, "get_analyst_recommendations", lambda ticker: {})

    out = json.loads(vt.calculate_multi_method_valuation.invoke({"ticker": "QDOWN"}))

    assert out["error"] == "Unable to determine current price for valuation"
    assert out.get("current_price") != 55.0
    assert "fair_value_base" not in out


def test_missing_ebitda_leaves_out_exit_multiple_sensitivity():
    # T-61: EV/EBITDA had 0% weight but the sensitivity table still showed the
    # default 14x exit multiple with a flat "$50.11 to $50.11" range.
    result = vt.calculate_multi_method_valuation_data(
        ticker="NOEB",
        current_price=40.0,
        fundamentals={
            "SharesOutstanding": 100_000_000,
            "EPS": 2.0,
            "TrailingPE": 20.0,
            "RevenueTTM": 10_000_000_000,
        },
        statements_payload=_statements(fcf=-50_000_000, operating_cf=100_000_000, capex=-150_000_000),
    )

    sensitivity = result["valuation_sensitivity"]
    assert sensitivity["exit_multiple"] is None
    for key in ("fcf_growth_rate", "wacc", "terminal_growth"):
        assert sensitivity[key] is not None


def test_real_ebitda_and_ev_multiple_keep_exit_multiple_row():
    result = vt.calculate_multi_method_valuation_data(
        ticker="REALEB",
        current_price=40.0,
        fundamentals={
            "SharesOutstanding": 100_000_000,
            "EPS": 2.0,
            "TrailingPE": 20.0,
            "RevenueTTM": 10_000_000_000,
            "EBITDA": 1_500_000_000,
            "EVToEBITDA": 10.0,
        },
        statements_payload=_statements(fcf=500_000_000),
    )

    row = result["valuation_sensitivity"]["exit_multiple"]
    assert row is not None
    assert row["parameter_name"] == "Exit EV/EBITDA Multiple"
    assert row["base_value"] != 14.0
    assert row["fair_value_high"] > row["fair_value_low"]


def test_default_ev_multiple_is_labelled_in_exit_multiple_row():
    result = vt.calculate_multi_method_valuation_data(
        ticker="DEFMUL",
        current_price=40.0,
        fundamentals={
            "SharesOutstanding": 100_000_000,
            "EPS": 2.0,
            "TrailingPE": 20.0,
            "RevenueTTM": 10_000_000_000,
            "EBITDA": 1_500_000_000,
        },
        statements_payload=_statements(fcf=500_000_000),
    )

    assert result["inputs"]["ev_ebitda_multiple_defaulted"] is True
    row = result["valuation_sensitivity"]["exit_multiple"]
    assert row is not None
    assert "default 14.0x assumption" in row["parameter_name"]


def test_negative_eps_without_forward_pe_drops_pe_comps():
    # T-62, the scout's repro: $40 stock, EPS -1.5, no forward P/E, no EBITDA,
    # negative FCF. P/E used to run on a $0.01 EPS and a 20x default, giving
    # values around $0.22 at a 19% weight that dragged the blend down.
    result = vt.calculate_multi_method_valuation_data(
        ticker="LOSS",
        current_price=40.0,
        fundamentals={
            "SharesOutstanding": 100_000_000,
            "EPS": -1.5,
            "RevenueTTM": 10_000_000_000,
        },
        statements_payload=_statements(fcf=-50_000_000, operating_cf=100_000_000, capex=-150_000_000),
    )

    assert result["valuation_available"] is True
    weights = result["valuation_summary"]["method_weights"]
    assert weights["P/E Comps"] == 0.0
    assert weights["EV/EBITDA"] == 0.0
    assert weights["DCF"] == pytest.approx(1.0)
    assert result["pe_comps"] == {"bear": None, "base": None, "bull": None}
    assert [row["method"] for row in result["valuation_summary"]["rows"]] == ["DCF"]
    assert result["fair_value_base"] == pytest.approx(result["dcf"]["base"])
    assert result["inputs"]["eps"] == -1.5
    text = _all_assumptions(result)
    assert "P/E Comps excluded" in text
    assert "left out" in text
    assert "Forward EPS used for P/E comps: 0.01" not in text
    assert "P/E Comps: n/a" in result["method_scenarios_text"]


def test_positive_eps_keeps_pe_comps():
    result = vt.calculate_multi_method_valuation_data(
        ticker="PROFIT",
        current_price=40.0,
        fundamentals={
            "SharesOutstanding": 100_000_000,
            "EPS": 2.0,
            "TrailingPE": 20.0,
            "RevenueTTM": 10_000_000_000,
        },
        statements_payload=_statements(fcf=500_000_000),
    )

    assert result["valuation_summary"]["method_weights"]["P/E Comps"] > 0.0
    assert all(v is not None and v > 1.0 for v in result["pe_comps"].values())
    assert "P/E Comps" in [row["method"] for row in result["valuation_summary"]["rows"]]
    assert "P/E Comps excluded" not in _all_assumptions(result)
    assert result["inputs"]["pe_multiple_defaulted"] is False


def test_negative_eps_with_forward_pe_keeps_pe_comps():
    # A loss-maker with a real forward P/E still has usable forward earnings.
    result = vt.calculate_multi_method_valuation_data(
        ticker="TURN",
        current_price=40.0,
        fundamentals={
            "SharesOutstanding": 100_000_000,
            "EPS": -1.5,
            "ForwardPE": 25.0,
            "RevenueTTM": 10_000_000_000,
        },
        statements_payload=_statements(fcf=500_000_000),
    )

    assert result["valuation_summary"]["method_weights"]["P/E Comps"] > 0.0
    assert result["pe_comps"]["base"] == pytest.approx(40.0)
    assert "P/E Comps excluded" not in _all_assumptions(result)


def test_no_pe_no_ebitda_and_floored_dcf_refuses():
    result = vt.calculate_multi_method_valuation_data(
        ticker="BROKE",
        current_price=40.0,
        fundamentals={
            "SharesOutstanding": 100_000_000,
            "EPS": -1.5,
            "RevenueTTM": 10_000_000,
        },
        statements_payload=_statements(fcf=-50_000_000, operating_cf=-40_000_000, capex=-10_000_000),
    )

    assert result["valuation_available"] is False
    assert "EPS" in result["valuation_unavailable_reason"]
    assert result["fair_value_base"] is None
