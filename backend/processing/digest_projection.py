"""Moved to ai_engine.processing.digest_projection; this name stays so `processing.digest_projection` imports keep working."""

import sys

from ai_engine.processing import digest_projection as _moved

# Alias the module itself (not a star import) so private helpers and class identity
# are shared: processing.digest_projection and ai_engine.processing.digest_projection are the same object.
sys.modules[__name__] = _moved
