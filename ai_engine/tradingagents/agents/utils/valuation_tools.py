"""
Valuation tools for calculating fair value using multiple methods.
"""

from langchain_core.tools import tool
from typing import Annotated, Optional, Dict, Any
import json
import math
from pathlib import Path
from statistics import median, pstdev

from ...datasources.info_service_client import (
    get_analyst_recommendations,
    get_fundamentals as get_fundamentals_via_service,
    get_quote,
    get_financial_statements,
    require_info_service,
)


DEFAULT_METHOD_WEIGHTS = {
    "DCF": 0.40,
    "P/E Comps": 0.30,
    "EV/EBITDA": 0.30,
}

DEFAULT_SCENARIO_WEIGHTS = {
    "bear": 0.25,
    "base": 0.50,
    "bull": 0.25,
}

_STOCKS_JSON_PATH = Path(__file__).resolve().parents[4] / "frontend" / "public" / "stocks.json"
_EXCLUDED_TICKER_SUFFIXES = (
    "-USD",
    "-USDT",
    "-WT",
    "-W",
    "-WS",
    "-U",
    "-UN",
    "-RT",
    "-R",
    "-P",
)
_EXCLUDED_NAME_KEYWORDS = (
    " ETF",
    " ETN",
    " FUND",
    " TRUST",
    " WARRANT",
    " PFD",
    " PREFERRED",
    " INCOME SHARES",
)


def _weighted_base_value(dcf_base: float, pe_comps_base: float, ev_ebitda_base: float) -> float:
    return (
        dcf_base * DEFAULT_METHOD_WEIGHTS["DCF"]
        + pe_comps_base * DEFAULT_METHOD_WEIGHTS["P/E Comps"]
        + ev_ebitda_base * DEFAULT_METHOD_WEIGHTS["EV/EBITDA"]
    )


def _load_stocks_universe() -> list[Dict[str, Any]]:
    try:
        payload = json.loads(_STOCKS_JSON_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_upper(value: Any) -> str:
    return _normalize_text(value).upper()


def _is_candidate_ticker_allowed(ticker: str, name: str) -> bool:
    ticker_upper = _normalize_upper(ticker)
    name_upper = _normalize_upper(name)
    if not ticker_upper:
        return False
    if any(ticker_upper.endswith(suffix) for suffix in _EXCLUDED_TICKER_SUFFIXES):
        return False
    if ticker_upper.count("-") >= 1:
        return False
    if any(keyword in name_upper for keyword in _EXCLUDED_NAME_KEYWORDS):
        return False
    return True


def _extract_company_profile(fundamentals_payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(fundamentals_payload, dict):
        return {}
    for key in ("company_info", "company", "profile", "overview"):
        value = fundamentals_payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _peer_metric_entry(
    ticker: str,
    name: str,
    sector: str,
    industry: str,
    fundamentals: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    trailing_pe = _first_numeric(fundamentals, "TrailingPE")
    forward_pe = _first_numeric(fundamentals, "ForwardPE")
    pe_ratio = forward_pe if forward_pe and forward_pe > 0 else trailing_pe
    ev_ebitda = _first_numeric(fundamentals, "EVToEBITDA")
    price_to_sales = _first_numeric(fundamentals, "PriceToSalesRatioTTM", "PriceToSalesTrailing12Months")
    growth = _first_numeric(
        fundamentals,
        "QuarterlyRevenueGrowthYOY",
        "QuarterlyEarningsGrowthYOY",
        "RevenueGrowthYOY",
        "EPSGrowthYOY",
    )
    margin = _first_numeric(
        fundamentals,
        "OperatingMarginTTM",
        "OperatingMargin",
        "ProfitMargin",
        "EBITDAMargin",
    )
    metrics = {
        "pe_ratio": pe_ratio,
        "ev_to_ebitda": ev_ebitda,
        "price_to_sales": price_to_sales,
        "growth": growth,
        "margin": margin,
    }
    valid_metric_count = sum(1 for value in metrics.values() if value is not None and value > 0)
    if valid_metric_count < 3:
        return None
    return {
        "ticker": _normalize_upper(ticker),
        "name": _normalize_text(name) or _normalize_upper(ticker),
        "sector": _normalize_text(sector),
        "industry": _normalize_text(industry),
        "metrics": metrics,
        "valid_metric_count": valid_metric_count,
    }


def _candidate_rank(
    candidate_sector: str,
    candidate_industry: str,
    target_sector: str,
    target_industry: str,
    valid_metric_count: int,
) -> tuple[int, int, int]:
    same_industry = int(
        bool(candidate_industry and target_industry and candidate_industry.casefold() == target_industry.casefold())
    )
    same_sector = int(
        bool(candidate_sector and target_sector and candidate_sector.casefold() == target_sector.casefold())
    )
    return (same_industry, same_sector, valid_metric_count)


def _average_metric(entries: list[Dict[str, Any]], metric_name: str) -> Optional[float]:
    values = []
    for entry in entries:
        metric_value = _safe_float(((entry or {}).get("metrics") or {}).get(metric_name))
        if metric_value is not None and metric_value > 0:
            values.append(metric_value)
    if not values:
        return None
    return sum(values) / len(values)


def _build_valuation_bridge(
    current_price: float,
    fair_value_base: float,
    dcf_base: float,
    pe_comps_base: float,
    ev_ebitda_base: float,
) -> Dict[str, float]:
    avg_comps_base = (pe_comps_base + ev_ebitda_base) / 2.0
    upside_gap = fair_value_base - current_price

    if upside_gap <= 0:
        return {
            "current_price": current_price,
            "growth_premium": 0.0,
            "multiple_expansion": 0.0,
            "risk_discount": max(current_price - fair_value_base, 0.0),
            "fair_value": fair_value_base,
        }

    growth_premium = max(dcf_base - current_price, 0.0)
    multiple_expansion = max(avg_comps_base - current_price, 0.0)
    positive_total = growth_premium + multiple_expansion

    if positive_total < upside_gap:
        shortfall = upside_gap - positive_total
        growth_premium += shortfall * 0.6
        multiple_expansion += shortfall * 0.4
        positive_total = growth_premium + multiple_expansion

    risk_discount = max(positive_total - upside_gap, 0.0)
    return {
        "current_price": current_price,
        "growth_premium": growth_premium,
        "multiple_expansion": multiple_expansion,
        "risk_discount": risk_discount,
        "fair_value": fair_value_base,
    }


def _build_sensitivity_analysis(
    *,
    current_fcf: float,
    base_growth: float,
    wacc_base: float,
    terminal_growth_base: float,
    net_debt: float,
    shares_outstanding: float,
    pe_comps_base: float,
    ev_ebitda_base: float,
    dcf_base: float,
    base_ev_multiple: float,
    ebitda: float,
) -> Dict[str, Dict[str, float]]:
    def weighted_from_dcf(dcf_value: float) -> float:
        return _weighted_base_value(dcf_value, pe_comps_base, ev_ebitda_base)

    fcf_low = _discounted_cash_flow_value(
        current_fcf=current_fcf,
        growth=base_growth - 0.02,
        wacc=wacc_base,
        terminal_growth=terminal_growth_base,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )
    fcf_high = _discounted_cash_flow_value(
        current_fcf=current_fcf,
        growth=base_growth + 0.02,
        wacc=wacc_base,
        terminal_growth=terminal_growth_base,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )
    wacc_low = _discounted_cash_flow_value(
        current_fcf=current_fcf,
        growth=base_growth,
        wacc=wacc_base - 0.01,
        terminal_growth=terminal_growth_base,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )
    wacc_high = _discounted_cash_flow_value(
        current_fcf=current_fcf,
        growth=base_growth,
        wacc=wacc_base + 0.01,
        terminal_growth=terminal_growth_base,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )
    tg_low = _discounted_cash_flow_value(
        current_fcf=current_fcf,
        growth=base_growth,
        wacc=wacc_base,
        terminal_growth=terminal_growth_base - 0.005,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )
    tg_high = _discounted_cash_flow_value(
        current_fcf=current_fcf,
        growth=base_growth,
        wacc=wacc_base,
        terminal_growth=terminal_growth_base + 0.005,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )
    exit_low_ev = max((((ebitda * (base_ev_multiple - 2.0)) - net_debt) / shares_outstanding), 0.01)
    exit_high_ev = max((((ebitda * (base_ev_multiple + 2.0)) - net_debt) / shares_outstanding), 0.01)

    return {
        "fcf_growth_rate": {
            "delta": 0.02,
            "low": min(weighted_from_dcf(fcf_low), weighted_from_dcf(fcf_high)),
            "high": max(weighted_from_dcf(fcf_low), weighted_from_dcf(fcf_high)),
        },
        "wacc": {
            "delta": 0.01,
            "low": min(weighted_from_dcf(wacc_high), weighted_from_dcf(wacc_low)),
            "high": max(weighted_from_dcf(wacc_high), weighted_from_dcf(wacc_low)),
        },
        "terminal_growth": {
            "delta": 0.005,
            "low": min(weighted_from_dcf(tg_low), weighted_from_dcf(tg_high)),
            "high": max(weighted_from_dcf(tg_low), weighted_from_dcf(tg_high)),
        },
        "exit_multiple": {
            "delta": 2.0,
            "low": _weighted_base_value(dcf_base, pe_comps_base, exit_low_ev),
            "high": _weighted_base_value(dcf_base, pe_comps_base, exit_high_ev),
        },
    }


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        num = float(value)
        if math.isnan(num) or math.isinf(num):
            return None
        return num
    except (TypeError, ValueError):
        return None


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _json_loads_maybe(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            loaded = json.loads(payload)
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}
    return {}


def _sort_reports(reports: Any) -> list[Dict[str, Any]]:
    items = [r for r in (reports or []) if isinstance(r, dict)]
    return sorted(items, key=lambda r: str(r.get("fiscalDateEnding") or ""), reverse=True)


def _statement_reports(statements_payload: Dict[str, Any], statement_key: str, report_key: str) -> list[Dict[str, Any]]:
    return _sort_reports(
        (((statements_payload or {}).get("statements") or {}).get(statement_key) or {}).get("data", {}).get(report_key) or []
    )


def _first_numeric(mapping: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = _safe_float(mapping.get(key))
        if value is not None:
            return value
    return None


def _latest_numeric(reports: list[Dict[str, Any]], *keys: str) -> Optional[float]:
    for report in reports:
        value = _first_numeric(report, *keys)
        if value is not None:
            return value
    return None


def _sum_latest(reports: list[Dict[str, Any]], key: str, count: int = 4) -> Optional[float]:
    values = []
    for report in reports:
        value = _safe_float(report.get(key))
        if value is not None:
            values.append(value)
        if len(values) >= count:
            break
    if not values:
        return None
    return sum(values)


def _cagr(reports: list[Dict[str, Any]], key: str) -> Optional[float]:
    values = []
    for report in reversed(reports):
        value = _safe_float(report.get(key))
        if value is not None and value > 0:
            values.append(value)
    if len(values) < 2:
        return None
    start = values[0]
    end = values[-1]
    periods = len(values) - 1
    if start <= 0 or end <= 0 or periods <= 0:
        return None
    return (end / start) ** (1 / periods) - 1


def _net_debt(
    fundamentals: Dict[str, Any],
    balance_sheet_annual: list[Dict[str, Any]],
    balance_sheet_quarterly: list[Dict[str, Any]],
) -> float:
    bs_candidates = balance_sheet_quarterly or balance_sheet_annual
    total_debt = _latest_numeric(
        bs_candidates,
        "totalDebt",
        "longTermDebtAndCapitalLeaseObligation",
        "longTermDebt",
    )
    current_debt = _latest_numeric(bs_candidates, "currentDebt", "currentCapitalLeaseObligation")
    cash = _latest_numeric(
        bs_candidates,
        "cashAndCashEquivalents",
        "cashCashEquivalentsAndShortTermInvestments",
        "cashAndShortTermInvestments",
    )
    if total_debt is None:
        ev = _first_numeric(fundamentals, "EnterpriseValue")
        market_cap = _first_numeric(fundamentals, "MarketCapitalization")
        if ev is not None and market_cap is not None:
            return ev - market_cap
        total_debt = 0.0
    if cash is None:
        cash = 0.0
    if current_debt is not None and total_debt is not None and total_debt < current_debt:
        total_debt += current_debt
    return float(total_debt - cash)


def _discounted_cash_flow_value(
    current_fcf: float,
    growth: float,
    wacc: float,
    terminal_growth: float,
    net_debt: float,
    shares_outstanding: float,
    projection_years: int = 5,
) -> float:
    """
    Calculate DCF fair value per share.
    
    Returns the equity value per share, which can be negative if net debt
    exceeds the present value of future cash flows. A minimum of $1.00 is
    applied to avoid unrealistic valuations below $1.
    """
    fcf = current_fcf
    present_value = 0.0
    
    # Project and discount future cash flows
    for year in range(1, projection_years + 1):
        fcf *= (1 + growth)
        present_value += fcf / ((1 + wacc) ** year)
    
    # Calculate terminal value
    spread = max(wacc - terminal_growth, 0.01)
    terminal_fcf = fcf * (1 + terminal_growth)
    terminal_value = terminal_fcf / spread
    present_value += terminal_value / ((1 + wacc) ** projection_years)
    
    # Calculate equity value (enterprise value minus net debt)
    equity_value = present_value - net_debt
    
    # Calculate per-share value with a floor of $1.00
    # (allows negative scenarios to show realistic low values)
    per_share_value = equity_value / shares_outstanding
    return max(per_share_value, 1.00)


def _deterministic_score(current_discount_pct: float) -> int:
    if current_discount_pct >= 40:
        return 10
    if current_discount_pct >= 25:
        return 8
    if current_discount_pct >= 10:
        return 7
    if current_discount_pct >= 0:
        return 6
    if current_discount_pct >= -10:
        return 5
    if current_discount_pct >= -20:
        return 3
    return 1


def calculate_multi_method_valuation_data(
    *,
    ticker: str,
    current_price: float,
    fundamentals: Dict[str, Any],
    statements_payload: Dict[str, Any],
    analyst_recommendations: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    balance_sheet_annual = _statement_reports(statements_payload, "balance_sheet", "annualReports")
    balance_sheet_quarterly = _statement_reports(statements_payload, "balance_sheet", "quarterlyReports")
    cashflow_annual = _statement_reports(statements_payload, "cashflow", "annualReports")
    cashflow_quarterly = _statement_reports(statements_payload, "cashflow", "quarterlyReports")
    income_annual = _statement_reports(statements_payload, "income_statement", "annualReports")

    shares_outstanding = _first_numeric(fundamentals, "SharesOutstanding")
    if shares_outstanding is None:
        shares_outstanding = _latest_numeric(balance_sheet_quarterly or balance_sheet_annual, "shareIssued", "ordinarySharesNumber")
    shares_outstanding = max(shares_outstanding or 1.0, 1.0)

    current_fcf = _latest_numeric(cashflow_annual, "freeCashFlow")
    if current_fcf is None:
        operating_cf = _latest_numeric(cashflow_annual, "operatingCashFlow")
        capex = _latest_numeric(cashflow_annual, "capitalExpenditure")
        if operating_cf is not None:
            current_fcf = operating_cf - abs(capex or 0.0)
    if current_fcf is None:
        quarterly_fcf = _sum_latest(cashflow_quarterly, "freeCashFlow", count=4)
        if quarterly_fcf is not None:
            current_fcf = quarterly_fcf
    if current_fcf is None:
        revenue_ttm = _first_numeric(fundamentals, "RevenueTTM") or _latest_numeric(income_annual, "totalRevenue") or 0.0
        profit_margin = _first_numeric(fundamentals, "ProfitMargin") or 0.15
        current_fcf = revenue_ttm * profit_margin * 0.9
    current_fcf = max(float(current_fcf), 0.0)

    revenue_growth = _first_numeric(fundamentals, "QuarterlyRevenueGrowthYOY")
    earnings_growth = _first_numeric(fundamentals, "QuarterlyEarningsGrowthYOY")
    revenue_cagr = _cagr(income_annual, "totalRevenue")
    earnings_cagr = _cagr(income_annual, "netIncome")
    growth_samples = [g for g in [revenue_growth, earnings_growth, revenue_cagr, earnings_cagr] if g is not None]
    base_growth = _clamp(sum(growth_samples) / len(growth_samples), 0.04, 0.18) if growth_samples else 0.08
    bear_growth = _clamp(base_growth - 0.05, 0.01, 0.16)
    bull_growth = _clamp(base_growth + 0.05, 0.06, 0.26)

    beta = _clamp(_first_numeric(fundamentals, "Beta") or 1.1, 0.8, 2.0)
    risk_free_rate = 0.045
    market_risk_premium = 0.055
    cost_of_equity = risk_free_rate + beta * market_risk_premium
    total_debt = _latest_numeric(balance_sheet_quarterly or balance_sheet_annual, "totalDebt", "longTermDebtAndCapitalLeaseObligation", "longTermDebt") or 0.0
    interest_expense = abs(_latest_numeric(income_annual, "interestExpense", "netInterestIncome") or 0.0)
    pretax_income = abs(_latest_numeric(income_annual, "pretaxIncome", "incomeBeforeTax") or 0.0)
    income_tax = abs(_latest_numeric(income_annual, "taxProvision", "incomeTaxExpense") or 0.0)
    tax_rate = _clamp((income_tax / pretax_income) if pretax_income > 0 else 0.15, 0.10, 0.25)
    cost_of_debt = _clamp((interest_expense / total_debt) if total_debt > 0 and interest_expense > 0 else 0.05, 0.03, 0.09)
    market_cap = _first_numeric(fundamentals, "MarketCapitalization") or (current_price * shares_outstanding)
    debt_weight = _clamp(total_debt / max(total_debt + market_cap, 1.0), 0.0, 0.35)
    wacc_base = _clamp((1 - debt_weight) * cost_of_equity + debt_weight * cost_of_debt * (1 - tax_rate), 0.08, 0.13)
    wacc_bear = _clamp(wacc_base + 0.01, 0.09, 0.14)
    wacc_bull = _clamp(wacc_base - 0.01, 0.07, 0.12)
    terminal_growth = {"bear": 0.02, "base": 0.03, "bull": 0.04}

    net_debt = _net_debt(fundamentals, balance_sheet_annual, balance_sheet_quarterly)
    dcf = {
        "bear": _discounted_cash_flow_value(current_fcf, bear_growth, wacc_bear, terminal_growth["bear"], net_debt, shares_outstanding),
        "base": _discounted_cash_flow_value(current_fcf, base_growth, wacc_base, terminal_growth["base"], net_debt, shares_outstanding),
        "bull": _discounted_cash_flow_value(current_fcf, bull_growth, wacc_bull, terminal_growth["bull"], net_debt, shares_outstanding),
    }

    eps = _first_numeric(fundamentals, "EPS")
    if eps is None:
        net_income = _latest_numeric(income_annual, "netIncome")
        if net_income is not None and shares_outstanding > 0:
            eps = net_income / shares_outstanding
    eps = max(eps or 0.01, 0.01)
    trailing_pe = _first_numeric(fundamentals, "TrailingPE") or (current_price / eps if eps > 0 else None)
    forward_pe = _first_numeric(fundamentals, "ForwardPE")
    analyst_recommendations = analyst_recommendations or {}
    price_targets = (analyst_recommendations.get("price_targets") or {}) if isinstance(analyst_recommendations, dict) else {}
    target_low = _safe_float(price_targets.get("low"))
    target_avg = _safe_float(price_targets.get("average"))
    target_high = _safe_float(price_targets.get("high"))
    forward_eps = (current_price / forward_pe) if forward_pe and forward_pe > 0 else eps * (1 + base_growth)
    forward_eps = max(forward_eps, 0.01)
    implied_target_pe_low = (target_low / forward_eps) if target_low and target_low > 0 else None
    implied_target_pe_avg = (target_avg / forward_eps) if target_avg and target_avg > 0 else None
    implied_target_pe_high = (target_high / forward_eps) if target_high and target_high > 0 else None
    base_pe = median([v for v in [forward_pe, trailing_pe, implied_target_pe_avg] if v is not None]) if any(v is not None for v in [forward_pe, trailing_pe, implied_target_pe_avg]) else 20.0
    bear_pe = median([v for v in [base_pe * 0.85, implied_target_pe_low] if v is not None])
    bull_pe = median([v for v in [base_pe * 1.15, implied_target_pe_high] if v is not None])
    pe_comps = {
        "bear": max(forward_eps * bear_pe, 0.01),
        "base": max(forward_eps * base_pe, 0.01),
        "bull": max(forward_eps * bull_pe, 0.01),
    }

    ebitda = _first_numeric(fundamentals, "EBITDA") or _latest_numeric(income_annual, "ebitda")
    ebitda = max(ebitda or (current_fcf / 0.75 if current_fcf > 0 else 1.0), 1.0)
    current_ev_to_ebitda = _first_numeric(fundamentals, "EVToEBITDA")
    if current_ev_to_ebitda is None:
        enterprise_value = _first_numeric(fundamentals, "EnterpriseValue")
        if enterprise_value is not None and ebitda > 0:
            current_ev_to_ebitda = enterprise_value / ebitda
    current_ev_to_ebitda = max(current_ev_to_ebitda or 14.0, 1.0)
    implied_ev_mult_low = ((target_low * shares_outstanding + net_debt) / ebitda) if target_low and ebitda > 0 else None
    implied_ev_mult_avg = ((target_avg * shares_outstanding + net_debt) / ebitda) if target_avg and ebitda > 0 else None
    implied_ev_mult_high = ((target_high * shares_outstanding + net_debt) / ebitda) if target_high and ebitda > 0 else None
    base_ev_mult = median([v for v in [current_ev_to_ebitda, implied_ev_mult_avg] if v is not None])
    bear_ev_mult = median([v for v in [base_ev_mult * 0.85, implied_ev_mult_low] if v is not None])
    bull_ev_mult = median([v for v in [base_ev_mult * 1.15, implied_ev_mult_high] if v is not None])
    ev_ebitda = {
        "bear": max(((ebitda * bear_ev_mult) - net_debt) / shares_outstanding, 0.01),
        "base": max(((ebitda * base_ev_mult) - net_debt) / shares_outstanding, 0.01),
        "bull": max(((ebitda * bull_ev_mult) - net_debt) / shares_outstanding, 0.01),
    }

    valuation_summary = calculate_valuation_summary(dcf=dcf, pe_comps=pe_comps, ev_ebitda=ev_ebitda)
    fair_value_bear = valuation_summary["weighted_avg"]["bear"]
    fair_value_base = valuation_summary["weighted_avg"]["base"]
    fair_value_bull = valuation_summary["weighted_avg"]["bull"]
    current_discount_pct = ((fair_value_base - current_price) / fair_value_base * 100.0) if fair_value_base > 0 else 0.0
    base_values = [dcf["base"], pe_comps["base"], ev_ebitda["base"]]
    dispersion = (pstdev(base_values) / max(sum(base_values) / len(base_values), 1e-9)) if len(base_values) >= 2 else 0.0
    valuation_conviction = "high" if dispersion < 0.12 else "medium" if dispersion < 0.25 else "low"
    valuation_score = _deterministic_score(current_discount_pct)
    valuation_bridge = _build_valuation_bridge(
        current_price=current_price,
        fair_value_base=fair_value_base,
        dcf_base=dcf["base"],
        pe_comps_base=pe_comps["base"],
        ev_ebitda_base=ev_ebitda["base"],
    )
    valuation_sensitivity = _build_sensitivity_analysis(
        current_fcf=current_fcf,
        base_growth=base_growth,
        wacc_base=wacc_base,
        terminal_growth_base=terminal_growth["base"],
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
        pe_comps_base=pe_comps["base"],
        ev_ebitda_base=ev_ebitda["base"],
        dcf_base=dcf["base"],
        base_ev_multiple=base_ev_mult,
        ebitda=ebitda,
    )

    return {
        "ticker": ticker.upper(),
        "current_price": current_price,
        "dcf": dcf,
        "pe_comps": pe_comps,
        "ev_ebitda": ev_ebitda,
        "valuation_summary": valuation_summary,
        "fair_value_bear": fair_value_bear,
        "fair_value_base": fair_value_base,
        "fair_value_bull": fair_value_bull,
        "current_discount_pct": current_discount_pct,
        "valuation_score": valuation_score,
        "valuation_conviction": valuation_conviction,
        "valuation_bridge": valuation_bridge,
        "valuation_sensitivity": valuation_sensitivity,
        "valuation_key_assumptions": [
            f"FCF growth: bear {bear_growth*100:.1f}%, base {base_growth*100:.1f}%, bull {bull_growth*100:.1f}%",
            f"WACC: bear {wacc_bear*100:.1f}%, base {wacc_base*100:.1f}%, bull {wacc_bull*100:.1f}%",
            f"Terminal growth: bear {terminal_growth['bear']*100:.1f}%, base {terminal_growth['base']*100:.1f}%, bull {terminal_growth['bull']*100:.1f}%",
            f"Forward EPS used for P/E comps: {forward_eps:.2f}",
            f"Base EV/EBITDA multiple: {base_ev_mult:.2f}x",
        ],
        "inputs": {
            "shares_outstanding": shares_outstanding,
            "current_fcf": current_fcf,
            "net_debt": net_debt,
            "eps": eps,
            "ebitda": ebitda,
            "analyst_price_targets": {"low": target_low, "average": target_avg, "high": target_high},
        },
    }


def calculate_valuation_summary(
    dcf: Dict[str, float],
    pe_comps: Dict[str, float],
    ev_ebitda: Dict[str, float],
    method_weights: Optional[Dict[str, float]] = None,
    scenario_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Compute valuation table figures deterministically from method scenario values."""
    method_weights = method_weights or DEFAULT_METHOD_WEIGHTS
    scenario_weights = scenario_weights or DEFAULT_SCENARIO_WEIGHTS
    methods = {
        "DCF": dcf,
        "P/E Comps": pe_comps,
        "EV/EBITDA": ev_ebitda,
    }

    rows = []
    for method_name, scenarios in methods.items():
        implied_value = sum(
            float(scenarios[scenario]) * float(scenario_weights[scenario])
            for scenario in ("bear", "base", "bull")
        )
        rows.append({
            "method": method_name,
            "bear": float(scenarios["bear"]),
            "base": float(scenarios["base"]),
            "bull": float(scenarios["bull"]),
            "weight": float(method_weights[method_name]),
            "implied_value": implied_value,
        })

    weighted_avg = {
        "bear": sum(row["bear"] * row["weight"] for row in rows),
        "base": sum(row["base"] * row["weight"] for row in rows),
        "bull": sum(row["bull"] * row["weight"] for row in rows),
        "weight": sum(row["weight"] for row in rows),
        "implied_value": sum(row["implied_value"] * row["weight"] for row in rows),
    }

    return {
        "method_weights": method_weights,
        "scenario_weights": scenario_weights,
        "rows": rows,
        "weighted_avg": weighted_avg,
    }


@tool
def calculate_valuation_summary_table(
    dcf_bear: Annotated[float, "DCF bear-case fair value per share"],
    dcf_base: Annotated[float, "DCF base-case fair value per share"],
    dcf_bull: Annotated[float, "DCF bull-case fair value per share"],
    pe_comps_bear: Annotated[float, "P/E comps bear-case fair value per share"],
    pe_comps_base: Annotated[float, "P/E comps base-case fair value per share"],
    pe_comps_bull: Annotated[float, "P/E comps bull-case fair value per share"],
    ev_ebitda_bear: Annotated[float, "EV/EBITDA bear-case fair value per share"],
    ev_ebitda_base: Annotated[float, "EV/EBITDA base-case fair value per share"],
    ev_ebitda_bull: Annotated[float, "EV/EBITDA bull-case fair value per share"],
) -> str:
    """
    Deterministically compute the valuation summary table.

    Fixed method weights:
    - DCF: 40%
    - P/E Comps: 30%
    - EV/EBITDA: 30%

    Fixed scenario weights for each method's implied value:
    - Bear: 25%
    - Base: 50%
    - Bull: 25%
    """
    result = calculate_valuation_summary(
        dcf={"bear": dcf_bear, "base": dcf_base, "bull": dcf_bull},
        pe_comps={"bear": pe_comps_bear, "base": pe_comps_base, "bull": pe_comps_bull},
        ev_ebitda={"bear": ev_ebitda_bear, "base": ev_ebitda_base, "bull": ev_ebitda_bull},
    )
    return json.dumps(result, indent=2)


@tool
def get_peer_comparables(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[Optional[str], "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve deterministic peer comparable valuation multiples (P/E, EV/EBITDA, P/S)
    for a given ticker using a local ticker universe and real fundamentals.
    """
    require_info_service()
    ticker_upper = ticker.upper()

    fundamentals_payload = _json_loads_maybe(get_fundamentals_via_service(ticker_upper))
    fundamentals = fundamentals_payload.get("fundamentals") or {}
    company_profile = _extract_company_profile(fundamentals_payload)

    target_sector = _normalize_text(
        company_profile.get("sector") or fundamentals.get("Sector") or fundamentals.get("sector")
    )
    target_industry = _normalize_text(
        company_profile.get("industry") or fundamentals.get("Industry") or fundamentals.get("industry")
    )
    target_name = _normalize_text(
        company_profile.get("name") or company_profile.get("company_name") or fundamentals.get("Name") or ticker_upper
    )

    company_entry = _peer_metric_entry(
        ticker=ticker_upper,
        name=target_name,
        sector=target_sector,
        industry=target_industry,
        fundamentals=fundamentals if isinstance(fundamentals, dict) else {},
    )

    universe = _load_stocks_universe()
    candidate_universe = []
    for item in universe:
        if not isinstance(item, dict):
            continue
        candidate_ticker = _normalize_upper(item.get("ticker"))
        candidate_name = _normalize_text(item.get("name"))
        candidate_sector = _normalize_text(item.get("sector"))
        candidate_industry = _normalize_text(item.get("industry"))
        if not candidate_ticker or candidate_ticker == ticker_upper:
            continue
        if not _is_candidate_ticker_allowed(candidate_ticker, candidate_name):
            continue
        if target_industry and candidate_industry.casefold() == target_industry.casefold():
            candidate_universe.append(item)
        elif target_sector and candidate_sector.casefold() == target_sector.casefold():
            candidate_universe.append(item)

    ranked_candidates = []
    for item in candidate_universe:
        candidate_ticker = _normalize_upper(item.get("ticker"))
        candidate_name = _normalize_text(item.get("name"))
        candidate_sector = _normalize_text(item.get("sector"))
        candidate_industry = _normalize_text(item.get("industry"))
        candidate_payload = _json_loads_maybe(get_fundamentals_via_service(candidate_ticker))
        candidate_fundamentals = candidate_payload.get("fundamentals") or {}
        candidate_profile = _extract_company_profile(candidate_payload)
        candidate_entry = _peer_metric_entry(
            ticker=candidate_ticker,
            name=candidate_profile.get("name") or candidate_name or candidate_ticker,
            sector=candidate_profile.get("sector") or candidate_sector,
            industry=candidate_profile.get("industry") or candidate_industry,
            fundamentals=candidate_fundamentals if isinstance(candidate_fundamentals, dict) else {},
        )
        if candidate_entry is None:
            continue
        ranked_candidates.append(candidate_entry)

    ranked_candidates.sort(
        key=lambda item: _candidate_rank(
            item.get("sector", ""),
            item.get("industry", ""),
            target_sector,
            target_industry,
            int(item.get("valid_metric_count") or 0),
        ),
        reverse=True,
    )
    selected_peers = ranked_candidates[:3]

    result = {
        "ticker": ticker_upper,
        "company": company_entry or {
            "ticker": ticker_upper,
            "name": target_name or ticker_upper,
            "sector": target_sector,
            "industry": target_industry,
            "metrics": {
                "pe_ratio": _first_numeric(fundamentals, "ForwardPE", "TrailingPE"),
                "ev_to_ebitda": _first_numeric(fundamentals, "EVToEBITDA"),
                "price_to_sales": _first_numeric(fundamentals, "PriceToSalesRatioTTM", "PriceToSalesTrailing12Months"),
                "growth": _first_numeric(fundamentals, "QuarterlyRevenueGrowthYOY", "QuarterlyEarningsGrowthYOY"),
                "margin": _first_numeric(fundamentals, "OperatingMarginTTM", "ProfitMargin"),
            },
        },
        "selection_context": {
            "target_sector": target_sector or None,
            "target_industry": target_industry or None,
            "peer_target_count": 3,
            "selected_peer_count": len(selected_peers),
            "selection_policy": "same_industry_first_then_same_sector",
            "note": (
                "Fewer than 3 valid peers were found; report should state the peer set is limited."
                if len(selected_peers) < 3
                else "Peer set satisfied the minimum target."
            ),
        },
        "peers": selected_peers,
        "peer_averages": {
            "pe_ratio": _average_metric(selected_peers, "pe_ratio"),
            "ev_to_ebitda": _average_metric(selected_peers, "ev_to_ebitda"),
            "price_to_sales": _average_metric(selected_peers, "price_to_sales"),
            "growth": _average_metric(selected_peers, "growth"),
            "margin": _average_metric(selected_peers, "margin"),
        },
    }

    return json.dumps(result, indent=2)


@tool
def get_growth_estimates(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[Optional[str], "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve analyst consensus growth estimates for revenue, earnings, and other key metrics.
    Includes historical growth rates and forward projections.
    
    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date you are trading at, yyyy-mm-dd (optional)
    
    Returns:
        str: JSON containing growth estimates and historical growth rates
    """
    require_info_service()
    
    # Get fundamental data and financial statements
    fundamentals = get_fundamentals_via_service(ticker)
    income_data = get_financial_statements(ticker, statement_type="income_statement", freq="annual")
    
    result = {
        "ticker": ticker.upper(),
        "growth_estimates": {
            "revenue_growth_next_year": "Extract from analyst estimates",
            "revenue_growth_next_5y": "Extract from analyst estimates",
            "earnings_growth_next_year": "Extract from analyst estimates",
            "earnings_growth_next_5y": "Extract from analyst estimates",
        },
        "historical_growth": {
            "revenue_cagr_3y": "Calculate from income statements",
            "revenue_cagr_5y": "Calculate from income statements",
            "earnings_cagr_3y": "Calculate from income statements",
            "earnings_cagr_5y": "Calculate from income statements",
        },
        "raw_data": {
            "fundamentals": fundamentals,
            "income_statements": str(income_data) if income_data else "Not available",
        },
    }
    
    return json.dumps(result, indent=2)


@tool
def get_wacc_inputs(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[Optional[str], "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve inputs needed for WACC (Weighted Average Cost of Capital) calculation:
    - Beta (systematic risk)
    - Risk-free rate (10-year Treasury yield)
    - Market risk premium
    - Cost of debt
    - Debt-to-equity ratio
    
    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date you are trading at, yyyy-mm-dd (optional)
    
    Returns:
        str: JSON containing WACC calculation inputs
    """
    require_info_service()
    
    # Get fundamental data and balance sheet
    fundamentals = get_fundamentals_via_service(ticker)
    balance_sheet = get_financial_statements(ticker, statement_type="balance_sheet", freq="quarterly")
    
    result = {
        "ticker": ticker.upper(),
        "wacc_inputs": {
            "beta": "Extract from fundamentals (typically 5-year beta)",
            "risk_free_rate": "Current 10-year Treasury yield (e.g., 4.5%)",
            "market_risk_premium": "Historical average ~7-8%",
            "cost_of_debt": "Calculate from interest expense / total debt",
            "tax_rate": "Effective tax rate from income statement",
            "debt_to_equity": "Calculate from balance sheet",
            "market_cap": "Extract from fundamentals",
            "total_debt": "Extract from balance sheet",
        },
        "calculated_wacc": "To be calculated: (E/V * Re) + (D/V * Rd * (1-Tc))",
        "raw_data": {
            "fundamentals": fundamentals,
            "balance_sheet": str(balance_sheet) if balance_sheet else "Not available",
        },
    }
    
    return json.dumps(result, indent=2)


@tool
def get_dcf_inputs(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[Optional[str], "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve all inputs needed for DCF (Discounted Cash Flow) valuation:
    - Free cash flow (historical and projected)
    - Growth rates
    - Terminal growth rate
    - WACC
    - Shares outstanding
    
    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date you are trading at, yyyy-mm-dd (optional)
    
    Returns:
        str: JSON containing DCF model inputs
    """
    require_info_service()
    
    # Get all necessary financial data
    fundamentals = get_fundamentals_via_service(ticker)
    cashflow = get_financial_statements(ticker, statement_type="cashflow", freq="annual")
    income = get_financial_statements(ticker, statement_type="income_statement", freq="annual")
    balance_sheet = get_financial_statements(ticker, statement_type="balance_sheet", freq="quarterly")
    
    result = {
        "ticker": ticker.upper(),
        "dcf_inputs": {
            "current_fcf": "Calculate: Operating CF - CapEx",
            "fcf_growth_rate": "Use analyst estimates or historical average",
            "projection_years": 5,
            "terminal_growth_rate": "Typically 2-3% (GDP growth)",
            "wacc": "Calculate using get_wacc_inputs",
            "shares_outstanding": "Extract from fundamentals",
            "net_debt": "Total Debt - Cash",
        },
        "historical_fcf": {
            "note": "Calculate from cashflow statements",
            "years": "Last 3-5 years",
        },
        "raw_data": {
            "fundamentals": fundamentals,
            "cashflow": str(cashflow) if cashflow else "Not available",
            "income": str(income) if income else "Not available",
            "balance_sheet": str(balance_sheet) if balance_sheet else "Not available",
        },
    }
    
    return json.dumps(result, indent=2)


@tool
def calculate_multi_method_valuation(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[Optional[str], "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Deterministically calculate DCF, P/E comps, and EV/EBITDA scenario values for a ticker.

    This is the authoritative tool for valuation method outputs used in the report.
    """
    require_info_service()
    ticker_upper = ticker.upper()
    fundamentals_payload = _json_loads_maybe(get_fundamentals_via_service(ticker_upper))
    fundamentals = fundamentals_payload.get("fundamentals") or {}
    quote = get_quote(ticker_upper) or {}
    current_price = _safe_float(quote.get("current_price"))
    if current_price is None:
        current_price = _first_numeric(fundamentals, "AnalystTargetPrice")
    if current_price is None or current_price <= 0:
        return json.dumps({"ticker": ticker_upper, "error": "Unable to determine current price for valuation"}, indent=2)

    statements_payload = get_financial_statements(ticker_upper, statement_type="all", freq="annual") or {}
    recommendations = get_analyst_recommendations(ticker_upper) or {}

    result = calculate_multi_method_valuation_data(
        ticker=ticker_upper,
        current_price=current_price,
        fundamentals=fundamentals if isinstance(fundamentals, dict) else {},
        statements_payload=statements_payload if isinstance(statements_payload, dict) else {},
        analyst_recommendations=recommendations if isinstance(recommendations, dict) else {},
    )
    return json.dumps(result, indent=2)

# Made with Bob
