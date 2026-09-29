"""
Regression tests for the valuation analyst's "refuse to compute rather than
guess" gate in run_self_contained_analyst.

Reproduces the CHAT (Roundhill ETF) bug: the ReAct loop could reach its final
structured-output call without calculate_multi_method_valuation ever having
been called, so the LLM filled the report with unfilled template text like
"$XX" instead of real numbers. These tests drive the loop with a fake LLM to
confirm: (1) a model that skips the calculator gets one nudge, (2) if the
nudge still doesn't produce a real calculation the report and every
fabricated numeric field are blanked, (3) a model that does call the
calculator is untouched, and (4) analysts without the calculator tool are
never nudged or blanked.
"""

from typing import List, Literal

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, Field

from ai_engine.tradingagents.agents.analysts.self_contained_analyst import (
    run_self_contained_analyst,
)
from ai_engine.tradingagents.agents.analysts.valuation_analyst import (
    ValuationAnalysisOutput,
    ValuationScoreBreakdown,
    ValuationMethodScenario,
    ValuationSummaryTable,
    ValuationSummaryRow,
    ValuationSummaryWeightedAverage,
    ValuationBridge,
    ValuationSensitivity,
    ValuationSensitivityRange,
    ValuationProbabilityDistribution,
    ScenarioInterpretation,
)


def _healthy_valuation_output(
    report: str = "Full valuation analysis with real computed numbers.",
    fair_value_base: float = 150.0,
    valuation_conviction: Literal["high", "medium", "low"] = "medium",
) -> ValuationAnalysisOutput:
    """A fully-populated ValuationAnalysisOutput, as if the LLM had real numbers."""
    return ValuationAnalysisOutput(
        report=report,
        valuation_score=3,
        valuation_score_breakdown=ValuationScoreBreakdown(
            method_agreement=1.5,
            sensitivity_stability=1.5,
            data_quality=1.5,
            assumption_realism=1.5,
            peer_consistency=1.5,
            total_score=3,
            explanation="Methods converge on a similar fair value.",
        ),
        fair_value_bear=120.0,
        fair_value_base=fair_value_base,
        fair_value_bull=180.0,
        current_discount_pct=5.0,
        valuation_conviction=valuation_conviction,
        valuation_key_assumptions=["FCF growth 10%", "WACC 9%"],
        dcf=ValuationMethodScenario(bear=110.0, base=150.0, bull=190.0),
        pe_comps=ValuationMethodScenario(bear=115.0, base=155.0, bull=195.0),
        ev_ebitda=ValuationMethodScenario(bear=105.0, base=145.0, bull=185.0),
        valuation_summary=ValuationSummaryTable(
            rows=[
                ValuationSummaryRow(
                    method="DCF", bear=110.0, base=150.0, bull=190.0,
                    weight=1.0, implied_value=150.0,
                )
            ],
            weighted_avg=ValuationSummaryWeightedAverage(
                bear=110.0, base=150.0, bull=190.0, weight=1.0, implied_value=150.0,
            ),
        ),
        valuation_bridge=ValuationBridge(
            current_price=142.0, growth_premium=10.0, multiple_expansion=5.0,
            risk_discount=-2.0, fair_value=150.0,
        ),
        valuation_sensitivity=ValuationSensitivity(
            fcf_growth_rate=ValuationSensitivityRange(
                parameter_name="fcf_growth_rate", base_value=0.1, delta_absolute=0.02,
                delta_percent=20.0, low_value=0.08, high_value=0.12,
                fair_value_low=140.0, fair_value_high=160.0, fair_value_range_pct=13.0,
            ),
            wacc=ValuationSensitivityRange(
                parameter_name="wacc", base_value=0.09, delta_absolute=0.01,
                delta_percent=11.0, low_value=0.08, high_value=0.10,
                fair_value_low=145.0, fair_value_high=155.0, fair_value_range_pct=6.5,
            ),
            terminal_growth=ValuationSensitivityRange(
                parameter_name="terminal_growth", base_value=0.025, delta_absolute=0.005,
                delta_percent=20.0, low_value=0.02, high_value=0.03,
                fair_value_low=148.0, fair_value_high=152.0, fair_value_range_pct=2.7,
            ),
            exit_multiple=ValuationSensitivityRange(
                parameter_name="exit_multiple", base_value=12.0, delta_absolute=1.0,
                delta_percent=8.0, low_value=11.0, high_value=13.0,
                fair_value_low=147.0, fair_value_high=153.0, fair_value_range_pct=4.0,
            ),
        ),
        probability_distribution=ValuationProbabilityDistribution(
            p10=110.0, p25=130.0, p50=150.0, p75=170.0, p90=190.0,
            expected_value=150.0, downside_risk_pct=22.5, upside_potential_pct=33.8,
            risk_reward_ratio=1.5,
        ),
        scenario_interpretation=ScenarioInterpretation(
            market_implied_scenario="base", market_implied_probability_pct=60.0,
            expected_return_pct=5.6, downside_protection_pct=15.5,
            upside_capture_pct=33.8, asymmetry_ratio=1.5,
            interpretation="Market is pricing the base case.",
        ),
        key_takeaways=["Trading near fair value", "DCF and comps converge"],
    )


class _OtherAnalystOutput(BaseModel):
    """Minimal structured output for an analyst that has no valuation calculator."""
    report: str = Field(description="report")
    other_score: int = Field(ge=1, le=5, description="score")


class FakeLLM:
    """
    Stands in for a real chat model inside run_self_contained_analyst.

    bind_tools()/with_structured_output() are called once per think/final step in
    the production loop; each call pops the next canned response off its queue
    and wraps it in a RunnableLambda so `prompt | llm.bind_tools(tools)` still
    builds a real Runnable that ChatPromptTemplate can invoke.
    """

    def __init__(self, think_responses: List[AIMessage], structured_responses: List[BaseModel]):
        self._think_responses = list(think_responses)
        self._structured_responses = list(structured_responses)

    def bind_tools(self, tools):
        response = self._think_responses.pop(0)
        return RunnableLambda(lambda _input, **kwargs: response)

    def with_structured_output(self, cls):
        response = self._structured_responses.pop(0)
        return RunnableLambda(lambda _input, **kwargs: response)


def _build_prompt(**kwargs):
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

    return ChatPromptTemplate.from_messages([
        ("system", "You are a test analyst for {ticker} on {current_date}."),
        MessagesPlaceholder(variable_name="messages"),
    ]).partial(ticker=kwargs["ticker"], current_date=kwargs["current_date"])


def _no_tool_calls_message(content: str = "thinking...") -> AIMessage:
    return AIMessage(content=content, tool_calls=[])


def _calculator_call_message(ticker: str = "TEST") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "calculate_multi_method_valuation",
                "args": {"ticker": ticker},
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )


def calculate_multi_method_valuation(ticker: str) -> str:
    """Named to match the real tool: tool_map keys off __name__ for plain functions."""
    return '{"valuation_available": true, "dcf": {"base": 150.0}}'


def _base_state():
    return {"trade_date": "2026-09-28", "company_of_interest": "TEST"}


def test_calculator_never_called_nudge_fails_blanks_everything():
    """
    Loop exits without calling the calculator, the nudge is ignored too ->
    report becomes the honest unavailable notice and every fabricated
    numeric/structured field is blanked.
    """
    llm = FakeLLM(
        think_responses=[
            _no_tool_calls_message(),  # main loop: no tools requested
            _no_tool_calls_message(),  # nudge: still ignored
        ],
        structured_responses=[
            _healthy_valuation_output(
                report="Fair value is $XX with -X% (to be calculated) upside.",
                fair_value_base=999.0,
            )
        ],
    )

    result = run_self_contained_analyst(
        state=_base_state(),
        llm=llm,
        tools=[calculate_multi_method_valuation],
        prompt_builder=_build_prompt,
        structured_output_class=ValuationAnalysisOutput,
        score_field="valuation_score",
        report_field="valuation_report",
        agent_name="Valuation Analyst",
        max_iterations=1,
    )

    assert "$XX" not in result["valuation_report"]
    assert "VALUATION_UNAVAILABLE" in result["valuation_report"] or "unavailable" in result["valuation_report"].lower()
    assert result["dcf"] == {"bear": None, "base": None, "bull": None}
    assert result["pe_comps"] == {"bear": None, "base": None, "bull": None}
    assert result["ev_ebitda"] == {"bear": None, "base": None, "bull": None}
    assert result["valuation_score"] is None
    assert result["fair_value_base"] is None
    assert result["fair_value_bull"] is None
    assert result["fair_value_bear"] is None
    assert result["current_discount_pct"] is None
    assert result["valuation_conviction"] == "UNAVAILABLE"
    assert result["valuation_score_breakdown"] == {}
    assert result["valuation_bridge"] == {}
    assert result["valuation_sensitivity"] == {}
    assert result["probability_distribution"] == {}
    assert result["scenario_interpretation"] == {}
    assert len(result["valuation_key_assumptions"]) == 1
    assert "VALUATION_UNAVAILABLE" in result["valuation_key_assumptions"][0]


def test_calculator_never_called_nudge_succeeds_preserves_real_values():
    """
    Loop exits without calling the calculator, but the nudge works and the
    model calls it -> real values are kept, nothing is blanked.
    """
    llm = FakeLLM(
        think_responses=[
            _no_tool_calls_message(),          # main loop: no tools requested
            _calculator_call_message("TEST"),  # nudge: model calls the calculator
        ],
        structured_responses=[
            _healthy_valuation_output(
                report="Real valuation with computed fair values.",
                fair_value_base=150.0,
            )
        ],
    )

    result = run_self_contained_analyst(
        state=_base_state(),
        llm=llm,
        tools=[calculate_multi_method_valuation],
        prompt_builder=_build_prompt,
        structured_output_class=ValuationAnalysisOutput,
        score_field="valuation_score",
        report_field="valuation_report",
        agent_name="Valuation Analyst",
        max_iterations=1,
    )

    assert result["valuation_report"] == "Real valuation with computed fair values."
    assert "VALUATION_UNAVAILABLE" not in result["valuation_report"]
    assert result["fair_value_base"] == 150.0
    assert result["dcf"] == {"bear": 110.0, "base": 150.0, "bull": 190.0}
    assert result["valuation_score"] == 3
    assert result["valuation_conviction"] == "medium"


def test_calculator_called_in_main_loop_no_nudge_no_blanking():
    """
    Normal/happy path: the model calls the calculator during the main loop
    itself -> no nudge is issued (FakeLLM would raise on a 3rd bind_tools
    call it has no response queued for) and nothing is blanked.
    """
    llm = FakeLLM(
        think_responses=[
            _calculator_call_message("TEST"),  # iteration 1: calls the calculator
            _no_tool_calls_message(),          # iteration 2: done, no more tools
        ],
        structured_responses=[
            _healthy_valuation_output(
                report="Real valuation with computed fair values.",
                fair_value_base=150.0,
            )
        ],
    )

    result = run_self_contained_analyst(
        state=_base_state(),
        llm=llm,
        tools=[calculate_multi_method_valuation],
        prompt_builder=_build_prompt,
        structured_output_class=ValuationAnalysisOutput,
        score_field="valuation_score",
        report_field="valuation_report",
        agent_name="Valuation Analyst",
        max_iterations=2,
    )

    assert result["valuation_report"] == "Real valuation with computed fair values."
    assert result["fair_value_base"] == 150.0
    assert result["dcf"] == {"bear": 110.0, "base": 150.0, "bull": 190.0}
    assert result["valuation_conviction"] == "medium"
    # No queued responses remain unused: FakeLLM was called exactly twice for
    # bind_tools (no nudge) and once for with_structured_output.
    assert llm._think_responses == []
    assert llm._structured_responses == []


def test_other_analyst_without_calculator_is_never_nudged_or_blanked():
    """
    An analyst whose tool_map lacks calculate_multi_method_valuation (e.g.
    technical/sentiment analysts) must never be nudged and never have its
    output blanked, even though it also exits the loop without tool calls.
    """
    def _other_tool(ticker: str) -> str:
        return "{}"

    llm = FakeLLM(
        think_responses=[
            _no_tool_calls_message(),  # single iteration, no tools requested
        ],
        structured_responses=[
            _OtherAnalystOutput(report="Plain technical analysis report.", other_score=4),
        ],
    )

    result = run_self_contained_analyst(
        state=_base_state(),
        llm=llm,
        tools=[_other_tool],
        prompt_builder=_build_prompt,
        structured_output_class=_OtherAnalystOutput,
        score_field="other_score",
        report_field="other_report",
        agent_name="Other Analyst",
        max_iterations=1,
    )

    assert result["other_report"] == "Plain technical analysis report."
    assert result["other_score"] == 4
    # No nudge call was ever made: exactly one bind_tools response was consumed.
    assert llm._think_responses == []
    assert llm._structured_responses == []
