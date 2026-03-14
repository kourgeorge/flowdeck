# Backend refactoring recommendations

Summary of inconsistencies, code smells, layer skips, duplication, and unstructured patterns in the server. Prioritized by impact and effort.

---

## 1. Layer skips (routers using DB directly)

**Issue:** Several routers perform `db.query()`, `db.add()`, `db.commit()` directly instead of going through a service. This mixes HTTP and persistence, makes testing harder, and duplicates query logic.

| Router | What to do |
|--------|------------|
| **public** | Add `PublicStatsService` (or `StatsService`) with `get_public_stats(db)`; router only calls the service. |
| **digest** | Add `DigestService` (or extend a “brief” service): `get_digest_dates(db, user_id)`, `get_digests_for_date(db, user_id, date)`, and move `_report_to_brief_item` + Execution/Report query logic there. |
| **admin** | Add `AdminService`: stats, list users, list reports/executions/subscriptions/views, mission control data. Router stays thin (auth + service calls). |
| **api_keys** | Add `ApiKeyService`: `create`, `list_by_user`, `get_by_id_for_user`, `delete`, `deactivate`, `activate`. Router only validates input and maps service results to responses. |
| **subscriptions** | Add `SubscriptionService`: `list_for_user`, `subscribe`, `update`, `unsubscribe`. Move `db.query(Subscription)` and `db.add`/`commit`/`delete` into the service. |
| **chat** | Move session/message load/save into `chat_persistence` or `chat_service`; router should only call “get_or_create_session”, “list_sessions”, “delete_session”, etc., not use `db.get`/`db.query` directly. |
| **me** | Add `MeService` (or `UserProfileService`): `get_profile(user_id, db)`, `update_profile(user_id, body, db)`, `get_user_stats(user_id, db)`. Move all `db.query(User)`, `db.query(sqla_func.count(...))` into the service. |

**analyses:** Background task already uses a service; the only “skip” is `SessionLocal()` in the router for the background job—acceptable if documented, or move “run sync in background” into a small `AnalysesBackgroundService` that owns the session.

---

## 2. Duplication

### 2.1 Ticker “not found” message and validation

- **data_api:** `_ticker_not_found_detail(ticker)` and `_ensure_ticker_exists(ticker)` (quote-based).
- **analyses:** Inline `detail=f"Ticker '{ticker}' not found. Check the symbol and try again."` and manual quote check.

**Recommendation:** Centralize in one place, e.g. `services/ticker_validation.py` or `utils/ticker.py`:

- `ticker_not_found_message(ticker: str) -> str`
- `ensure_ticker_exists(ticker: str, *, get_quote: Callable) -> None` (async if needed), raising `HTTPException(404, detail=ticker_not_found_message(ticker))`.

Then both `data_api` and `analyses` use these (and share the same message).

### 2.2 ReportService instance

- **main.py + app_services:** Shared `ReportService` set at startup; `get_report_service()` used by analyses, tickers.
- **data_api:** Own `_get_report_service()` creating a new `ReportService()` (or module-level instance).

**Recommendation:** Data API should use `app_services.get_report_service()` so there is a single source of truth. Remove `_get_report_service()` and the extra `ReportService` construction from `data_api`.

### 2.3 ApiKeyResponse / entity → response mapping

- **api_keys:** Repeated pattern: “get entity, then build `ApiKeyResponse(id=..., name=..., key_prefix=..., ...)`” in create, list, deactivate, activate. Same for 404 when key not found.

**Recommendation:** Add `ApiKeyService` and a single helper `api_key_to_response(key: ApiKey) -> ApiKeyResponse` (in service or schemas). Service methods return entities; router maps with the helper. Reduces duplication and keeps ISO formatting in one place.

### 2.4 Stats aggregation pattern

- **me:** `get_me_stats` — multiple `db.query(sqla_func.count(...))` / `coalesce(sum(...))` for one user.
- **admin:** `get_admin_stats` — similar aggregates (counts, time windows).

**Recommendation:** When introducing `MeService` and `AdminService`, consider a small shared module for “user stats” and “platform stats” queries (e.g. `repositories/stats_queries.py` or methods on a `StatsRepository`) so the same aggregation logic is not reimplemented in two places.

---

## 3. Inconsistencies

### 3.1 Sync vs async route handlers

- **Async:** public, payments, analyses, chat (most), me, digest (get_digest), tickers (several), data_api, etc.
- **Sync:** users (register, login, delete, google), contact, api_keys, subscriptions, digest (get_digest_dates, get_digests_for_date), admin (all).

**Recommendation:** Prefer `async def` for all HTTP handlers for consistency and to avoid blocking the event loop on I/O. Move blocking work (DB, external calls) to `asyncio.to_thread()` or run in a thread pool where appropriate. Migrate admin, api_keys, subscriptions, users, contact to `async def` incrementally.

### 3.2 Request body: Pydantic vs raw dict

- **analyses** `start_analysis`: uses `body = await request.json()` and `body.get("ticker")`, `body.get("analysis_date")`, etc.

**Recommendation:** Define a Pydantic model, e.g. `StartAnalysisRequest(ticker: str, analysis_date: Optional[str] = None, analysts: list[str] = ..., ...)`, and use it as the endpoint body. Validates types and documents the API; avoids manual `.get()` and string checks.

### 3.3 Response shape: Pydantic vs plain dict

- Many endpoints use `response_model=SomeModel` (users, public, api_keys, subscriptions, me, digest, chat, admin).
- Others return plain dicts: analyses (`{"analysis_run_id", "ticker", "date", "existing"}`), data_api (e.g. `{"ticker", "data"}`, `{"articles", "count"}`), contact `{"ok", "message"}`, admin `{"ok", "run_id"}`, me `{"token_balance"}`.

**Recommendation:** Add Pydantic response models for these endpoints and set `response_model=...`. Improves OpenAPI docs and client contracts; keeps responses consistent with the rest of the API.

### 3.4 Schema location (router vs models/schemas)

- **api_keys, subscriptions, me, digest, contact:** Request/response models defined in the router file.
- **models/schemas.py:** TickerQuote, ReportInsight, etc.

**Recommendation:** Move API request/response models to `models/schemas.py` (or `routers/schemas/` per domain if you prefer). Routers import from there. Keeps a single place for API contracts and allows reuse (e.g. `ApiKeyResponse` in OpenAPI and in service tests).

---

## 4. Error handling (code smell / rule violation)

Per workspace rule “No Excessive Defensive Programming”: avoid broad `try/except Exception` that swallow and return a generic message.

- **contact.py:** `except Exception as e` → `HTTPException(500, "Failed to send message...")`. Real exception is chained (`from e`) but client never sees the cause. Prefer: let `HTTPException` propagate; for known failures (e.g. SMTP error), map to 503 or 400; avoid catching generic `Exception` for “friendly” 500.
- **payments.py:** Similar broad `except Exception` → 500. Prefer mapping known payment failures and letting the rest propagate.
- **subscriptions.py:** `except Exception: pass` around `notify_admin_new_subscription` and `send_subscription_confirmation`. Acceptable for “best effort” side effects, but consider logging so failures are visible.

**Recommendation:** In contact (and payments), catch only specific exceptions (e.g. `SMTPException`, provider-specific errors), map to appropriate HTTP status; remove the generic `except Exception` that returns a friendly 500. For “best effort” email in subscriptions, keep the `pass` but add a log (e.g. `logger.warning("...", exc_info=True)`).

---

## 5. Service registry vs ad‑hoc wiring

- **app_services:** Only registers `report_service`, `market_data_service`, `analysis_service`. Other services (auth, token, email, paypal, chat, edgar, info_fetcher) are imported directly in routers or created inside modules (e.g. `get_info_fetcher()`, `get_edgar_service()`).

**Recommendation (optional):** If you want uniform dependency injection and easier testing, extend `app_services` (or a small container) to hold token_service, email_service, auth_service, etc., and set them at startup. Routers then depend on getters instead of importing services from multiple modules. Lower priority than fixing layer skips and duplication.

---

## 6. Minor / optional

- **auth_service.send_welcome_email / google_callback:** `except Exception: pass` after sending welcome email. Consider logging on failure so you can detect email delivery issues.
- **Session handling:** Mix of `Depends(get_db)` in routes and `SessionLocal()` in background tasks and some services. Document that background/standalone code must create and close its own session; route handlers use `get_db`. No need to change if it’s intentional.
- **admin mission control / file loading:** `_load_mission_control_entries` and JSON parsing could live in a small “config loader” or admin service so the router doesn’t deal with paths and file I/O.

---

## Suggested order of work

1. **High impact, low effort:** Use `app_services.get_report_service()` in data_api; add shared ticker validation (message + `ensure_ticker_exists`); add Pydantic body for `start_analysis` and Pydantic response models for endpoints that return dicts.
2. **High impact, medium effort:** Introduce ApiKeyService and SubscriptionService; move DB access from api_keys and subscriptions routers into these services.
3. **High impact, higher effort:** Add MeService, AdminService, DigestService, PublicStatsService; refactor me, admin, digest, public to use them. Then chat session handling via chat_persistence/chat_service only.
4. **Consistency:** Migrate sync route handlers to async; move router-local schemas to `models/schemas.py`; tighten contact/payments exception handling and add logging for best-effort email.

This keeps the codebase consistent, testable, and aligned with a clear router → service → DB/repository layering.
