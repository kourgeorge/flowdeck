"""Add backend to sys.path so imports work when running scripts from repo root."""
import sys
from pathlib import Path

# watchlist_consulting lives under ai_engine/ -> repo root is parent.parent.parent
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
