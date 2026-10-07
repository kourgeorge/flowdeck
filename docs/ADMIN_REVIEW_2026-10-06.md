# Admin page and API review — 2026-10-06

**Follow-up:** the findings below describe the pre-fix state. See [the remediation record](ADMIN_REMEDIATION_2026-10-06.md) for implemented changes, migration behavior, and regression results.

Reviewed commit `d860a9f`. This is a review, not a remediation or deployment. Application source is unchanged; the two pre-existing `.env.example` modifications were preserved.

The highest-priority finding is deletion of active paid analyses: it removes the records needed for cancellation recovery and refunds. Several independent accounting and dashboard defects also reproduced. No critical issue or authorization bypass was found in the checks below.

## Scope and approach

The system was divided into authorization, account/token operations, analysis lifecycle, reporting/export, analytics/accuracy, Mission Control, and frontend request/state handling. Each suspected finding was traced through its API, service, database, and UI consumers where applicable. Focused reproductions used temporary SQLite databases with foreign keys enabled and blocked outbound networking.

| Part | Result |
| --- | --- |
| Authorization | All 26 admin routes declare the shared admin guard. All rejected anonymous requests with 401 and regular-user JWT/API-key requests with 403. Authorized mutations were exercised only against synthetic data. |
| Accounts and tokens | Reproduced opening-balance loss, false-success grants, and deletion of the sole administrator. |
| Analysis lifecycle | Reproduced active execution/job deletion without refund and disappearance from monitoring immediately on stop request. |
| Analytics | Reproduced missing chat tokens, inconsistent operation counts, history loss on conversation deletion, and a date-boundary HTTP 500. |
| Accuracy and Mission Control | Reproduced intermediate recommendation selection and failed partial runs qualifying as already reported. |
| Frontend | Executed production components with controlled hooks/transports; reproduced stale period responses and permanently cached Users-tab failure. Inspected pagination and other loading/error flows. |
| Reports/export | Existing ZIP test passed; inspected metadata handling, export provenance, download cleanup, and report-detail request ownership. |

## Prioritized findings

### H1 — Deleting an active paid analysis permanently breaks refund recovery

**Evidence:** `backend/routers/admin.py:428`, `backend/services/token_service.py:398`, `backend/services/token_service.py:438`, `frontend/src/components/admin/OverviewTab.tsx:260`.

The Delete action is enabled for running analyses. Its endpoint deletes cached status and calls `delete_execution`, which deliberately does not refund. Database cascades remove the durable `AnalysisJob` and reports. No cancellation signal is sent. The worker checks for stop requests between graph chunks (`backend/services/analysis_service.py:994`), so deletion does not itself stop its work.

**Reproduced:** charge a user for an analysis, attach an active job, then call the authenticated DELETE endpoint. It returns 200; both execution and job disappear; the charge remains. Explicit refund and periodic reconciliation cannot recover the money because the execution no longer exists. The test verifies persistence and stop signaling; it does not run a paid worker.

**Recommended fix:** reject deletion of queued/running work, route cancellation through the existing failure/refund lifecycle, and retain execution identity until settlement. Permit deletion or archival only after terminal state and settlement have been established. Return 404 for absent IDs.

### M1 — Admin grants can replace an opening balance and report success after failure

**Evidence:** `backend/routers/admin.py:337`, `backend/services/token_service.py:710`, `backend/services/admin_service.py:111`.

Users without a ledger display their legacy opening balance. Admin top-up writes the first purchase transaction without initializing that balance. **Reproduced:** a displayed balance of 1,000 becomes 500 after granting 500, rather than 1,500. This affects uninitialized accounts; it is not a claim that every established account is affected.

The endpoint also ignores the boolean returned by `top_up`. A simulated failed write returns HTTP 200 with the unchanged balance. Grants are recorded as purchases without an admin actor, reason, or operation identity, so retries cannot be distinguished from intentional repeated grants.

**Recommended fix:** initialize the opening balance and apply the grant atomically, check the write result, and record an idempotent admin adjustment with actor/reason. Validate amounts consistently: `UsersTab.tsx:139` coerces empty, zero, and negative input to 1; its HTML maximum is not enforced by the handler or API.

### M2 — A rolling-date boundary crashes recommendations and blocks the Analytics tab

**Evidence:** `backend/services/analytics_service.py:105`, `backend/services/analytics_service.py:735`, `backend/services/analytics_service.py:841`, `frontend/src/components/admin/AnalyticsTab.tsx:139`.

Cost breakdown filters by execution creation time, whereas model distribution filters by report creation time. A run starting just before the cutoff and saving a report just afterward can therefore produce total cost 0 with positive model cost. Recommendations divide model cost by total cost without a zero check.

**Reproduced:** one run and report straddling the 30-day cutoff caused `ZeroDivisionError` and HTTP 500 from `/api/admin/analytics/recommendations`. The UI requires all six analytics requests to succeed in a single `Promise.all`, so this one failure blocks their combined display.

**Recommended fix:** define and reuse one accounting timestamp/window, guard zero denominators, and allow independent analytics panels to show successful results.

### M3 — A failed Users-tab load stays empty and hides its error

**Evidence:** `frontend/src/pages/AdminDashboardPage.tsx:555`, `frontend/src/pages/AdminDashboardPage.tsx:671`.

`usersLoadedRef` is set before users, subscriptions, and views finish loading. If any request fails, no results are committed and the flag stays true. The error is only displayed when dashboard statistics are absent, which is normally false after loading Overview.

**Reproduced using the production component:** fail the users request after successful Overview loading, navigate away, and return. Users remain empty, no error appears, and the request count remains one.

**Recommended fix:** mark the tab loaded only after success; provide tab-local loading, error, and retry states. Avoid discarding successful users data because a supplementary request failed.

### M4 — Changing analytics periods allows stale responses to overwrite current results

**Evidence:** `frontend/src/components/admin/AnalyticsTab.tsx:131`, `frontend/src/pages/AdminDashboardPage.tsx:584`.

Analytics and accuracy requests have no request identity or effect cleanup. **Reproduced for Analytics:** request 30 days, switch to 7 days, resolve 7-day data first, then resolve the older request. All analytics state is overwritten with 30-day results while the selected period remains 7 days. The accuracy effect has the same unguarded pattern, confirmed by inspection.

**Recommended fix:** apply request ownership checks to data, errors, and loading state; abort obsolete requests when supported. The existing report-detail request counter in the same page is a useful local precedent.

### M5 — Analytics totals and operation averages disagree across views

**Evidence:** `backend/services/analytics_service.py:79`, `backend/services/analytics_service.py:96`, `backend/services/analytics_service.py:117`, `backend/services/analytics_service.py:270`.

Chat token accumulation is initialized to zero but never updated. **Reproduced:** a completed chat with 12,000 tokens and $0.12 cost reports zero tokens in the summary, but 12,000 in per-user analytics.

Analysis operation counts use report rows in the breakdown, but execution rows in per-user analytics. **Reproduced:** one analysis with two reports counts as two operations in the breakdown and one analysis per user. This also understates average cost per analysis and makes cross-panel comparisons unreliable.

**Recommended fix:** sum chat tokens and define operation identity consistently: one analysis execution, one completed chat turn, and one digest execution. Keep report-level detail explicitly labeled as reports.

### M6 — Deleting a conversation rewrites historical cost analytics

**Evidence:** `backend/services/analytics_service.py:64`, `backend/services/chat_persistence.py:126`.

Analytics uses deletable messages/reports as its accounting source. **Reproduced:** deleting a completed conversation through the real chat deletion service drops its $0.12 from historical analytics while its token charge remains in `Usage`. Removing reports has the corresponding structural problem for analysis costs.

**Recommended fix:** retain minimal immutable usage/cost facts independently of user-visible content and calculate financial analytics from those facts. This need not retain conversation text. If content-dependent analytics are intentional, label their limited coverage explicitly.

### M7 — Prediction accuracy scores an intermediate recommendation before the final decision

**Evidence:** `backend/services/admin_service.py:571`, `backend/services/analysis_service.py:1313`.

Accuracy prefers `investment_plan`, then legacy `final_trade_decision`, then `trader_investment_plan`. Current execution completion requires the final trader report. **Reproduced:** intermediate BUY and final SELL select BUY. At a higher current price, that would score the intermediate recommendation correct even though the final recommendation was wrong.

**Recommended fix:** use the canonical final recommendation and its corresponding analysis price, with documented legacy fallback. Also make the sampling clear: the current query selects only the latest completed run per ticker and compares it to a current quote, rather than scoring every run at a fixed horizon.

### M8 — Mission Control treats failed partial output as a completed daily report

**Evidence:** `backend/services/admin_service.py:873`, `backend/routers/admin.py:596`, `backend/services/admin_service.py:919`.

The daily exclusion query accepts any report, regardless of execution status or completeness. **Reproduced:** a failed execution containing only a market report qualifies as reported today. The run endpoint then returns `skipped_existing` unless forced, although the requested final analysis is missing.

The field called `last_completed_at` also draws from the latest completed **or failed** execution, so a failed attempt can replace the displayed last success.

**Recommended fix:** share the completed-analysis criteria with the worker/public report lifecycle. Track last attempt and last successful completion separately.

### M9 — Stop immediately hides work that is still running

**Evidence:** `backend/routers/admin.py:290`, `backend/routers/admin.py:311`, `frontend/src/pages/AdminDashboardPage.tsx:351`.

Stop records a request and immediately deletes the cached status used by the running list and Mission Control. **Reproduced:** after a successful stop request, the list omits the run while its durable execution still says running. Real cancellation is cooperative and can wait for a graph chunk to finish.

The UI additionally turns monitoring-fetch errors into an empty list, and the stop handler has no local error handling. Both make operational failure look like absence of work.

**Recommended fix:** show a stopping state until terminal acknowledgement, derive membership from durable active jobs/executions, retain the last known list on refresh failure, and show refresh/stop errors.

### M10 — The sole administrator can delete its own account

**Evidence:** `backend/routers/admin.py:353`, `backend/services/admin_service.py:65`, `frontend/src/components/admin/UsersTab.tsx:80`.

There is no current-user or last-administrator guard. **Reproduced:** the sole admin deletes itself with HTTP 200; zero administrators remain and its next request receives 401. This is an administrative availability problem, not privilege escalation.

**Recommended fix:** reject self-deletion and removal of the final administrator, with checks enforced transactionally on the server. Display account role so destructive actions are understandable.

### M11 — Users and associated data become inaccessible beyond fixed frontend limits

**Evidence:** `frontend/src/pages/AdminDashboardPage.tsx:565`, `frontend/src/components/admin/UsersTab.tsx:97`.

**Confirmed by inspection:** the tab fetches only the newest 100 users, 500 subscriptions, and 500 viewed runs. It offers no pagination or server search, while headings show global totals. Administrators cannot reach older accounts through this tab, and subscription/view detail can be incomplete even for visible users.

**Recommended fix:** add pagination/search with explicit shown-versus-total counts and load user-specific supplementary data on demand. Overview filtering also applies only to already-loaded analyses; move filters into paginated API queries.

## Additional design and robustness observations

- **Export provenance:** ZIP creation prefers filesystem Markdown to database content while exporting database metadata. The existing test explicitly asserts that preference. Decide the authoritative source and expose provenance or hashes so stale files cannot silently produce mismatched exports (`backend/services/admin_service.py:202`).
- **Model cost attribution:** every report is labeled with the configured primary/deep model, even though execution config includes quick and deep models. Model distribution assigns report cost to that label. Preserve actual per-model usage if this chart is intended to guide provider/model spending decisions (`backend/services/analysis_service.py:795`, `backend/services/analytics_service.py:741`). This was traced, not measured against live provider invoices.
- **Malformed metadata:** list endpoints assume parsed metadata is a dictionary and numeric fields are coercible. One non-object JSON value or invalid number can fail a whole list and consequently the initial dashboard request group (`backend/services/admin_service.py:144`, `backend/services/admin_service.py:307`). Validate writes and isolate bad legacy rows on reads. This is a hardening observation; no public arbitrary-metadata write path was established.
- **Unused activity endpoints:** Overview initializes both daily series to empty arrays and never calls `getAnalysesDaily`/`getViewsDaily`; its activity charts can never appear (`frontend/src/pages/AdminDashboardPage.tsx:543`, `frontend/src/components/admin/OverviewTab.tsx:132`). Restore loading or remove the dead feature deliberately.

## Verification and limitations

Backend command:

```sh
.venv/bin/python scripts/run_backend_tests.py /private/tmp/flowdeck-admin-review/test_admin_review.py backend/tests/test_admin_service.py -s
```

Result: **16 passed**: 11 review reproductions/checks and 5 existing admin-service tests. The authorization test covers **78 HTTP rejection cases** (26 routes × anonymous, regular JWT, regular API key). Review reproductions assert the observed defective behavior; they must be converted to desired-behavior tests when fixes are implemented.

Frontend command:

```sh
node /private/tmp/flowdeck-admin-review/check-admin-ui.cjs
```

Result: **2 reproduced frontend failures** using transpiled production components with controlled hooks and transport completion order. This is not a browser rendering/layout test.

Reproduction files are local temporary artifacts, not committed acceptance tests. No production database, live mutation, provider request, payment, or email was used. No live deployment, browser QA, load test, or complete authorized-response matrix was performed. These checks support the specific findings above and do not establish that every admin behavior is correct.

Suggested remediation order: protect active-run deletion first; repair grants and analytics errors next; then correct lifecycle/accuracy semantics, frontend request ownership, and access to paginated data.
