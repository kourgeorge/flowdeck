# Morning watchlist updates

The scheduler checks subscribed users every 15 minutes. Each user's check is due at
08:00 in their saved notification timezone, with catch-up until noon. Before a
notification preference exists, the service uses their saved brief timezone or
`DIGEST_DEFAULT_TIMEZONE` (UTC by default). Existing and new accounts are enabled.

An email requires **both** an absolute daily move **strictly greater than 6%** and an
event score at least `MIN_EVENT_SCORE` (currently 10). The move uses the latest two
completed daily bars before the user's local date, prefers adjusted closes, and
rejects stale or invalid prices. The event score is the existing deterministic
score for that session. No previous AI report is required. The older re-analysis
monitor retains its separate score-delta and cooldown policy.

Only after eligibility is established does the service fetch news, enrich up to four
article bodies per qualifying ticker, and run the configured deep LLM twice: first
for evidence and competing explanations, then for an original combined article.
Source links come from the news feed. Missing article bodies fall back to summaries;
missing substantive news fails the attempt instead of emailing an invented explanation.
These automatic notifications do not debit a user's platform tokens.

Users can turn the feature off or change timezone in **Profile → Overview → Watchlist
email preferences**. The existing per-ticker email switch also excludes that ticker
from morning emails. Preferences are checked again after research, before sending.
The API is `GET/PUT /api/watchlist/notifications`, authenticated as the current user.

`watchlist_updates` records a unique check per user/local day. Conditional claims
prevent overlapping workers, and persisted ticker/session keys suppress repeat
alerts across weekends and restarts. Research failures retry after 15 minutes, up to
three attempts; expired research leases can be reclaimed after two hours. Sending
is persisted before calling the mail transport. Unconfirmed delivery is marked
`delivery_unknown` and is not retried automatically, because a timeout can happen
after successful delivery. Inspect provider logs before manually reconciling such
records. Confirmed deliveries have status `sent` and a `sent_at` timestamp.

Deployment: the new table is additive and created by the existing `init_db()` startup
path. The existing email credentials and LLM configuration are used. Set
`ENABLE_WATCHLIST_UPDATES=false` to disable the scheduler globally; its default is
true. No production database or delivery is needed to test this feature.

Focused checks: `PYTHONPATH=.:backend .venv/bin/python -m pytest backend/tests/test_watchlist_updates.py`.

Verification: 43 tests passed across the new notification tests and existing event
monitor tests (plus five parameterized subtests). TypeScript and the frontend
production build passed. Checks used temporary databases, mocked email/model calls,
and blocked network connections. No live notifications were sent during development.
