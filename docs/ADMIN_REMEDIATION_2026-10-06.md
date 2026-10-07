# Admin review remediation — 2026-10-06

Implemented the high and medium findings in [the admin review](ADMIN_REVIEW_2026-10-06.md), plus its export, metadata, model-attribution, and activity-chart observations.

| Finding | Result |
| --- | --- |
| H1: active paid-run deletion | The API rejects active executions and active jobs with 409. Failed charged executions are refunded in the deletion transaction. Missing IDs return 404. Account deletion cannot bypass active-work protection. |
| M1: token grants | Opening balances are initialized atomically, including zero balances. Grants use an audited `admin_adjustment` with actor, reason, and request identity. Retries credit once; conflicting reuse returns 409; write failures return 500 and roll back. UI and API enforce integer amounts from 1 through 10,000. |
| M2: analytics date-boundary failure | All analytics views share retained cost facts, operation identity, and time-window semantics. Recommendations guard zero denominators. Successful UI panels remain available when another request fails. |
| M3: Users-tab failures | Errors and loading state are visible; explicit retry and tab return reload data. A failed supplementary request does not discard successful results. |
| M4: stale period responses | Analytics and accuracy ignore obsolete completions. The admin content is keyed by authenticated account so cached state cannot cross account changes. |
| M5: inconsistent accounting | Chat tokens are included. One execution or completed chat turn counts as one operation across summaries, per-user totals, expensive operations, and trends. |
| M6: disappearing history | Content-free cost facts survive conversation, report, execution, and account deletion. They are written in the source transaction and backfilled once for existing data. |
| M7: recommendation accuracy | Uses the final trader report, with legacy fallback only when the final report is absent. Price and recommendation come from the same report. The UI explains latest-run sampling and variable time horizons. |
| M8: failed partial runs | Mission Control shares completion criteria with the worker, requires completed status and required outputs, and tracks last successful completion independently of the latest failed attempt. Failed admission is recorded as failed. |
| M9: stopping/monitoring | Active membership comes from durable executions, with cached progress as supplementary data. Stopping remains visible until terminal acknowledgement. Refresh failures preserve the last known list and show an error. |
| M10: administrator deletion | Server rejects self-deletion and last-administrator deletion. The UI identifies administrators and disables deletion of the current account. |
| M11: inaccessible older data | Users, subscriptions, viewed runs, and analyses have page controls with displayed/total counts. User search and analysis ticker/creator filters run on the server. Pagination has stable ordering for equal timestamps. |

Other changes:

- ZIP exports use database content and metadata together, with content provenance in the manifest.
- Malformed report metadata no longer fails whole admin lists.
- New analysis reports retain measured per-call model usage. Costs without reliable historical model attribution are labeled `unattributed` rather than assigned to the configured deep model.
- Overview loads the activity endpoints so its daily charts can appear.

## Upgrade and API behavior

Normal backend startup creates `operation_costs` and runs additive migration version 2. The migration backfills available report/turn metadata once; repeated startup does not repeat that scan. Cost facts contain operation identifiers, user ID, a subject label, timestamps, token totals, and model costs; they contain no report text, conversation text, or email address. Source writes and usage snapshots commit or roll back together.

All analytics attribute an execution's saved report costs to its start time. Chat uses the assistant message timestamp. A rolling window includes the partial first calendar day and the current day. These metrics reflect recorded usage, not reconciled provider invoices. Data deleted before this upgrade cannot be reconstructed, and legacy reports without measured model attribution remain unattributed.

`POST /api/admin/users/{id}/tokens` now requires a UUID `request_id`. Reuse that UUID when retrying the same grant; use a new one for an intentional new grant. Optional `reason` defaults to `Admin token grant`. The updated UI retains the request ID across uncertain failures within the current grant flow.

`POST /api/admin/mission-control/run` requires an explicit, nonempty ticker list. An omitted list no longer means the entire universe. User listing accepts `search`; analyses accept `ticker` and `creator`; viewed-run listing now accepts `offset`.

Cancellation remains cooperative: an in-flight model/tool call can continue until the worker reaches a cancellation checkpoint. The UI now represents that waiting period accurately. Offset pagination has deterministic ordering, but live inserts can still shift later pages; refresh/search retrieves the current data.

## Validation

- Backend suite: **318 passed, 1 skipped, 12 subtests passed** with temporary databases/cache/results and outbound sockets blocked.
- The new admin regression module includes **28 cases**, including all **78 authorization rejection combinations** across the 26 admin routes, concurrent/idempotent grants, rollback, deletion/refund invariants, metadata robustness, completion criteria, retention, migration, and filtered pagination.
- `npm run test:admin`: passed. Executes production components with controlled hooks/transports to check account ownership, stale and partial analytics responses, user-load retry, pagination/search, activity loading, grant validation, and request identity.
- `npm run test:ownership`: passed.
- `npm run build`: passed, including TypeScript and prerendering. Existing bundle-size and Browserslist-age notices remain.
- `git diff --check`: passed.

Two existing digest-context tests needed a missing Polymarket mock to keep the full suite independent of vendor retries. No production database, live payment, email, model call, or deployment was used. Browser layout and live deployment behavior were not tested in this environment.

Commands:

```sh
.venv/bin/python scripts/run_backend_tests.py backend/tests -o faulthandler_timeout=45
cd frontend
npm run test:ownership
npm run test:admin
npm run build
```
