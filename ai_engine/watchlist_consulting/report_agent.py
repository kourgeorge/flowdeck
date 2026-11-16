"""
Report agent: takes watchlist payload, calls LLM, returns structured report (portfolio summary, narrative, per-ticker highlights).
Uses ai_engine.llm_provider for LLM access (OpenAI, Azure, etc.).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure repo root is on path so ai_engine.llm_provider can be imported
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _get_llm():
    """Return LLM via ai_engine.llm_provider (quick role). Raises if not configured."""
    from ai_engine.llm_provider import get_config_from_env, get_llm
    config = get_config_from_env()
    return get_llm(
        "quick",
        config,
        temperature=0.3,
        request_timeout=120,
    )
