"""
Valuation Analyst - Multi-method fair value analysis with scenario modeling.
"""

import logging
from typing import List, Literal

from pydantic import BaseModel, Field

from ..utils.agent_utils import (
    get_events,
    get_ticker_quote,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
)
from ..utils.valuation_tools import (
    calculate_multi_method_valuation,
    calculate_valuation_summary_table,
    get_peer_comparables,
    get_growth_estimates,
    get_wacc_inputs,
    get_dcf_inputs,
)
from ..utils.market_rates_tools import get_market_rates
from .self_contained_analyst import create_self_contained_analyst
from .output_schema import analyst_key_takeaways_field
from .prompts import build_valuation_analyst_prompt

logger = logging.getLogger(__name__)


class ValuationMethodScenario(BaseModel):
    bear: float = Field(description="Bear-case fair value per share for this method")
    base: float = Field(description="Base-case fair value per share for this method")
    bull: float = Field(description="Bull-case fair value per share for this method")


class ValuationSummaryRow(BaseModel):
    method: str = Field(description="Valuation method name")
    bear: float = Field(description="Bear-case valuation for this method")
    base: float = Field(description="Base-case valuation for this method")
    bull: float = Field(description="Bull-case valuation for this method")
    weight: float = Field(description="Method weight as a decimal")
    implied_value: float = Field(description="Scenario-weighted implied value for this method")


class ValuationSummaryWeightedAverage(BaseModel):
    bear: float = Field(description="Weighted average bear-case valuation")
    base: float = Field(description="Weighted average base-case valuation")
    bull: float = Field(description="Weighted average bull-case valuation")
    weight: float = Field(description="Total weight, expected to equal 1.0")
    implied_value: float = Field(description="Weighted average implied valuation")


class ValuationSummaryTable(BaseModel):
    rows: List[ValuationSummaryRow] = Field(description="Per-method valuation rows")
    weighted_avg: ValuationSummaryWeightedAverage = Field(
        description="Weighted-average valuation summary row"
    )


class ValuationBridge(BaseModel):
    current_price: float = Field(description="Current share price used in the bridge")
    growth_premium: float = Field(description="Bridge component attributed to growth")
    multiple_expansion: float = Field(description="Bridge component attributed to multiple expansion")
    risk_discount: float = Field(description="Bridge component attributed to risk discount")
    fair_value: float = Field(description="Bridge ending fair value")


class ValuationSensitivityRange(BaseModel):
    delta: float = Field(description="Sensitivity change applied to the driver")
    low: float = Field(description="Lower bound fair value under this sensitivity")
    high: float = Field(description="Upper bound fair value under this sensitivity")


class ValuationSensitivity(BaseModel):
    fcf_growth_rate: ValuationSensitivityRange
    wacc: ValuationSensitivityRange
    terminal_growth: ValuationSensitivityRange
    exit_multiple: ValuationSensitivityRange


class ValuationAnalysisOutput(BaseModel):
    """Structured output for valuation analysis including fair values and conviction."""
    
    report: str = Field(
        description="Comprehensive valuation analysis report covering multiple methods, scenarios, and sensitivity analysis"
    )
    valuation_score: int = Field(
        ge=1, le=10,
        description=(
            "Valuation score from 1-10 based on upside/downside to fair value. "
            "1-3: Significantly overvalued (>20% downside), "
            "4-5: Fairly valued (±10%), "
            "6-7: Undervalued (10-25% upside), "
            "8-10: Significantly undervalued (>25% upside)"
        )
    )
    fair_value_bear: float = Field(
        description="Conservative fair value estimate (bear case scenario)"
    )
    fair_value_base: float = Field(
        description="Base case fair value estimate (most likely scenario)"
    )
    fair_value_bull: float = Field(
        description="Optimistic fair value estimate (bull case scenario)"
    )
    current_discount_pct: float = Field(
        description=(
            "Percentage discount/premium of current price vs base fair value. "
            "Positive = trading below fair value (discount), "
            "Negative = trading above fair value (premium)"
        )
    )
    valuation_conviction: Literal["high", "medium", "low"] = Field(
        description=(
            "Conviction level in the valuation. "
            "high: Multiple methods converge, clear drivers, low sensitivity. "
            "medium: Some method divergence, moderate uncertainty. "
            "low: Wide dispersion, high sensitivity, unclear drivers"
        )
    )
    valuation_key_assumptions: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Top 3-5 most critical assumptions driving the valuation (e.g., 'FCF growth 15%', 'WACC 9.5%')"
    )
    dcf: ValuationMethodScenario = Field(
        description="DCF fair value outputs by scenario"
    )
    pe_comps: ValuationMethodScenario = Field(
        description="P/E comps fair value outputs by scenario"
    )
    ev_ebitda: ValuationMethodScenario = Field(
        description="EV/EBITDA fair value outputs by scenario"
    )
    valuation_summary: ValuationSummaryTable = Field(
        description="Deterministic valuation summary generated from calculate_valuation_summary_table"
    )
    valuation_bridge: ValuationBridge = Field(
        description="Deterministic bridge from current price to fair value"
    )
    valuation_sensitivity: ValuationSensitivity = Field(
        description="Deterministic sensitivity analysis ranges"
    )
    key_takeaways: List[str] = analyst_key_takeaways_field()


def create_valuation_analyst(llm):
    """Create a self-contained valuation analyst that handles all tool calling internally."""
    return create_self_contained_analyst(
        llm=llm,
        tools=[
            get_events,
            get_ticker_quote,
            get_fundamentals,
            get_peer_comparables,
            get_growth_estimates,
            get_wacc_inputs,
            get_dcf_inputs,
            get_market_rates,
            calculate_multi_method_valuation,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
            # calculate_valuation_summary_table removed - redundant with calculate_multi_method_valuation
        ],
        prompt_builder=build_valuation_analyst_prompt,
        structured_output_class=ValuationAnalysisOutput,
        score_field="valuation_score",
        report_field="valuation_report",
        agent_name="Valuation Analyst",
        max_iterations=5,  # Increased from 4: allows buffer if LLM doesn't batch tools optimally
    )

# Made with Bob
