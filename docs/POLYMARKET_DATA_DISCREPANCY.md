# Polymarket Data Discrepancy Analysis

## Issue Description

User reported that the probabilities shown in FlowDeck for NVIDIA (NVDA) don't match what's visible on Polymarket directly.

### Polymarket Direct View (Week of March 30, 2026)
Markets showing NVDA hitting specific price levels:
- $192: 4%
- $188: 9%
- $184: 11%
- $180: 31%
- $176: 40%
- $172: 52%
- $168: 73%
- $164: 60%
- $160: 49%
- $156: 30%
- $152: (volume data)
- $148: 6%
- $144: 6%
- $140: 6%

### FlowDeck Display
Top Relevant Markets showing:
- "Will NVIDIA (NVDA) close above $180 end of March?" - 1%
- "Will NVIDIA (NVDA) hit (HIGH) $192 Week of March 30 2026?" - 0%
- "Will NVIDIA (NVDA) close at $165-$170 on final day..." - 17%
- "Will NVIDIA (NVDA) close above $190 end of March?" - 3%
- "Will NVIDIA (NVDA) close above $170 end of March?" - 43%

## Root Cause Analysis

### 1. Different Market Sets
The markets shown on Polymarket's direct interface are **price ladder markets** for a specific week, while FlowDeck is finding **broader time-frame markets** through keyword search.

### 2. Search Query Limitations
FlowDeck searches using these narratives for NVDA:
- "NVDA", "NVDA stock", "NVDA price", "NVDA earnings"
- "Nvidia", "GPU", "AI chips", "graphics cards"
- "chip shortage", "semiconductor demand", "GPU market", "AI chips"
- Sector/macro narratives

The Polymarket API's search may not return the specific weekly price ladder markets when searching for general terms like "NVDA" or "Nvidia".

### 3. Volume/Liquidity Filtering
FlowDeck filters out markets with:
- Volume < $100
- Liquidity < $50

Some of the price ladder markets shown on Polymarket have "$0 Vol." which would be filtered out.

### 4. Relevance Scoring
FlowDeck ranks markets by relevance score, which considers:
- Keyword matching
- Volume (log scale)
- Liquidity
- Time decay factor
- Narrative category

Markets with low volume but high specificity might score lower than broader markets with higher volume.

## Why the Numbers Don't Match

The probabilities ARE correct for the markets FlowDeck is showing - they're just **different markets** than what you see on Polymarket's direct interface.

For example:
- Polymarket shows: "$180 Week of March 30" = 31%
- FlowDeck shows: "$180 end of March" = 1%

These are different markets with different resolution criteria and timeframes.

## Solutions

### Short-term Improvements

1. **Add Specific Price Search Terms**
   - Add search queries like "NVDA $180", "NVDA $170", etc.
   - Add "Week of [date]" patterns

2. **Lower Volume Thresholds**
   - Reduce MIN_VOLUME from $100 to $10
   - Reduce MIN_LIQUIDITY from $50 to $10
   - This will capture more markets but may include noise

3. **Improve Search Specificity**
   - Add date-specific searches: "NVDA March 2026", "NVDA April 2026"
   - Add price-specific searches: "NVDA price target", "NVDA $XXX"

4. **Better Logging**
   - Already added detailed logging to track:
     - Which markets are found
     - What probabilities are extracted
     - How relevance scores are calculated
     - Which markets are filtered out

### Long-term Solutions

1. **Direct Event Access**
   - Instead of searching, directly access Polymarket's event pages
   - For NVDA, find the "NVIDIA Weekly Price" event and get all markets

2. **Market Grouping**
   - Group related markets (e.g., all price ladder markets for same week)
   - Show them as a cohesive set rather than individual markets

3. **Custom Market Discovery**
   - Build a mapping of known high-value market series
   - Directly fetch these by event ID rather than search

4. **User Feedback Loop**
   - Allow users to report missing markets
   - Learn which market types are most valuable

## Implementation Plan

### Phase 1: Enhanced Logging (✓ Completed)
- Added detailed logging to `extract_probability()` function
- Added aggregation logging to track sentiment calculation
- This will help diagnose exactly what's happening

### Phase 2: Lower Thresholds
```python
# In polymarket_vendor.py
MIN_VOLUME = 10  # Down from 100
MIN_LIQUIDITY = 10  # Down from 50
```

### Phase 3: Enhanced Search Terms
```python
# In polymarket_narrative_mapper.py
# Add for NVDA:
- "NVDA Week of"
- "NVDA March 2026"
- "NVDA price target"
- "NVDA $180"
- "NVDA $170"
- "NVDA $160"
```

### Phase 4: Market Type Detection
- Detect "price ladder" markets
- Group them together
- Display as a cohesive price distribution

## Testing Recommendations

1. **Check Backend Logs**
   - Look for the detailed probability extraction logs
   - See which markets are being found
   - Check relevance scores

2. **Test with Lower Thresholds**
   - Temporarily set MIN_VOLUME=1 and MIN_LIQUIDITY=1
   - See if more markets appear

3. **Manual API Testing**
   - Use Polymarket API directly to search for "NVDA"
   - Compare results with what FlowDeck finds

4. **Compare Market IDs**
   - Get market IDs from Polymarket's UI
   - Check if FlowDeck is finding those specific markets

## Conclusion

The discrepancy is NOT a bug in probability extraction - the probabilities are correct for the markets being shown. The issue is that FlowDeck is finding **different markets** than what's prominently displayed on Polymarket's interface.

The solution is to improve market discovery to find the specific price ladder markets that users expect to see.