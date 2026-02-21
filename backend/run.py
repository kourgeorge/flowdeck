"""Run script for the backend server."""

import sys
import os
from pathlib import Path

# Get the backend directory (where this script is located)
backend_dir = Path(__file__).parent.absolute()

# Change working directory to backend directory
os.chdir(backend_dir)

# Add repo root to path so we can import ai_engine (tradingagents, stock_deep_research, etc.)
project_root = backend_dir.parent
sys.path.insert(0, str(project_root))

# Add backend directory to path so we can import modules
sys.path.insert(0, str(backend_dir))

# So uvicorn reload subprocess can find tradingagents
os.environ["PYTHONPATH"] = os.pathsep.join(
    [str(project_root), os.environ.get("PYTHONPATH", "")]
)

if __name__ == "__main__":
    import uvicorn
    log_config_path = backend_dir / "uvicorn_logging.json"

    # Use import string so reload/workers work (uvicorn re-imports in subprocess)
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True, log_config=str(log_config_path))
