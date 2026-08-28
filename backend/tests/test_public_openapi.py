"""Tests for the redacted public OpenAPI schema (api_docs.py).

Imports the real app and generates its schema once -- costs ~3s, see api_docs.py
for why admin/payment surfaces must never appear here.
"""

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from api_docs import (
    API_DESCRIPTION,
    API_VERSION,
    _admin_gated_operations,
    _optional_auth_operations,
    _collect_schema_refs,
)

SCHEMA = main.app.openapi()


def _operations():
    for path, ops in SCHEMA["paths"].items():
        for method, op in ops.items():
            if method == "parameters":
                continue
            yield path, method, op


def test_no_admin_or_payment_paths_survive():
    leaked = [p for p in SCHEMA["paths"] if p.startswith(("/api/admin", "/api/payments"))]
    assert leaked == []


def test_no_contact_path_survives():
    # No third-party use case, and SKILL.md (the agent-facing guide) never
    # documents it -- it's the marketing site's contact form, not an API.
    assert "/api/contact" not in SCHEMA["paths"]


def test_no_app_internal_paths_survive():
    # Documented in SKILL.md for completeness, but not third-party-usable:
    # the Google OAuth flow redirects through *our* client_id/redirect_uri and
    # back to FRONTEND_URL with a token in the query string, and the config/stats/
    # polymarket-health endpoints exist only to feed our own logged-out homepage
    # or internal vendor monitoring.
    leaked = [
        p
        for p in SCHEMA["paths"]
        if p.startswith(("/api/auth/google", "/api/config/public", "/api/stats", "/api/polymarket/health"))
    ]
    assert leaked == []


def test_no_admin_gated_operation_survives():
    admin_ops = _admin_gated_operations(main.app)
    surviving = [(p, m) for p, m, _ in _operations() if (p, m) in admin_ops]
    assert surviving == []


def test_top_up_and_major_stocks_absent():
    hits = [p for p in SCHEMA["paths"] if "top-up" in p or "major-stocks" in p]
    assert hits == []


def test_no_orphan_component_schemas():
    schemas = SCHEMA["components"]["schemas"]
    reachable = set()
    frontier = set()
    _collect_schema_refs(SCHEMA["paths"], frontier)
    while frontier:
        name = frontier.pop()
        if name in reachable:
            continue
        reachable.add(name)
        body = schemas.get(name)
        if body is not None:
            _collect_schema_refs(body, frontier)
    orphans = set(schemas.keys()) - reachable
    assert orphans == set()


def test_public_surface_size():
    assert len(SCHEMA["paths"]) == 75
    assert sum(len(ops) for ops in SCHEMA["paths"].values()) == 82


def test_optional_and_required_auth_partition():
    optional_ops = _optional_auth_operations(main.app)
    optional = required = 0
    for path, method, op in _operations():
        sec = op.get("security")
        if sec is None:
            continue
        if (path, method) in optional_ops:
            assert sec == [{"HTTPBearer": []}, {}]
            optional += 1
        else:
            assert sec == [{"HTTPBearer": []}]
            required += 1
    assert optional == 7
    assert required == 39


def test_every_public_operation_has_a_description():
    missing = [(p, m) for p, m, op in _operations() if not op.get("description")]
    assert missing == []


def test_api_version_matches_skill_md_frontmatter():
    import re
    from pathlib import Path

    skill_md = Path(__file__).parent.parent / "SKILL.md"
    text = skill_md.read_text()
    match = re.search(r"^version:\s*(\S+)", text, re.MULTILINE)
    assert match is not None
    assert match.group(1) == API_VERSION


def test_key_facts_stay_consistent_with_skill_md():
    """SKILL.md and API_DESCRIPTION are two independent copies of the same facts.

    They drifted before (dfd28bd fixed a 10,000x tokens_used/platform_tokens_used
    conflation); this pins the load-bearing substrings so a future edit to one
    without the other fails loudly instead of silently.
    """
    skill_md = (Path(__file__).parent.parent / "SKILL.md").read_text()

    shared_substrings = [
        "https://flowdeck.biz",
        "fd_live_",
        "platform_tokens_used",
        "started",
        "thinking",
        "tool_call",
        "token",
        "done",
        "error",
    ]
    for substring in shared_substrings:
        assert substring in skill_md, f"missing from SKILL.md: {substring!r}"
        assert substring in API_DESCRIPTION, f"missing from API_DESCRIPTION: {substring!r}"


def _data_api_operations():
    return [(p, m, op) for p, m, op in _operations() if p.startswith("/api/data")]


def _declared_example_keys():
    """example_key strings passed to data_responses(...) in data_api.py's source.

    Reading the source rather than the schema: the schema only shows which keys
    resolved to a 200 example, not which keys a route *asked for* (a typo'd key
    silently resolves to no 200 via EXAMPLES.get() -- see api_docs.data_responses).
    """
    import re

    source = (Path(__file__).parent.parent / "routers" / "data_api.py").read_text()
    return set(re.findall(r'data_responses\(\s*"(\w+)"', source))


def test_every_data_api_route_has_doc_metadata():
    """Every /api/data operation documents itself with a summary and responses.

    Catches a new endpoint added to data_api.py without a summary/responses --
    the plan's Phase 3 requirement -- rather than silently falling back to FastAPI's
    auto-derived "Data Something" summary.
    """
    ops = _data_api_operations()
    assert len(ops) == 31

    for path, method, op in ops:
        summary = op.get("summary", "")
        assert summary and not summary.startswith("Data "), (path, method, summary)
        assert set(op.get("responses", {})) - {"422"}, f"no documented responses: {path}"


def test_captured_examples_match_declared_keys():
    """Every key in the generated api_docs_examples.py is still referenced by a route.

    A route rename/removal in data_api.py without re-running
    scripts/capture_openapi_examples.py would otherwise leave a stale, silently-unused
    entry in EXAMPLES.
    """
    from api_docs_examples import EXAMPLES

    declared = _declared_example_keys()
    orphaned = set(EXAMPLES) - declared
    assert orphaned == set(), f"captured examples with no matching route: {orphaned}"

    # insider_sentiment (no Finnhub key) and reports_dates (pre-existing SQLAlchemy
    # bug in report_service.list_report_dates) are declared but not captured --
    # data_responses() tolerates this by omitting their 200 example.
    missing = declared - set(EXAMPLES)
    assert missing <= {"insider_sentiment", "reports_dates"}, missing
