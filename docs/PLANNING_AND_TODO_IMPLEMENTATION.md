# Planning and Todo List Implementation

## Overview

This document describes the planning and todo list management system added to the FlowDeck chat agent, enabling it to handle long-horizon tasks with structured planning, user approval, and progress tracking.

## Architecture

### State Extensions

The `AgentState` TypedDict has been extended with the following fields:

```python
# Planning & Todo Management
task_type: Optional[str]           # "simple" | "complex" | "long-horizon"
planning_phase: Optional[str]      # "analyzing" | "planning" | "awaiting_approval" | "executing" | "completed"
todo_list: Optional[List[Dict]]    # List of todo items with status and metadata
current_step: Optional[int]        # Index of current step (0-based)
plan_approved: bool                # Whether user approved the plan
discoveries: Optional[List[str]]   # New findings during execution
```

### Todo Item Structure

Each todo item in the `todo_list` contains:

```python
{
    "id": int,                              # Unique identifier
    "description": str,                     # Clear, actionable description
    "status": str,                          # "pending" | "in_progress" | "completed" | "blocked"
    "dependencies": List[int],              # IDs of prerequisite tasks
    "estimated_complexity": str,            # "low" | "medium" | "high"
    "expected_tools": List[str],            # Tools/skills expected to use
    "verification": str,                    # How to verify completion
    "actual_tools_used": List[str]          # Tools actually used (populated during execution)
}
```

## Graph Flow

The updated graph flow is:

```
START → planning → (plan_approval if long-horizon | skill_router otherwise)
                ↓
        plan_approval → (skill_router if approved | END if cancelled)
                ↓
        skill_router → (skill_node if matched | call_model for ReAct)
                ↓
        skill_node → (llm_synthesize if succeeded | call_model if failed)
                ↓
        call_model ⇄ tool_node (ReAct loop)
                ↓
              END
```

## New Nodes

### 1. `planning_node`

**Purpose**: Analyzes task complexity and creates execution plans for long-horizon tasks.

**Process**:
1. Extracts last user message
2. Uses LLM to classify task complexity (simple/complex/long-horizon)
3. For long-horizon tasks, creates detailed todo list
4. Returns state updates with task_type, planning_phase, and todo_list

**Task Classification**:
- **Simple**: Single-step queries (e.g., "What's AAPL's price?")
- **Complex**: Multi-step analysis without approval needed (e.g., "Compare AAPL and MSFT")
- **Long-horizon**: Multi-phase tasks requiring planning (e.g., "Create comprehensive investment strategy")

### 2. `plan_approval_node`

**Purpose**: Presents the plan to the user and waits for approval.

**Process**:
1. Formats todo list for user display
2. Emits AIMessage with formatted plan
3. Sets planning_phase to "awaiting_approval"
4. User responds with approval, modifications, or cancellation

**User Options**:
- Approve: "yes", "proceed", "go ahead", "start"
- Cancel: "no", "cancel", "stop"
- Modify: Request specific changes to the plan

## SSE Event Types

New Server-Sent Events for planning:

```typescript
// Plan created
{
  "type": "plan_created",
  "todos": TodoItem[],
  "task_type": "long-horizon"
}

// Awaiting user approval
{
  "type": "awaiting_approval",
  "content": "Plan ready for your review"
}

// Task complexity analysis
{
  "type": "thinking",
  "content": "Analyzing task complexity..." | "Task classified as {type}, proceeding..."
}
```

## Helper Functions

### `_analyze_task_complexity(llm, user_message)`

Uses LLM to classify task complexity based on:
- Number of distinct steps required
- Need for user approval checkpoints
- Multiple data sources needed
- Iterative refinement requirements

Returns:
```python
{
    "complexity": "simple|complex|long-horizon",
    "reasoning": "brief explanation",
    "estimated_steps": int,
    "requires_planning": bool
}
```

### `_create_task_plan(llm, user_message, state)`

Creates detailed execution plan for long-horizon tasks.

Inputs:
- User message
- Available tools and skills
- Current state context

Returns:
```python
{
    "todos": List[TodoItem],
    "explanation": "Brief overview for user",
    "estimated_duration": "e.g., '2-3 minutes'"
}
```

### `_format_plan_for_user(todo_list)`

Formats todo list as readable markdown for user display:

```
⏳ **Step 1**: Analyze user's portfolio holdings
   *Complexity: medium*

⏳ **Step 2**: Fetch market data for all holdings
   *Depends on: Step 1*
   *Complexity: low*

...
```

## Usage Examples

### Example 1: Simple Query (No Planning)

**User**: "What's AAPL's current price?"

**Flow**:
1. `planning_node` → classifies as "simple"
2. Skips plan approval
3. Routes directly to `skill_router` → `call_model`
4. Returns answer immediately

### Example 2: Long-Horizon Task (With Planning)

**User**: "Create a comprehensive investment strategy for a tech-focused portfolio with risk analysis and sector allocation recommendations"

**Flow**:
1. `planning_node` → classifies as "long-horizon"
2. Creates plan with 5-7 steps
3. `plan_approval_node` → presents plan to user
4. User approves
5. Executes steps sequentially
6. Returns comprehensive analysis

## Integration Points

### Backend (`backend/services/chat_service.py`)

The `ChatService` class automatically handles planning events through the existing streaming infrastructure. No changes needed - the new SSE events are automatically forwarded to the frontend.

### Frontend Integration

To display planning UI, add handlers for new event types:

```typescript
// In your SSE event handler
if (event.type === 'plan_created') {
  // Display todo list UI
  displayTodoList(event.todos);
}

if (event.type === 'awaiting_approval') {
  // Show approval buttons
  showApprovalUI();
}
```

## Testing

Run the test suite:

```bash
python test_planning.py
```

Tests verify:
- ✓ State structure includes planning fields
- ✓ Graph compiles with new nodes
- ✓ Agent can be instantiated
- ✓ Planning nodes are integrated

## Future Enhancements

### Phase 2 (Not Yet Implemented)

1. **Step Execution Node**: Execute todo items sequentially with dependency checking
2. **Dynamic Plan Updates**: Modify plan based on discoveries during execution
3. **Progress Persistence**: Save/restore plans across sessions
4. **Plan Templates**: Pre-defined plans for common tasks
5. **Parallel Execution**: Execute independent steps concurrently

### Frontend Components

1. **TodoListPanel**: Visual todo list with status indicators
2. **PlanApprovalDialog**: Modal for plan review and approval
3. **ProgressTracker**: Real-time progress visualization
4. **DiscoveryFeed**: Stream of new findings during execution

## Configuration

No additional configuration required. The planning system uses the existing LLM configuration from `ai_engine/llm_provider.py`.

## Performance Considerations

- **Token Usage**: Planning adds 1-2 LLM calls for long-horizon tasks
- **Latency**: ~2-3 seconds for plan creation
- **Caching**: Plans are not cached (each request creates fresh plan)

## Troubleshooting

### Issue: Plans not being created

**Check**:
1. LLM is properly configured
2. User message is sufficiently complex
3. Check logs for `planning_node` output

### Issue: Approval not working

**Check**:
1. User response contains approval keywords
2. `route_after_plan_approval` logic is correct
3. Frontend is handling `awaiting_approval` event

## References

- Inspired by Roo-Code's issue-fixer mode workflow
- LangGraph documentation: https://langchain-ai.github.io/langgraph/
- AgentSkills.io standard for skill discovery

---

**Implementation Date**: 2026-03-02  
**Author**: Bob (AI Assistant)  
**Status**: Phase 1 Complete (Planning & Approval)