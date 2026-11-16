"""Backend name for the event layer, which now lives in ai_engine.processing.

Importing this package also plugs the backend cache into the event summaries (see
service.py), so backend callers keep using `processing` / `backend.processing`.
"""

from ai_engine.processing import *  # noqa: F401,F403
from ai_engine.processing import __all__  # noqa: F401

from . import service as _service  # noqa: F401  (registers the backend cache)
