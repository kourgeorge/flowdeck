# Valuation Analyst Implementation Guide

## Overview

This document describes the implementation of the Valuation Analyst component for the TradingAgents workflow, providing multi-method fair value analysis with bear/base/bull scenarios.

## What Was Created

### 1. Valuation Tools (`ai_engine/tradingagents/agents/utils/valuation_tools.py`)

New tools for valuation analysis:

- **`get_peer_comparables(ticker)`**: Retrieves P/E, EV/EBITDA, P/S, P/B multiples for the company and peer averages
- **`get_growth_estimates(ticker)`**: Gets analyst consensus growth estimates and historical growth rates
- **`get_wacc_inputs(ticker)`**: Provides inputs for WACC calculation (beta, risk-free rate, cost of debt, etc.)
- **`get_dcf_inputs(ticker)`**: Retrieves all inputs needed for DCF valuation (FCF, growth rates, terminal value)

**Note**: These tools currently return placeholder structures. They need to be enhanced to parse actual data from the info service responses.

### 2. Valuation Analyst Prompt (`ai_engine/tradingagents/agents/analysts/prompts.py`)

Added `VALUATION_ANALYST_SYSTEM_MESSAGE` with comprehensive instructions for:

- Multiple valuation methods (DCF, P/E comps, EV/EBITDA comps)
- Bear/base/bull scenario generation
- Valuation bridge calculation
- Sensitivity analysis
- Detailed output format with tables and structured data

Added `build_valuation_analyst_prompt()` function to create the prompt.

### 3. Valuation Analyst Component (`ai_engine/tradingagents/agents/analysts/valuation_analyst.py`)

Created self-contained analyst with:

- **Output Schema** (`ValuationAnalysisOutput`):
  - `report`: Full narrative analysis
  - `valuation_score`: 1-10 (based on upside/downside)
  - `fair_value_bear/base/bull`: Three scenario values
  - `current_discount_pct`: Discount/premium vs fair value
  - `conviction`: high/medium/low
  - `key_assumptions`: Top 3-5 assumptions
  - `key_takeaways`: 3-5 trader takeaways

- **Tools**: All valuation tools plus fundamentals, balance sheet, cashflow, income statement
- **Max Iterations**: 8 (more than other analysts due to complexity)

### 4. State Schema Updates (`ai_engine/tradingagents/agents/utils/agent_states.py`)

Added to `AgentState`:

```python
valuation_report: str
valuation_score: Optional[int]
valuation_key_takeaways: Optional[List[str]]
fair_value_bear: Optional[float]
fair_value_base: Optional[float]
fair_value_bull: Optional[float]
current_discount_pct: Optional[float]
valuation_conviction: Optional[str]
valuation_key_assumptions: Optional[List[str]]
```

## Integration Steps (TODO)

### Step 1: Register Valuation Analyst in `__init__.py`

**File**: `ai_engine/tradingagents/agents/__init__.py`

Add import:
```python
from .analysts.valuation_analyst import create_valuation_analyst
```

Add to `__all__`:
```python
__all__ = [
    # ... existing exports ...
    "create_valuation_analyst",
]
```

### Step 2: Integrate into Graph Setup

**File**: `ai_engine/tradingagents/graph/setup.py`

In `GraphSetup.__init__()`, add:
```python
self.valuation_analyst = create_valuation_analyst(self.quick_thinking_llm)
```

In `setup_graph()`, add "valuation" to the analyst options and node creation:

```python
def setup_graph(self, selected_analysts=None, parallel_analysts=True):
    # ... existing code ...
    
    analyst_map = {
        "market": self.market_analyst,
        "social": self.social_media_analyst,
        "news": self.news_analyst,
        "technical": self.technical_analyst,
        "fundamentals": self.fundamentals_analyst,
        "sec": self.sec_analyst,
        "valuation": self.valuation_analyst,  # ADD THIS
    }
    
    # ... rest of setup ...
```

### Step 3: Update Default Configuration

**File**: `ai_engine/tradingagents/default_config.py`

Add to config:
```python
DEFAULT_CONFIG = {
    # ... existing config ...
    "enable_valuation_analyst": True,  # Toggle for valuation analyst
}
```

### Step 4: Update Research Manager to Use Valuation Data

**File**: `ai_engine/tradingagents/agents/managers/research_manager.py`

In `research_manager_node()`, add valuation context:

```python
def research_manager_node(state) -> dict:
    # ... existing code ...
    
    valuation_report = state.get("valuation_report", "")
    fair_value_base = state.get("fair_value_base")
    fair_value_bear = state.get("fair_value_bear")
    fair_value_bull = state.get("fair_value_bull")
    current_discount_pct = state.get("current_discount_pct")
    
    curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
    if valuation_report:
        curr_situation += f"\n\n{valuation_report}"
    # ... rest of function ...
```

Update prompt to include valuation context:
```python
prompt = f"""...

Valuation Analysis (if available):
{valuation_report if valuation_report else "No valuation analysis available"}
Fair Value Base: ${fair_value_base if fair_value_base else 'N/A'}
Fair Value Range: ${fair_value_bear if fair_value_bear else 'N/A'} - ${fair_value_bull if fair_value_bull else 'N/A'}
Current Discount/Premium: {current_discount_pct if current_discount_pct else 'N/A'}%

When providing return expectations, consider the valuation analysis alongside the debate arguments.
If fair value suggests significant upside/downside, factor this into your expected_return_pct.

..."""
```

### Step 5: Update Trader to Use Fair Value Bands

**File**: `ai_engine/tradingagents/agents/trader/trader.py`

In `trader_node()`, add valuation context:

```python
context = {
    "role": "user",
    "content": (
        f"Investment Plan: {investment_plan}\n\n"
        f"Valuation Context:\n"
        f"- Fair Value (Base): ${state.get('fair_value_base', 'N/A')}\n"
        f"- Fair Value Range: ${state.get('fair_value_bear', 'N/A')} - ${state.get('fair_value_bull', 'N/A')}\n"
        f"- Current Discount: {state.get('current_discount_pct', 'N/A')}%\n"
        f"- Conviction: {state.get('valuation_conviction', 'N/A')}\n\n"
        f"Use these fair value bands to inform your entry.near and take_profit.tp1 in the TPS plan.\n"
        f"Consider the valuation conviction when setting position sizing (risk.max_position)."
    ),
}
```

### Step 6: Update Risk Manager to Assess Valuation Risk

**File**: `ai_engine/tradingagents/agents/managers/risk_manager.py`

Add valuation risk assessment:

```python
def risk_manager_node(state) -> dict:
    # ... existing code ...
    
    valuation_report = state.get("valuation_report") or ""
    current_discount_pct = state.get("current_discount_pct")
    valuation_conviction = state.get("valuation_conviction")
    
    # Add to score_candidates
    score_candidates = {
        # ... existing scores ...
        "valuation_score": state.get("valuation_score"),
    }
    
    # ... rest of function ...
```

Update prompt:
```python
prompt = f"""...

Valuation Risk Context:
{valuation_report if valuation_report else "No valuation analysis available"}
Current Discount/Premium: {current_discount_pct if current_discount_pct else 'N/A'}%
Valuation Conviction: {valuation_conviction if valuation_conviction else 'N/A'}

Consider valuation risk in your assessment:
- If significantly overvalued (negative discount), increase risk assessment
- If undervalued with high conviction, this supports the trade
- If valuation conviction is low, factor in higher uncertainty

..."""
```

### Step 7: Update Logging in Trading Graph

**File**: `ai_engine/tradingagents/graph/trading_graph.py`

In `_log_state()`, add valuation fields:

```python
def _log_state(self, trade_date, final_state):
    self.log_states_dict[str(trade_date)] = {
        # ... existing fields ...
        "valuation_report": final_state.get("valuation_report", ""),
        "valuation_score": final_state.get("valuation_score"),
        "fair_value_bear": final_state.get("fair_value_bear"),
        "fair_value_base": final_state.get("fair_value_base"),
        "fair_value_bull": final_state.get("fair_value_bull"),
        "current_discount_pct": final_state.get("current_discount_pct"),
        "valuation_conviction": final_state.get("valuation_conviction"),
        # ... rest of fields ...
    }
```

## Usage Example

Once integrated, enable the valuation analyst:

```python
from ai_engine.tradingagents.graph.trading_graph import TradingAgentsGraph

# Create graph with valuation analyst
graph = TradingAgentsGraph(
    selected_analysts=["market", "fundamentals", "valuation", "technical", "news"],
    config={
        "enable_valuation_analyst": True,
        # ... other config ...
    }
)

# Run analysis
final_state, signal = graph.propagate("AAPL", "2024-01-15")

# Access valuation results
print(f"Fair Value (Base): ${final_state['fair_value_base']}")
print(f"Fair Value Range: ${final_state['fair_value_bear']} - ${final_state['fair_value_bull']}")
print(f"Current Discount: {final_state['current_discount_pct']}%")
print(f"Valuation Score: {final_state['valuation_score']}/10")
print(f"Conviction: {final_state['valuation_conviction']}")
```

## Enhancing Valuation Tools (Future Work)

The placeholder valuation tools need to be enhanced to parse actual data:

### Example: Enhance `get_peer_comparables()`

```python
@tool
def get_peer_comparables(ticker: str, curr_date: Optional[str] = None) -> str:
    require_info_service()
    
    # Get fundamental data
    fundamentals = get_fundamentals_via_service(ticker)
    
    # Parse the response to extract actual multiples
    # This depends on the structure of your info service response
    try:
        data = json.loads(fundamentals) if isinstance(fundamentals, str) else fundamentals
        
        company_multiples = {
            "pe_ratio": data.get("valuation", {}).get("trailingPE"),
            "forward_pe": data.get("valuation", {}).get("forwardPE"),
            "peg_ratio": data.get("valuation", {}).get("pegRatio"),
            "price_to_sales": data.get("valuation", {}).get("priceToSalesTrailing12Months"),
            "price_to_book": data.get("valuation", {}).get("priceToBook"),
            "ev_to_ebitda": data.get("valuation", {}).get("enterpriseToEbitda"),
            "ev_to_revenue": data.get("valuation", {}).get("enterpriseToRevenue"),
        }
        
        # TODO: Fetch peer group data and calculate averages
        # This would require additional API calls or database queries
        
        result = {
            "ticker": ticker.upper(),
            "company_multiples": company_multiples,
            "peer_averages": {
                "note": "Peer averages calculated from sector data",
                # Add actual peer averages here
            },
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "raw_data": fundamentals})
```

## Testing

Create a test script:

```python
# test_valuation_analyst.py
from ai_engine.tradingagents.graph.trading_graph import TradingAgentsGraph

def test_valuation_analyst():
    graph = TradingAgentsGraph(
        selected_analysts=["valuation"],
        debug=True,
    )
    
    final_state, signal = graph.propagate("AAPL", "2024-01-15")
    
    assert "valuation_report" in final_state
    assert final_state.get("valuation_score") is not None
    assert final_state.get("fair_value_base") is not None
    
    print("✓ Valuation analyst test passed")
    print(f"Fair Value: ${final_state['fair_value_base']}")
    print(f"Score: {final_state['valuation_score']}/10")

if __name__ == "__main__":
    test_valuation_analyst()
```

## Benefits

1. **Quantitative Foundation**: Adds rigorous valuation analysis to complement qualitative debate
2. **Scenario Planning**: Bear/base/bull scenarios provide risk/reward framework
3. **Entry/Exit Guidance**: Fair value bands inform TPS plan entry and take-profit levels
4. **Risk Assessment**: Valuation conviction and discount/premium inform position sizing
5. **Transparency**: Key assumptions and sensitivity analysis make valuation auditable

## Next Steps

1. Complete integration steps 1-7 above
2. Enhance valuation tools to parse real data from info service
3. Test with multiple tickers
4. Add valuation report to frontend display
5. Consider adding more valuation methods (precedent transactions, sum-of-parts, etc.)

## Related Documentation

- [Integration Plan](../INTEGRATION_PLAN.md) - Full plan for all 17 report types
- [TPS YAML Specification](../../backend/TPS/TPS-YAML-v0.1-1.yaml) - Trading plan format
- [Agent States](../../ai_engine/tradingagents/agents/utils/agent_states.py) - State schema