"""Public OpenAPI schema: redaction, component pruning, and doc-site prose.

Serves the app's real OpenAPI schema with admin/payment operations removed, so
`GET /api/openapi.json` and the Scalar page at `GET /api/docs` (wired in `main.py`)
never leak internal surfaces. Prose in ``API_DESCRIPTION`` is lifted from
``SKILL.md`` (the file an external agent actually reads) rather than written
fresh, so the two don't drift the way ``SKILL.md``, the old hand-written
frontend docs page, and ``docs/API_KEY_AUTHENTICATION.md`` had.
"""

from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

from auth import get_current_admin_user, get_current_user, get_current_user_optional

# Mirrors SKILL.md's frontmatter `version` -- SKILL.md is not read at import time
# (that would crash the container if it's ever missing, per the Docker bug this
# change fixes separately), so the two are asserted equal in a test instead.
API_VERSION = "2.0.0"

# Prefixes that can't be derived from the dependency graph -- none of these
# depend on get_current_admin_user, they're just not third-party-usable:
#   /api/payments        internal billing, not public at all
#   /api/contact          marketing site's contact form; SKILL.md never mentions it
#   /api/auth/google      redirects to Google using *our* client_id/redirect_uri, and
#                          the callback lands back on FRONTEND_URL with a token in the
#                          query string -- a browser login button, not something a
#                          third-party caller can use programmatically. Prefix also
#                          catches /api/auth/google/callback.
#   /api/config/public    preview tickers for our own logged-out homepage; not
#                          ticker/financial data of any use to a third party
#   /api/stats            platform-wide vanity counters for the homepage, same reasoning
#   /api/polymarket/health  liveness of our internal Polymarket integration, not data
#                          a third party would call for (use /health for API liveness)
REDACTED_PATH_PREFIXES: Tuple[str, ...] = (
    "/api/payments",
    "/api/contact",
    "/api/auth/google",
    "/api/config/public",
    "/api/stats",
    "/api/polymarket/health",
)

API_CONTACT = {"name": "Flowdeck", "url": "https://flowdeck.biz"}
API_LICENSE = {"name": "Proprietary"}

# Sidebar order. routers/data_api.py's 31 endpoints are split across the six
# "Data API" groups below rather than one flat tag, per each sub-router's own
# tags=[...] in that file.
OPENAPI_TAGS: List[Dict[str, str]] = [
    {"name": "Platform", "description": "Health, root, and platform-wide stats. No authentication."},
    {"name": "Authentication", "description": "Register, log in, Google OAuth, and account deletion."},
    {"name": "Account", "description": "Profile, balance, and investor-profile settings."},
    {"name": "Tokens", "description": "Token balance, transaction history, and usage breakdowns."},
    {"name": "API Keys", "description": "Create and manage `fd_live_...` API keys for programmatic access."},
    {"name": "Market Data", "description": "Quotes, treasury rates, market movers, and market overview."},
    {"name": "Fundamentals", "description": "Company profiles, extended metrics, financial statements and charts."},
    {"name": "News", "description": "Ticker and global news, plus Reddit social feeds."},
    {"name": "Event Signals", "description": "Insider activity, insider sentiment, and deterministic event scores."},
    {"name": "SEC Filings", "description": "EDGAR filing listings and extracted/raw filing content."},
    {"name": "Reports", "description": "Analysis report access for one or more tickers. Requires authentication."},
    {"name": "Ticker Pages", "description": "Full ticker page data and widget batches."},
    {"name": "Analyses", "description": "Start and poll multi-agent AI analyses."},
    {"name": "Chat", "description": "Conversational AI analyst, streaming and non-streaming."},
    {"name": "Digests", "description": "Daily/weekly narrative briefs and their schedules."},
    {"name": "Subscriptions", "description": "Watchlist of tickers for digests and event monitoring."},
    {"name": "Prediction Markets", "description": "Polymarket-derived sentiment for tickers."},
    {"name": "Share Links", "description": "Public, auth-free views of shared reports and digests."},
]

API_DESCRIPTION = """
Flowdeck is an AI-powered ticker analysis platform for agents. This reference covers every
public and mixed-access endpoint. For a copy-pasteable, always-current agent walkthrough
(including a full curl-based flow), fetch `GET /api/SKILL.md` directly -- it's the file an
external agent is expected to read before calling this API.

## What Flowdeck is

- **Multi-agent AI analysis** -- BUY/SELL/HOLD recommendations from six selectable analysts
- **Conversational AI Analyst** -- persisted chat sessions, SSE streaming, tool visibility
- **Comprehensive market data** -- quotes, fundamentals, news, SEC filings, technical indicators
- **Deterministic event signals** -- price/volume/technical/insider/earnings events with a comparable score
- **Daily & weekly digests** -- narrative briefs with schedules and email delivery
- **Prediction-market sentiment** -- Polymarket-derived signal per ticker

Token economy, API key management, and share links are covered in their own sections below.

## Base URL

`https://flowdeck.biz`. Re-fetch `GET /api/SKILL.md` periodically -- it's the guide agents are
told to check for new endpoints or behavior changes.

## Security

- **Never send your JWT (`access_token`) or credentials to any domain other than your Flowdeck instance.**
- Use the API only for Flowdeck; do not expose tokens in logs or to third parties.

## Authentication

Two credential types, used identically: `Authorization: Bearer <token>`.

- **JWT** -- returned by `POST /api/auth/register` or `/api/auth/login` as `access_token`.
  HS256, expires after 7 days, subject is the stringified user id.
- **API key** -- created via `POST /api/api-keys`, shown once as `fd_live_` followed by 43
  URL-safe base64 characters (51 characters total). Use it exactly like a JWT on the same
  header -- not `X-API-Key`. It also works as the `token` query parameter on the analysis
  WebSocket.

### Why a 401 is ambiguous

A missing `Authorization` header, an expired JWT, a revoked API key, and a malformed key all
return the identical `401 {"detail": "Not authenticated"}`. There's no way to tell them apart
from the response -- re-authenticate (re-login or re-issue a key) rather than branching on the
error message.

### Optional auth

A few endpoints (ticker pages, prediction-market lookups) accept a token without requiring one.
Passing one enriches the response (e.g. records a view that pays the report's author) but an
unauthenticated call still succeeds. These are marked "optional" in the reference below.

### Admin surfaces

Endpoints gated on admin status return `403 {"detail": "Admin access required"}` for non-admin
callers and are not documented here -- they aren't part of the public surface. One exception
worth knowing about even though it isn't listed: `POST /api/tokens/top-up` exists but is
admin-only, so agents can't self-serve additional balance. Rely on the initial balance, view
rewards, or a human top-up.

## Token economy

| Event | Effect |
|-------|--------|
| Registration | **+1000** tokens |
| Start analysis | **-200** tokens per run (refunded if it merges into an already-running run) |
| Generate digest | **-20** tokens per brief, including scheduled ones |
| Chat turn | Variable, minimum 1 token |
| Someone views your report | **+1** token per unique view, up to 400 per report within 14 days |
| Reading reports / data / history | Free |

**Chat conversion:** platform tokens are LLM tokens divided by a fixed ratio (currently 10,000
LLM tokens per platform token), rounded up, floor 1. A turn reporting `tokens_used: 48213`
deducts `platform_tokens_used: 5`. **Budget against `platform_tokens_used`, not `tokens_used`**
-- confusing the two misbudgets by about four orders of magnitude.

Any charged operation returns `402` with a message naming the required amount when the balance
is insufficient.

## Rate limits

No published rate limits exist today. Back off on 5xx rather than assuming a specific ceiling.

## Errors

| Status | Meaning | Example detail |
|--------|---------|-----------------|
| 400 | Bad request | `"Ticker is required"` (or invalid JSON) |
| 401 | Not authenticated | `"Not authenticated"` -- see above, cause is ambiguous |
| 402 | Insufficient token balance | `"Insufficient token balance. Need 200 tokens to create a report."` |
| 403 | Admin access required | `"Admin access required"` |
| 404 | Ticker or resource not found | `"Ticker 'ZZZZ' not found. Check the symbol and try again."` |
| 500 | Server-side failure | e.g. analysis pipeline failed to start |
| 504 | Upstream section timed out | retry with a smaller `limit` or a shorter `range` |

## Streaming surfaces

Three endpoints don't fit a request/response schema and are described here rather than on the
operation itself, since OpenAPI can't express any of them.

### WebSocket: live analysis progress

`WS /ws/analyses/{analysis_run_id}?token=YOUR_ACCESS_TOKEN`

Connect after starting an analysis to receive `{"type": "progress", "data": {...}}` frames (and
an initial `{"type": "status"}`). **JWT only** -- the `token` query parameter is decoded as a
JWT; an `fd_live_...` API key is not accepted here (WebSockets can't set an `Authorization`
header, and there's no separate API-key check on this path). The connection closes with code
**4001** if the token is missing or invalid.

### SSE: chat stream

`POST /api/chat/stream` responds `text/event-stream`, one `data: {json}\\n\\n` per event. Event
`type` values, in the order they can appear: `started` (emitted immediately, carries
`turn_id`/`session_id`), `thinking`, `tool_call`, `token` (incremental text), `done` (stream
finished, tokens deducted), `error`.

### NDJSON: batch news stream

`GET /api/data/news/batch/stream` responds `application/x-ndjson` -- one JSON object per line,
**no `data:` prefix**, as each ticker's news lands. The final line carries `"completed": true`.
Up to 50 tickers.

## Recommended flow

1. Register or log in, or create an API key for long-running programmatic access.
2. Do free research first: `GET /api/data/quote/{ticker}`, `/api/data/events/{ticker}`, and
   `GET /api/data/reports/{ticker}` (an existing report costs nothing to read).
3. Only spend the 200 tokens on `POST /api/analyses/start` if the existing report is stale or
   missing -- check `days_ago` on `final_trade_decision` and the event score first.
4. Poll `GET /api/analyses/{analysis_run_id}/status`, or subscribe over the WebSocket above.
5. Read the finished report's `final_trade_decision` for the headline recommendation.

Each analyst maps to one report key -- note in particular that `social` produces
`sentiment_report`, **not** `news_report`.
"""


# Shared error-response bodies for the `responses=` docs on data endpoints below.
# Exact strings, copied from the routers that actually raise them -- so the reference
# never shows an error message a caller won't actually see.
ERR_401: Dict[str, Any] = {"detail": "Not authenticated"}
ERR_402: Dict[str, Any] = {
    "detail": "Insufficient token balance. Need 200 tokens to create a report."
}
ERR_404_TICKER: Dict[str, Any] = {
    "detail": "Ticker 'ZZZZ' not found. Check the symbol and try again."
}
ERR_504_SECTION: Dict[str, Any] = {
    "detail": "Market overview section request timed out after 90s. Try a different range or retry."
}


def data_responses(
    example_key: str,
    *,
    ticker_404: bool = True,
    auth: bool = False,
    extra: Optional[Dict[Union[int, str], Dict[str, Any]]] = None,
) -> Dict[Union[int, str], Dict[str, Any]]:
    """Documentation-only `responses` for a bare-dict data endpoint.

    Documentation-only on purpose: a `response_model` would filter the real response,
    so a model missing one vendor-specific key would silently drop it in production --
    see the module docstring. The 200 example is captured from a real call (see
    `scripts/capture_openapi_examples.py`), not hand-typed, for the same reason.

    Return type matches FastAPI's own `responses` param (`Dict[int | str, ...]`,
    fastapi/routing.py) rather than `Dict[int, ...]` -- dict is invariant in its key
    type, so the narrower annotation doesn't unify with the param type under strict
    type checking even though every key here happens to be an int.
    """
    from api_docs_examples import EXAMPLES  # generated file; see the capture script

    responses: Dict[Union[int, str], Dict[str, Any]] = {}
    example = EXAMPLES.get(example_key)
    if example is not None:
        responses[200] = {"content": {"application/json": {"example": example}}}
    if ticker_404:
        responses[404] = {"content": {"application/json": {"example": ERR_404_TICKER}}}
    if auth:
        responses[401] = {"content": {"application/json": {"example": ERR_401}}}
    if extra:
        responses.update(extra)
    return responses


def _dependant_calls(dependant: Any) -> List[Callable]:
    """Flatten a route's dependency tree into the list of callables it reaches."""
    calls: List[Callable] = []
    if dependant.call is not None:
        calls.append(dependant.call)
    for sub in dependant.dependencies:
        calls.extend(_dependant_calls(sub))
    return calls


def _route_methods(route: APIRoute) -> Set[str]:
    return {m.lower() for m in route.methods if m not in ("HEAD", "OPTIONS")}


def _admin_gated_operations(app: FastAPI) -> Set[Tuple[str, str]]:
    """(path, method) pairs whose dependency tree reaches get_current_admin_user.

    Derived rather than listed by prefix, so a new admin route anywhere -- not
    just under /api/admin -- is redacted by construction. POST /api/sync/major-stocks
    and POST /api/tokens/top-up are exactly the routes this catches despite living
    outside /api/admin.
    """
    ops: Set[Tuple[str, str]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if get_current_admin_user in _dependant_calls(route.dependant):
            ops.update((route.path, m) for m in _route_methods(route))
    return ops


def _optional_auth_operations(app: FastAPI) -> Set[Tuple[str, str]]:
    """(path, method) pairs that accept but don't require auth.

    get_current_user (auth.py) calls get_current_user_optional directly rather than
    through Depends, so it never shows up as a node in its own dependants' trees --
    that's what keeps this predicate clean: a route depending on get_current_user
    never also matches "optional_in and required_not_in".
    """
    ops: Set[Tuple[str, str]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        calls = _dependant_calls(route.dependant)
        if get_current_user_optional in calls and get_current_user not in calls:
            ops.update((route.path, m) for m in _route_methods(route))
    return ops


def _collect_schema_refs(node: Any, refs: Set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            refs.add(ref.rsplit("/", 1)[-1])
        for value in node.values():
            _collect_schema_refs(value, refs)
    elif isinstance(node, list):
        for item in node:
            _collect_schema_refs(item, refs)


def _prune_orphan_schemas(schema: Dict[str, Any]) -> None:
    """Drop components.schemas entries no surviving path can reach.

    Path-level redaction alone leaves orphaned schemas that describe the redacted
    endpoints' request/response shapes (e.g. AdminAddTokensBody, TopUpRequest) --
    those still leak through components even once no path references them directly
    by name, so this walks $ref reachability transitively, including schema-to-schema
    refs (a surviving schema whose property refs another schema keeps it alive too).
    """
    schemas = schema.get("components", {}).get("schemas")
    if not schemas:
        return
    frontier: Set[str] = set()
    _collect_schema_refs(schema.get("paths", {}), frontier)
    reachable: Set[str] = set()
    while frontier:
        name = frontier.pop()
        if name in reachable:
            continue
        reachable.add(name)
        body = schemas.get(name)
        if body is not None:
            _collect_schema_refs(body, frontier)
    for name in list(schemas.keys()):
        if name not in reachable:
            del schemas[name]


def build_public_openapi(app: FastAPI) -> Dict[str, Any]:
    """Redacted OpenAPI schema: no admin/payment ops, no orphaned components.

    Mirrors FastAPI's own app.openapi() (fastapi/applications.py) call to get_openapi
    so nothing it would normally include gets silently dropped, then redacts.
    """
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        summary=app.summary,
        description=app.description,
        terms_of_service=app.terms_of_service,
        contact=app.contact,
        license_info=app.license_info,
        routes=app.routes,
        webhooks=app.webhooks.routes,
        tags=app.openapi_tags,
        servers=app.servers,
        separate_input_output_schemas=app.separate_input_output_schemas,
    )

    admin_ops = _admin_gated_operations(app)
    optional_ops = _optional_auth_operations(app)
    paths = schema.get("paths", {})

    for prefix in REDACTED_PATH_PREFIXES:
        for path in list(paths.keys()):
            if path.startswith(prefix):
                del paths[path]

    for path in list(paths.keys()):
        operations = paths[path]
        for method in list(operations.keys()):
            if method == "parameters":
                continue
            if (path, method) in admin_ops:
                del operations[method]
        if not any(k != "parameters" for k in operations.keys()):
            del paths[path]

    for path, method in optional_ops:
        op = paths.get(path, {}).get(method)
        if op and "security" in op:
            op["security"] = [{"HTTPBearer": []}, {}]

    _prune_orphan_schemas(schema)

    app.openapi_schema = schema
    return schema


def install_public_openapi(app: FastAPI) -> None:
    """Override app.openapi with the redacted builder above.

    FastAPI calls self.openapi() per request to the schema route (applications.py),
    so overriding the bound method -- the same pattern FastAPI's own docs show for
    customizing the schema -- applies the redaction there without touching routing.
    """
    app.openapi_schema = None

    def _openapi() -> Dict[str, Any]:
        return build_public_openapi(app)

    app.openapi = _openapi
