# Polymarket Relevance Scoring Fix

## Problem
When viewing Polymarket sentiment for INTC (Intel), the system was showing markets for other tech companies (META, GOOGL, TSLA, etc.) instead of Intel-specific markets. This happened because:

1. **Overly broad narrative matching**: The system searched for generic terms like "tech sector", "AI stocks", "semiconductor industry" which matched markets about ANY tech company
2. **No penalty for other tickers**: Markets about "META price" or "GOOGL earnings" were scored positively because they matched broad sector narratives
3. **Low relevance threshold**: The 0.1 minimum score allowed weakly related markets through
4. **Missing event-level context**: Event descriptions weren't being analyzed, missing important ticker mentions

## Solution

### 1. Enhanced Text Analysis to Include Event-Level Data (`polymarket_relevance_scorer.py`)
- **What**: Now analyzes **4 text sources** instead of 2:
  - Market question
  - Market description
  - **Event description** (NEW)
  - **Event title** (NEW)
- **Why**: Polymarket groups related markets into events. The event-level description often contains the ticker/company name even when individual market questions don't
- **Example**:
  ```
  Event: "Intel Stock Price Predictions"
  Event Description: "Track INTC performance for Q2 2026"
  Market Question: "Will price exceed $50?" ← No ticker here!
  ```
  Without event data, we'd miss this Intel-specific market.

### 2. Added Negative Scoring for Other Tickers (`polymarket_relevance_scorer.py`)
- **What**: Modified `calculate_keyword_score()` to return **-0.5** when a market is about a different specific company
- **How**: Uses regex to detect other ticker symbols (META, GOOGL, AMZN, TSLA, etc.) in ALL text sources
- **Result**: Markets like "What will META hit Week of April 6 2026?" now get -0.5 score for INTC searches

```python
# Example scores:
"What will Intel (INTC) hit Week of April 6 2026?" → +0.30 (direct match)
"What will Meta Platforms, Inc. (META) hit Week of April 6 2026?" → -0.50 (other ticker)
"Will semiconductor industry grow in 2026?" → 0.00 (neutral, no specific ticker)
```

### 3. Improved Narrative Generation (`polymarket_narrative_mapper.py`)
- **Expanded direct matches**: Added more ticker-specific queries:
  - `INTC Week` (catches "INTC Week of..." markets)
  - `$INTC`, `(INTC)` (different ticker formats)
  - Company name + "price" variations
  
- **Reduced broad narratives**:
  - Industry narratives: Limited to top 3 (was unlimited)
  - Sector narratives: Limited to top 2 specific ones, filtered out generic "tech sector" and "tech stocks"
  - Macro narratives: Reduced from 4 to 2, only added if few direct matches
  - Removed economic indicators and market sentiment (too generic)

### 4. Increased Minimum Relevance Threshold (`polymarket_service.py`)
- **Changed**: `min_score` from 0.1 to 0.15
- **Effect**: Filters out weakly related markets that only match through broad narratives

## Testing Results

```bash
# Text Analysis (4 sources):
question + description + event_description + event_title

# INTC Narratives (prioritized):
1. INTC
2. INTC stock
3. INTC price
4. INTC earnings
5. INTC Week          # NEW - catches weekly price markets
6. $INTC              # NEW - alternative format
7. (INTC)             # NEW - parenthetical format
8. Intel
9. Intel stock
10. Intel price       # NEW - more specific
11. processors
12. chips
# ... (reduced generic narratives)

# Scoring Examples:
Intel (INTC) in question:        +0.30 ✓ (shown)
Intel (INTC) in event desc:      +0.30 ✓ (shown - NEW!)
META in any text source:         -0.50 ✗ (filtered out)
Generic tech market:              0.00 ✗ (below 0.15 threshold)
```

## Impact

### Before Fix
- Showed 30 markets for INTC
- Most were about other companies (META, GOOGL, TSLA, etc.)
- Sentiment was diluted by unrelated markets

### After Fix
- Shows only INTC-specific markets
- Markets about other companies are filtered out (negative scores)
- Generic industry markets need higher relevance to appear
- More accurate sentiment based on Intel-specific predictions

## Files Modified

1. `backend/services/polymarket_relevance_scorer.py`
   - Added negative scoring for other tickers in `calculate_keyword_score()`

2. `backend/services/polymarket_narrative_mapper.py`
   - Expanded direct ticker matches
   - Reduced broad sector/industry narratives
   - Filtered generic terms

3. `backend/services/polymarket_service.py`
   - Increased minimum relevance threshold from 0.1 to 0.15

## Future Improvements

1. **Dynamic threshold**: Adjust min_score based on number of direct matches found
2. **Competitor awareness**: Add positive scoring for direct competitor comparisons (e.g., "Intel vs AMD")
3. **Market type filtering**: Prioritize price prediction markets over general sentiment markets
4. **Time-based weighting**: Give more weight to markets resolving soon

## Deployment

No database changes required. Changes take effect immediately after deployment.

To test locally:
```bash
python backend/test_polymarket_nvda.py  # Update to test INTC