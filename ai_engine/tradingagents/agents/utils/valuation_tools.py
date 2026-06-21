"""
Valuation tools for calculating fair value using multiple methods.
"""

from langchain_core.tools import tool
from typing import Annotated, Optional, Dict, Any, List
import json
import logging
import math
import re
from pathlib import Path
from statistics import median, pstdev

logger = logging.getLogger(__name__)

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

_INDEX_ETF_NAME_KEYWORDS = (
    " ETF",
    " ETN",
    " INDEX FUND",
    " MUTUAL FUND",
    " EXCHANGE TRADED FUND",
    " SPDR",
    " ISHARES",
    " PROSHARES",
    " DIREXION",
)

_INDEX_ETF_FIELD_VALUES = {
    "ETF",
    "ETN",
    "INDEX",
    "INDEX FUND",
    "MUTUAL FUND",
    "MUTUALFUND",
    "EXCHANGE TRADED FUND",
    "EXCHANGETRADED FUND",
    "EXCHANGETRADEDFUND",
}


def _weighted_base_value(
    dcf_base: float,
    pe_comps_base: float,
    ev_ebitda_base: float,
    method_weights: Optional[Dict[str, float]] = None,
) -> float:
    method_weights = method_weights or DEFAULT_METHOD_WEIGHTS
    return (
        dcf_base * method_weights["DCF"]
        + pe_comps_base * method_weights["P/E Comps"]
        + ev_ebitda_base * method_weights["EV/EBITDA"]
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


def _contains_keyword_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    if not text:
        return False
    padded = f" {text} "
    return any(re.search(rf"(?<![A-Z0-9]){re.escape(phrase.strip())}(?![A-Z0-9])", padded) for phrase in phrases)


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
    geography_penalty: float = 1.0,
) -> tuple[int, int, float]:
    """
    Rank peer candidates for selection.
    
    Returns tuple for sorting (higher is better):
    - same_industry (1 or 0): Highest priority
    - same_sector (1 or 0): Second priority
    - adjusted_metric_count (float): Third priority, adjusted for geography
    """
    same_industry = int(
        bool(candidate_industry and target_industry and candidate_industry.casefold() == target_industry.casefold())
    )
    same_sector = int(
        bool(candidate_sector and target_sector and candidate_sector.casefold() == target_sector.casefold())
    )
    # Apply geography penalty to metric count for ranking
    adjusted_metric_count = valid_metric_count * geography_penalty
    return (same_industry, same_sector, adjusted_metric_count)


def _average_metric(entries: list[Dict[str, Any]], metric_name: str) -> Optional[float]:
    values = []
    for entry in entries:
        metric_value = _safe_float(((entry or {}).get("metrics") or {}).get(metric_name))
        if metric_value is not None and metric_value > 0:
            values.append(metric_value)
    if not values:
        return None
    return sum(values) / len(values)


def _is_index_or_etf(fundamentals: Dict[str, Any]) -> bool:
    profile = _extract_company_profile(fundamentals)
    candidates = [
        fundamentals.get("QuoteType"),
        fundamentals.get("AssetType"),
        fundamentals.get("SecurityType"),
        fundamentals.get("InstrumentType"),
        fundamentals.get("Category"),
        fundamentals.get("FundFamily"),
        profile.get("quoteType"),
        profile.get("assetType"),
        profile.get("securityType"),
        profile.get("instrumentType"),
        profile.get("category"),
    ]
    for value in candidates:
        normalized = _normalize_upper(value)
        if not normalized:
            continue
        compact = normalized.replace(" ", "")
        if normalized in _INDEX_ETF_FIELD_VALUES or compact in _INDEX_ETF_FIELD_VALUES:
            return True

    name_candidates = [
        fundamentals.get("Name"),
        fundamentals.get("name"),
        profile.get("name"),
        profile.get("longName"),
        profile.get("shortName"),
    ]
    normalized_name = " ".join(_normalize_upper(value) for value in name_candidates if value)
    return _contains_keyword_phrase(normalized_name, _INDEX_ETF_NAME_KEYWORDS)


def _build_index_etf_valuation(
    *,
    ticker: str,
    current_price: float,
    fundamentals: Dict[str, Any],
    analyst_recommendations: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    analyst_recommendations = analyst_recommendations or {}
    profile = _extract_company_profile(fundamentals)
    name = (
        _normalize_text(fundamentals.get("Name"))
        or _normalize_text(profile.get("longName"))
        or _normalize_text(profile.get("shortName"))
        or ticker.upper()
    )
    quote_type = (
        _normalize_text(fundamentals.get("QuoteType"))
        or _normalize_text(fundamentals.get("AssetType"))
        or _normalize_text(profile.get("quoteType"))
        or "ETF/Index"
    )

    trailing_pe = _first_numeric(fundamentals, "TrailingPE")
    forward_pe = _first_numeric(fundamentals, "ForwardPE")
    price_to_book = _first_numeric(fundamentals, "PriceToBookRatio", "PriceToBookRatioTTM", "PriceToBook")
    ev_to_ebitda = _first_numeric(fundamentals, "EVToEBITDA")
    beta = _clamp(_first_numeric(fundamentals, "Beta") or 1.0, 0.7, 2.0)
    risk_free_rate = _get_current_risk_free_rate()
    market_risk_premium = _get_market_risk_premium()

    price_targets = (analyst_recommendations.get("price_targets") or {}) if isinstance(analyst_recommendations, dict) else {}
    target_low = _safe_float(price_targets.get("low"))
    target_avg = _safe_float(price_targets.get("average"))
    target_high = _safe_float(price_targets.get("high"))

    methods: Dict[str, Dict[str, float]] = {}
    method_weights: Dict[str, float] = {}

    if forward_pe or trailing_pe:
        base_pe = forward_pe or trailing_pe or 18.0
        fair_pe = 18.0 if risk_free_rate >= 0.04 else 20.0
        ratio = fair_pe / max(base_pe, 1.0)
        pe_base = max(current_price * ratio, 0.01)
        methods["P/E Regime"] = {
            "bear": max(pe_base * 0.90, 0.01),
            "base": pe_base,
            "bull": max(pe_base * 1.10, 0.01),
        }
        method_weights["P/E Regime"] = 1.0 + (0.15 if forward_pe else 0.0)

    if price_to_book:
        fair_pb = 3.0 if beta > 1.1 else 2.4
        ratio = fair_pb / max(price_to_book, 0.1)
        pb_base = max(current_price * ratio, 0.01)
        methods["P/B Regime"] = {
            "bear": max(pb_base * 0.92, 0.01),
            "base": pb_base,
            "bull": max(pb_base * 1.08, 0.01),
        }
        method_weights["P/B Regime"] = 0.8

    if ev_to_ebitda:
        fair_ev_ebitda = 13.0 if risk_free_rate >= 0.04 else 15.0
        ratio = fair_ev_ebitda / max(ev_to_ebitda, 1.0)
        ev_base = max(current_price * ratio, 0.01)
        methods["EV/EBITDA Regime"] = {
            "bear": max(ev_base * 0.90, 0.01),
            "base": ev_base,
            "bull": max(ev_base * 1.10, 0.01),
        }
        method_weights["EV/EBITDA Regime"] = 0.9

    if target_avg:
        methods["Market Target"] = {
            "bear": max(target_low or (target_avg * 0.92), 0.01),
            "base": max(target_avg, 0.01),
            "bull": max(target_high or (target_avg * 1.08), 0.01),
        }
        method_weights["Market Target"] = 0.7

    if not methods:
        methods["Price Regime"] = {
            "bear": current_price * 0.92,
            "base": current_price,
            "bull": current_price * 1.08,
        }
        method_weights["Price Regime"] = 1.0

    total_weight = sum(method_weights.values()) or 1.0
    normalized_weights = {method: weight / total_weight for method, weight in method_weights.items()}

    rows = []
    for method_name, scenarios in methods.items():
        implied_value = sum(
            float(scenarios[scenario]) * float(DEFAULT_SCENARIO_WEIGHTS[scenario])
            for scenario in ("bear", "base", "bull")
        )
        rows.append({
            "method": method_name,
            "bear": float(scenarios["bear"]),
            "base": float(scenarios["base"]),
            "bull": float(scenarios["bull"]),
            "weight": float(normalized_weights[method_name]),
            "implied_value": implied_value,
        })

    weighted_avg = {
        "bear": sum(row["bear"] * row["weight"] for row in rows),
        "base": sum(row["base"] * row["weight"] for row in rows),
        "bull": sum(row["bull"] * row["weight"] for row in rows),
        "weight": sum(row["weight"] for row in rows),
        "implied_value": sum(row["implied_value"] * row["weight"] for row in rows),
    }
    valuation_summary = {
        "method_weights": normalized_weights,
        "scenario_weights": DEFAULT_SCENARIO_WEIGHTS,
        "rows": rows,
        "weighted_avg": weighted_avg,
    }

    fair_value_bear = weighted_avg["bear"]
    fair_value_base = weighted_avg["base"]
    fair_value_bull = weighted_avg["bull"]
    current_discount_pct = ((fair_value_base - current_price) / fair_value_base * 100.0) if fair_value_base > 0 else 0.0

    base_values = [row["base"] for row in rows]
    dispersion = (pstdev(base_values) / max(sum(base_values) / len(base_values), 1e-9)) if len(base_values) >= 2 else 0.0
    valuation_conviction = "high" if dispersion < 0.10 else "medium" if dispersion < 0.20 else "low"
    valuation_score = _deterministic_score(current_discount_pct, valuation_conviction)

    valuation_bridge = {
        "current_price": current_price,
        "growth_premium": 0.0,
        "multiple_expansion": max(fair_value_base - current_price, 0.0),
        "risk_discount": max(current_price - fair_value_base, 0.0),
        "fair_value": fair_value_base,
    }
    valuation_sensitivity = {
        "fcf_growth_rate": {"delta": 0.0, "low": fair_value_base, "high": fair_value_base},
        "wacc": {
            "delta": round(0.005 + (0.005 * abs(beta - 1.0)), 4),
            "low": fair_value_base * 0.97,
            "high": fair_value_base * 1.03,
        },
        "terminal_growth": {"delta": 0.0, "low": fair_value_base, "high": fair_value_base},
        "exit_multiple": {"delta": 0.0, "low": fair_value_bear, "high": fair_value_bull},
    }

    key_assumptions = [
        f"Instrument type: {quote_type} - aggregate valuation regime analysis used instead of single-company intrinsic DCF",
        f"Rates context: risk-free {risk_free_rate*100:.2f}%, market risk premium {market_risk_premium*100:.2f}%",
        f"Method weights: " + ", ".join(f"{method} {normalized_weights[method]*100:.1f}%" for method in normalized_weights),
    ]
    if forward_pe or trailing_pe:
        key_assumptions.append(
            f"P/E inputs: trailing {trailing_pe:.2f}x, forward {forward_pe:.2f}x; fair band anchored near {'18.0x' if risk_free_rate >= 0.04 else '20.0x'}"
            if trailing_pe is not None and forward_pe is not None
            else f"P/E input: {(forward_pe if forward_pe is not None else trailing_pe):.2f}x"
        )
    if price_to_book:
        key_assumptions.append(f"Price/book input: {price_to_book:.2f}x")
    if ev_to_ebitda:
        key_assumptions.append(f"EV/EBITDA input: {ev_to_ebitda:.2f}x")
    if target_avg:
        key_assumptions.append(
            f"Analyst target context: low {target_low:.2f}, average {target_avg:.2f}, high {target_high:.2f}"
            if target_low is not None and target_high is not None
            else f"Analyst target context: average {target_avg:.2f}"
        )

    return {
        "ticker": ticker.upper(),
        "instrument_type": quote_type,
        "instrument_name": name,
        "current_price": current_price,
        "dcf": {"bear": 0.0, "base": 0.0, "bull": 0.0},
        "pe_comps": methods.get("P/E Regime", methods.get("Price Regime", {"bear": 0.0, "base": 0.0, "bull": 0.0})),
        "ev_ebitda": methods.get("EV/EBITDA Regime", methods.get("Market Target", {"bear": 0.0, "base": 0.0, "bull": 0.0})),
        "valuation_summary": valuation_summary,
        "fair_value_bear": fair_value_bear,
        "fair_value_base": fair_value_base,
        "fair_value_bull": fair_value_bull,
        "current_discount_pct": current_discount_pct,
        "valuation_score": valuation_score,
        "valuation_conviction": valuation_conviction,
        "valuation_bridge": valuation_bridge,
        "valuation_sensitivity": valuation_sensitivity,
        "valuation_key_assumptions": key_assumptions,
        "inputs": {
            "quote_type": quote_type,
            "trailing_pe": trailing_pe,
            "forward_pe": forward_pe,
            "price_to_book": price_to_book,
            "ev_to_ebitda": ev_to_ebitda,
            "beta": beta,
            "analyst_price_targets": {"low": target_low, "average": target_avg, "high": target_high},
            "valuation_mode": "index_etf_relative",
        },
    }


def _build_valuation_bridge(
    current_price: float,
    fair_value_base: float,
    dcf_base: float,
    pe_comps_base: float,
    ev_ebitda_base: float,
    method_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """
    Build valuation bridge attributing price gap to growth, multiples, and risk.
    
    Attribution logic:
    - Growth premium: DCF value above current price (future cash flow value)
    - Multiple expansion: Comps value above current price (peer re-rating potential)
    - Risk discount: Difference between methods (uncertainty/risk premium)
    """
    method_weights = method_weights or DEFAULT_METHOD_WEIGHTS
    avg_comps_base = (pe_comps_base + ev_ebitda_base) / 2.0
    total_gap = fair_value_base - current_price

    # Handle overvalued case (negative gap)
    if total_gap <= 0:
        return {
            "current_price": current_price,
            "growth_premium": 0.0,
            "multiple_expansion": 0.0,
            "risk_discount": abs(total_gap),  # Premium being paid
            "fair_value": fair_value_base,
        }

    # Calculate actual contributions from each method
    dcf_contribution = max(dcf_base - current_price, 0.0)
    comps_contribution = max(avg_comps_base - current_price, 0.0)
    
    # Determine which driver is dominant
    if dcf_base > avg_comps_base:
        # DCF-driven: Growth is the primary driver
        # Growth premium = DCF upside
        growth_premium = dcf_contribution
        
        # Multiple expansion = additional comps upside
        multiple_expansion = comps_contribution
        
        # Risk discount = difference between weighted fair value and sum of components
        # This captures the discount applied when averaging methods
        implied_total = growth_premium + multiple_expansion
        risk_discount = max(implied_total - total_gap, 0.0)
        
    else:
        # Comps-driven: Multiple expansion is the primary driver
        # Multiple expansion = comps upside
        multiple_expansion = comps_contribution
        
        # Growth premium = additional DCF upside
        growth_premium = dcf_contribution
        
        # Risk discount = difference between weighted fair value and sum of components
        implied_total = growth_premium + multiple_expansion
        risk_discount = max(implied_total - total_gap, 0.0)
    
    # Handle edge case where components don't sum to gap
    # This happens when fair value is between current price and both methods
    if growth_premium + multiple_expansion < total_gap:
        # Distribute shortfall proportionally to method distances from current price
        shortfall = total_gap - (growth_premium + multiple_expansion)
        
        total_distance = dcf_contribution + comps_contribution
        if total_distance > 0:
            # Proportional allocation based on method contributions
            growth_weight = dcf_contribution / total_distance
            multiple_weight = comps_contribution / total_distance
            
            growth_premium += shortfall * growth_weight
            multiple_expansion += shortfall * multiple_weight
        else:
            # Equal split if no clear driver
            growth_premium += shortfall * 0.5
            multiple_expansion += shortfall * 0.5

    return {
        "current_price": current_price,
        "growth_premium": round(growth_premium, 2),
        "multiple_expansion": round(multiple_expansion, 2),
        "risk_discount": round(risk_discount, 2),
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
    beta: float = 1.0,
    growth_samples: Optional[list] = None,
    method_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Build sensitivity analysis with dynamic deltas based on actual uncertainty.
    
    Args:
        beta: Company beta for WACC uncertainty calculation
        growth_samples: List of growth rate samples for volatility calculation
    """
    method_weights = method_weights or DEFAULT_METHOD_WEIGHTS

    def weighted_from_dcf(dcf_value: float) -> float:
        return _weighted_base_value(dcf_value, pe_comps_base, ev_ebitda_base, method_weights)

    # Calculate dynamic growth delta based on historical volatility
    if growth_samples and len(growth_samples) >= 2:
        growth_std = pstdev(growth_samples)
        # Use 1 standard deviation for sensitivity (captures ~68% of outcomes)
        growth_delta = min(max(growth_std, 0.01), 0.05)  # Between 1% and 5%
    else:
        growth_delta = 0.02  # Fallback to 2%
    
    # Calculate dynamic WACC delta based on beta uncertainty
    # Higher beta = more systematic risk = more WACC uncertainty
    wacc_uncertainty = 0.005 + (0.005 * abs(beta - 1.0))  # 0.5% base + beta adjustment
    wacc_delta = min(wacc_uncertainty, 0.02)  # Cap at 2%
    
    # Terminal growth delta: smaller than FCF growth (more stable long-term)
    terminal_delta = 0.005  # 0.5% is reasonable for perpetual growth
    
    # Exit multiple delta: scale with current multiple (higher multiples = more volatility)
    exit_multiple_delta = max(base_ev_multiple * 0.15, 2.0)  # 15% of current or min 2x

    # Calculate sensitivity ranges
    fcf_low = _discounted_cash_flow_value(
        current_fcf=current_fcf,
        growth=base_growth - growth_delta,
        wacc=wacc_base,
        terminal_growth=terminal_growth_base,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )
    fcf_high = _discounted_cash_flow_value(
        current_fcf=current_fcf,
        growth=base_growth + growth_delta,
        wacc=wacc_base,
        terminal_growth=terminal_growth_base,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )
    wacc_low = _discounted_cash_flow_value(
        current_fcf=current_fcf,
        growth=base_growth,
        wacc=wacc_base - wacc_delta,
        terminal_growth=terminal_growth_base,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )
    wacc_high = _discounted_cash_flow_value(
        current_fcf=current_fcf,
        growth=base_growth,
        wacc=wacc_base + wacc_delta,
        terminal_growth=terminal_growth_base,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )
    tg_low = _discounted_cash_flow_value(
        current_fcf=current_fcf,
        growth=base_growth,
        wacc=wacc_base,
        terminal_growth=terminal_growth_base - terminal_delta,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )
    tg_high = _discounted_cash_flow_value(
        current_fcf=current_fcf,
        growth=base_growth,
        wacc=wacc_base,
        terminal_growth=terminal_growth_base + terminal_delta,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )
    exit_low_ev = max((((ebitda * (base_ev_multiple - exit_multiple_delta)) - net_debt) / shares_outstanding), 0.01)
    exit_high_ev = max((((ebitda * (base_ev_multiple + exit_multiple_delta)) - net_debt) / shares_outstanding), 0.01)

    return {
        "fcf_growth_rate": {
            "delta": round(growth_delta, 4),
            "low": min(weighted_from_dcf(fcf_low), weighted_from_dcf(fcf_high)),
            "high": max(weighted_from_dcf(fcf_low), weighted_from_dcf(fcf_high)),
        },
        "wacc": {
            "delta": round(wacc_delta, 4),
            "low": min(weighted_from_dcf(wacc_high), weighted_from_dcf(wacc_low)),
            "high": max(weighted_from_dcf(wacc_high), weighted_from_dcf(wacc_low)),
        },
        "terminal_growth": {
            "delta": round(terminal_delta, 4),
            "low": min(weighted_from_dcf(tg_low), weighted_from_dcf(tg_high)),
            "high": max(weighted_from_dcf(tg_low), weighted_from_dcf(tg_high)),
        },
        "exit_multiple": {
            "delta": round(exit_multiple_delta, 2),
            "low": _weighted_base_value(dcf_base, pe_comps_base, exit_low_ev, method_weights),
            "high": _weighted_base_value(dcf_base, pe_comps_base, exit_high_ev, method_weights),
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


def _normalize_fcf_for_growth_stage(
    current_fcf: float,
    operating_cf: float,
    capex: float,
    revenue: float,
    is_high_growth: bool = False,
) -> tuple[float, str]:
    """
    Normalize FCF for companies with negative cash flows due to growth investments.
    
    Returns:
        tuple: (normalized_fcf, explanation)
    """
    # If FCF is already positive, no normalization needed
    if current_fcf > 0:
        return current_fcf, "FCF is positive, no normalization needed"
    
    # Case 1: Negative FCF due to high CapEx (growth investments)
    if operating_cf > 0 and capex > operating_cf:
        # Use operating cash flow as proxy, assuming normalized CapEx
        normalized_capex = operating_cf * 0.15  # Assume 15% maintenance CapEx
        normalized_fcf = operating_cf - normalized_capex
        explanation = f"Normalized negative FCF (${current_fcf:,.0f}) by using operating CF (${operating_cf:,.0f}) with normalized CapEx (15% of OpCF)"
        return max(normalized_fcf, revenue * 0.05), explanation
    
    # Case 2: Negative operating cash flow (more concerning)
    if operating_cf <= 0:
        # For high-growth companies, estimate based on revenue
        if is_high_growth and revenue > 0:
            normalized_fcf = revenue * 0.08  # Assume 8% FCF margin at maturity
            explanation = f"High-growth company with negative OpCF. Estimated normalized FCF based on 8% of revenue (${revenue:,.0f})"
            return normalized_fcf, explanation
        else:
            # Conservative estimate for struggling companies
            normalized_fcf = max(revenue * 0.03, 1.0) if revenue > 0 else 1.0
            explanation = f"Negative operating cash flow. Using conservative 3% revenue estimate"
            return normalized_fcf, explanation
    
    # Case 3: Small negative FCF
    if current_fcf > -abs(revenue * 0.05):
        normalized_fcf = abs(current_fcf) * 0.5  # Assume temporary issue
        explanation = f"Small negative FCF, assuming temporary. Using 50% of absolute value"
        return max(normalized_fcf, 1.0), explanation
    
    # Default: use small positive value
    return max(revenue * 0.02, 1.0), "Unable to normalize, using 2% of revenue"


def _detect_growth_stage(
    revenue_growth: Optional[float],
    revenue_cagr: Optional[float],
    current_fcf: float,
    operating_cf: float,
) -> tuple[bool, int]:
    """
    Detect if company is in high-growth stage and determine appropriate projection period.
    
    Returns:
        tuple: (is_high_growth, recommended_projection_years)
    """
    # High growth indicators
    growth_rates = [g for g in [revenue_growth, revenue_cagr] if g is not None]
    avg_growth = sum(growth_rates) / len(growth_rates) if growth_rates else 0.0
    
    is_high_growth = (
        avg_growth > 0.20 or  # 20%+ growth
        (current_fcf < 0 and operating_cf > 0 and avg_growth > 0.15)  # Negative FCF but growing fast
    )
    
    # Determine projection period
    if is_high_growth:
        if avg_growth > 0.30:
            return True, 10  # Very high growth: 10-year projection
        else:
            return True, 7   # High growth: 7-year projection
    else:
        return False, 5  # Mature: standard 5-year projection


def _reverse_dcf_implied_growth(
    current_price: float,
    current_fcf: float,
    wacc: float,
    terminal_growth: float,
    net_debt: float,
    shares_outstanding: float,
    projection_years: int = 5,
) -> Optional[float]:
    """
    Calculate the implied growth rate given the current stock price (reverse DCF).
    
    This helps determine what growth rate the market is pricing in.
    """
    if current_fcf <= 0 or shares_outstanding <= 0:
        return None
    
    # Target enterprise value from current price
    target_equity_value = current_price * shares_outstanding
    target_enterprise_value = target_equity_value + net_debt
    
    # Binary search for implied growth rate
    low, high = -0.10, 0.50  # Search between -10% and 50% growth
    tolerance = 0.0001
    max_iterations = 100
    
    for _ in range(max_iterations):
        mid_growth = (low + high) / 2
        
        # Calculate PV with this growth rate
        fcf = current_fcf
        present_value = 0.0
        
        for year in range(1, projection_years + 1):
            fcf *= (1 + mid_growth)
            present_value += fcf / ((1 + wacc) ** year)
        
        # Terminal value
        spread = max(wacc - terminal_growth, 0.01)
        terminal_fcf = fcf * (1 + terminal_growth)
        terminal_value = terminal_fcf / spread
        present_value += terminal_value / ((1 + wacc) ** projection_years)
        
        # Check if we're close enough
        if abs(present_value - target_enterprise_value) < tolerance * target_enterprise_value:
            return mid_growth
        
        # Adjust search range
        if present_value < target_enterprise_value:
            low = mid_growth
        else:
            high = mid_growth
    
    # Return best estimate if didn't converge
    return (low + high) / 2


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
    Calculate DCF fair value per share with enhanced negative cash flow handling.
    
    This function properly handles negative cash flows by:
    1. Discounting negative flows (which reduces NPV)
    2. Allowing negative valuations when debt exceeds PV of cash flows
    3. Applying a floor of $1.00 to avoid unrealistic sub-dollar valuations
    
    Args:
        current_fcf: Current free cash flow (can be negative)
        growth: Expected FCF growth rate
        wacc: Weighted average cost of capital (discount rate)
        terminal_growth: Perpetual growth rate for terminal value
        net_debt: Net debt (total debt - cash)
        shares_outstanding: Number of shares outstanding
        projection_years: Number of years to project (default 5, use 7-10 for high-growth)
    
    Returns:
        Fair value per share (minimum $1.00)
    """
    fcf = current_fcf
    present_value = 0.0
    
    # Project and discount future cash flows (handles negative flows naturally)
    for year in range(1, projection_years + 1):
        fcf *= (1 + growth)
        # Negative cash flows are discounted just like positive ones
        # This reduces the total NPV appropriately
        present_value += fcf / ((1 + wacc) ** year)
    
    # Calculate terminal value
    # Only calculate if terminal FCF is positive
    spread = max(wacc - terminal_growth, 0.01)
    terminal_fcf = fcf * (1 + terminal_growth)
    
    if terminal_fcf > 0:
        terminal_value = terminal_fcf / spread
        present_value += terminal_value / ((1 + wacc) ** projection_years)
    else:
        # If still negative at terminal year, don't add terminal value
        # This is appropriate for companies that may not reach profitability
        pass
    
    # Calculate equity value (enterprise value minus net debt)
    equity_value = present_value - net_debt
    
    # Calculate per-share value with a floor of $1.00
    # This prevents unrealistic valuations below $1 while still showing
    # when a company is overvalued (negative equity value becomes $1)
    per_share_value = equity_value / shares_outstanding
    return max(per_share_value, 1.00)


def _deterministic_score(current_discount_pct: float, conviction: str = "medium") -> int:
    """
    Calculate valuation score based on discount/premium and conviction level.
    
    Args:
        current_discount_pct: Percentage discount (positive) or premium (negative)
        conviction: Conviction level ("high", "medium", "low")
    
    Returns:
        Score from 1-10
    """
    # Base score from discount/premium
    if current_discount_pct >= 40:
        base = 10
    elif current_discount_pct >= 25:
        base = 8
    elif current_discount_pct >= 10:
        base = 7
    elif current_discount_pct >= 0:
        base = 6
    elif current_discount_pct >= -10:
        base = 5
    elif current_discount_pct >= -20:
        base = 3
    else:
        base = 1
    
    # Adjust for conviction level
    if conviction == "low":
        # Reduce score for low conviction (more uncertainty)
        base = max(base - 1, 1)
    elif conviction == "high" and base >= 7:
        # Boost high conviction opportunities (but not overvalued stocks)
        base = min(base + 1, 10)
    
    return base


def _get_current_risk_free_rate() -> float:
    """
    Fetch current risk-free rate from market rates service.
    Falls back to reasonable default if service unavailable.
    """
    try:
        from ...datasources.info_service_client import get_market_rates
        rates = get_market_rates()
        if rates and rates.get("risk_free_rate"):
            return float(rates["risk_free_rate"])
    except Exception:
        pass
    # Fallback to reasonable default (will be logged by service)
    return 0.045


def _get_market_risk_premium() -> float:
    """
    Fetch current market risk premium based on VIX (volatility index).
    Falls back to historical average if service unavailable.
    
    Returns:
        Market risk premium as decimal (e.g., 0.055 for 5.5%)
    """
    try:
        from ...datasources.info_service_client import get_market_rates
        rates = get_market_rates()
        if rates and rates.get("market_risk_premium"):
            return float(rates["market_risk_premium"])
    except Exception:
        pass
    # Fallback to historical average
    return 0.055


def _calculate_terminal_growth(
    sector: Optional[str] = None,
    is_high_growth: bool = False,
    revenue_growth: Optional[float] = None
) -> Dict[str, float]:
    """
    Calculate terminal growth rate based on sector characteristics and company growth stage.
    
    Terminal growth represents the perpetual growth rate in the terminal value calculation
    and should reflect long-term sustainable growth considering:
    - Long-term GDP growth (~2.5% for US economy)
    - Sector-specific growth characteristics
    - Company maturity stage (high-growth companies may sustain higher terminal rates)
    
    Args:
        sector: Company sector (e.g., "Technology", "Healthcare")
        is_high_growth: Whether company is in high-growth stage
        revenue_growth: Recent revenue growth rate (as decimal)
    
    Returns:
        Dict with bear/base/bull terminal growth rates
    """
    # Base: Long-term US GDP growth
    base_gdp = 0.025  # 2.5%
    
    # Sector-specific adjustments based on long-term growth characteristics
    sector_adjustments = {
        "Utilities": -0.005,              # 2.0% - Regulated, mature, GDP-like
        "Consumer Staples": 0.000,        # 2.5% - Defensive, GDP-like growth
        "Industrials": 0.000,             # 2.5% - Cyclical but GDP-like long-term
        "Materials": 0.000,               # 2.5% - Commodity-driven, GDP-like
        "Financials": 0.002,              # 2.7% - Slight premium from financial deepening
        "Real Estate": 0.002,             # 2.7% - Population growth, urbanization
        "Energy": 0.003,                  # 2.8% - Global demand growth
        "Healthcare": 0.005,              # 3.0% - Aging demographics, innovation
        "Consumer Discretionary": 0.005,  # 3.0% - Economic growth, rising incomes
        "Technology": 0.010,              # 3.5% - Digital transformation, innovation
        "Communication Services": 0.008,  # 3.3% - Digital adoption, connectivity
    }
    
    sector_adj = sector_adjustments.get(sector, 0.0) if sector else 0.0
    base_terminal = base_gdp + sector_adj
    
    # Growth stage adjustment
    # High-growth companies (>20% revenue growth) that are expanding market share
    # may sustain above-sector terminal growth as they mature
    if is_high_growth and revenue_growth and revenue_growth > 0.20:
        # Add 0.5% premium for high-growth companies, capped at 4.0%
        # Rationale: Market leaders often sustain above-average growth long-term
        base_terminal = min(base_terminal + 0.005, 0.040)
    
    # Generate bear/base/bull scenarios with reasonable bounds
    return {
        "bear": max(base_terminal - 0.010, 0.015),  # -1.0%, minimum 1.5%
        "base": base_terminal,
        "bull": min(base_terminal + 0.010, 0.045)   # +1.0%, maximum 4.5%
    }


def _determine_dynamic_method_weights(
    *,
    sector: Optional[str],
    is_high_growth: bool,
    current_fcf: float,
    current_fcf_for_valuation: float,
    fcf_normalization_note: Optional[Dict[str, Any]],
    growth_samples: List[float],
    growth_data_source: List[str],
    eps: Optional[float],
    trailing_pe: Optional[float],
    forward_pe: Optional[float],
    ebitda: Optional[float],
    total_debt: float,
    market_cap: float,
    revenue_ttm: float,
) -> Dict[str, float]:
    scores = {
        "DCF": 1.0,
        "P/E Comps": 1.0,
        "EV/EBITDA": 1.0,
    }

    debt_ratio = total_debt / max(total_debt + market_cap, 1.0)
    fcf_margin = current_fcf / revenue_ttm if revenue_ttm > 0 else 0.0
    normalized_fcf_ratio = (
        current_fcf_for_valuation / max(abs(current_fcf), 1.0)
        if current_fcf < 0 else 1.0
    )
    sector_normalized = (sector or "").strip().lower()

    if current_fcf <= 0:
        scores["DCF"] *= 0.45
    elif fcf_margin < 0.05:
        scores["DCF"] *= 0.80
    else:
        scores["DCF"] *= 1.15

    if fcf_normalization_note:
        scores["DCF"] *= 0.75 if is_high_growth else 0.60
        if normalized_fcf_ratio > 2.0:
            scores["DCF"] *= 0.85

    if "FALLBACK_ESTIMATE" in growth_data_source:
        scores["DCF"] *= 0.75
    elif len(growth_samples) >= 3:
        scores["DCF"] *= 1.10
    elif len(growth_samples) == 1:
        scores["DCF"] *= 0.90

    if is_high_growth:
        scores["DCF"] *= 0.90
        scores["P/E Comps"] *= 0.85
        scores["EV/EBITDA"] *= 1.10

    if eps is None or eps <= 0:
        scores["P/E Comps"] = 0.05
    else:
        if trailing_pe is None and forward_pe is None:
            scores["P/E Comps"] *= 0.85
        if forward_pe is not None and forward_pe > 60:
            scores["P/E Comps"] *= 0.75
        elif forward_pe is not None and forward_pe < 8:
            scores["P/E Comps"] *= 0.90

    if ebitda is None or ebitda <= 0:
        scores["EV/EBITDA"] *= 0.35
    else:
        scores["EV/EBITDA"] *= 1.10

    if debt_ratio > 0.25:
        scores["EV/EBITDA"] *= 1.20
        scores["P/E Comps"] *= 0.90
    elif debt_ratio < 0.10:
        scores["DCF"] *= 1.05

    if revenue_ttm > 0 and (abs(current_fcf_for_valuation) / revenue_ttm) < 0.03:
        scores["EV/EBITDA"] *= 1.10

    if any(keyword in sector_normalized for keyword in ("financial", "bank", "insurance", "capital markets")):
        scores["DCF"] *= 0.55
        scores["P/E Comps"] *= 1.15
        scores["EV/EBITDA"] *= 0.75
    elif "real estate" in sector_normalized or "reit" in sector_normalized:
        scores["DCF"] *= 0.80
        scores["EV/EBITDA"] *= 1.20
    elif "utilities" in sector_normalized:
        scores["DCF"] *= 1.15
        scores["EV/EBITDA"] *= 1.10
    elif any(keyword in sector_normalized for keyword in ("technology", "software", "internet")):
        scores["DCF"] *= 1.05 if current_fcf_for_valuation > 0 else 0.85
        scores["P/E Comps"] *= 0.90
        scores["EV/EBITDA"] *= 1.10
    elif any(keyword in sector_normalized for keyword in ("energy", "materials", "industrials", "manufacturing")):
        scores["EV/EBITDA"] *= 1.15

    scores = {method: max(score, 0.05) for method, score in scores.items()}
    total_score = sum(scores.values()) or 1.0
    normalized = {method: score / total_score for method, score in scores.items()}

    return normalized


def calculate_multi_method_valuation_data(
    *,
    ticker: str,
    current_price: float,
    fundamentals: Dict[str, Any],
    statements_payload: Dict[str, Any],
    analyst_recommendations: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if _is_index_or_etf(fundamentals):
        return _build_index_etf_valuation(
            ticker=ticker,
            current_price=current_price,
            fundamentals=fundamentals,
            analyst_recommendations=analyst_recommendations,
        )

    balance_sheet_annual = _statement_reports(statements_payload, "balance_sheet", "annualReports")
    balance_sheet_quarterly = _statement_reports(statements_payload, "balance_sheet", "quarterlyReports")
    cashflow_annual = _statement_reports(statements_payload, "cashflow", "annualReports")
    cashflow_quarterly = _statement_reports(statements_payload, "cashflow", "quarterlyReports")
    income_annual = _statement_reports(statements_payload, "income_statement", "annualReports")

    shares_outstanding = _first_numeric(fundamentals, "SharesOutstanding")
    if shares_outstanding is None:
        shares_outstanding = _latest_numeric(balance_sheet_quarterly or balance_sheet_annual, "shareIssued", "ordinarySharesNumber")
    shares_outstanding = max(shares_outstanding or 1.0, 1.0)

    # Extract FCF and its components for negative cash flow analysis
    current_fcf = _latest_numeric(cashflow_annual, "freeCashFlow")
    operating_cf = _latest_numeric(cashflow_annual, "operatingCashFlow") or 0.0
    capex = abs(_latest_numeric(cashflow_annual, "capitalExpenditure") or 0.0)
    
    if current_fcf is None:
        if operating_cf is not None:
            current_fcf = operating_cf - capex
    if current_fcf is None:
        quarterly_fcf = _sum_latest(cashflow_quarterly, "freeCashFlow", count=4)
        if quarterly_fcf is not None:
            current_fcf = quarterly_fcf
    if current_fcf is None:
        revenue_ttm = _first_numeric(fundamentals, "RevenueTTM") or _latest_numeric(income_annual, "totalRevenue") or 0.0
        profit_margin = _first_numeric(fundamentals, "ProfitMargin") or 0.15
        current_fcf = revenue_ttm * profit_margin * 0.9
    
    current_fcf = float(current_fcf)
    revenue_ttm = _first_numeric(fundamentals, "RevenueTTM") or _latest_numeric(income_annual, "totalRevenue") or 0.0
    
    # Detect growth stage and determine projection period
    revenue_growth = _first_numeric(fundamentals, "QuarterlyRevenueGrowthYOY")
    earnings_growth = _first_numeric(fundamentals, "QuarterlyEarningsGrowthYOY")
    revenue_cagr = _cagr(income_annual, "totalRevenue")
    earnings_cagr = _cagr(income_annual, "netIncome")
    
    is_high_growth, projection_years = _detect_growth_stage(
        revenue_growth, revenue_cagr, current_fcf, operating_cf
    )
    
    # Handle negative FCF scenarios
    fcf_normalization_note = None
    original_fcf = current_fcf
    if current_fcf < 0:
        normalized_fcf, explanation = _normalize_fcf_for_growth_stage(
            current_fcf, operating_cf, capex, revenue_ttm, is_high_growth
        )
        fcf_normalization_note = {
            "original_fcf": original_fcf,
            "normalized_fcf": normalized_fcf,
            "explanation": explanation,
            "is_high_growth": is_high_growth,
        }
        # Use normalized FCF for valuation but keep original for reporting
        current_fcf_for_valuation = normalized_fcf
    else:
        current_fcf_for_valuation = current_fcf
    # Collect growth samples with metadata for weighted averaging
    growth_samples = [g for g in [revenue_growth, earnings_growth, revenue_cagr, earnings_cagr] if g is not None]
    
    # Track data availability for transparency
    growth_data_source = []
    if revenue_growth is not None:
        growth_data_source.append("revenue_growth_yoy")
    if earnings_growth is not None:
        growth_data_source.append("earnings_growth_yoy")
    if revenue_cagr is not None:
        growth_data_source.append("revenue_cagr")
    if earnings_cagr is not None:
        growth_data_source.append("earnings_cagr")
    
    if growth_samples:
        # Use weighted average favoring more recent metrics
        # Order: revenue_growth (most recent), earnings_growth, revenue_cagr, earnings_cagr
        weights = [0.35, 0.30, 0.20, 0.15][:len(growth_samples)]
        weights_sum = sum(weights)
        weighted_growth = sum(g * w for g, w in zip(growth_samples, weights)) / weights_sum
        
        # Calculate growth volatility for dynamic scenario spreads
        if len(growth_samples) >= 2:
            growth_volatility = pstdev(growth_samples)
            # Use 1.5 standard deviations for bear/bull scenarios
            bear_spread = min(1.5 * growth_volatility, 0.10)  # Cap at 10%
            bull_spread = min(1.5 * growth_volatility, 0.10)
        else:
            # Fallback to moderate spread if insufficient data
            bear_spread = 0.05
            bull_spread = 0.05
        
        base_growth = weighted_growth
    else:
        # FALLBACK: No growth data available - use conservative estimate
        # This is a FALLBACK ONLY - LLM should note data limitation
        base_growth = 0.08
        bear_spread = 0.03
        bull_spread = 0.03
        growth_data_source = ["FALLBACK_ESTIMATE"]
    
    # Apply dynamic clamping based on company growth stage
    if is_high_growth:
        # High-growth companies: 10-40% range
        base_growth = _clamp(base_growth, 0.10, 0.40)
        bear_growth = _clamp(base_growth - bear_spread, 0.05, 0.35)
        bull_growth = _clamp(base_growth + bull_spread, 0.15, 0.50)
    else:
        # Mature companies: 2-20% range
        base_growth = _clamp(base_growth, 0.02, 0.20)
        bear_growth = _clamp(base_growth - bear_spread, 0.00, 0.15)
        bull_growth = _clamp(base_growth + bull_spread, 0.04, 0.25)

    beta = _clamp(_first_numeric(fundamentals, "Beta") or 1.1, 0.8, 2.0)
    # Fetch current risk-free rate from FRED (10-year treasury)
    risk_free_rate = _get_current_risk_free_rate()
    # Fetch dynamic market risk premium based on VIX
    market_risk_premium = _get_market_risk_premium()
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
    
    # Calculate dynamic terminal growth based on sector and growth stage
    sector = fundamentals.get("Sector") or fundamentals.get("sector")
    terminal_growth = _calculate_terminal_growth(
        sector=sector,
        is_high_growth=is_high_growth,
        revenue_growth=revenue_growth
    )

    net_debt = _net_debt(fundamentals, balance_sheet_annual, balance_sheet_quarterly)
    debt_ratio = total_debt / max(total_debt + market_cap, 1.0)
    
    # Calculate DCF with appropriate projection period for growth stage
    dcf = {
        "bear": _discounted_cash_flow_value(
            current_fcf_for_valuation, bear_growth, wacc_bear,
            terminal_growth["bear"], net_debt, shares_outstanding, projection_years
        ),
        "base": _discounted_cash_flow_value(
            current_fcf_for_valuation, base_growth, wacc_base,
            terminal_growth["base"], net_debt, shares_outstanding, projection_years
        ),
        "bull": _discounted_cash_flow_value(
            current_fcf_for_valuation, bull_growth, wacc_bull,
            terminal_growth["bull"], net_debt, shares_outstanding, projection_years
        ),
    }
    
    # Calculate reverse DCF (implied growth rate from current price)
    implied_growth = _reverse_dcf_implied_growth(
        current_price, current_fcf_for_valuation, wacc_base,
        terminal_growth["base"], net_debt, shares_outstanding, projection_years
    )

    raw_eps = _first_numeric(fundamentals, "EPS")
    if raw_eps is None:
        net_income = _latest_numeric(income_annual, "netIncome")
        if net_income is not None and shares_outstanding > 0:
            raw_eps = net_income / shares_outstanding
    eps = max(raw_eps or 0.01, 0.01)
    trailing_pe = _first_numeric(fundamentals, "TrailingPE") or (current_price / raw_eps if raw_eps and raw_eps > 0 else None)
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

    method_weights = _determine_dynamic_method_weights(
        sector=sector,
        is_high_growth=is_high_growth,
        current_fcf=original_fcf,
        current_fcf_for_valuation=current_fcf_for_valuation,
        fcf_normalization_note=fcf_normalization_note,
        growth_samples=growth_samples,
        growth_data_source=growth_data_source,
        eps=raw_eps,
        trailing_pe=trailing_pe,
        forward_pe=forward_pe,
        ebitda=ebitda,
        total_debt=total_debt,
        market_cap=market_cap,
        revenue_ttm=revenue_ttm,
    )

    valuation_summary = calculate_valuation_summary(
        dcf=dcf,
        pe_comps=pe_comps,
        ev_ebitda=ev_ebitda,
        method_weights=method_weights,
    )
    fair_value_bear = valuation_summary["weighted_avg"]["bear"]
    fair_value_base = valuation_summary["weighted_avg"]["base"]
    fair_value_bull = valuation_summary["weighted_avg"]["bull"]
    current_discount_pct = ((fair_value_base - current_price) / fair_value_base * 100.0) if fair_value_base > 0 else 0.0
    
    # Calculate method dispersion
    base_values = [dcf["base"], pe_comps["base"], ev_ebitda["base"]]
    dispersion = (pstdev(base_values) / max(sum(base_values) / len(base_values), 1e-9)) if len(base_values) >= 2 else 0.0
    
    # Enhanced conviction scoring with data quality factors
    data_quality_score = 1.0
    if fcf_normalization_note:
        data_quality_score *= 0.85  # Penalize normalized FCF (higher uncertainty)
    if growth_samples and len(growth_samples) < 2:
        data_quality_score *= 0.90  # Penalize limited growth data
    
    # Adjust dispersion for data quality
    adjusted_dispersion = dispersion / data_quality_score
    valuation_conviction = (
        "high" if adjusted_dispersion < 0.15
        else "medium" if adjusted_dispersion < 0.30
        else "low"
    )
    
    # Validations for extreme values
    if any(dcf[k] <= 0 for k in dcf):
        logger.warning(f"{ticker}: Negative or zero DCF values detected - {dcf}")
    if any(pe_comps[k] > 200 for k in pe_comps):
        logger.warning(f"{ticker}: Extreme P/E multiples (>200) detected - {pe_comps}")
    if any(ev_ebitda[k] > 100 for k in ev_ebitda):
        logger.warning(f"{ticker}: Extreme EV/EBITDA multiples (>100) detected - {ev_ebitda}")
    if abs(current_discount_pct) > 80:
        logger.warning(f"{ticker}: Extreme discount/premium (>{abs(current_discount_pct):.1f}%) - may indicate data issues")
    
    # Calculate score with conviction adjustment
    valuation_score = _deterministic_score(current_discount_pct, valuation_conviction)
    valuation_bridge = _build_valuation_bridge(
        current_price=current_price,
        fair_value_base=fair_value_base,
        dcf_base=dcf["base"],
        pe_comps_base=pe_comps["base"],
        ev_ebitda_base=ev_ebitda["base"],
        method_weights=method_weights,
    )
    valuation_sensitivity = _build_sensitivity_analysis(
        current_fcf=current_fcf_for_valuation,
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
        beta=beta,
        growth_samples=growth_samples,
        method_weights=method_weights,
    )
    
    # Build key assumptions with data source transparency
    key_assumptions = [
        f"DCF projection period: {projection_years} years ({'high-growth' if is_high_growth else 'mature'} company)",
        f"FCF growth: bear {bear_growth*100:.1f}%, base {base_growth*100:.1f}%, bull {bull_growth*100:.1f}% (source: {', '.join(growth_data_source)})",
        f"WACC: bear {wacc_bear*100:.1f}%, base {wacc_base*100:.1f}%, bull {wacc_bull*100:.1f}% (from market rates: risk-free {risk_free_rate*100:.2f}%, MRP {market_risk_premium*100:.2f}%)",
        f"Terminal growth: bear {terminal_growth['bear']*100:.1f}%, base {terminal_growth['base']*100:.1f}%, bull {terminal_growth['bull']*100:.1f}% (sector-based: {sector or 'Unknown'})",
        f"Forward EPS used for P/E comps: {forward_eps:.2f}",
        f"Base EV/EBITDA multiple: {base_ev_mult:.2f}x",
        "Method weights: "
        f"DCF {method_weights['DCF']*100:.1f}%, "
        f"P/E Comps {method_weights['P/E Comps']*100:.1f}%, "
        f"EV/EBITDA {method_weights['EV/EBITDA']*100:.1f}% "
        f"(dynamic by company profile: sector={sector or 'Unknown'}, "
        f"{'high-growth' if is_high_growth else 'mature'}, "
        f"FCF {'normalized' if fcf_normalization_note else 'reported'}, "
        f"debt ratio {debt_ratio*100:.1f}%)",
    ]
    
    # Add negative FCF context if applicable
    if fcf_normalization_note:
        key_assumptions.insert(1, f"⚠️ Negative FCF normalized: {fcf_normalization_note['explanation']}")
    
    # Add implied growth from reverse DCF
    if implied_growth is not None:
        key_assumptions.append(f"Market-implied growth rate (reverse DCF): {implied_growth*100:.1f}%")
    
    # Add data quality warning if using fallback estimates
    if "FALLBACK_ESTIMATE" in growth_data_source:
        key_assumptions.append("⚠️ WARNING: Growth estimates unavailable - using conservative fallback (8%). Valuation reliability is LOW.")

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
        "valuation_key_assumptions": key_assumptions,
        "inputs": {
            "shares_outstanding": shares_outstanding,
            "current_fcf": original_fcf,  # Report original FCF
            "current_fcf_for_valuation": current_fcf_for_valuation,  # Show normalized if different
            "operating_cash_flow": operating_cf,
            "capex": capex,
            "net_debt": net_debt,
            "eps": eps,
            "ebitda": ebitda,
            "analyst_price_targets": {"low": target_low, "average": target_avg, "high": target_high},
            "fcf_normalization": fcf_normalization_note,  # Include normalization details
            "is_high_growth": is_high_growth,
            "projection_years": projection_years,
            "implied_growth_rate": implied_growth,
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

    # Extract target company characteristics for validation
    target_market_cap = _first_numeric(fundamentals, "MarketCapitalization")
    target_country = fundamentals.get("Country") or fundamentals.get("country")
    
    ranked_candidates = []
    for item in candidate_universe:
        candidate_ticker = _normalize_upper(item.get("ticker"))
        candidate_name = _normalize_text(item.get("name"))
        candidate_sector = _normalize_text(item.get("sector"))
        candidate_industry = _normalize_text(item.get("industry"))
        candidate_payload = _json_loads_maybe(get_fundamentals_via_service(candidate_ticker))
        candidate_fundamentals = candidate_payload.get("fundamentals") or {}
        candidate_profile = _extract_company_profile(candidate_payload)
        
        # Enhanced validation: Size filter
        candidate_market_cap = _first_numeric(candidate_fundamentals, "MarketCapitalization")
        if target_market_cap and candidate_market_cap:
            # Calculate size ratio (larger / smaller)
            size_ratio = max(target_market_cap, candidate_market_cap) / min(target_market_cap, candidate_market_cap)
            # Skip peers with >10x size difference (different market dynamics)
            if size_ratio > 10.0:
                logger.debug(f"Skipping {candidate_ticker}: size ratio {size_ratio:.1f}x too large")
                continue
        
        # Enhanced validation: Geography filter
        candidate_country = candidate_fundamentals.get("Country") or candidate_fundamentals.get("country")
        geography_penalty = 1.0
        if target_country and candidate_country:
            if target_country != candidate_country:
                # Penalize international peers (different regulatory/tax environments)
                # But don't exclude them entirely (useful for global companies)
                geography_penalty = 0.7
                logger.debug(f"{candidate_ticker}: international peer ({candidate_country} vs {target_country}), applying 0.7x penalty")
        
        candidate_entry = _peer_metric_entry(
            ticker=candidate_ticker,
            name=candidate_profile.get("name") or candidate_name or candidate_ticker,
            sector=candidate_profile.get("sector") or candidate_sector,
            industry=candidate_profile.get("industry") or candidate_industry,
            fundamentals=candidate_fundamentals if isinstance(candidate_fundamentals, dict) else {},
        )
        if candidate_entry is None:
            continue
        
        # Apply geography penalty to ranking score
        candidate_entry["geography_penalty"] = geography_penalty
        ranked_candidates.append(candidate_entry)

    ranked_candidates.sort(
        key=lambda item: _candidate_rank(
            item.get("sector", ""),
            item.get("industry", ""),
            target_sector,
            target_industry,
            int(item.get("valid_metric_count") or 0),
            item.get("geography_penalty", 1.0),
        ),
        reverse=True,
    )
    # Select up to 3 peers, but only those with sufficient data quality
    MIN_VALID_METRICS = 2
    selected_peers = [
        p for p in ranked_candidates[:5]
        if p.get("valid_metric_count", 0) >= MIN_VALID_METRICS
    ][:3]

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
    fundamentals_str = get_fundamentals_via_service(ticker)
    fundamentals = _json_loads_maybe(fundamentals_str)
    income_data = get_financial_statements(ticker, statement_type="income_statement", freq="annual")
    
    # Extract analyst growth estimates from fundamentals
    revenue_growth_next_year = _first_numeric(fundamentals, "RevenueGrowthNextYear", "QuarterlyRevenueGrowthYOY")
    revenue_growth_next_5y = _first_numeric(fundamentals, "RevenueGrowth5Y", "RevenueGrowthNext5Y")
    earnings_growth_next_year = _first_numeric(fundamentals, "EarningsGrowthNextYear", "QuarterlyEarningsGrowthYOY")
    earnings_growth_next_5y = _first_numeric(fundamentals, "EarningsGrowth5Y", "EarningsGrowthNext5Y", "EPSGrowth5Y")
    
    # Calculate historical growth rates from income statements
    annual_reports = []
    if income_data is not None:
        annual_reports = _statement_reports(income_data, "income_statement", "annualReports")
    
    # Revenue CAGR calculations
    revenue_cagr_3y = None
    revenue_cagr_5y = None
    if len(annual_reports) >= 4:
        revenue_cagr_3y = _cagr(annual_reports[:4], "totalRevenue")
    if len(annual_reports) >= 6:
        revenue_cagr_5y = _cagr(annual_reports[:6], "totalRevenue")
    
    # Earnings CAGR calculations
    earnings_cagr_3y = None
    earnings_cagr_5y = None
    if len(annual_reports) >= 4:
        earnings_cagr_3y = _cagr(annual_reports[:4], "netIncome")
    if len(annual_reports) >= 6:
        earnings_cagr_5y = _cagr(annual_reports[:6], "netIncome")
    
    # Format percentages
    def format_pct(value: Optional[float]) -> Optional[str]:
        if value is None:
            return None
        return f"{value * 100:.2f}%"
    
    result = {
        "ticker": ticker.upper(),
        "growth_estimates": {
            "revenue_growth_next_year": format_pct(revenue_growth_next_year) or "Not available",
            "revenue_growth_next_5y": format_pct(revenue_growth_next_5y) or "Not available",
            "earnings_growth_next_year": format_pct(earnings_growth_next_year) or "Not available",
            "earnings_growth_next_5y": format_pct(earnings_growth_next_5y) or "Not available",
        },
        "historical_growth": {
            "revenue_cagr_3y": format_pct(revenue_cagr_3y) or "Not available",
            "revenue_cagr_5y": format_pct(revenue_cagr_5y) or "Not available",
            "earnings_cagr_3y": format_pct(earnings_cagr_3y) or "Not available",
            "earnings_cagr_5y": format_pct(earnings_cagr_5y) or "Not available",
        },
        "raw_values": {
            "revenue_growth_next_year": revenue_growth_next_year,
            "revenue_growth_next_5y": revenue_growth_next_5y,
            "earnings_growth_next_year": earnings_growth_next_year,
            "earnings_growth_next_5y": earnings_growth_next_5y,
            "revenue_cagr_3y": revenue_cagr_3y,
            "revenue_cagr_5y": revenue_cagr_5y,
            "earnings_cagr_3y": earnings_cagr_3y,
            "earnings_cagr_5y": earnings_cagr_5y,
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
        str: JSON containing WACC calculation inputs and calculated WACC
    """
    require_info_service()
    
    # Get fundamental data and financial statements
    fundamentals_str = get_fundamentals_via_service(ticker)
    fundamentals = _json_loads_maybe(fundamentals_str)
    balance_sheet_data = get_financial_statements(ticker, statement_type="balance_sheet", freq="quarterly")
    income_data = get_financial_statements(ticker, statement_type="income_statement", freq="annual")
    
    # Extract beta from fundamentals
    beta = _first_numeric(fundamentals, "Beta", "beta")
    if beta is None:
        beta = 1.0  # Default to market beta if not available
    
    # Extract market cap
    market_cap = _first_numeric(fundamentals, "MarketCapitalization", "marketCap")
    
    # Extract tax rate from income statement
    tax_rate = None
    if income_data is not None:
        annual_reports = _statement_reports(income_data, "income_statement", "annualReports")
        if annual_reports:
            latest = annual_reports[0]
            income_before_tax = _safe_float(latest.get("incomeBeforeTax"))
            income_tax = _safe_float(latest.get("incomeTaxExpense"))
            if income_before_tax and income_tax and income_before_tax > 0:
                tax_rate = income_tax / income_before_tax
    
    if tax_rate is None:
        tax_rate = 0.21  # Default US corporate tax rate
    
    # Calculate debt metrics from balance sheet
    total_debt = None
    cash = None
    net_debt = None
    
    if balance_sheet_data is not None:
        bs_reports = _statement_reports(balance_sheet_data, "balance_sheet", "annualReports")
        if not bs_reports:
            bs_reports = _statement_reports(balance_sheet_data, "balance_sheet", "quarterlyReports")
        
        if bs_reports:
            total_debt = _latest_numeric(
                bs_reports,
                "totalDebt",
                "longTermDebtAndCapitalLeaseObligation",
                "longTermDebt"
            )
            cash = _latest_numeric(
                bs_reports,
                "cashAndCashEquivalents",
                "cashCashEquivalentsAndShortTermInvestments"
            )
    
    if total_debt is None:
        total_debt = 0.0
    if cash is None:
        cash = 0.0
    
    net_debt = total_debt - cash
    
    # Calculate cost of debt from income statement
    cost_of_debt = None
    if income_data is not None:
        annual_reports = _statement_reports(income_data, "income_statement", "annualReports")
        if annual_reports:
            interest_expense = _latest_numeric(annual_reports, "interestExpense", "interestAndDebtExpense")
            if interest_expense and total_debt and total_debt > 0:
                cost_of_debt = interest_expense / total_debt
    
    if cost_of_debt is None:
        cost_of_debt = 0.05  # Default 5% cost of debt
    
    # Fetch current market rates dynamically
    risk_free_rate = _get_current_risk_free_rate()
    market_risk_premium = _get_market_risk_premium()
    
    # Calculate cost of equity using CAPM: Re = Rf + Beta * (Rm - Rf)
    cost_of_equity = risk_free_rate + (beta * market_risk_premium)
    
    # Calculate WACC: (E/V * Re) + (D/V * Rd * (1-Tc))
    wacc = None
    debt_to_equity = None
    
    if market_cap and market_cap > 0:
        total_value = market_cap + net_debt
        if total_value > 0:
            equity_weight = market_cap / total_value
            debt_weight = net_debt / total_value
            
            wacc = (equity_weight * cost_of_equity) + (debt_weight * cost_of_debt * (1 - tax_rate))
            
            if total_debt > 0 and market_cap > 0:
                debt_to_equity = total_debt / market_cap
    
    result = {
        "ticker": ticker.upper(),
        "wacc_inputs": {
            "beta": round(beta, 3) if beta else None,
            "risk_free_rate": f"{risk_free_rate * 100:.2f}%",
            "market_risk_premium": f"{market_risk_premium * 100:.2f}%",
            "cost_of_debt": f"{cost_of_debt * 100:.2f}%" if cost_of_debt else None,
            "tax_rate": f"{tax_rate * 100:.2f}%" if tax_rate else None,
            "cost_of_equity": f"{cost_of_equity * 100:.2f}%",
            "market_cap": market_cap,
            "total_debt": total_debt,
            "net_debt": net_debt,
            "debt_to_equity": round(debt_to_equity, 3) if debt_to_equity else None,
        },
        "calculated_wacc": f"{wacc * 100:.2f}%" if wacc else "Unable to calculate (missing market cap)",
        "raw_values": {
            "beta": beta,
            "risk_free_rate": risk_free_rate,
            "market_risk_premium": market_risk_premium,
            "cost_of_debt": cost_of_debt,
            "tax_rate": tax_rate,
            "cost_of_equity": cost_of_equity,
            "wacc": wacc,
            "debt_to_equity": debt_to_equity,
        },
    }
    
    return json.dumps(result, indent=2)


@tool
def get_dcf_inputs(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[Optional[str], "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve all inputs needed for DCF (Discounted Cash Flow) valuation with enhanced
    negative cash flow handling:
    
    - Free cash flow (historical and projected)
    - Growth rates and growth stage detection
    - Terminal growth rate
    - WACC (Weighted Average Cost of Capital)
    - Shares outstanding
    - Negative FCF normalization (if applicable)
    - Reverse DCF implied growth rate
    
    The function automatically:
    1. Detects if company is in high-growth stage (uses 7-10 year projections)
    2. Normalizes negative FCF due to growth investments vs. operational issues
    3. Calculates market-implied growth rate from current stock price
    4. Handles negative cash flows by discounting them appropriately
    
    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date you are trading at, yyyy-mm-dd (optional)
    
    Returns:
        str: JSON containing comprehensive DCF model inputs with negative FCF context
    """
    require_info_service()
    
    # Get all necessary financial data
    fundamentals_str = get_fundamentals_via_service(ticker)
    fundamentals = _json_loads_maybe(fundamentals_str)
    cashflow_data = get_financial_statements(ticker, statement_type="cashflow", freq="annual")
    cashflow_quarterly = get_financial_statements(ticker, statement_type="cashflow", freq="quarterly")
    income_data = get_financial_statements(ticker, statement_type="income_statement", freq="annual")
    balance_sheet_data = get_financial_statements(ticker, statement_type="balance_sheet", freq="quarterly")
    
    # Extract shares outstanding
    shares_outstanding = _first_numeric(fundamentals, "SharesOutstanding", "sharesOutstanding")
    
    # Calculate net debt
    net_debt = _net_debt(fundamentals,
                        _statement_reports(balance_sheet_data, "balance_sheet", "annualReports") if balance_sheet_data else [],
                        _statement_reports(balance_sheet_data, "balance_sheet", "quarterlyReports") if balance_sheet_data else [])
    
    # Get cashflow data
    cf_reports = []
    cf_quarterly_reports = []
    if cashflow_data is not None:
        cf_reports = _statement_reports(cashflow_data, "cashflow", "annualReports")
    if cashflow_quarterly is not None:
        cf_quarterly_reports = _statement_reports(cashflow_quarterly, "cashflow", "quarterlyReports")
    
    # Calculate current FCF with comprehensive fallback logic
    current_fcf = None
    operating_cf = None
    capex = None
    historical_fcf = []
    fcf_data_source = []
    
    # Try 1: Direct FCF from annual reports
    if cf_reports:
        current_fcf = _latest_numeric(cf_reports, "freeCashFlow")
        if current_fcf is not None:
            fcf_data_source.append("annual_freeCashFlow")
    
    # Try 2: Calculate from operating CF and CapEx (annual)
    if current_fcf is None and cf_reports:
        latest_cf = cf_reports[0]
        operating_cf = _safe_float(latest_cf.get("operatingCashflow"))
        capex = _safe_float(latest_cf.get("capitalExpenditures"))
        
        if operating_cf is not None and capex is not None:
            current_fcf = operating_cf - abs(capex)
            fcf_data_source.append("annual_operating_cf_minus_capex")
    
    # Try 3: Sum quarterly FCF (TTM)
    if current_fcf is None and cf_quarterly_reports:
        quarterly_fcf = _sum_latest(cf_quarterly_reports, "freeCashFlow", count=4)
        if quarterly_fcf is not None:
            current_fcf = quarterly_fcf
            fcf_data_source.append("quarterly_fcf_ttm")
    
    # Try 4: Calculate from quarterly operating CF and CapEx (TTM)
    if current_fcf is None and cf_quarterly_reports:
        quarterly_op_cf = _sum_latest(cf_quarterly_reports, "operatingCashflow", count=4)
        quarterly_capex = _sum_latest(cf_quarterly_reports, "capitalExpenditures", count=4)
        if quarterly_op_cf is not None and quarterly_capex is not None:
            current_fcf = quarterly_op_cf - abs(quarterly_capex)
            fcf_data_source.append("quarterly_operating_cf_minus_capex_ttm")
    
    # Try 5: Estimate from revenue and profit margin
    if current_fcf is None:
        revenue_ttm = _first_numeric(fundamentals, "RevenueTTM")
        profit_margin = _first_numeric(fundamentals, "ProfitMargin")
        if revenue_ttm and profit_margin:
            current_fcf = revenue_ttm * profit_margin * 0.9  # 90% conversion to FCF
            fcf_data_source.append("estimated_from_revenue_and_margin")
    
    # Extract operating CF and CapEx for analysis (if not already set)
    if operating_cf is None and cf_reports:
        operating_cf = _safe_float(cf_reports[0].get("operatingCashflow"))
    if capex is None and cf_reports:
        capex = _safe_float(cf_reports[0].get("capitalExpenditures"))
    
    # Calculate historical FCF for last 3-5 years
    if cf_reports:
        for report in cf_reports[:5]:
            op_cf = _safe_float(report.get("operatingCashflow"))
            cx = _safe_float(report.get("capitalExpenditures"))
            if op_cf is not None and cx is not None:
                fcf = op_cf - abs(cx)
                historical_fcf.append({
                    "year": report.get("fiscalDateEnding"),
                    "operating_cf": op_cf,
                    "capex": abs(cx),
                    "fcf": fcf
                })
    
    # Get revenue for normalization
    revenue = None
    revenue_growth = None
    if income_data is not None:
        income_reports = _statement_reports(income_data, "income_statement", "annualReports")
        if income_reports:
            revenue = _safe_float(income_reports[0].get("totalRevenue"))
            # Calculate revenue growth
            if len(income_reports) >= 2:
                prev_revenue = _safe_float(income_reports[1].get("totalRevenue"))
                if revenue and prev_revenue and prev_revenue > 0:
                    revenue_growth = (revenue - prev_revenue) / prev_revenue
    
    # Calculate historical revenue CAGR
    revenue_cagr_3y = None
    if income_data is not None:
        income_reports = _statement_reports(income_data, "income_statement", "annualReports")
        if len(income_reports) >= 4:
            revenue_cagr_3y = _cagr(income_reports[:4], "totalRevenue")
    
    # Detect growth stage
    is_high_growth = False
    projection_years = 5
    if current_fcf is not None and operating_cf is not None:
        is_high_growth, projection_years = _detect_growth_stage(
            revenue_growth, revenue_cagr_3y, current_fcf, operating_cf
        )
    
    # Normalize FCF if negative
    normalized_fcf = current_fcf
    normalization_note = None
    if current_fcf is not None and current_fcf < 0 and revenue:
        normalized_fcf, normalization_note = _normalize_fcf_for_growth_stage(
            current_fcf, operating_cf or 0, abs(capex) if capex else 0, revenue, is_high_growth
        )
    
    # Calculate FCF growth rate from historical data
    fcf_growth_rate = None
    if len(historical_fcf) >= 3:
        fcf_values = [item["fcf"] for item in historical_fcf if item["fcf"] > 0]
        if len(fcf_values) >= 2:
            fcf_growth_rate = _cagr([{"fcf": v} for v in reversed(fcf_values)], "fcf")
    
    # Use revenue growth as fallback
    if fcf_growth_rate is None:
        fcf_growth_rate = revenue_cagr_3y or revenue_growth
    
    # Track data source for growth rate
    growth_data_source = []
    if fcf_growth_rate is not None:
        growth_data_source.append("historical_fcf_cagr")
    elif revenue_cagr_3y is not None:
        growth_data_source.append("revenue_cagr_3y")
    elif revenue_growth is not None:
        growth_data_source.append("revenue_growth_yoy")
    
    # Use fallback only if no data available
    if fcf_growth_rate is None:
        fcf_growth_rate = 0.10 if is_high_growth else 0.05
        growth_data_source.append("FALLBACK_ESTIMATE")
    
    # Terminal growth - use GDP estimate (this is a reasonable economic assumption)
    terminal_growth_rate = 0.025  # Long-term GDP growth estimate
    
    # WACC calculation - simplified, should use get_wacc_inputs for full calculation
    wacc = 0.10  # Default 10% WACC
    wacc_data_source = ["SIMPLIFIED_ESTIMATE"]
    beta = _first_numeric(fundamentals, "Beta", "beta")
    if beta:
        risk_free_rate = 0.045  # Approximate current rate
        market_risk_premium = 0.075  # Historical average
        wacc = risk_free_rate + (beta * market_risk_premium)
        wacc_data_source = ["beta_based_calculation"]
    
    result = {
        "ticker": ticker.upper(),
        "dcf_inputs": {
            "current_fcf": current_fcf,
            "normalized_fcf": normalized_fcf if normalized_fcf != current_fcf else None,
            "fcf_growth_rate": fcf_growth_rate,
            "projection_years": projection_years,
            "terminal_growth_rate": terminal_growth_rate,
            "wacc": wacc,
            "shares_outstanding": shares_outstanding,
            "net_debt": net_debt,
        },
        "growth_analysis": {
            "is_high_growth": is_high_growth,
            "revenue_growth_yoy": revenue_growth,
            "revenue_cagr_3y": revenue_cagr_3y,
            "fcf_growth_rate": fcf_growth_rate,
            "recommended_projection_years": projection_years,
        },
        "fcf_analysis": {
            "operating_cashflow": operating_cf,
            "capex": abs(capex) if capex else None,
            "free_cashflow": current_fcf,
            "is_negative": current_fcf < 0 if current_fcf is not None else None,
            "normalization_applied": normalization_note,
        },
        "historical_fcf": historical_fcf[:5],
        "formatted_values": {
            "current_fcf": f"${current_fcf:,.0f}" if current_fcf else "Not available",
            "normalized_fcf": f"${normalized_fcf:,.0f}" if normalized_fcf and normalized_fcf != current_fcf else None,
            "fcf_growth_rate": f"{fcf_growth_rate * 100:.2f}%" if fcf_growth_rate else "Not available",
            "terminal_growth_rate": f"{terminal_growth_rate * 100:.2f}%",
            "wacc": f"{wacc * 100:.2f}%",
            "net_debt": f"${net_debt:,.0f}" if net_debt else "Not available",
        },
        "data_sources": {
            "current_fcf": fcf_data_source if fcf_data_source else ["NOT_AVAILABLE"],
            "fcf_growth_rate": growth_data_source,
            "wacc": wacc_data_source,
            "note": "FALLBACK_ESTIMATE or estimated values indicate missing data - analyst must explicitly state this limitation"
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
