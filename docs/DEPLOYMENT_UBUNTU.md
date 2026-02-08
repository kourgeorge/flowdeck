# Deployment Guidelines for Ubuntu

This guide covers deploying the TradingAgents framework and Stock Dashboard on Ubuntu 22.04 LTS (or 20.04+) in **production**.

---

## Production Configuration Checklist

Before deploying, set these values. Replace `your-domain.com` with your actual domain.

| Variable | Where | Production Value | Notes |
|----------|-------|------------------|-------|
| `CORS_ORIGINS` | `backend/.env` | `https://your-domain.com,https://www.your-domain.com` | **Required.** Comma-separated frontend URLs. Do not rely on localhost defaults. |
| `VITE_API_URL` | Before `npm run build` | `https://your-domain.com` or `''` | If API is at `/api` on same domain, use `''` for same-origin. If API is on `api.your-domain.com`, use full URL. |
| `BACKEND_URL` | `backend/.env` | `http://127.0.0.1:8002` | Used internally by analysis service and cron on same server. Keep as loopback. |
| `INFO_SERVICE_URL` | `backend/.env` (optional) | Same as `BACKEND_URL` | Override only if backend is on another host. |
| `ENABLE_DAILY_SYNC` | `backend/.env` | `true` | Enable in-process daily sync. |
| `SYNC_SCHEDULE_TIME` | `backend/.env` | `06:00` | Time for daily sync. |
| `PORT` | `backend/.env` or systemd | `8002` | Backend port (internal; Nginx proxies to it). |

**Important:** `127.0.0.1` is intentional for `BACKEND_URL` when everything runs on the same server. The backend binds to loopback; only Nginx (reverse proxy) is exposed to the internet. Cron and in-process agents call the backend via loopback.

**Config files:** No code changes are required. `backend/config.py` reads `CORS_ORIGINS` and `BACKEND_URL` from the environment; set them in `backend/.env`.

---

## Overview

The system has two main components:

1. **TradingAgents** — Python-based multi-agent trading framework (CLI, backend services)
2. **Stock Dashboard** — FastAPI backend + React frontend

---

## Prerequisites

### System Requirements

- Ubuntu 22.04 LTS (or 20.04+)
- 2+ CPU cores, 4 GB RAM minimum (8 GB recommended for AI analysis)
- Internet access for API calls (OpenAI, Alpha Vantage, yfinance)
- Optional: Domain name and SSL for production

### Install System Dependencies

```bash
sudo apt update
sudo apt install -y build-essential git curl wget python3-dev
```

---

## 1. Install Python 3.11

```bash
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
python3.11 --version  # Should show 3.11.x
```

### Optional: Use pyenv for flexible Python versions

```bash
curl https://pyenv.run | bash
# Add to ~/.bashrc or ~/.zshrc:
#   export PATH="$HOME/.pyenv/bin:$PATH"
#   eval "$(pyenv init -)"
exec "$SHELL"
pyenv install 3.11
pyenv global 3.11
```

---

## 2. Install Node.js (for frontend build)

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node --version   # Should show v20.x
npm --version
```

---

## 3. Clone and Setup Repository

```bash
cd /opt  # or your preferred deploy path
sudo git clone https://github.com/kourgeorge/flowdeck.git
sudo chown -R $USER:$USER flowdeck
cd flowdeck
```

---

## 4. Backend Setup (Stock Dashboard)

### Create virtual environment

```bash
cd /opt/flowdeck
python3.11 -m venv venv
source venv/bin/activate
```

### Install main dependencies (TradingAgents)

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Install backend dependencies

```bash
pip install -r backend/requirements.txt
```

### Environment variables

Create `.env` in project root (for systemd) and `backend/.env`:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
nano .env
nano backend/.env
```

Add real values to both. Root `.env` provides API keys for systemd. `backend/.env` is loaded by the app and should include production settings (see Production Configuration Checklist).

```env
# Production: required for CORS (do not rely on localhost defaults)
CORS_ORIGINS=https://your-domain.com,https://www.your-domain.com

# Internal: analysis service and cron call backend via loopback on same server
BACKEND_URL=http://127.0.0.1:8002

# Daily sync
ENABLE_DAILY_SYNC=true
SYNC_SCHEDULE_TIME=06:00
PORT=8002
```

Replace `your-domain.com` with your actual domain. If your API is on a subdomain (e.g. `api.your-domain.com`), add it to `CORS_ORIGINS` as well.

---

## 5. Frontend Build (Stock Dashboard)

```bash
cd /opt/flowdeck/frontend
cp .env.example .env   # optional; edit for production
npm ci
npm run build
```

For production, set the API URL before build (in `.env` or inline). If the API is served at `/api` on the same domain as the frontend, use same-origin:

```bash
# Same-origin (API at https://your-domain.com/api): leave empty
export VITE_API_URL=
npm run build
```

If the API is on a separate subdomain:

```bash
export VITE_API_URL=https://api.your-domain.com
npm run build
```

Built assets will be in `frontend/dist/`.

---

## 6. Run with systemd (Production)

### Backend service

Create `/etc/systemd/system/stock-dashboard-backend.service`:

```ini
[Unit]
Description=Stock Dashboard Backend (FastAPI)
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/flowdeck/backend

# Load .env from project root
EnvironmentFile=/opt/flowdeck/.env

# Python path for tradingagents package
Environment=PYTHONPATH=/opt/flowdeck
Environment=PORT=8002

# Bind to loopback only; Nginx reverse proxy handles external traffic
ExecStart=/opt/flowdeck/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8002

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Important:** Binding to `127.0.0.1` is correct for production—the backend is not exposed directly; Nginx proxies requests. Adjust `User`/`Group` and paths to match your setup. Ensure the user has read access to `results/` and `.env`.

### Frontend (serve static files via Nginx)

The frontend is a static build; Nginx will serve it. No separate Node process needed in production.

### Enable and start backend

```bash
sudo systemctl daemon-reload
sudo systemctl enable stock-dashboard-backend
sudo systemctl start stock-dashboard-backend
sudo systemctl status stock-dashboard-backend
```

---

## 7. Nginx Reverse Proxy

Install Nginx:

```bash
sudo apt install -y nginx
```

Create `/etc/nginx/sites-available/stock-dashboard`:

```nginx
# Upstream: backend listens on loopback only (internal)
upstream backend {
    server 127.0.0.1:8002;
}

# Redirect HTTP to HTTPS (enable after SSL is configured in section 8)
# server {
#     listen 80;
#     server_name your-domain.com www.your-domain.com;
#     return 301 https://$server_name$request_uri;
# }

server {
    listen 80;
    # Production with SSL: add listen 443 ssl http2; and cert paths, then enable redirect above
    # listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    # SSL (see section 8 for Let's Encrypt)
    # ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Frontend static files
    root /opt/flowdeck/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # API and WebSocket
    location /api {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /health {
        proxy_pass http://backend;
    }
}
```

Enable site and restart Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/stock-dashboard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 8. SSL with Let's Encrypt (Recommended for Production)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

Follow prompts. Certbot will configure Nginx for HTTPS and auto-renewal. After SSL is in place, enable the HTTP→HTTPS redirect in the Nginx config (see comments in section 7).

---

## 9. Cron for Daily Sync (Optional)

If you prefer cron over the in-process scheduler:

```bash
crontab -e
```

Add (adjust path to your deploy directory):

```cron
0 6 * * * /opt/flowdeck/scripts/sync_major_stocks_daily.sh
```

The script defaults to `BACKEND_URL=http://127.0.0.1:8002`; that is correct when cron runs on the same server as the backend. Override only if the backend is on another host.

---

## 10. Firewall

```bash
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

---

## 11. Directory Permissions

Ensure the service user can read/write where needed:

```bash
# If using www-data
sudo chown -R www-data:www-data /opt/flowdeck/results
sudo chown -R www-data:www-data /opt/flowdeck/backend
sudo chmod 640 /opt/flowdeck/.env
```

---

## 12. Environment Variables Reference

| Variable | Location | Production | Description |
|----------|----------|------------|-------------|
| `OPENAI_API_KEY` | Root `.env` | Required | Required for agents |
| `ALPHA_VANTAGE_API_KEY` | Root `.env` | Required | Market/fundamental data |
| `CORS_ORIGINS` | Backend `.env` | `https://your-domain.com,...` | **Required.** Comma-separated frontend origins. Do not use localhost. |
| `BACKEND_URL` | Backend `.env` | `http://127.0.0.1:8002` | Internal URL for analysis service and cron (loopback on same server) |
| `INFO_SERVICE_URL` | Backend `.env` | Same as `BACKEND_URL` | Override only if backend is on another host |
| `VITE_API_URL` | Build-time | `''` or `https://api.your-domain.com` | API base URL for frontend (see section 5) |
| `ENABLE_DAILY_SYNC` | Backend `.env` | `true` | Enable in-process daily sync |
| `SYNC_SCHEDULE_TIME` | Backend `.env` | `06:00` | Time for sync |
| `PORT` | Backend `.env` | `8002` | Backend port (internal) |

---

## 13. Verify Deployment

1. **Backend health (from server):** `curl http://127.0.0.1:8002/health`
2. **Frontend:** Open `https://your-domain.com` (or `http://` before SSL) in a browser
3. **API docs:** `https://your-domain.com/api/docs` (or `/api/redoc`) if exposed
4. **Generate report:** Search a ticker and trigger analysis to confirm end-to-end flow

---

## 14. Troubleshooting

### Backend fails to start

- Check logs: `sudo journalctl -u stock-dashboard-backend -f`
- Verify `PYTHONPATH` includes `/opt/flowdeck`
- Ensure `tradingagents` package is importable from the backend directory

### CORS errors in browser

- Set `CORS_ORIGINS` to your production frontend URL(s), e.g. `https://your-domain.com`
- Do not rely on localhost defaults in production
- Restart the backend after changing env vars

### Reports not found

- Ensure `results/` exists and is readable
- Check `RESULTS_DIR` in `backend/config.py`

### 502 Bad Gateway

- Confirm backend is running: `systemctl status stock-dashboard-backend`
- Check Nginx upstream matches backend port (8002)

---

## 15. Upgrade Procedure

```bash
cd /opt/flowdeck
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
pip install -r backend/requirements.txt
cd frontend && npm ci && npm run build
sudo systemctl restart stock-dashboard-backend
```

---

## Summary Checklist

- [ ] Ubuntu 22.04+, Python 3.11, Node.js 20
- [ ] Repository cloned and dependencies installed
- [ ] Root `.env` with API keys; `backend/.env` with production `CORS_ORIGINS`, `BACKEND_URL`
- [ ] Frontend built with production `VITE_API_URL` (or `''` for same-origin)
- [ ] systemd service for backend (binding to 127.0.0.1)
- [ ] Nginx configured (reverse proxy + static frontend)
- [ ] SSL with Let's Encrypt (recommended for production)
- [ ] Firewall rules (22, 80, 443)
- [ ] Permissions on `results/` and `.env`
- [ ] Cron or in-process daily sync (optional)
