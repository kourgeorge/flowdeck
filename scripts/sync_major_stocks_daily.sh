#!/usr/bin/env bash
# Trigger daily sync of major stocks reports via the dashboard backend API.
# Set BACKEND_URL to override (default: http://localhost:8002).
# Example crontab (run at 6:00 AM daily): 0 6 * * * /path/to/TradingAgents/scripts/sync_major_stocks_daily.sh

set -e
BACKEND_URL="${BACKEND_URL:-http://localhost:8002}"
URL="${BACKEND_URL%/}/api/sync/major-stocks"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Syncing major stocks: POST $URL"
if response=$(curl -s -w "\n%{http_code}" -X POST "$URL" -H "Content-Type: application/json" -d "{}"); then
  http_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | sed '$d')
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] HTTP $http_code"
  echo "$body" | head -c 500
  echo ""
  if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
    exit 0
  fi
  exit 1
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] curl failed"
  exit 1
fi
