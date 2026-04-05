# SEC File Exploration Implementation

## Overview

The SEC agent now has file exploration capabilities, allowing it to intelligently navigate SEC filings like a coding agent explores code files. This replaces blind truncation with targeted exploration.

## Architecture

### Three-Phase Implementation

#### Phase 1: Backend Support (Completed)
- Added `truncate` parameter to `_fetch_document_text()` in `edgar_service.py`
- Added `raw` parameter to `get_filing_content()` method
- Added `raw` parameter to `/api/data/edgar-filing-content/{ticker}` endpoint
- Updated gateway to pass `raw` parameter through

#### Phase 2: Agent-Side Exploration (Completed)
- Created `SECFilingExplorer` class for file operations
- Created exploration tools (grep, read sections, TOC, stats, read lines)
- Updated SEC analyst to use exploration tools
- Updated prompt to guide exploration strategy

#### Phase 3: Monitoring & Optimization (Current)
- Document usage patterns
- Add logging for mode selection
- Optimization strategies

## How It Works

### Backend API

```python
GET /api/data/edgar-filing-content/{ticker}?raw=false  # LLM extraction (default)
GET /api/data/edgar-filing-content/{ticker}?raw=true   # Full text for exploration
```

**raw=false (Default - LLM Extraction Mode)**:
- Fetches filing, truncates to 100K chars
- Runs LLM extraction (GPT-4o-mini)
- Returns structured sections (12K chars each)
- Cached for 24 hours
- Cost: ~$0.01-0.05 per filing
- Time: 10-60 seconds

**raw=true (Exploration Mode)**:
- Fetches filing, NO truncation
- Returns full text (500K-1M+ chars)
- No LLM extraction
- Cost: ~$0 (no LLM call)
- Time: 2-5 seconds

### Agent Tools

1. **get_sec_toc(ticker)** - Table of contents
   - Lists all sections with sizes and previews
   - Like `ls -l` for files

2. **get_sec_stats(ticker)** - Filing statistics
   - Total size, word count, top terms
   - Like `wc` for files

3. **grep_sec_filing(ticker, pattern, context=3)** - Search
   - Regex search with context lines
   - Like `grep -C 3 pattern file`

4. **read_sec_section(ticker, section, max_chars=20000)** - Read section
   - Extract specific section (risk_factors, mda, etc.)
   - Like reading a function from code

5. **read_sec_lines(ticker, start, end)** - Read line range
   - Get specific lines
   - Like `sed -n 'X,Yp' file`

6. **get_edgar_filing_content(ticker)** - Fallback
   - Original LLM extraction tool
   - Use when exploration doesn't find what's needed

### Exploration Workflow

```
1. get_sec_toc("AAPL")
   → See all sections and sizes

2. get_sec_stats("AAPL")
   → Understand scope, identify key terms

3. grep_sec_filing("AAPL", "regulatory|antitrust")
   → Find specific concerns

4. read_sec_section("AAPL", "risk_factors", max_chars=30000)
   → Get full section based on findings

5. grep_sec_filing("AAPL", "tariff")
   → Follow leads from previous findings
```

## Benefits

### Cost Reduction
- **Before**: Every analysis requires LLM extraction (~$0.01-0.05)
- **After**: Exploration mode is free (no LLM call)
- **Savings**: ~100% on extraction costs when using exploration

### Speed Improvement
- **Before**: 10-60 seconds for LLM extraction
- **After**: 2-5 seconds for full text fetch
- **Improvement**: 2-10x faster

### Better Coverage
- **Before**: Truncated to 100K → 80K → 12K per section
- **After**: Full filing access (500K-1M+ chars)
- **Improvement**: No information loss

### Flexibility
- **Before**: Fixed sections (risk, MD&A, competition)
- **After**: Search anything, follow leads dynamically
- **Improvement**: Agent-driven exploration

## Monitoring

### Logging

The backend logs when exploration mode is used:

```python
logger.info(f"Fetching raw text for {ticker} {form_type} (exploration mode)")
```

### Metrics to Track

1. **Mode Usage**:
   - Count of `raw=true` vs `raw=false` requests
   - Which mode agents prefer

2. **Performance**:
   - Response time for each mode
   - Cache hit rates

3. **Cost**:
   - LLM extraction costs (raw=false)
   - Total cost savings from exploration mode

4. **Quality**:
   - Compare analysis quality between modes
   - Agent iteration counts (exploration may use more)

### Implementation

Add to `backend/services/edgar_service.py`:

```python
import logging
from collections import Counter

logger = logging.getLogger(__name__)

# Track mode usage
_mode_usage_stats = Counter()

def get_filing_content(..., raw: bool = False):
    mode = "exploration" if raw else "extraction"
    _mode_usage_stats[mode] += 1
    
    if raw:
        logger.info(f"Fetching raw text for {ticker} {form_type} (exploration mode)")
    else:
        logger.info(f"Fetching extracted sections for {ticker} {form_type} (LLM extraction mode)")
    
    # ... rest of method
```

## Optimization Strategies

### 1. Hybrid Approach

Agent can use both modes strategically:

```python
# Quick overview with LLM extraction
get_edgar_filing_content("AAPL")  # Fast, structured

# Deep dive with exploration
grep_sec_filing("AAPL", "specific_concern")  # Targeted
```

### 2. Caching Strategy

- Cache full text (exploration mode) separately from extracted sections
- LRU eviction for memory management
- Consider Redis for distributed caching

### 3. Prompt Optimization

Guide agent to:
- Start with TOC and stats (cheap, informative)
- Use grep for targeted searches (efficient)
- Only read full sections when needed (avoid waste)
- Use LLM extraction as fallback (when exploration fails)

### 4. Performance Tuning

- **Parallel fetching**: If analyzing multiple tickers
- **Streaming**: For very large filings
- **Compression**: Store cached text compressed
- **Indexing**: Pre-index filings for faster grep (optional)

## Usage Examples

### Example 1: Quick Analysis

```python
# Agent uses LLM extraction (fast, structured)
get_edgar_filing_content("AAPL")
→ Returns pre-extracted sections
→ Agent analyzes and generates report
```

### Example 2: Deep Investigation

```python
# Agent explores filing
get_sec_toc("AAPL")
→ Sees "Risk Factors" is 45K chars

grep_sec_filing("AAPL", "regulatory|antitrust")
→ Finds 3 mentions

read_sec_section("AAPL", "risk_factors", max_chars=50000)
→ Gets full section

grep_sec_filing("AAPL", "App Store")
→ Follows lead from risk factors
```

### Example 3: Hybrid Approach

```python
# Start with extraction for overview
get_edgar_filing_content("AAPL")
→ Quick structured overview

# Drill down with exploration
grep_sec_filing("AAPL", "services revenue")
→ Find all mentions

read_sec_lines("AAPL", 1234, 1250)
→ Read specific context
```

## Comparison: Before vs After

| Aspect | Before (LLM Extraction) | After (File Exploration) |
|--------|------------------------|--------------------------|
| **Cost** | ~$0.01-0.05 per filing | ~$0 (no LLM) |
| **Speed** | 10-60 seconds | 2-5 seconds |
| **Coverage** | 12K chars per section | Full filing (500K+ chars) |
| **Flexibility** | Fixed sections | Search anything |
| **Accuracy** | LLM interpretation | Direct text matching |
| **Information Loss** | High (truncation) | Low (full text) |
| **Agent Control** | Passive (reads sections) | Active (explores) |

## Future Enhancements

### Phase 4: Advanced Features

1. **Semantic Search**: Use embeddings for concept-based search
2. **Cross-Filing Analysis**: Compare sections across multiple filings
3. **Table Extraction**: Parse financial tables from HTML
4. **Historical Tracking**: Track changes in sections over time
5. **Smart Caching**: Predict which sections agent will need

### Phase 5: Performance Optimization

1. **Indexing**: Pre-index filings for instant grep
2. **Streaming**: Stream large filings in chunks
3. **Parallel Processing**: Fetch multiple filings concurrently
4. **Smart Truncation**: Intelligently truncate based on relevance

## Troubleshooting

### Issue: Agent not using exploration tools

**Solution**: Check prompt, ensure tools are available, verify max_iterations is sufficient (8+)

### Issue: Exploration too slow

**Solution**: Check network latency, consider caching, verify filing size

### Issue: Agent wastes iterations

**Solution**: Improve prompt guidance, add examples, tune exploration strategy

### Issue: Missing information

**Solution**: Verify section patterns, check filing format, use LLM extraction as fallback

## Conclusion

The SEC file exploration implementation transforms the SEC agent from a passive reader of truncated content into an active explorer that can intelligently navigate large filings to find the most relevant information for traders.

**Key Takeaway**: Like a coding agent explores code files, the SEC agent now explores SEC filings - searching, reading sections, and following leads to extract trader-relevant insights.