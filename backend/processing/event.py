"""Moved to ai_engine.processing.event; this name stays so `processing.event` imports keep working."""

import sys

from ai_engine.processing import event as _moved

# Alias the module itself (not a star import) so private helpers and class identity
# are shared: processing.event and ai_engine.processing.event are the same object.
sys.modules[__name__] = _moved
