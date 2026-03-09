# Chat Agent Design Gaps vs Claude Code–Style Behavior

This doc compares the current FlowDeck chat agent to a “Claude Code”–style experience (transparent tool use, streaming, plan approval, code actions) and lists **design issues you have today** that can be fixed.

---

## 1. No true token-by-token streaming

**Current behavior:** The agent uses `llm.invoke()` in `_call_model_node` and `llm_synthesize_node`. LangGraph is streamed with `stream_mode="updates"`, so the client only gets one `token` event per LLM **turn** — i.e. the full reply text when the node finishes. The UI shows “streaming” by appending that one big chunk and a cursor, but the model output is not streamed incrementally.

**Claude Code behavior:** Text appears token-by-token as the model generates it.

**Fix:** Use the LLM’s streaming API inside the graph (e.g. `llm.stream()` or `astream`) and yield SSE `token` events from a streaming callback. That requires either:
- A custom “streaming” node that consumes the LLM stream and yields events (and still participates in the graph state updates), or
- LangGraph’s stream modes that support streaming within a node (e.g. streaming the `call_model` node’s output).  

Then the frontend will receive many small `token` chunks and can render them incrementally.

---

## 2. Tools-first, then one big reply (no interleaved “I’m doing X”)

**Current behavior:** The system prompt says: *“Execute tool calls IMMEDIATELY without announcing your intent first. Do NOT say ‘I’ll fetch...’ … Call the necessary tools directly.”* So the agent stays silent until tools finish, then sends one final answer. The UI order is: skill blocks → tool call blocks → single message bubble.

**Claude Code behavior:** Often a short line of reasoning or “I’ll look that up” before or between tool use, then tool blocks, then the main answer. Feels more conversational and transparent.

**Fix:** Relax the prompt to allow (optional) one short line before/around tool use (e.g. “Checking current price…”). Optionally, for certain tools, emit a short “status” message (e.g. “Fetching quote for AAPL…”) as an SSE event so the UI can show it without changing the model’s style too much.

---

## 3. Planning / long-horizon events not surfaced in the UI

**Current behavior:** The graph has `planning_node` and `plan_approval_node`, and the stream emits:
- `plan_created` (with `todos`, `task_type`)
- `awaiting_approval` (“Plan ready for your review”)

The frontend **does not** handle these: no `plan_created` or `awaiting_approval` in the API client, so the user never sees a plan or “Proceed / Cancel” step.

**Claude Code behavior:** For multi-step tasks, the assistant can show a plan and wait for confirmation before executing.

**Fix:**
- In `api.ts`, handle `plan_created` and `awaiting_approval` in the SSE parser and expose them (e.g. `onPlanCreated`, `onAwaitingApproval`).
- In `ChatView` / `useChatState`, store “current plan” and “awaiting approval” state; render a plan card with “Proceed” / “Cancel” (or “Modify”).
- Backend: plan approval currently assumes the *next* user message is the approval. For a dedicated “Proceed” button you may need a separate endpoint or a special message (e.g. `{"approve_plan": true}`) so the graph routes to execution instead of treating it as a new user query.

---

## 4. One assistant message blob per turn

**Current behavior:** One assistant message holds: `content`, `tool_call_events[]`, `skill_activation_events[]`, `charts[]`, `tokens_used`, `follow_up_questions`. Everything is attached to a single bubble; order is fixed (skills → tools → text + charts).

**Claude Code behavior:** Clear visual separation: optional thinking block, then tool/action blocks, then the main answer. Sometimes multiple distinct blocks (e.g. “Here’s what I did” vs “Here’s the answer”).

**Fix:** Keep a single logical “turn” but improve structure:
- Option A: Render “phases” inside one message: e.g. “Step 1: Tools” (collapsible), “Step 2: Answer”. No backend change.
- Option B: Split into multiple UI “blocks” (thinking, tools, answer) with distinct styling and order, still under one turn. Backend could optionally emit block boundaries (e.g. `type: "block_start", block: "answer"`) for consistency.

---

## 5. “Thinking” is sparse and not reasoning

**Current behavior:** “Thinking” updates are only sent at specific points: planning (“Analyzing task complexity…”), skill start (“Running X workflow…”), or when the model returns tool_calls (“Calling get_ticker_quote…”). There is no stream of the model’s internal reasoning.

**Claude Code behavior:** Can show extended thinking (e.g. “Considerations” / chain-of-thought) when the model emits it, then the final answer.

**Fix:** If your LLM supports extended thinking (e.g. a thinking block in the response), parse it and emit it as a dedicated SSE type (e.g. `thinking_block` or `reasoning`) and render it in a separate, collapsible section. If the model doesn’t support it, the current “Thinking…” + tool names is acceptable; you could still add short status messages (see §2) for clarity.

---

## 6. No code block actions (Run / Apply)

**Current behavior:** Markdown code blocks are rendered with syntax highlighting and a global “Copy message” button; there is no “Run” or “Apply” on code blocks.

**Claude Code behavior:** Code blocks often have “Copy”, “Run”, “Apply” (or “Insert into file”).

**Fix:** For blocks that look like executable code (e.g. from `execute_python` or markdown ```python):
- Add a “Run” button that sends the code to a safe execution endpoint (or reuses `execute_python` semantics) and shows output below the block.
- “Apply” only makes sense if you have an editor or file context; otherwise skip or defer.

---

## 7. Stop is “stop receiving”, not “stop the agent”

**Current behavior:** The client uses `AbortController` to cancel the fetch. The backend runs the agent in a thread; when the client disconnects, the thread keeps running until the next yield. Tokens are not deducted for the partial run in a well-defined way.

**Claude Code behavior:** Cancel typically stops the model and tool execution on the server.

**Fix:** Use the request’s lifecycle (e.g. `request.is_disconnected()` in FastAPI or a shared “cancel” flag) inside the streaming loop and break out of the graph stream when the client disconnects. Optionally: deduct only tokens used up to the stop point; or don’t deduct on cancel (policy choice).

---

## 8. Reply text only after all tool rounds

**Current behavior:** Because there’s no LLM streaming (§1), the user sees: tool 1 → tool 2 → … → then the entire reply. If the agent does 5 tool calls, the user waits for all 5 before seeing any prose.

**Claude Code behavior:** Often some text is streamed before or between tool calls (e.g. “Let me check that” then tools then “Here’s what I found…”).

**Fix:** Same as §1 (stream tokens) and §2 (allow short pre/post tool phrases). Once the LLM streams, you can show partial text as it arrives; combined with optional status messages, the experience gets closer to Claude Code.

---

## 9. Error content is generic

**Current behavior:** On exception, the backend yields `{"type":"error","content":"I encountered an error: ..."}`. The frontend shows it in a single error banner. No structured error type or retry.

**Claude Code behavior:** Errors are often clear and sometimes suggest “Try again” or a concrete next step.

**Fix:** Keep raising on the backend (no swallowing), but in the HTTP/SSE layer map known exceptions to clearer messages (e.g. “Rate limit exceeded — try again in a minute”). Optionally add `error_code` or `retry_after` in the SSE payload so the UI can show a “Retry” button or a countdown.

---

## 10. History window is fixed (last 20 messages)

**Current behavior:** `_make_initial_state` sends only `messages[-20:]` to the graph. Long conversations lose older context.

**Claude Code behavior:** Often uses larger context or summarization for long threads.

**Fix:** Increase the window (e.g. 50) or add a summarization step that condenses older turns into a “context summary” and sends recent messages in full. Depends on model context length and cost.

---

## Summary: what to fix first

| Priority | Issue | Effort | Impact |
|----------|--------|--------|--------|
| High | True token streaming (§1) | Medium | Feels responsive, “live” |
| High | Plan approval in UI (§3) | Medium | Long-horizon tasks become usable |
| Medium | Short status / “I’m doing X” (§2, §8) | Low | More transparent, conversational |
| Medium | Stop agent on cancel (§7) | Medium | Clear semantics, no wasted work |
| Low | Code block Run (§6) | Medium | Power users |
| Low | Richer errors (§9) | Low | Better UX on failure |
| Low | Thinking block / phases (§4, §5) | Low–Medium | Clearer structure |

Implementing **§1 (token streaming)** and **§3 (plan approval UI)** will bring the design closest to Claude Code–style behavior; the rest can follow incrementally.
