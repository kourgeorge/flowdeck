"""
Configuration for data_layer vendors (yfinance, Alpha Vantage, etc.).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

# vendors/ -> data_layer/ -> backend/
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

_config: Optional[Dict[str, Any]] = None
DATA_DIR: Optional[str] = None


def _default_config() -> Dict[str, Any]:
    """Build default config from env and backend paths."""
    data_dir = os.getenv("DATA_SOURCES_DATA_DIR", "").strip() or str(_BACKEND_DIR.parent / "data")
    project_dir = os.getenv("DATA_SOURCES_PROJECT_DIR", "").strip() or str(_BACKEND_DIR.parent)
    return {
        "project_dir": project_dir,
        "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "results"),
        "data_dir": data_dir,
        "backend_url": os.getenv("LLM_BACKEND_URL", "https://api.openai.com/v1"),
        "data_vendors": {
            "core_stock_apis": "yfinance",
            "technical_indicators": "yfinance",
            "fundamental_data": "yfinance",
            "news_data": "yfinance",
        },
        "tool_vendors": {},
    }


def initialize_config() -> None:
    """Initialize with default values."""
    global _config, DATA_DIR
    if _config is None:
        _config = _default_config()
        DATA_DIR = _config["data_dir"]


def set_config(config: Dict[str, Any]) -> None:
    """Update config (for tests or runtime overrides)."""
    global _config, DATA_DIR
    if _config is None:
        initialize_config()
    _config.update(config)
    DATA_DIR = _config.get("data_dir", DATA_DIR)


def get_config() -> Dict[str, Any]:
    """Get current config."""
    if _config is None:
        initialize_config()
    return _config.copy()


initialize_config()
