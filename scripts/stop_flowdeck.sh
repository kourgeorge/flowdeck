#!/usr/bin/env bash
# Stop Flowdeck backend and frontend.
# Usage: ./scripts/stop_flowdeck.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$ROOT_DIR/.flowdeck.pids"

# Kill a PID and its entire process group (catches npm -> vite child processes)
kill_group() {
  local pid="$1"
  [ -z "$pid" ] && return
  local pgid
  pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')
  if [ -n "$pgid" ] && [ "$pgid" != "0" ]; then
    kill -- -"$pgid" 2>/dev/null || true
    echo "  Stopped PID $pid (process group $pgid)"
  else
    kill "$pid" 2>/dev/null || true
    echo "  Stopped PID $pid"
  fi
}

echo "[$(date '+%H:%M:%S')] Stopping Flowdeck..."

if [ -f "$PID_FILE" ]; then
  while read -r pid; do
    if [ -n "$pid" ]; then
      kill_group "$pid"
    fi
  done < "$PID_FILE"
  rm -f "$PID_FILE"
else
  echo "  No .flowdeck.pids found — killing by process name..."
fi

# Always clean up any orphaned vite/uvicorn processes (handles setsid child escape on Linux)
pkill -f "vite preview" 2>/dev/null || true
pkill -f "vite/bin/vite.js" 2>/dev/null || true
pkill -f "uvicorn main:app" 2>/dev/null || true

echo "[$(date '+%H:%M:%S')] Done."
