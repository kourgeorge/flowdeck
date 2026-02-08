# Deployment Guidelines for Ubuntu

This guide covers deploying the TradingAgents framework and Stock Dashboard on Ubuntu 22.04 LTS (or 20.04+).

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
sudo git clone https://github.com/TauricResearch/TradingAgents.git
sudo chown -R $USER:$USER TradingAgents
cd TradingAgents
```

---

## 4. Backend Setup (Stock Dashboard)

### Create virtual environment

```bash
cd /opt/TradingAgents
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

Create `.env` in project root:

```bash
cp .env.example .env
nano .env
```

Add (replace placeholders with real values):

```env
OPENAI_API_KEY=sk-...
ALPHA_VANTAGE_API_KEY=...
```

Create `backend/.env` if needed (backend can inherit from root or use its own):

```bash
nano backend/.env
```

```env
# Optional backend-specific
CORS_ORIGINS=https://your-domain.com,https://www.your-domain.com
BACKEND_URL=https://api.your-domain.com
ENABLE_DAILY_SYNC=true
SYNC_SCHEDULE_TIME=06:00
PORT=8002
```

---

## 5. Frontend Build (Stock Dashboard)

```bash
cd /opt/TradingAgents/frontend
npm ci
npm run build
```

For production, set API URL before build:

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
WorkingDirectory=/opt/TradingAgents/backend

# Load .env from project root
EnvironmentFile=/opt/TradingAgents/.env

# Python path for tradingagents package
Environment=PYTHONPATH=/opt/TradingAgents
Environment=PORT=8002

ExecStart=/opt/TradingAgents/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8002

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Important:** Adjust `User`/`Group` and paths to match your setup. Ensure the user has read access to `results/` and `.env`.

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
# Upstream for backend
upstream backend {
    server 127.0.0.1:8002;
}

# Redirect HTTP to HTTPS (uncomment when SSL is configured)
# server {
#     listen 80;
#     server_name your-domain.com www.your-domain.com;
#     return 301 https://$server_name$request_uri;
# }

server {
    listen 80;
    # listen 443 ssl http2;  # Uncomment for HTTPS
    server_name your-domain.com www.your-domain.com;

    # SSL (uncomment when using Let's Encrypt)
    # ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Frontend static files
    root /opt/TradingAgents/frontend/dist;
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

## 8. SSL with Let's Encrypt (Optional)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

Follow prompts. Certbot will configure Nginx for HTTPS and auto-renewal.

---

## 9. Cron for Daily Sync (Optional)

If you prefer cron over the in-process scheduler:

```bash
crontab -e
```

Add (adjust path and BACKEND_URL):

```cron
0 6 * * * BACKEND_URL=http://127.0.0.1:8002 /opt/TradingAgents/scripts/sync_major_stocks_daily.sh
```

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
sudo chown -R www-data:www-data /opt/TradingAgents/results
sudo chown -R www-data:www-data /opt/TradingAgents/backend
sudo chmod 640 /opt/TradingAgents/.env
```

---

## 12. Environment Variables Reference

| Variable | Location | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Root `.env` | Required for agents |
| `ALPHA_VANTAGE_API_KEY` | Root `.env` | Market/fundamental data |
| `CORS_ORIGINS` | Backend env | Comma-separated allowed origins |
| `BACKEND_URL` | Backend env | Used by analysis service |
| `VITE_API_URL` | Build-time | API base URL for frontend |
| `ENABLE_DAILY_SYNC` | Backend env | Enable in-process daily sync |
| `SYNC_SCHEDULE_TIME` | Backend env | Time for sync (e.g. `06:00`) |
| `PORT` | Backend env | Backend port (default 8002) |

---

## 13. Verify Deployment

1. **Backend health:** `curl http://localhost:8002/health`
2. **API docs:** `http://your-domain.com/api/docs` (if exposed)
3. **Frontend:** Open `http://your-domain.com` in a browser
4. **Generate report:** Search a ticker and trigger analysis

---

## 14. Troubleshooting

### Backend fails to start

- Check logs: `sudo journalctl -u stock-dashboard-backend -f`
- Verify `PYTHONPATH` includes `/opt/TradingAgents`
- Ensure `tradingagents` package is importable from the backend directory

### CORS errors in browser

- Set `CORS_ORIGINS` to your frontend URL(s)
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
cd /opt/TradingAgents
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
- [ ] `.env` configured with API keys
- [ ] Frontend built with production `VITE_API_URL`
- [ ] systemd service for backend
- [ ] Nginx configured (reverse proxy + static frontend)
- [ ] SSL (optional)
- [ ] Firewall rules
- [ ] Permissions on `results/` and `.env`
- [ ] Cron or in-process daily sync (optional)
