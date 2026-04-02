# SEC Analyst Duplicate Key Takeaways Extraction Fix

## Problem

The SEC analyst was causing duplicate LLM calls for extracting key takeaways from the same report content. This resulted in:

1. **Wasted API calls**: The same extraction prompt was being sent multiple times
2. **Increased costs**: Each duplicate call costs money
3. **Slower analysis**: Unnecessary processing time

## Root Cause

The SEC analyst generates a structured report that **already includes** a "## 5. Key Trader Takeaways" section as part of its output (defined in `ai_engine/tradingagents/agents/analysts/prompts.py`).

However, the report persistence logic in both:
- `backend/services/analysis_service.py` (line 381)
- `backend/run_analysis_standalone.py` (line 218)

Was calling `_takeaways(content)` for **every** report, which uses `extract_key_takeaways_structured()` to extract takeaways from the entire report content using an LLM call.

This meant:
1. SEC analyst generates report with takeaways in section 5 ✓
2. Report persistence extracts takeaways from the full report (including section 5) ✗ **DUPLICATE**

## Solution

Modified the `_write_report()` function in both files to **skip** key takeaway extraction for SEC reports since they already contain the takeaways in their structured output.

### Changes Made

**File: `backend/services/analysis_service.py`**
```python
def _write_report(key, content, score, label, llm_usage=None, resources=None, **extra):
    try:
        # SEC report already has "Key Trader Takeaways" section built-in, don't extract again
        # This prevents duplicate LLM calls for the same content
        if key == "sec_report":
            takeaways = []  # SEC report has takeaways in section 5, don't extract
        else:
            takeaways = _takeaways(content)
        data = _build_report_json(content, score, label, takeaways, **extra)
        # ... rest of function
```

**File: `backend/run_analysis_standalone.py`**
Same change applied to the standalone script's `_write_report()` function.

## Impact

- **Eliminates duplicate LLM calls** for SEC report key takeaway extraction
- **Reduces API costs** by avoiding unnecessary structured output calls
- **Faster analysis execution** by removing redundant processing
- **No functional change**: SEC reports still have their key takeaways (in section 5 of the report content)

## Notes

- The SEC analyst's report format is defined in `ai_engine/tradingagents/agents/analysts/prompts.py` (SEC_ANALYST_SYSTEM_MESSAGE)
- Section 5 of SEC reports explicitly includes "Key Trader Takeaways" as 3-5 bullet points
- Other analyst reports (market, sentiment, news, fundamentals, technical) do NOT have built-in takeaways sections, so they still need extraction
- The Risk Manager's final trade decision also extracts its own key takeaways via structured output, which is correct and should remain

## Testing

To verify the fix:
1. Run an analysis with SEC analyst enabled
2. Check the logs for LLM calls
3. Confirm only ONE call is made for SEC report generation (no duplicate extraction call)
4. Verify SEC report still contains key takeaways in section 5

## Related Files

- `ai_engine/tradingagents/agents/analysts/sec_analyst.py` - SEC analyst implementation
- `ai_engine/tradingagents/agents/analysts/prompts.py` - SEC analyst prompt with section 5 definition
- `ai_engine/tradingagents/agents/utils/insight_extraction.py` - Key takeaway extraction utility
- `backend/services/analysis_service.py` - Main analysis service (fixed)
- `backend/run_analysis_standalone.py` - Standalone analysis script (fixed)