# Critical and high finding remediation

Implementation baseline: `b18987e` (includes changes made after the review).
Scope: F01–F16 and F29. No deployment or live database migration is performed by this work.

- [x] F01: request-scoped chat tool identity and sessions
- [x] F02: remove unsafe host Python execution
- [x] F03: foreign keys, immutable authentication identities, deletion and migration
- [x] F04: trusted provider/model configuration and bounded research requests
- [x] F05: serialized, idempotent ledger operations
- [x] F06: durable, recoverable, idempotent PayPal settlement
- [x] F07: chat reservation and truthful settlement
- [x] F08: browser-bound, one-use OAuth state
- [x] F09: reject missing/default production signing secrets
- [x] F10: durable analysis admission, recovery, terminal status, output validation
- [x] F11: persistent absolute container paths
- [x] F12: historical-price contract and period boundaries
- [x] F13: preserve outcome probabilities without invented direction/confidence
- [x] F14: unavailable ETF valuation and consistent output schemas
- [x] F15: cancellation and request ownership for ticker data
- [x] F16: shared enforced tool budget
- [x] F29: supported single-instance deployment and correct upstream DNS
- [x] Focused regressions, backend suite, frontend build, migration/deployment checks

## Implementation and evidence

| Findings | Change | Regression evidence |
| --- | --- | --- |
| F01, F16 | Cached graph definitions contain no principal/session closures. Tools receive the invocation's context, open their own SQLAlchemy session, and consume one shared synchronized budget across skill and graph calls. | Actual compiled tool nodes alternate and overlap two users' reads/writes. Three parallel calls with budget one execute exactly one tool. |
| F02 | Python execution is disabled and removed from advertised tools. The compatibility entry point cannot execute code. | A host sentinel cannot be read or overwritten. |
| F03, F08, F09 | SQLite foreign keys; immutable random auth subjects; API-key identity binding; ordered additive migrations; persistent numeric-ID high-water marks; expiring, browser-bound, one-use OAuth state; fail-fast signing configuration. | Account deletion cascades, forced numeric-ID reuse cannot revive credentials, realistic legacy-schema upgrade preserves valid data and deletes orphans, old keys are revoked, OAuth mismatch/expiry/replay fail, insecure secrets fail. |
| F04 | The public analysis endpoint uses server provider/model/endpoint settings and accepts depth 1–5 with supported analysts. Invalid policy is rejected before vendor access or charging. | Endpoint tests reject alternate hosts, models, providers, invalid depths, and analyst lists without calling vendors or writing charges. |
| F05 | A real database write serializes balance checks and ledger inserts. Stable operation keys deduplicate grants, charges, releases, refunds, and purchases. View rewards include each viewer. Entity IDs survive deletions. | Competing debits cannot overspend; replayed grants do not repeat; deleting a refunded run cannot reuse its charge; distinct viewers each receive one reward. |
| F06 | Persist PayPal order snapshots, require a completed sale with matching account/amount/currency, checkpoint capture, and atomically commit one purchase credit. A bounded periodic sweep retries pending credits. | Mocked capture followed by failed local credit can be retried without capture or duplicate credit; a different account cannot claim payment. |
| F07 | Reserve up to `CHAT_MAX_PLATFORM_TOKENS` (default 20) before starting. Share a conservative LLM-call budget and cap output tokens. Atomically release the reserve and charge actual usage with the assistant reply. Both routes use four workers/eight admitted turns. Start streaming workers before response consumption; reject overlapping session turns and active-session deletion. | Excess usage cannot become a successful charge; normal settlement has the correct net cost; repeated failure cannot refund twice or change completed state; capacity rejection releases tokens without a provider call; an unconsumed SSE response still starts its worker. |
| F10 | Persist unique active analysis admission and parameters. Require selected analyst reports and the terminal `trader_investment_plan` in storage before completion. Recover interrupted work as failed/refunded before accepting traffic. SQLite terminal status overrides stale progress cache. | Empty or unsaved output fails/refunds, duplicate service instances share admission, completed status survives stale cache, repeated restart recovery refunds/releases once. |
| F11, F29 | Absolute database/cache/results paths under the mounted `/app/data`; one backend process enforced with a file lock; one Kubernetes replica with `Recreate`; matching nginx service DNS; secrets provisioned separately. | Parsed Compose/Kubernetes manifests satisfy persistence, replicas, strategy, secret, and DNS assertions. A second runtime lock owner is rejected. |
| F12–F14 | Shared annotated-CSV parser; inclusive end dates and a prior-session return baseline; unknown market direction/confidence; missing ETF values unavailable and unsupported sensitivities null; single-method ETF conviction low. Frontend sensitivity rendering uses saved parameter changes and fair-value fields, with legacy-report compatibility. | Vendor CSV, last-day inclusion, YTD return baseline, bearish event probability, missing ETF inputs, nullable sensitivity schema, and actual frontend sensitivity-rendering regressions. |
| F15 | Remount ticker state on ticker/account changes, reject foreign prefetched data, and suppress canceled quote responses. Reconnect timers cannot revive a disconnected WebSocket. | Production TypeScript hook/component/class harness reverses responses and exercises account/ticker keys, foreign prefetch, and queued reconnect callbacks; TypeScript/Vite build passes. |

Small related corrections also remove duplicate chat tail emission (F17) and the
pending WebSocket reconnect timer (part of F21). The remaining Medium findings
are outside this remediation scope. Existing valuation/usage/OpenAPI test
fixtures were aligned with the current schemas and watchlist endpoints without
removing their contract assertions.

## Validation

Final verification on 2026-10-06:

- Backend: **290 passed, 1 skipped**, plus 12 passing subtests (316.96 seconds).
  The skip is the existing optional tool-node module test.
- Frontend: production TypeScript ownership/sensitivity harness passed;
  TypeScript/Vite production build and six prerendered pages passed.
- Migration: both minimal and complete legacy-schema upgrades passed, including
  repeat migration, data preservation, orphan cleanup, credential revocation,
  and ID high-water marks after deletion.
- Deployment: Compose/Kubernetes parsing and assertions passed for mounted paths,
  backend replica/strategy, external secrets, and nginx service resolution.
- Static checks: all 45 changed/new Python files parsed; `git diff --check` passed.

Reproduce the suites with:

```sh
.venv/bin/python scripts/run_backend_tests.py
cd frontend
npm run test:ownership
npm run build
```

The backend runner uses temporary databases and dummy credentials, disables
dotenv loading, and blocks outbound socket connections. No live payments,
emails, paid model calls, or production database changes are used for verification.

## Deployment notes

1. **Back up before upgrading.** Stop the old backend and take a consistent SQLite
   backup. Locate the actual running database: the old Compose relative URL could
   place it at `/app/backend/data/flowdeck.db`, outside the `/app/data` mount.
   Copy that database into the mounted data directory before replacing the old
   container. Also preserve cache/results if needed. Do not start with an empty
   mount and assume the previous account/payment data was migrated.
2. **Use one backend process.** Keep one Uvicorn worker and one backend replica.
   Remove any previously installed backend HPA; removing its YAML definition alone
   does not delete an existing cluster object. Use `Recreate` and retain the PVC.
   The runtime lock and SQLite require a filesystem with working local locking.
3. **Provision signing and provider settings.** Set a random `JWT_SECRET` of at
   least 32 characters. Compose now requires it. Kubernetes no longer writes a
   placeholder `flowdeck-secrets`; provision real secrets separately. Missing
   production signing configuration stops startup. Explicit
   `FLOWDECK_ENV=development` may use an ephemeral signing secret.
4. **Allow the startup migration/recovery to finish.** It adds identity and
   idempotency columns and new state tables, seeds ID high-water marks, revokes
   unbound API keys, and removes truly orphaned FK rows. Existing JWT sessions
   are invalidated; users must sign in again and recreate legacy API keys.
   Historically misattributed rows after prior numeric-ID reuse cannot be
   automatically distinguished from valid rows and need a separate data audit.
5. **Expect interrupted work to fail and refund once.** Startup does not rerun
   paid work. Queued/running analyses and digests fail with recovery messages;
   unfinished chat reservations are released. Users can start another operation.
   Failed-charge and payment-credit reconciliation runs every two minutes,
   independently of optional content schedulers.
6. **Reconcile pre-upgrade pending PayPal payments.** Their old numeric `custom`
   identity cannot be safely rebound automatically. Settle/check them against
   the PayPal dashboard and existing ledger before upgrade, or reconcile them
   manually with verified ownership afterward. New orders persist their package
   snapshot; a captured but uncredited order is retried without a second sale.
7. **Account for the visible behavior changes.** Host Python execution remains
   disabled pending real OS isolation. Public analysis callers must remove
   endpoint/model overrides and use depth 1–5. Missing ETF valuations and
   prediction-market direction/confidence are now unavailable instead of
   fabricated values.

## Verification limits

Live provider/PayPal behavior, browser layout, container startup, cluster rollout,
and production data migration were not exercised. External services were mocked;
frontend ownership used deterministic execution of production code. The chat
budget bounds admitted logical calls conservatively and rejects excess settlement;
provider-side retries or hidden tool-provider usage are not a provider invoice
guarantee. Thread timeouts still do not cancel underlying work (F23, Medium).
This change intentionally supports a single SQLite backend; automatic paid-job
retry and horizontal backend scaling still require a durable worker architecture.
