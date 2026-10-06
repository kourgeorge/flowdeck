# Flowdeck codebase review — 2026-10-06

Review baseline: `263b634`. This document records the findings before remediation.
For the implemented Critical/High fixes and validation, see
[Critical/high remediation](CRITICAL_HIGH_REMEDIATION.md).

## Assessment

The most urgent problems are security boundaries and financial consistency. The cached chat graph can execute one user's tools for another user; the Python tool can read host files; SQLite account deletion can leave credentials that authenticate a replacement account; and an ordinary analysis request can select a provider URL that receives the server's provider key.

The code also has reproducible failures in concurrent debits, payment settlement, chat charging, historical-price parsing, financial interpretations, and frontend request ownership. Several modules describe stronger guarantees than they implement: “secure sandbox,” “prevent concurrent transactions,” “wait for approval,” “hard timeout,” and rotating monitor coverage.

This report contains **30 prioritized findings**, followed by architectural recommendations and a sequenced remediation plan. “Critical” means a security boundary can fail under the stated conditions; it does not assert that a production compromise occurred.

## Review plan and coverage

- [x] Inventory modules, entry points, dependencies, and existing tests.
- [x] Review authentication, authorization, account lifecycle, and public endpoints.
- [x] Review payment verification, token accounting, and transaction boundaries.
- [x] Review analysis execution, concurrency, status persistence, and report access.
- [x] Review chat lifecycle, tool execution, AI orchestration, and financial calculations.
- [x] Review market-data contracts, caching, vendor fallbacks, and event processing.
- [x] Review scheduled jobs, brief generation, and notification delivery.
- [x] Review frontend authentication, streaming, state ownership, and API integration.
- [x] Review deployment, dependency reproducibility, migrations, and test coverage.
- [x] Reproduce important findings with isolated checks and record limitations.
- [x] Consolidate prioritized findings and recommended implementation order.

| Part | Main boundaries inspected | Findings |
| --- | --- | --- |
| Identity and account lifecycle | Routes → authentication → users, profiles, API keys, deletion | F03, F08, F09 |
| Billing and payments | Usage ledger, charge/refund operations, PayPal execution, chat completion | F05–F07 |
| Analysis and reports | Queue admission, workers, progress, terminal state, report lookup | F04, F10, F21, F26, F27 |
| Chat and AI tools | Cached graph, request context, tool execution, planning, streaming | F01, F02, F16–F18 |
| Financial data and calculations | Vendor formats, price history, valuation, prediction-market interpretation | F12–F14 |
| Cache and event processing | Batch ownership, TTL/error behavior, monitoring universe | F19, F20, F24 |
| Briefs, schedules, notifications | Charging, persistence, time zones, retries, timeout enforcement | F22, F23, F25 |
| Frontend and delivery | Effects, auth state, WebSockets, CORS, images, manifests, tests | F11, F15, F21, F28–F30 |

Inventory covered 166 backend Python files (48,413 lines, including 8,471 generated API-example lines), 127 AI Python files (27,693 lines), and 111 frontend TS/TSX files (39,037 lines). Core flows and high-risk branches were read in depth; router/service definitions and secondary research modules were also inventoried through parsing and searches. **This was not a manual review of every line.**

Verification used temporary SQLite databases, synthetic users, mocked providers/payment objects, and controlled frontend transports. No production database, real payment, email delivery, or paid LLM request was used. Deployment findings concern the checked-in manifests; the running production configuration was not audited. No dependency vulnerability-feed audit or full browser regression suite was performed.

### Evidence labels

- **Reproduced:** an isolated check exercised the relevant implementation and observed the defect.
- **Traced:** a concrete call/data path demonstrates the issue, without a full runtime reproduction.
- **Configuration:** the checked-in configuration fails under the specified deployment conditions.

## Prioritized findings

### F01 — Critical: cached chat tools retain a previous user's identity

**Evidence: Reproduced.** Sources: [graph cache](/Users/georgekour/repositories/flowdeck/ai_engine/agent/graph.py:964), [user-bound tools](/Users/georgekour/repositories/flowdeck/ai_engine/agent/lc_tools.py:315), [shared agent](/Users/georgekour/repositories/flowdeck/backend/services/chat_service.py:319).

`FlowDeckAgent._get_graph()` keys graphs only by tool names. `ToolNode(tools)` captures the original tool objects, while `make_user_lc_tools()` creates closures bound to a particular `user_id` and SQLAlchemy session. A later user supplies the same tool names and receives the graph containing the earlier user's closures. The service keeps that agent across requests.

A check built graphs for synthetic users 101 and 202. They were the same graph. Invoking the actual compiled tool node from user 202's graph returned `synthetic-user-101` from a patched identity-reporting `UserContextTool.execute`. The same closure pattern applies to watchlists, portfolio context, and **writes through `update_user_memory`**. The first session is also retained and can be accessed from unrelated worker threads.

**Change:** cache only immutable, identity-independent graph/tool definitions. Inject the authenticated principal and a fresh operation-scoped database session at execution time. Rebuilding per request is a possible immediate containment; adding user ID to the cache key alone still retains sessions and creates unbounded per-user state.

**Acceptance:** alternate and overlap two users' context reads and memory writes; neither identity nor session may cross requests.

### F02 — Critical: the Python tool is not a filesystem sandbox

**Evidence: Reproduced.** Source: [Python execution wrapper](/Users/georgekour/repositories/flowdeck/ai_engine/agent/tools/execute_python.py:126).

The tool relies on text filtering, restricted builtins, and an import allowlist. It permits `io`; `io.FileIO` bypasses the replacement for `builtins.open`. The subprocess runs with the service's OS permissions and no independent filesystem boundary. Its stripped environment does not restrict access to host files.

A benign check used `import io; print(io.FileIO(<repository LICENSE path>, 'r').read(30))` through `_run_sandboxed()` and successfully read the file. No secret file was read. The demonstrated primitive can access other files available to the service account; the same API also supports writing. Separately, output is capped only after `capture_output=True` has buffered it, so the nominal 8 KB cap is not an ingestion limit.

**Change:** disable this capability until execution has a real isolation boundary: dedicated restricted process/container environment, no application credentials or host data mounts, constrained filesystem/network access, resource limits, and bounded streaming output. Extending the substring blocklist will not establish that boundary.

**Acceptance:** a harmless host sentinel outside the allowed workspace is inaccessible for both reads and writes; output flooding cannot exhaust the parent process.

### F03 — Critical: deleted accounts leave data and credentials that can attach to a new account

**Evidence: Reproduced.** Sources: [SQLite setup](/Users/georgekour/repositories/flowdeck/backend/database.py:35), [account deletion](/Users/georgekour/repositories/flowdeck/backend/services/auth_service.py:87), [user identity](/Users/georgekour/repositories/flowdeck/backend/models/db_models.py:22), [credential lookup](/Users/georgekour/repositories/flowdeck/backend/auth.py:46).

The connection setup enables WAL and a busy timeout but never enables SQLite foreign keys. Most dependent records rely on `ondelete="CASCADE"`; the User ORM relationships cascade only profiles and subscriptions. Deleting the User therefore does not implement complete account deletion.

In a temporary database using the actual configured engine, `PRAGMA foreign_keys` was 0. Usage, ChatSession, ChatMessage, and ApiKey rows survived deletion. A replacement user reused the deleted user's numeric ID. **The old JWT and old API key both authenticated the replacement account.**

ID reuse occurs when SQLite can reuse a deleted highest row ID, such as deleting the only account. `autoincrement=True` on the column does not enable SQLite's explicit `AUTOINCREMENT` table behavior. This does not occur after every deletion, but the trigger is ordinary account lifecycle behavior.

**Change:** enable and verify foreign keys on every connection, migrate existing orphan data, use non-reusable identities, and implement credential revocation/versioning. Define deletion or retention semantics for every dependent table. Fixing cascades alone does not prevent a still-valid JWT from matching a reused ID.

**Acceptance:** delete the highest-ID account, create another account, and verify old credentials fail and retained data follows the explicit retention policy.

### F04 — Critical, conditional: analysis requests can redirect provider credentials

**Evidence: Traced end to end; client configuration reproduced without network.** Sources: [request overrides](/Users/georgekour/repositories/flowdeck/backend/routers/analyses.py:201), [configuration propagation](/Users/georgekour/repositories/flowdeck/backend/services/analysis_service.py:555), [provider construction](/Users/georgekour/repositories/flowdeck/ai_engine/llm_provider.py:169).

The authenticated analysis endpoint accepts `llm_provider`, `backend_url`, model names, and research depth from an ordinary user. The OpenAI-compatible and Anthropic branches pass that URL to clients that use server-side environment credentials.

Using a dummy OpenAI key and `https://review.invalid/v1`, the provider factory constructed a client with that destination and the dummy server key. No outbound call was made. A real request would send the configured provider's credentials to its configured destination.

The key-exposure condition requires a configured affected provider key. The Azure branch ignores this URL override, so this is not a claim that every configured provider leaks credentials. The arbitrary destination also creates an outbound-request boundary problem. Unbounded model/depth overrides undermine the flat analysis price.

**Change:** expose named, server-owned research profiles with validated model, provider, endpoint, depth, and budget. Provider endpoint changes belong in trusted configuration, not an ordinary user's analysis payload.

**Acceptance:** public requests cannot alter outbound provider hosts or use models/depths outside their allowed profile.

### F05 — High: concurrent SQLite debits can create a negative token balance

**Evidence: Reproduced.** Source: [ledger transaction](/Users/georgekour/repositories/flowdeck/backend/services/token_service.py:38).

`record_transaction()` reads the ledger sum and then inserts a debit, relying on `SELECT ... FOR UPDATE`. SQLite does not implement that row lock.

Two independent sessions each read a balance of 1,000, synchronized immediately after the real balance read, and each debited 700. Both succeeded and recorded `balance_after=300`; the final ledger balance was **−400**. The ledger also lacks unique operation keys for initial grants, purchase credits, and refunds, leaving additional check-then-insert races.

**Change:** serialize the balance check and mutation at the database boundary. For a supported SQLite topology, acquire the write transaction before reading, with contention handling; alternatively use atomic conditional reservations or a database that supports the intended locking. Add unique idempotency keys for logical ledger operations.

**Acceptance:** concurrent spending cannot exceed available/reserved funds; replaying a grant, payment, or refund produces one ledger effect.

### F06 — High: PayPal can report success without crediting the customer

**Evidence: Reproduced with a mocked provider.** Source: [payment execution](/Users/georgekour/repositories/flowdeck/backend/services/paypal_service.py:86).

After `payment.execute()` succeeds, `token_service.top_up()` is called and its boolean result is ignored. A probe with approved payment execution and `top_up=False` returned `success: true, tokens_credited: 500`.

There is no durable payment/order state or unique provider transaction reference tying settlement to credit. A crash or database failure after capture leaves a paid but uncredited customer, and a retry repeats the remote execution path instead of reconciling the captured transaction. This review did not establish that PayPal itself would double-capture.

**Change:** persist an order tied to the authenticated user and package, verify the remote transaction, and credit once using a unique provider ID. Treat capture and local credit as separately recoverable states, with webhook/poll reconciliation. Never return a credited amount unless the credit is committed.

**Acceptance:** retry after remote success/local failure credits exactly once; a rejected local credit cannot produce a success response.

### F07 — High: chat completes and reports a charge even when settlement is rejected

**Evidence: Reproduced.** Sources: [turn completion](/Users/georgekour/repositories/flowdeck/backend/services/chat_turn_service.py:257), [chat debit](/Users/georgekour/repositories/flowdeck/backend/services/token_service.py:623).

The request checks for a minimal balance before work, but the full cost is known afterward. `_complete_turn()` ignores the debit result, marks the turn completed, and reports the calculated cost.

A synthetic user with 1 platform token completed a turn consuming 20,001 LLM tokens. The result said `platform_tokens_used=3`, balance remained 1, and there were **no chat-cost ledger rows**. Concurrent per-turn threads expand this gap between admission and settlement.

**Change:** reserve an enforceable budget before model work, enforce that budget during execution, and settle exactly once with the turn result. Represent settlement failure explicitly and reconcile it; do not infer a committed charge from a conversion formula.

**Acceptance:** reported charges match committed ledger entries, including low-balance and concurrent-turn cases.

### F08 — High: Google OAuth state is generated but never validated

**Evidence: Traced.** Sources: [state generation](/Users/georgekour/repositories/flowdeck/backend/services/auth_service.py:102), [callback](/Users/georgekour/repositories/flowdeck/backend/routers/users.py:102).

The authorization URL includes a random state, but it is not stored or bound to the initiating browser. The callback accepts a `state` parameter and never checks it. Random generation alone provides no login-CSRF protection; a callback initiated in another browser can be accepted.

**Change:** bind a short-lived nonce to the initiating browser, validate it before code exchange, and consume it once. Review account linking against the verified provider subject/email. Replace the JWT-bearing redirect query with a short-lived exchange or secure session mechanism to reduce credential exposure through URL handling.

**Acceptance:** missing, mismatched, expired, and replayed states are rejected; the valid browser-bound flow succeeds.

### F09 — High, conditional: production startup accepts publicly known signing secrets

**Evidence: Configuration.** Sources: [auth default](/Users/georgekour/repositories/flowdeck/backend/auth.py:16), [Compose default](/Users/georgekour/repositories/flowdeck/docker/compose.yml:40).

The application and Compose each supply a known fallback JWT secret. There is no fail-fast requirement for a production secret. A deployment missing its environment configuration will still issue and accept tokens with a public signing key, allowing credential forgery.

The actual deployed secret was not inspected.

**Change:** require an explicit strong signing secret outside a clearly isolated development mode. Reject the shipped fallback values at startup and plan key rotation/session invalidation if a deployment has used them.

**Acceptance:** production startup without valid secret configuration fails before serving requests.

### F10 — High: paid analysis jobs have no durable ownership or recovery

**Evidence: Traced.** Sources: [local queue/deduplication](/Users/georgekour/repositories/flowdeck/backend/services/analysis_service.py:440), [executor](/Users/georgekour/repositories/flowdeck/backend/services/analysis_executor.py:50), [failure handling](/Users/georgekour/repositories/flowdeck/backend/services/analysis_service.py:673), [terminal status deletion](/Users/georgekour/repositories/flowdeck/backend/services/analysis_service.py:1326).

Job parameters and ownership live in a process-local dictionary and ThreadPoolExecutor. SQLite stores progress but no claim lease, durable queue, or restart reconciliation. A process crash loses accepted work while executions can remain “running,” cache entries can show ghost progress, and already committed charges are not reconciled by a surviving worker.

Queued jobs are represented as `running` in the Execution model. Completed/failed cache entries are deleted, while the status endpoint only reads that cache, so polling can transition from progress to 404 instead of a durable terminal result. Deduplication is local to one service process.

There is also no strong completion invariant: report-save errors are logged, and the run can still be marked completed without all required outputs being persisted.

**Change:** make a database job record authoritative: queued/running/terminal state, immutable request parameters, operation identity, claim lease, heartbeat, retry policy, and settlement reference. Recover expired claims on startup. Serve terminal status from durable state and require persisted outputs before completion. Keep progress cache as a derived view.

**Acceptance:** kill a worker after charging and at several persistence boundaries; every run becomes recoverable, completed, or failed/refunded, and status remains queryable.

### F11 — High: container SQLite data is outside the mounted persistence directory

**Evidence: Configuration.** Sources: [Compose database URL](/Users/georgekour/repositories/flowdeck/docker/compose.yml:13), [volume mount](/Users/georgekour/repositories/flowdeck/docker/compose.yml:47), [image working directory](/Users/georgekour/repositories/flowdeck/docker/backend.Dockerfile:46).

The URL `sqlite:///./data/flowdeck.db` resolves relative to `WORKDIR /app/backend`, producing `/app/backend/data/flowdeck.db`. The volume is mounted at `/app/data`. The former directory exists because backend data files are copied into the image, making silent writes to the container layer plausible. Recreating the container loses that database.

The Kubernetes manifest repeats the relative URL/mount mismatch. Cache and log/result defaults should also be reviewed for persistence intent.

**Change:** use an absolute URL such as `sqlite:////app/data/flowdeck.db` and explicit paths for other persistent state. Before rollout, locate and migrate any actual data in the old container layer.

**Acceptance:** create a synthetic record, replace the container, and retrieve it from the mounted database. No deployment was changed during this review.

### F12 — High: the multi-price tool cannot parse the backend's actual CSV

**Evidence: Reproduced.** Sources: [vendor formatter](/Users/georgekour/repositories/flowdeck/backend/data_layer/vendors/y_finance.py:59), [tool parser](/Users/georgekour/repositories/flowdeck/ai_engine/agent/tools/multi_market_data.py:124).

The vendor prepends three `#` metadata lines and a blank line to its CSV. The information-service client returns that string unchanged. The multi-price tool passes it directly to `csv.DictReader`, which treats the first metadata line as the header; Date and Close are never found.

A fixture matching the vendor's output returned `tickers_fetched: []` and `AAPL: No valid rows` despite valid price records.

**Change:** use a structured price-series contract shared by vendor adapters, API, and tools. As a local repair, centralize comment/header handling. Also define date boundaries explicitly: Yahoo's end date is exclusive, and period returns often need the close before the first session rather than the first session's close. The comparison path should disclose its 20-ticker cap.

**Acceptance:** actual vendor-format fixtures survive the full adapter/client/tool chain with correct session boundaries and adjusted-price semantics.

### F13 — High: prediction-market event probability is mislabeled as bullish sentiment

**Evidence: Reproduced.** Sources: [aggregation](/Users/georgekour/repositories/flowdeck/backend/services/polymarket_service.py:209), [outcome extraction](/Users/georgekour/repositories/flowdeck/backend/data_layer/vendors/polymarket_vendor.py:545).

The service averages outcome probabilities and calls values above 0.6 “bullish.” It never models whether “Yes” is beneficial or harmful for the stock, or how the event affects that company. Negative events can therefore produce positive investment signals.

A single synthetic market, “Will TEST stock crash 50%?”, with Yes probability 0.9, volume 1 million, and relevance 1 produced **bullish, confidence 1.0**. “Confidence” is derived from volume, not calibrated certainty in the sentiment inference.

**Change:** preserve event/outcome probabilities as their own data. Derive directional exposure only with an explicit, validated outcome-to-company mapping; otherwise return unknown direction. Distinguish liquidity/support from forecast confidence.

**Acceptance:** complementary or negatively phrased events do not reverse the economic meaning of the displayed signal.

### F14 — High: missing ETF inputs produce invented values with high conviction

**Evidence: Reproduced.** Sources: [fallback](/Users/georgekour/repositories/flowdeck/ai_engine/tradingagents/agents/utils/valuation_tools.py:342), [conviction and sensitivity](/Users/georgekour/repositories/flowdeck/ai_engine/tradingagents/agents/utils/valuation_tools.py:387).

When no ETF multiples or analyst targets are available, the code invents a “Price Regime” at 92%, 100%, and 108% of current price. One method has zero measured dispersion, which becomes “high” conviction.

For price 100 and fundamentals containing only `QuoteType: ETF`, the function returned fair values **92 / 100 / 108**, conviction **high**, and score 3. The equity branch has explicit unavailable handling, so the system's missing-data policy is inconsistent.

The ETF branch also emits the old sensitivity shape `{delta, low, high}`, which does not conform to the current `ValuationSensitivityRange` schema.

**Change:** make unavailable/unsupported a typed result. If scenario bands are intentionally heuristic, label them as scenarios with explicit assumptions and evidence limits. Use ETF-appropriate NAV/look-through inputs for valuation, and share a validated output model across branches.

**Acceptance:** insufficient evidence never increases conviction or manufactures a fair-value claim; all instrument paths validate against their advertised schema.

### F15 — High: stale requests can display another ticker's financial data

**Evidence: Hook behavior reproduced; panel flow traced.** Sources: [ticker loading](/Users/georgekour/repositories/flowdeck/frontend/src/components/TickerDetailPanel.tsx:550), [ticker effect](/Users/georgekour/repositories/flowdeck/frontend/src/components/TickerDetailPanel.tsx:604), [quote polling](/Users/georgekour/repositories/flowdeck/frontend/src/hooks/useQuoteRefresh.ts:16).

On ticker change, the panel resets state but leaves earlier requests active. Their callbacks can still apply quote, company, fundamentals, recommendations, and report data. The quote hook clears the interval but neither cancels an in-flight response nor resets the previous quote on a nonempty ticker change.

A controlled execution of the actual transpiled hook started AAPL, switched to NVDA, resolved NVDA first, and then resolved AAPL. The active ticker was NVDA while stored quote state was **AAPL, price 100**. This was a hook/effect harness, not a full browser render.

**Change:** own remote state by ticker/request key, use cancellation plus an identity/epoch check before applying results, and clear incompatible stale data on navigation. Centralize this behavior in a query layer. Existing cancellation in some neighboring effects provides a local pattern to build on.

**Acceptance:** deliberately reverse response order during rapid ticker changes; displayed data always matches its ticker and account context.

### F16 — High: the agent's tool-call budget is never consumed

**Evidence: Reproduced.** Sources: [budget checks](/Users/georgekour/repositories/flowdeck/ai_engine/agent/graph.py:899), [initial state](/Users/georgekour/repositories/flowdeck/ai_engine/agent/graph.py:1032), [direct tool wrappers](/Users/georgekour/repositories/flowdeck/ai_engine/agent/lc_tools.py:45).

`tool_calls_made` is initialized to zero and read during routing, but no graph node increments it. The standard ToolNode only adds tool messages. In a compiled graph with mocked routing/model responses and a budget of 1, **three harmless calls executed and the counter remained 0**.

ReAct wrappers also call tool `.execute()` directly, bypassing the legacy ToolExecutor's execution protections. The skill path and general-agent path therefore do not share one enforceable policy.

**Change:** enforce a per-turn budget before dispatching each tool call, including parallel batches. Route every execution path through one wrapper for identity, limits, cancellation, timeouts, output bounds, and accounting. A graph recursion limit is not a tool/cost budget.

**Acceptance:** a budget of one permits exactly one call, even if the model requests multiple calls at once or falls back between skills and ReAct.

### F17 — Medium: chat streaming repeats the last line

**Evidence: Reproduced.** Source: [stream forwarding and flush](/Users/georgekour/repositories/flowdeck/backend/services/chat_service.py:434).

Every token event is immediately forwarded. The final incomplete line remains in `reply_buffer`, and the done handler emits it again after removing follow-up metadata.

A fake agent emitting a single `Hello world` token followed by done produced **Hello worldHello world**. The turn service accumulates those token events, so stored text is affected too.

**Change:** assign text emission to one layer. Metadata parsing may inspect already-emitted text but must not resend it; alternatively buffer before emission and preserve exact chunk ownership.

**Acceptance:** text with no trailing newline, multiple lines, chart metadata, and follow-ups is emitted and persisted once.

### F18 — Medium: plan “approval” does not pause for user input

**Evidence: Traced.** Sources: [approval node and router](/Users/georgekour/repositories/flowdeck/ai_engine/agent/graph.py:343), [graph edges](/Users/georgekour/repositories/flowdeck/ai_engine/agent/graph.py:761).

The node says it will wait, but the graph immediately routes onward without an interrupt or persisted continuation. The router examines the original HumanMessage, not a new response. Substring matching treats “no” inside “technology” as cancellation, while an unclear response defaults to approval. A new request starts new state rather than resuming the proposed plan.

**Change:** choose a clear product behavior. If approval is required, persist the plan and interrupt execution until an explicit plan/version action resumes it. If planning is informational, remove the misleading approval interaction and brittle keyword gate.

**Acceptance:** no approved-plan work runs before the explicit approval action; normal task words cannot accidentally approve or cancel it.

### F19 — Medium: duplicate batch-cache keys prevent the fetch

**Evidence: Reproduced.** Source: [batch in-flight ownership](/Users/georgekour/repositories/flowdeck/backend/services/data_cache.py:515).

For a duplicated missing key, the dictionary comprehension calls `_begin_inflight` twice. The first call establishes a leader; the second overwrites that dictionary entry with the follower result. There is no leader left to fetch the value.

A cold batch containing the same key twice returned an empty result without calling its fetch function. The normal follower timeout is 35 seconds; the probe shortened only the wait to 0.01 seconds. Market/company batch paths normalize case without deduplicating, so ordinary duplicate tickers can reach this condition.

**Change:** deduplicate normalized keys before assigning ownership, with explicit behavior for conflicting TTLs. Ensure all success, timeout, and error paths release ownership.

**Acceptance:** duplicate-only and mixed batches fetch each missing key once and return promptly.

### F20 — Medium: a transient vendor failure is cached as fresh data for 24 hours

**Evidence: Reproduced.** Sources: [fundamentals error conversion](/Users/georgekour/repositories/flowdeck/backend/data_layer/market.py:271), [TTL](/Users/georgekour/repositories/flowdeck/backend/config.py:33).

The fetch function converts exceptions to a nonempty dictionary containing empty fundamentals and an error. Generic caching treats it like success and uses the 86,400-second fundamentals TTL.

A vendor mock that failed once and would then succeed was called only once across two requests; both requests returned the cached error.

**Change:** use a result type that distinguishes success, absence, unsupported data, stale data, and transient failure. Cache successful values normally, bound negative caching separately, and consider serving the last good value with explicit freshness/error metadata.

**Acceptance:** a temporary outage cannot hide recovered data for a full success TTL or masquerade as a fresh successful fetch.

### F21 — Medium: WebSocket ownership and reconnect cleanup are inconsistent

**Evidence: Frontend reconnect reproduced; backend behavior traced.** Sources: [connection registry](/Users/georgekour/repositories/flowdeck/backend/routers/analyses.py:322), [cross-thread publication](/Users/georgekour/repositories/flowdeck/backend/routers/analyses.py:221), [client retry](/Users/georgekour/repositories/flowdeck/frontend/src/services/websocket.ts:62).

The backend stores one socket per run. A second viewer overwrites the first, and either viewer's disconnect deletes the run's entry, potentially unregistering the still-connected viewer. Worker callbacks schedule socket sends on the analysis worker's current/new event loop instead of the ASGI socket's owning loop.

The frontend does not retain or cancel reconnect timers. In a fake-transport run of the actual class, a close scheduled a retry, `disconnect()` was called, and the pending retry still created a second socket and reset the manual-close flag.

**Change:** track a subscriber set per run with identity-safe removal, publish on the ASGI loop through a queue, and use shared pub/sub if multiple processes are supported. Retain/cancel reconnect timers and check lifecycle state before reconnecting.

**Acceptance:** multiple tabs receive progress independently; leaving a page creates no later socket; publication never crosses event loops directly.

### F22 — Medium: scheduler timestamps can skip valid runs, and failed attempts consume the period

**Evidence: Time-zone defect reproduced; attempt handling traced.** Sources: [time comparison](/Users/georgekour/repositories/flowdeck/backend/services/scheduler.py:119), [early execution stamp](/Users/georgekour/repositories/flowdeck/backend/services/scheduler.py:214).

SQLite reloads these DateTime values as naive UTC, but `.astimezone(tz)` interprets a naive value in the host's local zone. With host TZ America/Los_Angeles, previous UTC time 2026-10-05 23:30, current time 2026-10-06 01:00Z, and a daily 00:30 UTC schedule, the check incorrectly skipped the new day.

Separately, `last_executed_at` is committed before balance checks, generation, or email delivery. A transient failure consumes the entire day/week. That timestamp is also not an atomic distributed claim; multiple schedulers can read it before either writes.

**Change:** normalize persisted timestamps explicitly to UTC, as other digest code already does. Track per-slot attempt, claim lease, success, and delivery independently. Retry transient generation/delivery failures without repeating successful paid work.

**Acceptance:** identical schedules behave consistently across host time zones and DST boundaries; an interrupted attempt remains recoverable within its intended slot.

### F23 — Medium: declared timeouts do not bound worker occupancy

**Evidence: Brief timeout reproduced; scheduler guard traced.** Sources: [briefing timeout](/Users/georgekour/repositories/flowdeck/ai_engine/briefing_agent/agents.py:30), [scheduler signal guard](/Users/georgekour/repositories/flowdeck/backend/main.py:161).

The briefing helper raises from `future.result(timeout=...)` inside a ThreadPoolExecutor context manager. Context exit waits for the running thread, so the caller still blocks until the underlying operation finishes. A harmless event-blocked chain with a 0.01-second timeout was still blocked after 0.08 seconds and returned only after the event was released.

The cache-refresh “hard timeout” uses SIGALRM only on the main thread; BackgroundScheduler jobs execute in worker threads, so the timeout guard is inactive there.

**Change:** enforce provider/network deadlines and an end-to-end deadline. Use a cancelable process boundary for work that must be forcibly stopped; abandoning a Future does not stop its thread. Ensure timed-out tasks cannot hold scheduler capacity indefinitely.

**Acceptance:** a deliberately blocked dependency releases the job slot within the documented deadline, with no orphan worker continuing unbounded work.

### F24 — Medium: event-monitor coverage can remain stuck on the same 25 tickers

**Evidence: Selection behavior reproduced; sustained starvation traced.** Source: [universe selection](/Users/georgekour/repositories/flowdeck/backend/services/event_monitor_service.py:83).

Selection orders subscribed tickers by oldest completed analysis and takes 25. A monitoring pass that finds no trigger does not change those analysis dates. The next pass therefore selects the same set. Tickers without usable baselines can also remain in that set while being skipped.

With 26 synthetic subscriptions/executions, consecutive selections returned the same first 25 and excluded the 26th. Unless one selected ticker gets a new analysis through another path, this does not rotate as the comment claims.

**Change:** persist last-checked time or a scan cursor; separate the monitoring scan budget from the expensive reanalysis budget. Apply cooldown to reruns, not to fair coverage.

**Acceptance:** an unchanged universe larger than the batch limit is fully scanned within a bounded number of passes.

### F25 — Medium: digest creation has unsafe HTTP and incomplete lifecycle semantics

**Evidence: Traced.** Sources: [GET generation endpoint](/Users/georgekour/repositories/flowdeck/backend/routers/digest.py:92), [charge and generation](/Users/georgekour/repositories/flowdeck/backend/services/digest_service.py:162), [persistence outside failure handling](/Users/georgekour/repositories/flowdeck/backend/services/digest_service.py:244), [response](/Users/georgekour/repositories/flowdeck/backend/routers/digest.py:178).

`GET /api/digest` generates and charges for a new brief. Retries and repeated calls are not protected by an operation key. The error/refund block covers generation but not subsequent metadata serialization or report persistence. Task cancellation is another gap: `CancelledError` is not caught by `except Exception`, while `to_thread` work can continue using the request's session.

The response model declares `execution_id`, but the successful response omits it and defaults it to null.

**Change:** create briefs through POST with an idempotency key and durable execution ID. Give the worker its own session and define cancellation/settlement semantics for the entire lifecycle. Separate report generation from retryable email delivery.

**Acceptance:** retrying the same operation does not charge twice; cancellation or save failure leaves a durable recoverable state; success returns its execution ID.

### F26 — Medium: report selection can silently return the wrong run

**Evidence: Service queries reproduced; route fallback traced.** Sources: [latest query](/Users/georgekour/repositories/flowdeck/backend/services/report_service.py:297), [date resolver](/Users/georgekour/repositories/flowdeck/backend/services/report_service.py:579), [API selection](/Users/georgekour/repositories/flowdeck/backend/routers/data_api.py:710).

“Latest” does not filter for completed executions, so a newer failed or running execution can hide an earlier usable report. The date parameter advertises numeric run IDs, but its resolver only compares SQL dates. When resolution fails, the route silently returns latest.

A temporary database with an older completed run and newer failed run selected the failed run. A numeric selector did not resolve. These behaviors make historical and agent research less reproducible.

**Change:** separate latest successful report from current run status. Use distinct typed selectors for date and run ID, validate ticker/run association, and return a clear not-found response for an explicit missing selection.

**Acceptance:** failed refreshes preserve access to the previous usable report; an explicit run selector never silently chooses another run.

### F27 — Medium: standalone research report clients omit required authentication

**Evidence: Traced.** Sources: [report client](/Users/georgekour/repositories/flowdeck/ai_engine/tradingagents/datasources/info_service_client.py:361), [batch request](/Users/georgekour/repositories/flowdeck/ai_engine/tradingagents/datasources/info_service_client.py:381), [portfolio research adapter](/Users/georgekour/repositories/flowdeck/ai_engine/portfolio_deep_research/tools.py:38).

These HTTP clients call authenticated report endpoints without a bearer header or a configurable credential path. Some failures are swallowed into missing reports, so a 401 can look like an absence of research. The portfolio graph has a similar direct batch call.

The regular backend chat path can use an in-process data gateway, so this finding does **not** imply all normal chat report access is broken.

**Change:** define an authenticated client contract for standalone agents, or deliberately route in-process jobs through an authorized service interface. Preserve unauthorized versus not-found errors.

**Acceptance:** a configured standalone research run fetches authorized reports, and missing/invalid credentials produce an explicit authentication failure.

### F28 — Medium, cross-origin deployments: CORS rejects existing PATCH endpoints

**Evidence: Reproduced using the actual configured method list.** Sources: [CORS](/Users/georgekour/repositories/flowdeck/backend/main.py:353), [profile route](/Users/georgekour/repositories/flowdeck/backend/routers/me.py:87), [subscription route](/Users/georgekour/repositories/flowdeck/backend/routers/subscriptions.py:86).

Allowed methods contain GET, POST, PUT, DELETE, and OPTIONS, but omit PATCH. Profile, investor-profile, subscription, and API-key activation/deactivation routes use PATCH.

An allowed-origin preflight for PATCH returned **400, “Disallowed CORS method.”** This affects a frontend using a separate API origin; same-origin proxy deployments are unaffected.

**Change:** include the supported methods and verify the actual cross-origin API contract as part of configuration validation.

**Acceptance:** preflight succeeds for each browser-used method from an allowed origin and remains rejected for disallowed origins.

### F29 — High, Kubernetes deployments: the shipped topology contradicts the runtime

**Evidence: Configuration and code trace.** Sources: [replicas](/Users/georgekour/repositories/flowdeck/ibm-cloud/kubernetes-deployment.yaml:73), [autoscaling](/Users/georgekour/repositories/flowdeck/ibm-cloud/kubernetes-deployment.yaml:359), [runtime constraint](/Users/georgekour/repositories/flowdeck/backend/services/analysis_executor.py:50), [nginx upstream](/Users/georgekour/repositories/flowdeck/docker/nginx.conf:28).

The manifest starts two backend replicas and scales to ten, while the runtime explicitly assumes one Uvicorn process and uses process-local queues, subscriber registries, and analysis capacity. Scheduler leadership uses a local file lock rather than a shared cluster lease. The PVC is ReadWriteOnce, which is not a portable shared-storage solution across nodes. Even fixing F11's path does not make this topology correct.

The reused nginx config targets service `backend`, but the Kubernetes backend Service is named `flowdeck-backend`. Without an extra alias or changed config, that upstream does not resolve to the shipped Service.

**Change:** document and ship one supported topology now, with matching DNS and persistent paths. Introduce shared database/queue/pub-sub/leases before enabling replicas and autoscaling. A service rename alone does not solve distributed ownership.

**Acceptance:** a manifest deployment resolves its upstreams, persists data, and demonstrates one claim/charge/delivery per logical job at the supported replica count.

### F30 — Medium: dependency and verification paths do not reproduce the same application

**Evidence: Manifest inspection, build, lint, and existing tests.** Sources: [project manifest](/Users/georgekour/repositories/flowdeck/pyproject.toml:7), [requirements](/Users/georgekour/repositories/flowdeck/requirements.txt:13), [Docker installation](/Users/georgekour/repositories/flowdeck/docker/backend.Dockerfile:15), [frontend scripts](/Users/georgekour/repositories/flowdeck/frontend/package.json:6).

The uv project/lock and pip requirements describe different environments. Direct runtime dependencies present only in requirements include `python-jose`, `paypalrestsdk`, `email-validator`, `google-auth-oauthlib`, `trafilatura`, `langchain-perplexity`, and `aiosqlite`; these are also absent from the reviewed uv lock. Other direct dependencies happen to arrive transitively. Docker installs broadly unpinned requirements, so a successful local environment is not proof of a clean reproducible install.

Frontend build passes, but its declared lint command fails because there is no ESLint configuration. There is no frontend test script or checked-in GitHub Actions workflow. Existing backend tests have four failures caused by stale usage/sensitivity expectations.

**Change:** use one canonical dependency source and lock for local, CI, and images; declare direct imports explicitly. Restore lint configuration, resolve the intended schemas rather than merely weakening tests, and add CI around the high-value invariants identified here.

**Acceptance:** a clean locked install starts the application, build/lint pass, and the same test contract runs in local and CI environments.

## Design changes I would make

These recommendations address the causes shared by several findings; they are not additional claims of reproduced defects.

### 1. Keep a modular monolith, with explicit ownership boundaries

The existing routes/services/data gateway provide a useful starting point. A microservice split would add operational complexity before fixing the ownership bugs.

I would organize the core around identity, billing, executions, market data, and delivery. Each owns its state transitions; routes translate HTTP, and agents request capabilities through interfaces. Transaction ownership should be explicit rather than hidden in helper methods that commit independently. Database sessions should be short-lived and owned by one request/operation or worker, never cached in tools or carried across cancellation boundaries.

### 2. Make one durable execution and settlement model

Analysis, chat, and briefs currently implement different combinations of admission, generation, charging, status, persistence, and refunds. They should share a lifecycle service with stable operation IDs and explicit invariants:

- Every accepted paid operation has durable parameters, owner, and budget/reservation.
- Every operation has at most one settlement and one reversal per ledger operation key.
- Completed means required outputs are persisted and settlement has a defined outcome.
- Interrupted work has a retry/recovery policy and remains visible to the user.
- Notifications use an outbox and can retry independently of paid generation.

SQLite can remain suitable for a deliberately constrained single-instance deployment with correct write transactions. Distributed workers or replicas need an appropriate shared store and atomic claims.

### 3. Define typed data contracts before adding more adapters

Use a common envelope with source, as-of time, units/currency, status, freshness, and structured data. Keep raw vendor payloads separate from normalized financial facts. Price series should expose session/date and adjustment semantics, not human-readable CSV preambles. Distinguish missing, unsupported, zero, stale, and failed values.

Validate the same valuation/usage/report models at producer and consumer boundaries. An LLM should describe deterministic financial outputs, not repair malformed contracts or invent confidence when inputs are absent.

### 4. Enforce AI policy in one runtime layer

Unify tool dispatch across skill and general-agent execution. That boundary should apply the principal, cost/call/time/output limits, cancellation, and telemetry. Remove or retire redundant legacy paths only after documenting which guarantees they provide.

Model configuration should be trusted server configuration. Planning should have an honest state machine. Dynamic code execution should be an independently isolated capability, rather than a special case inside the web service's permission boundary.

### 5. Centralize frontend server state by ticker and user

The large ticker panel contains duplicated loading branches and many independently owned effects. Move remote data into query hooks keyed by ticker, run ID, user, and relevant parameters. Standardize cancellation, invalidation, loading/error states, and stale-response suppression.

The same approach applies to authentication and subscriptions. [Auth initialization](/Users/georgekour/repositories/flowdeck/frontend/src/contexts/AuthContext.tsx:96) currently clears credentials on any profile request error, including network/5xx failures. Login stores credentials before profile loading succeeds. These should be explicit authenticated/loading/unavailable/unauthenticated states, with logout reserved for an invalid session. User-specific caches and outstanding requests should reset on account changes.

### 6. Make schema and deployment evolution explicit

[Database initialization](/Users/georgekour/repositories/flowdeck/backend/database.py:51) uses `create_all()`; it does not migrate existing columns or repair existing constraints/data. Replace manual migration expectations with a versioned, ordered migration runner, including rollback/recovery planning for identity and ledger changes.

Validate persistent paths, secrets, schema version, provider profiles, and supported concurrency at startup. Keep one deployable configuration aligned with the runtime before supporting another orchestration topology. Add operational signals for orphaned executions, failed credits, old queue items, stale cache errors, delivery retries, and tool-budget rejections.

## Verification results

| Check | Result | What it establishes |
| --- | --- | --- |
| Existing `backend/tests` suite | **199 passed, 4 failed, 1 skipped**, 315.22 s | Broad baseline with isolated DB/cache and blocked outbound connections |
| Frontend `npm run build` | **Passed** | TypeScript, Vite, and prerender of six pages; large-bundle warnings remain |
| Frontend `npm run lint` | **Failed** | ESLint configuration is missing |
| Compiled chat tool-node identity | User 202's graph executed user 101's bound context tool | Cross-user cached closure, F01 |
| Python tool benign host read | Read repository LICENSE through `io.FileIO` | Filesystem isolation bypass, F02 |
| Account deletion/recreation | Orphans remained; both old JWT and API key authenticated new account | F03 with SQLite ID reuse |
| Provider factory, dummy key | Caller URL and server-key configuration combined | F04 configuration path; no request sent |
| Concurrent ledger transactions | 1,000 − 700 − 700 = **−400** | F05 under controlled concurrent reads |
| Mocked payment settlement | Success/500 credited despite `top_up=False` | F06 |
| Low-balance chat settlement | Done/3 charged reported; balance 1; no debit entry | F07 |
| Price parsing fixture | Valid vendor-format data yielded no fetched tickers | F12 |
| Negative prediction-market event | 90% crash probability → bullish, confidence 1 | F13 |
| ETF with no valuation inputs | 92/100/108 fair values, high conviction | F14 |
| Actual quote hook, controlled effects | NVDA active; stale AAPL quote stored | F15, without full browser rendering |
| Compiled agent tool budget | Budget 1; three tool calls; counter 0 | F16 |
| Chat event stream | `Hello worldHello world` | F17 |
| Duplicate batch-cache key | No fetch; empty result | F19; shortened wait only |
| Recovering vendor mock | One vendor call; error served twice | F20 |
| Actual WebSocket class, fake transport | Disconnect followed by a new socket | F21 frontend lifecycle |
| Schedule on non-UTC host | Previous UTC day treated as current day | F22 time-zone branch |
| Briefing timeout helper | Still blocked after deadline until worker released | F23 |
| 26-ticker monitor fixture | Same 25 selected on consecutive passes | F24 |
| Report queries | New failed run selected; numeric selector unresolved | F26 |
| CORS preflight | PATCH → 400 “Disallowed CORS method” | F28 |

The backend suite ran through `pytest.main(['backend/tests', '-q', '--disable-warnings', '--tb=short'])` with the repository and backend import roots, temporary `DATABASE_URL`/`DATA_CACHE_PATH`, schedulers disabled, dummy credentials, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, and an outbound socket guard. Python was 3.10.19. These controls were necessary to avoid testing against the workspace's normal database or external services.

The four baseline failures were:

1. `test_usage_history_combines_analysis_chat_and_digest`: expects `chat_turn_id=401`, while current usage aggregation groups chat by session and emits null for that field.
2. `test_model_dump_uses_state_field_names`: constructs the old sensitivity model.
3. `test_multi_method_valuation_data_returns_non_zero_methods`: reads the removed `low` key.
4. `test_structured_output_contains_deterministic_summary`: constructs the old sensitivity model.

The current sensitivity schema requires nine fields, including parameter/base/delta information and fair-value bounds. These failures establish contract/test drift; they are not by themselves proof that every equity valuation is broken. The ETF producer mismatch and unsupported high-conviction fallback in F14 are separate implementation findings.

Local raw logs and supplemental harnesses are under `/private/tmp/flowdeck-review-2026-10-06/`. The tables and finding descriptions preserve the substantive results in this report. The additional frontend harness transpiles the original TypeScript and controls transports/effect cleanup; it does not substitute for a browser regression test.

## Recommended implementation order and acceptance tasks

This is a proposed remediation backlog. No implementation tasks below were performed during this review.

| Order | Work package | Dependencies | Completion evidence |
| --- | --- | --- | --- |
| 1 | Contain cross-user tool caching, unsafe Python execution, and caller-controlled provider destinations (F01, F02, F04) | None | Two-user isolation; host sentinel inaccessible; provider-host allowlist |
| 2 | Repair identity lifecycle, OAuth binding, and secret validation (F03, F08, F09) | Data/credential migration plan | Deleted-user credentials never authenticate new users; state replay rejected |
| 3 | Correct persistent container paths and choose the supported topology (F11, F29) | Locate existing stored data | Container replacement preserves records; replicas match ownership model |
| 4 | Make ledger and payment/chat settlement atomic and idempotent (F05–F07) | Database transaction strategy | Concurrent debits safe; remote-success/local-failure replay credits once |
| 5 | Unify durable job state, cancellation, recovery, and delivery (F10, F21–F25) | Stable operation IDs and settlement model | Crash recovery, terminal status, fair scan coverage, bounded deadlines |
| 6 | Correct financial data contracts and evidence handling (F12–F14, F19, F20, F26, F27) | Typed result/selector decisions | Vendor fixtures round-trip; missing data stays unavailable; explicit runs remain exact |
| 7 | Repair tool budgets, streaming, planning, and frontend ownership (F15–F18, F21, F28) | Shared runtime/query lifecycle | Exact budget counts; no duplicated text; no stale quote or reconnect after teardown |
| 8 | Make release checks reproducible (F30 and migration work) | Run alongside the earlier packages | Clean locked install, versioned upgrade, green tests/build/lint in CI |

Small contained fixes can proceed alongside the earlier security work: PATCH CORS support, duplicate-key normalization, final-token emission, and explicit response execution IDs. They should still have focused acceptance checks. Larger lifecycle changes need concurrency, restart, replay, and failure-boundary tests rather than only additional happy-path mocks.
