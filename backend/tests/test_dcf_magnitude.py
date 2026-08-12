"""
Regression tests that pin the DCF calculation to a known-good magnitude.

A $6.32/share result for Amazon-like inputs (correct FCF=$60B, shares=10.8B)
is the specific regression this file guards against.  See docs/VALUATION_AUDIT.md
for the full root-cause analysis.
"""
import pytest
from ai_engine.tradingagents.agents.utils.valuation_tools import (
    calculate_multi_method_valuation_data,
)


AMAZON_LIKE_INPUTS = {
    "fundamentals": {
        "MarketCapitalization": 2_200_000_000_000,
        "EnterpriseValue": 2_180_000_000_000,
        "SharesOutstanding": 10_800_000_000,   # 10.8B — critical
        "TrailingPE": 45.0,
        "ForwardPE": 38.0,
        "EVToEBITDA": 22.0,
        "EBITDA": 85_000_000_000,
        "EPS": 4.20,
        "Beta": 1.2,
        "QuarterlyRevenueGrowthYOY": 0.10,
        "QuarterlyEarningsGrowthYOY": 0.18,
    },
    "statements": {
        "balance_sheet": {
            "data": {
                "annualReports": [
                    {
                        "fiscalDateEnding": "2024-12-31",
                        "totalDebt": 58_000_000_000,
                        "cashAndCashEquivalents": 128_000_000_000,
                    }
                ],
                "quarterlyReports": [],
            }
        },
        "cashflow": {
            "data": {
                "annualReports": [
                    {
                        "fiscalDateEnding": "2024-12-31",
                        "freeCashFlow": 60_000_000_000,
                        "operatingCashFlow": 108_000_000_000,
                        "capitalExpenditure": -48_000_000_000,
                    }
                ],
                "quarterlyReports": [],
            }
        },
        "income_statement": {
            "data": {
                "annualReports": [
                    {
                        "fiscalDateEnding": "2024-12-31",
                        "totalRevenue": 620_000_000_000,
                        "netIncome": 30_000_000_000,
                        "interestExpense": 2_500_000_000,
                        "taxProvision": 8_000_000_000,
                        "pretaxIncome": 38_000_000_000,
                    }
                ],
                "quarterlyReports": [],
            }
        },
    },
}


def test_dcf_base_within_institutional_range():
    """DCF base must fall in $80–$400/share for Amazon-like inputs, not ~$6."""
    result = calculate_multi_method_valuation_data(
        ticker="AMZN",
        current_price=205.0,
        fundamentals=AMAZON_LIKE_INPUTS["fundamentals"],
        statements_payload={"statements": AMAZON_LIKE_INPUTS["statements"]},
        analyst_recommendations={"price_targets": {"low": 180.0, "average": 220.0, "high": 260.0}},
    )
    dcf_base = result["dcf"]["base"]
    assert dcf_base >= 80.0, (
        f"DCF base ${dcf_base:.2f} is implausibly low — likely shares or FCF unit error"
    )
    assert dcf_base <= 400.0, (
        f"DCF base ${dcf_base:.2f} is implausibly high"
    )


def test_dcf_shares_denominator_sanity():
    """
    When SharesOutstanding is absent and the balance-sheet fallback would
    resolve to a value > 50B (balance-sheet dollar misread), the function
    must refuse to compute and return valuation_available=False.
    """
    inputs = {k: v for k, v in AMAZON_LIKE_INPUTS["fundamentals"].items()}
    inputs.pop("SharesOutstanding", None)  # Force fallback path

    result = calculate_multi_method_valuation_data(
        ticker="AMZN",
        current_price=205.0,
        fundamentals=inputs,
        statements_payload={"statements": AMAZON_LIKE_INPUTS["statements"]},
        analyst_recommendations={},
    )
    assert result["valuation_available"] is False, (
        "Expected valuation_available=False when SharesOutstanding is absent "
        "and balance-sheet fallback cannot supply a reliable share count"
    )
    assert result["dcf"]["base"] is None, (
        "DCF base must be None when valuation is unavailable"
    )


def test_dcf_not_degraded_by_missing_free_cash_flow_key():
    """
    When 'freeCashFlow' is absent from the cashflow report,
    the operating-CF-minus-capex fallback must fire and
    still produce a plausible result.
    """
    statements = {k: v for k, v in AMAZON_LIKE_INPUTS["statements"].items()}
    # Remove freeCashFlow from annual reports
    patched_cashflow = [
        {k: v for k, v in r.items() if k != "freeCashFlow"}
        for r in statements["cashflow"]["data"]["annualReports"]
    ]
    statements["cashflow"]["data"]["annualReports"] = patched_cashflow

    result = calculate_multi_method_valuation_data(
        ticker="AMZN",
        current_price=205.0,
        fundamentals=AMAZON_LIKE_INPUTS["fundamentals"],
        statements_payload={"statements": statements},
        analyst_recommendations={},
    )
    dcf_base = result["dcf"]["base"]
    assert dcf_base >= 80.0, (
        f"DCF base ${dcf_base:.2f} dropped below threshold when freeCashFlow key was absent"
    )


def test_dcf_returns_unavailable_when_shares_cannot_resolve():
    """
    When shares_outstanding cannot be reliably resolved (None, <= 0, or > 50B),
    the function must return valuation_available=False with None DCF values
    and a reason string mentioning 'shares'.
    """
    # Provide fundamentals with no SharesOutstanding and no balance-sheet fallback
    minimal_fundamentals = {
        "MarketCapitalization": 2_200_000_000_000,
        "TrailingPE": 45.0,
        "EPS": 4.20,
    }
    minimal_statements = {
        "balance_sheet": {
            "data": {"annualReports": [], "quarterlyReports": []}
        },
        "cashflow": {
            "data": {
                "annualReports": [
                    {
                        "fiscalDateEnding": "2024-12-31",
                        "freeCashFlow": 60_000_000_000,
                        "operatingCashFlow": 108_000_000_000,
                        "capitalExpenditure": -48_000_000_000,
                    }
                ],
                "quarterlyReports": [],
            }
        },
        "income_statement": {
            "data": {
                "annualReports": [
                    {
                        "fiscalDateEnding": "2024-12-31",
                        "totalRevenue": 620_000_000_000,
                        "netIncome": 30_000_000_000,
                    }
                ],
                "quarterlyReports": [],
            }
        },
    }

    result = calculate_multi_method_valuation_data(
        ticker="TEST",
        current_price=100.0,
        fundamentals=minimal_fundamentals,
        statements_payload={"statements": minimal_statements},
    )

    assert result["valuation_available"] is False, (
        "Expected valuation_available=False when shares_outstanding cannot be resolved"
    )
    assert result["dcf"]["base"] is None, "DCF base must be None when valuation is unavailable"
    assert "shares" in result["valuation_unavailable_reason"].lower(), (
        f"Expected 'shares' in reason, got: {result['valuation_unavailable_reason']!r}"
    )
