# Flowdeck deployment guide

This guide covers deploying Flowdeck (backend + frontend) on a Linux server. For a detailed Ubuntu 22.04 walkthrough, see [DEPLOYMENT_UBUNTU.md](DEPLOYMENT_UBUNTU.md).

---

## Overview

| Component | Role |
|-----------|------|
| **Backend** | Python FastAPI app (port 8002). Serves API + WebSockets, runs TradingAgents analysis. |
| **Frontend** | Static React build. Served by Nginx; no Node process in production. |

**Requirements:** Python 3.10–3.12 (3.11 recommended), Node.js 18+ (for build only), 4 GB RAM minimum (8 GB for heavy analysis).

---

## 1. Prerequisites

- Linux server (Ubuntu 20.04+ or similar)
- `python3.11`, `python3.11-venv`, `git`, `curl`, `build-essential`
- Node.js 18+ (for building the frontend once)

---

## 2. Clone and install

```bash
cd /opt   # or your deploy path
sudo git clone https://github.com/kourgeorge/flowdeck.git
sudo chown -R $USER:$USER flowdeck
cd flowdeck
```

**Python (backend + agents):**

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r backend/requirements.txt
```

**Environment:**

Create `.env` in the **project root**:

```env
OPENAI_API_KEY=sk-...
ALPHA_VANTAGE_API_KEY=...
```

Optional `backend/.env` for app settings:

```env
CORS_ORIGINS=https://your-domain.com
BACKEND_URL=https://api.your-domain.com
PORT=8002
ENABLE_DAILY_SYNC=true
SYNC_SCHEDULE_TIME=06:00
```

---

## 3. Build frontend

Build with the production API URL so the app talks to your backend:

```bash
cd /opt/flowdeck/frontend
npm ci
export VITE_API_URL=https://api.your-domain.com   # or https://your-domain.com if same origin
npm run build
```

Output is in `frontend/dist/`. Nginx will serve this directory.

---

## 4. Run backend with systemd

Create `/etc/systemd/system/flowdeck-backend.service` (or keep `stock-dashboard-backend` for compatibility):

```ini
[Unit]
Description=Flowdeck Backend (FastAPI)
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/flowdeck/backend

EnvironmentFile=/opt/flowdeck/.env
Environment=PYTHONPATH=/opt/flowdeck
Environment=PORT=8002

ExecStart=/opt/flowdeck/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8002

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable flowdeck-backend
sudo systemctl start flowdeck-backend
sudo systemctl status flowdeck-backend
```

**Permissions:** Ensure the service user can read `.env` and write to `results/`:

```bash
sudo chown -R www-data:www-data /opt/flowdeck/results /opt/flowdeck/backend
sudo chmod 640 /opt/flowdeck/.env
```

---

## 5. Nginx (reverse proxy + static frontend)

Install Nginx, then create a site config (e.g. `/etc/nginx/sites-available/flowdeck`):

```nginx
upstream flowdeck_backend {
    server 127.0.0.1:8002;
}

server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    root /opt/flowdeck/frontend/dist;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://flowdeck_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /ws {
        proxy_pass http://flowdeck_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
    location /health {
        proxy_pass http://flowdeck_backend;
    }
}
```

Enable and reload:

```bash
sudo ln -s /etc/nginx/sites-available/flowdeck /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 6. SSL (recommended)

Using Let’s Encrypt with Nginx:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

Certbot will adjust the Nginx config for HTTPS and renewal.

---

## 7. Environment variables reference

| Variable | Where | Description |
|----------|--------|-------------|
| `OPENAI_API_KEY` | Root `.env` | Required for agents |
| `ALPHA_VANTAGE_API_KEY` | Root `.env` | Fundamentals/news data |
| `CORS_ORIGINS` | Backend `.env` | Allowed frontend origins (comma-separated) |
| `BACKEND_URL` | Backend `.env` | Public API URL (for analysis callbacks) |
| `VITE_API_URL` | Build-time | API base URL for frontend (set before `npm run build`) |
| `PORT` | Backend | Backend port (default 8002) |
| `ENABLE_DAILY_SYNC` | Backend `.env` | `true` to run in-process daily sync |
| `SYNC_SCHEDULE_TIME` | Backend `.env` | e.g. `06:00` |

---

## 8. Verify

- **Backend:** `curl http://localhost:8002/health` → `{"status":"healthy",...}`
- **Site:** Open `http://your-domain.com` (or HTTPS)
- **API docs:** `https://your-domain.com/api/docs`
- **Report:** Search a ticker and trigger an analysis to confirm the full pipeline.

---

## 9. Troubleshooting

| Issue | What to check |
|-------|----------------|
| Backend won’t start | `sudo journalctl -u flowdeck-backend -f`; ensure `PYTHONPATH=/opt/flowdeck` and `tradingagents` is importable from `backend/`. |
| CORS errors | Set `CORS_ORIGINS` to the exact frontend URL(s); restart backend. |
| Reports not found | `results/` exists and is writable by the service user; `RESULTS_DIR` in `backend/config.py`. |
| 502 Bad Gateway | Backend running on 8002; Nginx upstream points to `127.0.0.1:8002`. |
| Wrong API in browser | Rebuild frontend with correct `VITE_API_URL` and redeploy `frontend/dist/`. |

---

## 10. Upgrades

```bash
cd /opt/flowdeck
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
pip install -r backend/requirements.txt
python backend/scripts/migrate_token_economy.py   # if token economy / new DB schema was added
cd frontend && npm ci && npm run build   # set VITE_API_URL if needed
sudo systemctl restart flowdeck-backend
```

**Database migrations:** If the upgrade adds new tables or columns, run the migration script before restarting. See [DATABASE_MIGRATION.md](DATABASE_MIGRATION.md) for details.

---

## Optional: daily sync via cron

Instead of (or in addition to) in-process sync, you can call the sync endpoint daily:

```cron
0 6 * * * curl -s -X POST http://127.0.0.1:8002/api/sync/major-stocks -H "Content-Type: application/json" -d '{}'
```

Or use the script (set `BACKEND_URL` if needed):

```cron
0 6 * * * BACKEND_URL=http://127.0.0.1:8002 /opt/flowdeck/scripts/sync_major_stocks_daily.sh
```

---

For step-by-step Ubuntu 22.04 instructions (Python/Node install, firewall, full Nginx example), see **[DEPLOYMENT_UBUNTU.md](DEPLOYMENT_UBUNTU.md)**.
