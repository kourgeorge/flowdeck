import json
import unittest
from unittest.mock import patch

from ai_engine.tradingagents.agents.analysts.valuation_analyst import (
    ValuationAnalysisOutput,
    ValuationBridge,
    ValuationMethodScenario,
    ValuationSensitivity,
    ValuationSensitivityRange,
    ValuationSummaryTable,
)
from ai_engine.tradingagents.agents.utils.valuation_tools import (
    _is_index_or_etf,
    calculate_multi_method_valuation_data,
    calculate_valuation_summary,
)
from ai_engine.tradingagents.agents.utils.agent_states import AgentState


class TestValuationSummary(unittest.TestCase):
    def test_calculate_valuation_summary_is_deterministic(self):
        summary = calculate_valuation_summary(
            dcf={"bear": 40.0, "base": 50.0, "bull": 70.0},
            pe_comps={"bear": 42.0, "base": 51.0, "bull": 63.0},
            ev_ebitda={"bear": 38.0, "base": 47.0, "bull": 55.0},
        )

        rows = {row["method"]: row for row in summary["rows"]}
        self.assertAlmostEqual(rows["DCF"]["implied_value"], 52.5)
        self.assertAlmostEqual(rows["P/E Comps"]["implied_value"], 51.75)
        self.assertAlmostEqual(rows["EV/EBITDA"]["implied_value"], 46.75)
        self.assertAlmostEqual(summary["weighted_avg"]["bear"], 40.0)
        self.assertAlmostEqual(summary["weighted_avg"]["base"], 49.4)
        self.assertAlmostEqual(summary["weighted_avg"]["bull"], 63.4)
        self.assertAlmostEqual(summary["weighted_avg"]["implied_value"], 50.55)

    def test_structured_output_contains_deterministic_summary(self):
        summary = calculate_valuation_summary(
            dcf={"bear": 40.0, "base": 50.0, "bull": 70.0},
            pe_comps={"bear": 42.0, "base": 51.0, "bull": 63.0},
            ev_ebitda={"bear": 38.0, "base": 47.0, "bull": 55.0},
        )
        result = ValuationAnalysisOutput(
            report="Valuation report body.",
            valuation_score=7,
            fair_value_bear=40.0,
            fair_value_base=49.4,
            fair_value_bull=63.4,
            current_discount_pct=10.0,
            valuation_conviction="medium",
            valuation_key_assumptions=["Revenue growth holds", "Margins expand"],
            dcf=ValuationMethodScenario(bear=40.0, base=50.0, bull=70.0),
            pe_comps=ValuationMethodScenario(bear=42.0, base=51.0, bull=63.0),
            ev_ebitda=ValuationMethodScenario(bear=38.0, base=47.0, bull=55.0),
            valuation_summary=ValuationSummaryTable(**summary),
            valuation_bridge=ValuationBridge(
                current_price=44.46,
                growth_premium=7.54,
                multiple_expansion=4.55,
                risk_discount=7.15,
                fair_value=49.40,
            ),
            valuation_sensitivity=ValuationSensitivity(
                fcf_growth_rate=ValuationSensitivityRange(delta=0.02, low=46.0, high=53.0),
                wacc=ValuationSensitivityRange(delta=0.01, low=45.0, high=54.0),
                terminal_growth=ValuationSensitivityRange(delta=0.005, low=47.0, high=52.0),
                exit_multiple=ValuationSensitivityRange(delta=2.0, low=48.0, high=51.0),
            ),
            key_takeaways=["Base case implies upside."],
        )

        dumped = result.model_dump()

        self.assertEqual(dumped["valuation_conviction"], "medium")
        self.assertEqual(dumped["valuation_key_assumptions"], ["Revenue growth holds", "Margins expand"])
        self.assertEqual(len(dumped["valuation_summary"]["rows"]), 3)
        self.assertAlmostEqual(dumped["valuation_summary"]["weighted_avg"]["implied_value"], 50.55)

    def test_model_dump_uses_state_field_names(self):
        result = ValuationAnalysisOutput(
            report="Report",
            valuation_score=6,
            fair_value_bear=40.0,
            fair_value_base=50.0,
            fair_value_bull=60.0,
            current_discount_pct=12.0,
            valuation_conviction="high",
            valuation_key_assumptions=["WACC 9%", "Terminal growth 3%"],
            dcf=ValuationMethodScenario(bear=40.0, base=50.0, bull=60.0),
            pe_comps=ValuationMethodScenario(bear=42.0, base=52.0, bull=62.0),
            ev_ebitda=ValuationMethodScenario(bear=38.0, base=48.0, bull=58.0),
            valuation_summary=ValuationSummaryTable(**calculate_valuation_summary(
                dcf={"bear": 40.0, "base": 50.0, "bull": 60.0},
                pe_comps={"bear": 42.0, "base": 52.0, "bull": 62.0},
                ev_ebitda={"bear": 38.0, "base": 48.0, "bull": 58.0},
            )),
            valuation_bridge=ValuationBridge(
                current_price=44.00,
                growth_premium=6.00,
                multiple_expansion=5.00,
                risk_discount=5.00,
                fair_value=50.00,
            ),
            valuation_sensitivity=ValuationSensitivity(
                fcf_growth_rate=ValuationSensitivityRange(delta=0.02, low=47.0, high=53.0),
                wacc=ValuationSensitivityRange(delta=0.01, low=46.0, high=54.0),
                terminal_growth=ValuationSensitivityRange(delta=0.005, low=48.0, high=52.0),
                exit_multiple=ValuationSensitivityRange(delta=2.0, low=49.0, high=51.0),
            ),
            key_takeaways=["Fair value above market."],
        )

        dumped = result.model_dump()

        self.assertEqual(dumped["fair_value_base"], 50.0)
        self.assertEqual(dumped["valuation_conviction"], "high")
        self.assertEqual(dumped["valuation_key_assumptions"], ["WACC 9%", "Terminal growth 3%"])
        self.assertEqual(dumped["valuation_bridge"]["fair_value"], 50.0)
        self.assertEqual(dumped["valuation_sensitivity"]["exit_multiple"]["delta"], 2.0)

    def test_agent_state_allows_valuation_metadata_to_persist(self):
        expected_keys = {
            "valuation_summary",
            "valuation_bridge",
            "valuation_sensitivity",
            "dcf",
            "pe_comps",
            "ev_ebitda",
        }

        self.assertTrue(expected_keys.issubset(AgentState.__annotations__))

    def test_structured_output_accepts_tool_assumption_list(self):
        summary = calculate_valuation_summary(
            dcf={"bear": 40.0, "base": 50.0, "bull": 60.0},
            pe_comps={"bear": 42.0, "base": 52.0, "bull": 62.0},
            ev_ebitda={"bear": 38.0, "base": 48.0, "bull": 58.0},
        )
        assumptions = [
            "DCF projection period: 10 years",
            "FCF growth: bear 5.0%, base 8.0%, bull 12.0%",
            "WACC: bear 10.0%, base 9.0%, bull 8.0%",
            "Terminal growth: bear 2.0%, base 3.0%, bull 4.0%",
            "Forward EPS used for P/E comps: 5.00",
            "Base EV/EBITDA multiple: 15.00x",
            "Method weights: DCF 40.0%, P/E Comps 30.0%, EV/EBITDA 30.0%",
        ]

        result = ValuationAnalysisOutput(
            report="Report",
            valuation_score=6,
            fair_value_bear=40.0,
            fair_value_base=50.0,
            fair_value_bull=60.0,
            current_discount_pct=12.0,
            valuation_conviction="medium",
            valuation_key_assumptions=assumptions,
            dcf=ValuationMethodScenario(bear=40.0, base=50.0, bull=60.0),
            pe_comps=ValuationMethodScenario(bear=42.0, base=52.0, bull=62.0),
            ev_ebitda=ValuationMethodScenario(bear=38.0, base=48.0, bull=58.0),
            valuation_summary=ValuationSummaryTable(**summary),
            valuation_bridge=ValuationBridge(
                current_price=44.00,
                growth_premium=6.00,
                multiple_expansion=5.00,
                risk_discount=5.00,
                fair_value=50.00,
            ),
            valuation_sensitivity=ValuationSensitivity(
                fcf_growth_rate=ValuationSensitivityRange(delta=0.02, low=47.0, high=53.0),
                wacc=ValuationSensitivityRange(delta=0.01, low=46.0, high=54.0),
                terminal_growth=ValuationSensitivityRange(delta=0.005, low=48.0, high=52.0),
                exit_multiple=ValuationSensitivityRange(delta=2.0, low=49.0, high=51.0),
            ),
            key_takeaways=["Fair value above market."],
        )

        self.assertEqual(result.valuation_key_assumptions, assumptions)

    def test_trust_equity_is_not_treated_as_etf_when_quote_type_is_equity(self):
        self.assertFalse(
            _is_index_or_etf(
                {
                    "QuoteType": "EQUITY",
                    "Name": "PennyMac Mortgage Investment Trust",
                }
            )
        )
        self.assertTrue(
            _is_index_or_etf(
                {
                    "QuoteType": "ETF",
                    "Name": "SPDR S&P 500 ETF Trust",
                }
            )
        )

    def test_multi_method_valuation_data_returns_non_zero_methods(self):
        fundamentals = {
            "MarketCapitalization": 1_000_000_000_000,
            "EnterpriseValue": 1_050_000_000_000,
            "TrailingPE": 32.0,
            "ForwardPE": 28.0,
            "EVToEBITDA": 24.0,
            "EBITDA": 42_000_000_000,
            "EPS": 5.0,
            "Beta": 1.3,
            "QuarterlyRevenueGrowthYOY": 0.18,
            "QuarterlyEarningsGrowthYOY": 0.22,
            "SharesOutstanding": 2_500_000_000,
        }
        statements = {
            "statements": {
                "balance_sheet": {
                    "data": {
                        "annualReports": [
                            {"fiscalDateEnding": "2025-01-31", "totalDebt": 80_000_000_000, "cashAndCashEquivalents": 30_000_000_000},
                            {"fiscalDateEnding": "2024-01-31", "totalDebt": 75_000_000_000, "cashAndCashEquivalents": 28_000_000_000},
                        ],
                        "quarterlyReports": [
                            {"fiscalDateEnding": "2025-10-31", "totalDebt": 82_000_000_000, "cashAndCashEquivalents": 32_000_000_000},
                        ],
                    }
                },
                "cashflow": {
                    "data": {
                        "annualReports": [
                            {"fiscalDateEnding": "2025-01-31", "freeCashFlow": 30_000_000_000, "operatingCashFlow": 35_000_000_000, "capitalExpenditure": -5_000_000_000},
                            {"fiscalDateEnding": "2024-01-31", "freeCashFlow": 24_000_000_000, "operatingCashFlow": 29_000_000_000, "capitalExpenditure": -5_000_000_000},
                        ],
                        "quarterlyReports": [],
                    }
                },
                "income_statement": {
                    "data": {
                        "annualReports": [
                            {"fiscalDateEnding": "2025-01-31", "totalRevenue": 130_000_000_000, "netIncome": 55_000_000_000, "interestExpense": 2_000_000_000, "taxProvision": 6_000_000_000, "pretaxIncome": 61_000_000_000},
                            {"fiscalDateEnding": "2024-01-31", "totalRevenue": 105_000_000_000, "netIncome": 42_000_000_000, "interestExpense": 1_800_000_000, "taxProvision": 4_500_000_000, "pretaxIncome": 46_500_000_000},
                        ],
                        "quarterlyReports": [],
                    }
                },
            }
        }
        recommendations = {
            "price_targets": {
                "low": 170.0,
                "average": 205.0,
                "high": 240.0,
            }
        }

        result = calculate_multi_method_valuation_data(
            ticker="NVDA",
            current_price=188.63,
            fundamentals=fundamentals,
            statements_payload=statements,
            analyst_recommendations=recommendations,
        )

        self.assertGreater(result["dcf"]["base"], 0.0)
        self.assertGreater(result["pe_comps"]["base"], 0.0)
        self.assertGreater(result["ev_ebitda"]["base"], 0.0)
        self.assertGreater(result["valuation_summary"]["weighted_avg"]["base"], 0.0)
        self.assertIn(result["valuation_conviction"], {"high", "medium", "low"})
        self.assertIsInstance(result["valuation_score"], int)
        self.assertGreaterEqual(result["valuation_bridge"]["growth_premium"], 0.0)
        self.assertGreaterEqual(result["valuation_bridge"]["multiple_expansion"], 0.0)
        self.assertGreaterEqual(result["valuation_bridge"]["risk_discount"], 0.0)
        self.assertLessEqual(result["valuation_sensitivity"]["fcf_growth_rate"]["low"], result["valuation_sensitivity"]["fcf_growth_rate"]["high"])
        self.assertLessEqual(result["valuation_sensitivity"]["wacc"]["low"], result["valuation_sensitivity"]["wacc"]["high"])
        self.assertLessEqual(result["valuation_sensitivity"]["terminal_growth"]["low"], result["valuation_sensitivity"]["terminal_growth"]["high"])
        self.assertLessEqual(result["valuation_sensitivity"]["exit_multiple"]["low"], result["valuation_sensitivity"]["exit_multiple"]["high"])
        self.assertAlmostEqual(
            result["valuation_bridge"]["current_price"]
            + result["valuation_bridge"]["growth_premium"]
            + result["valuation_bridge"]["multiple_expansion"]
            - result["valuation_bridge"]["risk_discount"],
            result["valuation_bridge"]["fair_value"],
            places=2,
        )


    def test_get_peer_comparables_selects_real_peers_and_computes_averages(self):
        universe = [
            {"ticker": "NVDA", "name": "NVIDIA CORP", "sector": "Technology", "industry": "Semiconductors"},
            {"ticker": "AMD", "name": "ADVANCED MICRO DEVICES", "sector": "Technology", "industry": "Semiconductors"},
            {"ticker": "AVGO", "name": "BROADCOM INC", "sector": "Technology", "industry": "Semiconductors"},
            {"ticker": "QCOM", "name": "QUALCOMM INC", "sector": "Technology", "industry": "Semiconductors"},
            {"ticker": "XLK", "name": "TECH ETF", "sector": "Technology", "industry": "ETF"},
        ]

        fundamentals_map = {
            "NVDA": {
                "fundamentals": {
                    "ForwardPE": 38.5,
                    "EVToEBITDA": 34.02,
                    "PriceToSalesRatioTTM": 21.23,
                    "QuarterlyRevenueGrowthYOY": 0.18,
                    "OperatingMarginTTM": 0.65,
                },
                "company_info": {"name": "NVIDIA CORP", "sector": "Technology", "industry": "Semiconductors"},
            },
            "AMD": {
                "fundamentals": {
                    "ForwardPE": 30.0,
                    "EVToEBITDA": 25.0,
                    "PriceToSalesRatioTTM": 15.0,
                    "QuarterlyRevenueGrowthYOY": 0.15,
                    "OperatingMarginTTM": 0.60,
                },
                "company_info": {"name": "ADVANCED MICRO DEVICES", "sector": "Technology", "industry": "Semiconductors"},
            },
            "AVGO": {
                "fundamentals": {
                    "ForwardPE": 35.0,
                    "EVToEBITDA": 30.0,
                    "PriceToSalesRatioTTM": 18.0,
                    "QuarterlyRevenueGrowthYOY": 0.20,
                    "OperatingMarginTTM": 0.62,
                },
                "company_info": {"name": "BROADCOM INC", "sector": "Technology", "industry": "Semiconductors"},
            },
            "QCOM": {
                "fundamentals": {
                    "ForwardPE": 32.5,
                    "EVToEBITDA": 29.0,
                    "PriceToSalesRatioTTM": 16.5,
                    "QuarterlyRevenueGrowthYOY": 0.175,
                    "OperatingMarginTTM": 0.61,
                },
                "company_info": {"name": "QUALCOMM INC", "sector": "Technology", "industry": "Semiconductors"},
            },
        }

        from ai_engine.tradingagents.agents.utils.valuation_tools import get_peer_comparables

        with patch(
            "ai_engine.tradingagents.agents.utils.valuation_tools._load_stocks_universe",
            return_value=universe,
        ), patch(
            "ai_engine.tradingagents.agents.utils.valuation_tools.require_info_service",
            return_value=None,
        ), patch(
            "ai_engine.tradingagents.agents.utils.valuation_tools.get_fundamentals_via_service",
            side_effect=lambda ticker: json.dumps(fundamentals_map[ticker]),
        ):
            result = json.loads(get_peer_comparables.invoke({"ticker": "NVDA"}))

        self.assertEqual(result["ticker"], "NVDA")
        self.assertEqual(result["selection_context"]["selected_peer_count"], 3)
        self.assertEqual([peer["ticker"] for peer in result["peers"]], ["AMD", "AVGO", "QCOM"])
        self.assertAlmostEqual(result["peer_averages"]["pe_ratio"], 32.5)
        self.assertAlmostEqual(result["peer_averages"]["ev_to_ebitda"], 28.0)
        self.assertAlmostEqual(result["peer_averages"]["price_to_sales"], 16.5)
        self.assertAlmostEqual(result["peer_averages"]["growth"], 0.175)
        self.assertAlmostEqual(result["peer_averages"]["margin"], 0.61)

    def test_get_peer_comparables_flags_limited_peer_set(self):
        universe = [
            {"ticker": "NVDA", "name": "NVIDIA CORP", "sector": "Technology", "industry": "Semiconductors"},
            {"ticker": "AMD", "name": "ADVANCED MICRO DEVICES", "sector": "Technology", "industry": "Semiconductors"},
            {"ticker": "BTC-USD", "name": "Bitcoin USD", "sector": "Technology", "industry": "Crypto"},
        ]

        fundamentals_map = {
            "NVDA": {
                "fundamentals": {
                    "ForwardPE": 38.5,
                    "EVToEBITDA": 34.02,
                    "PriceToSalesRatioTTM": 21.23,
                    "QuarterlyRevenueGrowthYOY": 0.18,
                    "OperatingMarginTTM": 0.65,
                },
                "company_info": {"name": "NVIDIA CORP", "sector": "Technology", "industry": "Semiconductors"},
            },
            "AMD": {
                "fundamentals": {
                    "ForwardPE": 30.0,
                    "EVToEBITDA": 25.0,
                    "PriceToSalesRatioTTM": 15.0,
                    "QuarterlyRevenueGrowthYOY": 0.15,
                    "OperatingMarginTTM": 0.60,
                },
                "company_info": {"name": "ADVANCED MICRO DEVICES", "sector": "Technology", "industry": "Semiconductors"},
            },
        }

        from ai_engine.tradingagents.agents.utils.valuation_tools import get_peer_comparables

        with patch(
            "ai_engine.tradingagents.agents.utils.valuation_tools._load_stocks_universe",
            return_value=universe,
        ), patch(
            "ai_engine.tradingagents.agents.utils.valuation_tools.require_info_service",
            return_value=None,
        ), patch(
            "ai_engine.tradingagents.agents.utils.valuation_tools.get_fundamentals_via_service",
            side_effect=lambda ticker: json.dumps(fundamentals_map[ticker]),
        ):
            result = json.loads(get_peer_comparables.invoke({"ticker": "NVDA"}))

        self.assertEqual(result["selection_context"]["selected_peer_count"], 1)
        self.assertIn("limited", result["selection_context"]["note"].lower())
        self.assertEqual([peer["ticker"] for peer in result["peers"]], ["AMD"])

if __name__ == "__main__":
    unittest.main()
