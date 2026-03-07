#!/usr/bin/env bash
# Start Flowdeck backend and frontend (macOS and Ubuntu compatible).
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

# Portable new-session launcher: use setsid on Linux, plain subshell on macOS
new_session() {
  if command -v setsid &>/dev/null; then
    setsid "$@"
  else
    # macOS: run in background subshell; process group separation via job control
    "$@"
  fi
}

# Kill a saved PID and its entire process group
kill_group() {
  local pid="$1"
  [ -z "$pid" ] && return
  # Get the process group ID of the saved PID
  local pgid
  pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')
  if [ -n "$pgid" ] && [ "$pgid" != "0" ]; then
    kill -- -"$pgid" 2>/dev/null || true
  else
    kill "$pid" 2>/dev/null || true
  fi
}

stop_services() {
  if [ -f "$PID_FILE" ]; then
    echo "[$(date '+%H:%M:%S')] Stopping Flowdeck..."
    while read -r pid; do
      [ -n "$pid" ] && kill_group "$pid"
    done < "$PID_FILE"
    rm -f "$PID_FILE"
    echo "[$(date '+%H:%M:%S')] Stopped."
  fi
  # Always kill orphaned vite/uvicorn processes (handles setsid child escape on Linux)
  pkill -f "vite preview" 2>/dev/null || true
  pkill -f "vite/bin/vite.js" 2>/dev/null || true
  pkill -f "uvicorn main:app" 2>/dev/null || true
  sleep 1
}

if [ "$1" = "--foreground" ]; then
  trap stop_services EXIT INT TERM
  echo "[$(date '+%H:%M:%S')] Starting backend (port 8002) and frontend (port 4173)..."
  echo "[$(date '+%H:%M:%S')] Press Ctrl+C to stop both."
  # Start backend in a new session so it leads its own process group
  cd "$BACKEND_DIR"
  new_session python -m uvicorn main:app --host 0.0.0.0 --port 8002 --workers 1 --log-config "$BACKEND_DIR/uvicorn_logging.json" &
  BACKEND_PID=$!
  echo $BACKEND_PID > "$PID_FILE"
  # Start frontend in a new session so npm + vite child share a process group
  cd "$FRONTEND_DIR"
  new_session npm run preview -- --host &
  FRONTEND_PID=$!
  echo $FRONTEND_PID >> "$PID_FILE"
  wait $BACKEND_PID $FRONTEND_PID
else
  # Background mode
  stop_services 2>/dev/null || true
  echo "[$(date '+%H:%M:%S')] Starting Flowdeck in background..."
  cd "$BACKEND_DIR"
  new_session nohup python -m uvicorn main:app --host 0.0.0.0 --port 8002 --workers 1 --log-config "$BACKEND_DIR/uvicorn_logging.json" > "$ROOT_DIR/backend.log" 2>&1 &
  echo $! > "$PID_FILE"
  cd "$FRONTEND_DIR"
  new_session nohup npm run preview -- --host >> "$ROOT_DIR/frontend.log" 2>&1 &
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
