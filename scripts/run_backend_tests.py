"""Run backend regressions against temporary databases with outbound calls blocked.

Usage: .venv/bin/python scripts/run_backend_tests.py [pytest paths/options]
Requires the project's test dependencies to be installed.
"""
import os
from pathlib import Path
import socket
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root / "backend"), str(root)]

    def blocked(*args, **kwargs):
        raise RuntimeError("Outbound network disabled in regression tests")

    socket.create_connection = blocked
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    os.environ.update({
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHON_DOTENV_DISABLED": "1",
        "JWT_SECRET": "regression-only-secret-0123456789abcdef0123456789",
        "OPENAI_API_KEY": "test-only", "ANTHROPIC_API_KEY": "test-only",
        "AZURE_OPENAI_API_KEY": "test-only", "AZURE_OPENAI_ENDPOINT": "https://example.invalid",
        "PAYPAL_CLIENT_ID": "test-only", "PAYPAL_CLIENT_SECRET": "test-only",
        "ENABLE_DAILY_SYNC": "false", "ENABLE_MARKET_OVERVIEW_CACHE_REFRESH": "false",
        "ENABLE_DIGEST_SCHEDULER": "false", "RUN_SCHEDULER": "false",
    })
    with tempfile.TemporaryDirectory(prefix="flowdeck-tests-") as tmp:
        os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/app.sqlite"
        os.environ["DATA_CACHE_PATH"] = f"{tmp}/cache.sqlite"
        os.environ["RESULTS_DIR"] = f"{tmp}/results"
        import pytest
        return pytest.main((sys.argv[1:] or [str(root / "backend/tests")]) +
                           ["-q", "--disable-warnings", "--tb=short"])


if __name__ == "__main__":
    raise SystemExit(main())
