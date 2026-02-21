#!/usr/bin/env bash
# Start Flowdeck backend and frontend on Ubuntu.
# Prerequisites: venv activated (or conda flowdeck), frontend built (npm run build).
# Usage: ./scripts/start_flowdeck.sh [--foreground]
#   --foreground: Run both in foreground (Ctrl+C stops both)
#   (default): Run both in background; use ./scripts/stop_flowdeck.sh to stop

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
PID_FILE="$ROOT_DIR/.flowdeck.pids"

cd "$ROOT_DIR"

# Activate venv if it exists
if [ -d "$ROOT_DIR/venv" ]; then
  source "$ROOT_DIR/venv/bin/activate"
elif [ -n "$CONDA_DEFAULT_ENV" ] && [ "$CONDA_DEFAULT_ENV" = "flowdeck" ]; then
  : # already in conda flowdeck env
elif command -v conda &>/dev/null && conda env list | grep -q "flowdeck"; then
  eval "$(conda shell.bash hook)"
  conda activate flowdeck
fi

export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"

stop_services() {
  if [ -f "$PID_FILE" ]; then
    echo "[$(date '+%H:%M:%S')] Stopping Flowdeck..."
    while read -r pid; do
      [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
    done < "$PID_FILE"
    rm -f "$PID_FILE"
    echo "[$(date '+%H:%M:%S')] Stopped."
  fi
}

if [ "$1" = "--foreground" ]; then
  trap stop_services EXIT INT TERM
  echo "[$(date '+%H:%M:%S')] Starting backend (port 8002) and frontend (port 4173)..."
  echo "[$(date '+%H:%M:%S')] Press Ctrl+C to stop both."
  # Start backend in background, capture PID
  cd "$BACKEND_DIR"
  python -m uvicorn main:app --host 0.0.0.0 --port 8002 --log-config "$BACKEND_DIR/uvicorn_logging.json" &
  BACKEND_PID=$!
  echo $BACKEND_PID > "$PID_FILE"
  # Start frontend in background, capture PID
  cd "$FRONTEND_DIR"
  npm run preview -- --host &
  FRONTEND_PID=$!
  echo $FRONTEND_PID >> "$PID_FILE"
  wait $BACKEND_PID $FRONTEND_PID
else
  # Background mode
  stop_services 2>/dev/null || true
  echo "[$(date '+%H:%M:%S')] Starting Flowdeck in background..."
  cd "$BACKEND_DIR"
  nohup python -m uvicorn main:app --host 0.0.0.0 --port 8002 --log-config "$BACKEND_DIR/uvicorn_logging.json" > "$ROOT_DIR/backend.log" 2>&1 &
  echo $! > "$PID_FILE"
  cd "$FRONTEND_DIR"
  nohup npm run preview -- --host >> "$ROOT_DIR/frontend.log" 2>&1 &
  echo $! >> "$PID_FILE"
  sleep 2
  if kill -0 $(head -1 "$PID_FILE") 2>/dev/null; then
    echo "[$(date '+%H:%M:%S')] Backend running on http://0.0.0.0:8002 (PID $(head -1 "$PID_FILE"))"
  fi
  if kill -0 $(tail -1 "$PID_FILE") 2>/dev/null; then
    echo "[$(date '+%H:%M:%S')] Frontend running on http://0.0.0.0:4173 (PID $(tail -1 "$PID_FILE"))"
  fi
  echo "[$(date '+%H:%M:%S')] Logs: backend.log, frontend.log"
  echo "[$(date '+%H:%M:%S')] Stop with: ./scripts/stop_flowdeck.sh"
fi
