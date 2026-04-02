# LangGraph Streaming Design Issue

## Problem

The current implementation uses `graph.stream()` which emits a chunk after every node execution. Each chunk contains the full state including all previously completed reports. This causes:

1. **Duplicate Processing**: Same report processed multiple times as it appears in every subsequent chunk
2. **Redundant LLM Calls**: Key takeaway extraction called repeatedly for the same content
3. **Increased Costs**: Unnecessary API calls and token usage

## Root Cause

### LangGraph Stream Behavior
```python
for chunk in graph.stream(init_state):
    # Chunk 1: {fundamentals_report: "..."}
    # Chunk 2: {fundamentals_report: "...", technical_report: "..."}  
    # Chunk 3: {fundamentals_report: "...", technical_report: "...", sec_report: "..."}
    # Each chunk contains ALL previous reports!
```

### Current Code Pattern (Problematic)
```python
for chunk in graph.stream(init_agent_state):
    if "fundamentals_report" in chunk and chunk["fundamentals_report"]:
        # This triggers EVERY time after fundamentals completes
        _write_report("fundamentals_report", chunk["fundamentals_report"])
        _takeaways(chunk["fundamentals_report"])  # Duplicate LLM call!
```

## Solutions

### Option 1: Use invoke() Instead of stream() (Recommended)
```python
# Get final state only - no intermediate chunks
final_state = graph.invoke(init_agent_state, **args)

# Process each report exactly once
for report_key in ["market_report", "fundamentals_report", ...]:
    if report_key in final_state and final_state[report_key]:
        _write_report(report_key, final_state[report_key])
```

**Pros:**
- Simple, clean design
- No duplicate processing
- Processes each report exactly once

**Cons:**
- No real-time progress updates
- Can't show which agent is currently running

### Option 2: Track Processed Reports (Current Fix)
```python
_written_reports = set()

for chunk in graph.stream(init_agent_state):
    if "fundamentals_report" in chunk and "fundamentals_report" not in _written_reports:
        _write_report("fundamentals_report", chunk["fundamentals_report"])
        _written_reports.add("fundamentals_report")
```

**Pros:**
- Keeps real-time progress updates
- Shows current agent status

**Cons:**
- More complex logic
- Still processes every chunk (just skips duplicates)

### Option 3: Stream with Mode="updates" (Best of Both)
```python
# Only get updates (changes), not full state each time
for chunk in graph.stream(init_agent_state, stream_mode="updates"):
    # chunk only contains NEW data, not full state
    for node_name, node_output in chunk.items():
        if "fundamentals_report" in node_output:
            _write_report("fundamentals_report", node_output["fundamentals_report"])
```

**Pros:**
- Real-time updates
- No duplicate processing
- Clean design

**Cons:**
- Requires understanding LangGraph stream modes
- May need code restructuring

## Recommendation

For production use with real-time progress:
1. Use `stream_mode="updates"` to only get changes
2. Or keep current fix with `_written_reports` tracking

For batch/background processing:
1. Use `.invoke()` instead of `.stream()`
2. Simpler and more efficient

## References

- LangGraph Streaming Docs: https://langchain-ai.github.io/langgraph/how-tos/stream-values/
- Stream Modes: "values" (full state), "updates" (only changes), "messages" (message updates)

## Date
2026-04-02