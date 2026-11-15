#!/usr/bin/env bash
# Trigger daily sync of major stocks reports via the dashboard backend API.
# Set BACKEND_URL to override (default: http://localhost:8002).
# Requires FLOWDECK_ADMIN_API_KEY: an API key (fd_live_...) owned by an admin user.
# POST /api/sync/major-stocks is admin-only, so without it every run gets a 401.
# An admin JWT also works, but it expires, so an API key is the right fit for cron.
# Example crontab (run at 6:00 AM daily):
#   0 6 * * * FLOWDECK_ADMIN_API_KEY=fd_live_... /path/to/TradingAgents/scripts/sync_major_stocks_daily.sh

set -e
BACKEND_URL="${BACKEND_URL:-http://localhost:8002}"
URL="${BACKEND_URL%/}/api/sync/major-stocks"

# Fail loudly here: a silent 401 from cron is how the daily reports stopped before.
if [ -z "${FLOWDECK_ADMIN_API_KEY:-}" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] FLOWDECK_ADMIN_API_KEY is not set. Set it to an admin user's API key (fd_live_...); the sync endpoint is admin-only." >&2
  exit 2
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Syncing major stocks: POST $URL"
if response=$(curl -s -w "\n%{http_code}" -X POST "$URL" \
    -H "Authorization: Bearer ${FLOWDECK_ADMIN_API_KEY}" \
    -H "Content-Type: application/json" -d "{}"); then
  http_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | sed '$d')
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] HTTP $http_code"
  echo "$body" | head -c 500
  echo ""
  if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
    exit 0
  fi
  if [ "$http_code" = "401" ] || [ "$http_code" = "403" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Auth rejected: check FLOWDECK_ADMIN_API_KEY is active and belongs to an admin user." >&2
  fi
  exit 1
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] curl failed"
  exit 1
fi
