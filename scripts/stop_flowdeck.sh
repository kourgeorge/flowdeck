#!/usr/bin/env bash
# Stop Flowdeck backend and frontend.
# Usage: ./scripts/stop_flowdeck.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$ROOT_DIR/.flowdeck.pids"

if [ ! -f "$PID_FILE" ]; then
  echo "No .flowdeck.pids found. Flowdeck may not be running."
  exit 0
fi

echo "[$(date '+%H:%M:%S')] Stopping Flowdeck..."
while read -r pid; do
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    echo "  Stopped PID $pid"
  fi
done < "$PID_FILE"
rm -f "$PID_FILE"
echo "[$(date '+%H:%M:%S')] Done."
