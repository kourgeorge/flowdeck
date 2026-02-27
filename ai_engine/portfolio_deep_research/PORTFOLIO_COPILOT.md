# Portfolio Copilot: Risk Profiling & Active Questioning

## Overview

The Portfolio Copilot extends FlowDeck's portfolio deep research with two powerful features:

1. **Portfolio Risk Profiling** - Comprehensive risk analysis of portfolio composition
2. **Active Questioning Engine** - Critical questions that challenge your investment decisions

These features transform FlowDeck from a passive dashboard into an **active advisor** that questions your portfolio positioning.

---

## Architecture

### New Components

```
ai_engine/portfolio_deep_research/
├── portfolio_risk_profiler.py    # Risk analysis engine
├── portfolio_interrogator.py     # Question generation system
├── state.py                       # Updated with risk_profile & portfolio_questions
├── graph.py                       # New analyze_portfolio_risk node
└── prompts.py                     # Risk profiling prompts
```

### Workflow Integration

The new `analyze_portfolio_risk` node runs after `load_existing_reports` and before `research`:

```
interpret_query → plan → load_existing_reports 
    → analyze_portfolio_risk → research → extract_evidence 
    → synthesize → qa → deliver
```

---

## Portfolio Risk Profiling

### What It Analyzes

1. **Sector Exposure**
   - Percentage allocation to each sector
   - Identifies concentration risks
   - Flags missing defensive sectors

2. **Position Concentration**
   - Top 3 and Top 5 concentration percentages
   - Herfindahl-Hirschman Index (HHI)
   - Single-stock risk assessment

3. **Beta Analysis**
   - Portfolio-level beta (market sensitivity)
   - High-beta vs low-beta stock counts
   - Volatility implications

4. **Correlation Clusters**
   - Groups of stocks that move together
   - Identifies false diversification
   - Sector-based correlation detection

5. **Risk Score (0-100)**
   - Composite risk metric
   - Weighted by concentration, beta, diversification
   - Higher = riskier portfolio

### Example Output

```python
{
    "sector_exposure": {
        "Technology": 45.0,
        "Healthcare": 20.0,
        "Financials": 15.0,
        "Consumer Discretionary": 10.0,
        "Energy": 10.0
    },
    "concentration_risk": {
        "top_3_concentration": 52.5,
        "top_5_concentration": 75.0,
        "herfindahl_index": 625.0,
        "total_positions": 8,
        "avg_position_size": 12.5
    },
    "beta_analysis": {
        "portfolio_beta": 1.35,
        "beta_std": 0.28,
        "high_beta_count": 4,
        "low_beta_count": 1,
        "beta_range": "0.75 - 1.82"
    },
    "correlation_clusters": [
        ["AAPL", "MSFT", "GOOGL", "META"],
        ["JPM", "BAC"]
    ],
    "risk_warnings": [
        "High sector concentration: 45.0% in Technology...",
        "Top 3 positions represent 52.5% of portfolio...",
        "High portfolio beta (1.35)..."
    ],
    "risk_score": 68.5
}
```

---

## Active Questioning Engine

### Question Categories

1. **Risk Questions** (🔴 High Urgency)
   - Concentration risks
   - Volatility exposure
   - Sector-specific vulnerabilities

2. **Opportunity Questions** (🟡 Medium Urgency)
   - Missing exposures
   - Underperformance risks
   - Rebalancing opportunities

3. **Macro Questions** (🟡 Medium Urgency)
   - Interest rate sensitivity
   - Growth vs value positioning
   - Economic cycle exposure

4. **Behavioral Questions** (🔴 High Urgency)
   - Emotional preparedness
   - Stress testing
   - Decision-making frameworks

### Example Questions

```python
[
    {
        "question": "Why are you 45% exposed to Technology?",
        "category": "risk",
        "urgency": "high",
        "context": "Your portfolio is heavily concentrated in Technology (45.0%). If this sector underperforms, your entire portfolio could suffer significant losses. Sector-specific risks (regulation, technology disruption, economic cycles) are amplified.",
        "suggested_action": "Consider reducing Technology exposure to 25-30% and diversifying into defensive sectors (Healthcare, Consumer Staples) or uncorrelated sectors."
    },
    {
        "question": "What happens if one of your top 3 holdings drops 30%?",
        "category": "risk",
        "urgency": "high",
        "context": "Your top 3 positions represent 52.5% of your portfolio. A 30% drop in just one position would cause a 5.3% portfolio loss. This concentration creates significant single-stock risk.",
        "suggested_action": "Reduce top 3 concentration to under 40% by trimming winners and adding new positions. No single stock should exceed 15% of portfolio."
    },
    {
        "question": "Are you prepared for 35% more volatility than the market?",
        "category": "risk",
        "urgency": "high",
        "context": "Your portfolio beta is 1.35, meaning it's 35% more volatile than the market. When the market drops 10%, you could drop 13.5%. But you also get amplified gains in bull markets.",
        "suggested_action": "If this volatility is uncomfortable, add lower-beta stocks (Consumer Staples, Utilities) or reduce position sizes in high-beta names. Target beta of 1.0-1.2 for balanced risk."
    }
]
```

---

## Usage

### Basic Usage

The risk profiling and questioning happen automatically in the portfolio deep research workflow:

```python
from ai_engine.portfolio_deep_research.graph import portfolio_research_graph

# Run portfolio analysis
result = await portfolio_research_graph.ainvoke({
    "tickers": ["AAPL", "MSFT", "GOOGL", "NVDA", "META", "TSLA", "AMD", "INTC"],
    "user_query": "Analyze my tech-heavy portfolio"
})

# Access risk profile
risk_profile = result["risk_profile"]
print(f"Risk Score: {risk_profile['risk_score']}/100")

# Access critical questions
questions = result["portfolio_questions"]
for q in questions:
    print(f"{q['urgency'].upper()}: {q['question']}")
```

### Standalone Risk Analysis

You can also use the risk profiler independently:

```python
from ai_engine.portfolio_deep_research.portfolio_risk_profiler import analyze_portfolio_risk

tickers = ["AAPL", "MSFT", "GOOGL", "NVDA", "META"]
existing_reports = {...}  # From backend API

risk_profile = analyze_portfolio_risk(tickers, existing_reports)

print(f"Sector Exposure: {risk_profile.sector_exposure}")
print(f"Risk Score: {risk_profile.risk_score}")
print(f"Warnings: {risk_profile.risk_warnings}")
```

### Standalone Question Generation

```python
from ai_engine.portfolio_deep_research.portfolio_interrogator import generate_portfolio_questions

risk_profile_dict = {...}  # From analyze_portfolio_risk
tickers = ["AAPL", "MSFT", "GOOGL"]

questions = generate_portfolio_questions(tickers, risk_profile_dict)

for q in questions:
    print(f"\n{q.question}")
    print(f"Context: {q.context}")
    print(f"Action: {q.suggested_action}")
```

---

## Report Integration

The risk profile and questions are automatically integrated into the final report:

### Risk Profile Section

```markdown
## Portfolio Risk Profile

**Risk Score:** 68/100

**Sector Exposure:**
- Technology: 45.0%
- Healthcare: 20.0%
- Financials: 15.0%
- Consumer Discretionary: 10.0%
- Energy: 10.0%

**Risk Warnings:**
- High sector concentration: 45.0% in Technology...
- Top 3 positions represent 52.5% of portfolio...
- High portfolio beta (1.35)...
```

### Critical Questions Section

```markdown
## Critical Questions About Your Portfolio

🔴 **Why are you 45% exposed to Technology?**

Your portfolio is heavily concentrated in Technology (45.0%). If this sector underperforms, your entire portfolio could suffer significant losses...

*Suggested Action:* Consider reducing Technology exposure to 25-30%...

🔴 **What happens if one of your top 3 holdings drops 30%?**

Your top 3 positions represent 52.5% of your portfolio...

*Suggested Action:* Reduce top 3 concentration to under 40%...
```

---

## Configuration

### Risk Score Weights

The risk score (0-100) is calculated from:

- **Sector Concentration** (0-30 points): >50% in one sector = 30 points
- **Position Concentration** (0-25 points): Top 3 >60% = 25 points
- **Beta Risk** (0-25 points): Beta >1.5 = 25 points
- **Diversification** (0-20 points): <5 positions = 20 points

### Question Limits

- Maximum 8 questions per portfolio
- Prioritized by urgency: high → medium → low
- Covers all categories: risk, opportunity, macro, behavioral

---

## Key Differentiators

### Why This Is Unique

1. **Active vs Passive**
   - Most tools show static metrics
   - FlowDeck actively questions your decisions

2. **Behavioral Focus**
   - Addresses investor psychology
   - Prepares for emotional responses to volatility

3. **Actionable Insights**
   - Every question includes suggested actions
   - Context explains why it matters

4. **Multi-Agent Architecture**
   - Leverages existing analyst reports
   - Integrates with debate system (conservative/aggressive/neutral)

5. **Institutional-Grade for Retail**
   - Risk metrics used by hedge funds
   - Presented in accessible language

---

## Future Enhancements

### Phase 2 (Behavioral Tracking)

- Track user actions (buys, sells, timing)
- Detect patterns (momentum chasing, panic selling)
- Personalized behavioral warnings

### Phase 3 (Scenario Analysis)

- "What if rates rise 100bps?"
- "What if tech sector drops 20%?"
- Monte Carlo simulations

### Phase 4 (Comparative Analysis)

- Compare to market indices
- Compare to similar portfolios
- Peer benchmarking

---

## Technical Details

### Dependencies

- Existing reports from `backend/services/report_service.py`
- Sector data from fundamentals analyst
- Beta data from technical analyst
- No external APIs required

### Performance

- Risk analysis: <1 second for 50 stocks
- Question generation: <1 second
- No LLM calls required (rule-based)
- Scales linearly with portfolio size

### Error Handling

- Gracefully handles missing data
- Falls back to "Unknown" sector if not available
- Skips beta analysis if data unavailable
- Always returns valid risk profile

---

## Example: Complete Workflow

```python
import asyncio
from ai_engine.portfolio_deep_research.graph import portfolio_research_graph

async def analyze_my_portfolio():
    result = await portfolio_research_graph.ainvoke({
        "tickers": ["AAPL", "MSFT", "GOOGL", "NVDA", "META", "TSLA", "AMD", "INTC"],
        "user_query": "Should I rebalance my tech portfolio?"
    })
    
    # Risk Profile
    risk = result["risk_profile"]
    print(f"\n=== RISK PROFILE ===")
    print(f"Risk Score: {risk['risk_score']}/100")
    print(f"Portfolio Beta: {risk['beta_analysis']['portfolio_beta']}")
    print(f"Top Sector: {max(risk['sector_exposure'].items(), key=lambda x: x[1])}")
    
    # Critical Questions
    questions = result["portfolio_questions"]
    print(f"\n=== CRITICAL QUESTIONS ({len(questions)}) ===")
    for i, q in enumerate(questions, 1):
        print(f"\n{i}. {q['question']}")
        print(f"   Urgency: {q['urgency'].upper()}")
        print(f"   Action: {q['suggested_action'][:100]}...")
    
    # Full Report
    print(f"\n=== FULL REPORT ===")
    print(result["final_answer"][:500] + "...")

asyncio.run(analyze_my_portfolio())
```

---

## Conclusion

The Portfolio Copilot transforms FlowDeck from a **passive information tool** into an **active investment advisor**.

Instead of just showing data, it:
- ✅ Identifies hidden risks
- ✅ Asks tough questions
- ✅ Challenges your assumptions
- ✅ Suggests concrete actions

This is the **moat**: institutional-grade reasoning for retail investors.