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


def _install_fake_service(monkeypatch, shares, cashflow_years, revenues):
    """revenues and cashflow_years are newest first."""
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
        return None

    fundamentals = {} if shares is None else {"SharesOutstanding": shares}
    monkeypatch.setattr(vt, "require_info_service", lambda: None)
    monkeypatch.setattr(vt, "get_fundamentals_via_service", lambda t: json.dumps(fundamentals))
    monkeypatch.setattr(vt, "get_financial_statements", fake_statements)


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
    assert result["data_sources"]["shares_outstanding_note"] is None


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
