"""
Tests for get_dcf_inputs, the Valuation Analyst's raw DCF-input tool.

It used to pass a 7e14 "share count" (a dollar figure misread as shares)
straight through, and labelled a one-year revenue growth number as
"historical_fcf_cagr", so the analyst's "state limitations" note never fired.
"""

import json

from ai_engine.tradingagents.agents.utils import valuation_tools as vt


def _statements(kind, report_key, reports):
    return {"statements": {kind: {"data": {report_key: reports}}}}


def _install_fake_service(monkeypatch, shares, cashflow_years, revenues, balance_sheet=None, beta=None):
    """revenues and cashflow_years are newest first.

    The fake fundamentals use the real /api/data/fundamentals shape, which nests
    the fields under "fundamentals" (backend/data_layer/market.py).
    """
    income = [
        {"fiscalDateEnding": f"{2025 - i}-12-31", "totalRevenue": str(r)}
        for i, r in enumerate(revenues)
    ]
    cashflow = [
        {
            "fiscalDateEnding": f"{2025 - i}-12-31",
            "operatingCashflow": str(op),
            "capitalExpenditures": str(cx),
        }
        for i, (op, cx) in enumerate(cashflow_years)
    ]

    def fake_statements(ticker, statement_type, freq):
        if statement_type == "cashflow" and freq == "annual":
            return _statements("cashflow", "annualReports", cashflow)
        if statement_type == "income_statement":
            return _statements("income_statement", "annualReports", income)
        if statement_type == "balance_sheet" and balance_sheet is not None:
            return _statements("balance_sheet", "quarterlyReports", balance_sheet)
        return None

    fundamentals = {} if shares is None else {"SharesOutstanding": shares}
    if beta is not None:
        fundamentals["Beta"] = beta
    payload = {"ticker": "TEST", "date": "2026-01-02", "fundamentals": fundamentals}
    monkeypatch.setattr(vt, "require_info_service", lambda: None)
    monkeypatch.setattr(vt, "get_fundamentals_via_service", lambda t: json.dumps(payload))
    monkeypatch.setattr(vt, "get_financial_statements", fake_statements)
    _install_rates(monkeypatch)


def _install_rates(monkeypatch, rf=(0.04, None), mrp=(0.05, "derived_from_vix")):
    monkeypatch.setattr(vt, "_get_risk_free_rate_with_source", lambda: rf)
    monkeypatch.setattr(vt, "_get_market_risk_premium_with_source", lambda: mrp)


def _run(ticker="TEST"):
    return json.loads(vt.get_dcf_inputs.invoke({"ticker": ticker}))


def test_implausible_share_count_is_refused(monkeypatch):
    _install_fake_service(monkeypatch, "7.0E14", [(50, 10)], [120, 100])
    result = _run()
    assert result["dcf_inputs"]["shares_outstanding"] is None
    assert result["data_sources"]["shares_outstanding"] == ["NOT_AVAILABLE"]
    assert "7" in result["data_sources"]["shares_outstanding_note"]


def test_missing_share_count_is_refused(monkeypatch):
    _install_fake_service(monkeypatch, None, [(50, 10)], [120, 100])
    result = _run()
    assert result["dcf_inputs"]["shares_outstanding"] is None
    assert result["data_sources"]["shares_outstanding_note"]


def test_valid_share_count_passes(monkeypatch):
    _install_fake_service(monkeypatch, "15000000000", [(50, 10)], [120, 100])
    result = _run()
    assert result["dcf_inputs"]["shares_outstanding"] == 15_000_000_000
    assert result["data_sources"]["shares_outstanding"] == ["fundamentals_SharesOutstanding"]
    assert result["data_sources"]["shares_outstanding_note"] is None


def test_top_level_share_count_is_ignored(monkeypatch):
    # The service never returns a flat shape; a stray top-level key must not be
    # mistaken for the real nested value.
    monkeypatch.setattr(vt, "require_info_service", lambda: None)
    monkeypatch.setattr(
        vt,
        "get_fundamentals_via_service",
        lambda t: json.dumps({"ticker": "TEST", "SharesOutstanding": "15000000000", "fundamentals": {}}),
    )
    monkeypatch.setattr(vt, "get_financial_statements", lambda *a, **k: None)
    result = _run()
    assert result["dcf_inputs"]["shares_outstanding"] is None


def test_nested_beta_drives_wacc_with_live_rates(monkeypatch):
    _install_fake_service(monkeypatch, "1000000", [(50, 10)], [120, 100], beta="1.2")
    result = _run()
    # 4.0% live risk-free + 1.2 * 5.0% live premium; the old hard-coded
    # 4.5% / 7.5% would give 13.5%.
    assert abs(result["dcf_inputs"]["wacc"] - (0.04 + 1.2 * 0.05)) < 1e-9
    sources = result["data_sources"]
    assert sources["risk_free_rate_source"] == "FRED"
    assert sources["market_risk_premium_source"] == "derived_from_vix"
    assert sources["wacc"] != ["beta_based_calculation"]
    assert "risk_free_rate: FRED" in sources["wacc"]
    assert "market_risk_premium: derived_from_vix" in sources["wacc"]
    assert "warnings" not in result


def test_assumed_rates_are_flagged(monkeypatch):
    _install_fake_service(monkeypatch, "1000000", [(50, 10)], [120, 100], beta="1.0")
    _install_rates(
        monkeypatch,
        rf=(vt._ASSUMED_RISK_FREE_RATE, vt._ASSUMED_RISK_FREE_RATE_SOURCE),
        mrp=(vt._ASSUMED_MARKET_RISK_PREMIUM, "assumed"),
    )
    result = _run()
    expected = vt._ASSUMED_RISK_FREE_RATE + vt._ASSUMED_MARKET_RISK_PREMIUM
    assert abs(result["dcf_inputs"]["wacc"] - expected) < 1e-9
    sources = result["data_sources"]
    assert sources["risk_free_rate_source"] == vt._ASSUMED_RISK_FREE_RATE_SOURCE
    assert sources["market_risk_premium_source"] == "assumed"
    assert sources["wacc"] != ["beta_based_calculation"]
    warnings = result["warnings"]
    assert len(warnings) == 2
    assert all("not market data" in w for w in warnings)
    assert any("Risk-free rate" in w for w in warnings)
    assert any("Market risk premium" in w for w in warnings)


def test_service_historical_premium_is_flagged(monkeypatch):
    _install_fake_service(monkeypatch, "1000000", [(50, 10)], [120, 100], beta="1.0")
    _install_rates(monkeypatch, mrp=(0.055, "historical_average_assumption"))
    result = _run()
    assert result["data_sources"]["market_risk_premium_source"] == "historical_average_assumption"
    assert len(result["warnings"]) == 1
    assert "Market risk premium" in result["warnings"][0]


def test_balance_sheet_share_count_fallback(monkeypatch):
    _install_fake_service(
        monkeypatch, None, [(50, 10)], [120, 100],
        balance_sheet=[{"fiscalDateEnding": "2025-12-31", "shareIssued": "2000000000"}],
    )
    result = _run()
    assert result["dcf_inputs"]["shares_outstanding"] == 2_000_000_000
    assert result["data_sources"]["shares_outstanding"] == [
        "balance_sheet_shareIssued_or_ordinarySharesNumber"
    ]
    assert result["data_sources"]["shares_outstanding_note"] is None


def test_implausible_balance_sheet_share_count_is_refused(monkeypatch):
    _install_fake_service(
        monkeypatch, None, [(50, 10)], [120, 100],
        balance_sheet=[{"fiscalDateEnding": "2025-12-31", "ordinarySharesNumber": "7.0E14"}],
    )
    result = _run()
    assert result["dcf_inputs"]["shares_outstanding"] is None
    assert result["data_sources"]["shares_outstanding"] == ["NOT_AVAILABLE"]


def test_one_year_revenue_growth_is_labelled_fallback(monkeypatch):
    _install_fake_service(monkeypatch, "1000000", [(50, 10)], [120, 100])
    result = _run()
    assert abs(result["dcf_inputs"]["fcf_growth_rate"] - 0.2) < 1e-9
    sources = result["data_sources"]["fcf_growth_rate"]
    assert "historical_fcf_cagr" not in sources
    assert sources == ["revenue_growth", "FALLBACK_ESTIMATE"]


def test_revenue_cagr_is_labelled_fallback(monkeypatch):
    _install_fake_service(monkeypatch, "1000000", [(50, 10)], [133.1, 121, 110, 100])
    result = _run()
    assert abs(result["dcf_inputs"]["fcf_growth_rate"] - 0.1) < 1e-6
    assert result["data_sources"]["fcf_growth_rate"] == ["revenue_cagr_3y", "FALLBACK_ESTIMATE"]


def test_real_fcf_cagr_is_labelled_historical(monkeypatch):
    # FCF 100 -> 110 -> 121 (oldest to newest): 10% CAGR.
    _install_fake_service(
        monkeypatch, "1000000", [(131, 10), (120, 10), (110, 10)], [500, 100]
    )
    result = _run()
    assert abs(result["dcf_inputs"]["fcf_growth_rate"] - 0.1) < 1e-9
    assert result["data_sources"]["fcf_growth_rate"] == ["historical_fcf_cagr"]
