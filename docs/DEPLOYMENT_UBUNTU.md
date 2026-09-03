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
| `PORT` | `backend/.env` or systemd | `8002` | Backend port (Caddy on gateway proxies to it). |

**Important:** Caddy runs on the gateway machine; the Flowdeck server runs the backend (8002) and frontend (4173). Cron and in-process agents call the backend via loopback.

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
- Internet access for API calls (OpenAI, Alpha Vantage, yfinance, SEC EDGAR)
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

### Optional: Use Miniconda

```bash
# Download and install Miniconda (Linux x86_64)
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda3
rm Miniconda3-latest-Linux-x86_64.sh

# Add to PATH (add to ~/.bashrc for persistence)
export PATH="$HOME/miniconda3/bin:$PATH"

# Create environment with Python 3.11
conda create -n flowdeck python=3.11 -y
conda activate flowdeck
```

When using Miniconda, replace `source venv/bin/activate` with `conda activate flowdeck` in the steps below. For systemd, use the conda Python path (e.g. `$HOME/miniconda3/envs/flowdeck/bin/python`).

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

**Option A: venv (default)**

```bash
cd /opt/flowdeck
python3.11 -m venv venv
source venv/bin/activate
```

**Option B: Miniconda** (if you used Miniconda in section 1)

```bash
cd /opt/flowdeck
conda activate flowdeck
# Skip creating venv; use conda env for packages
```

### Install Python dependencies

All backend, TradingAgents, and EDGAR dependencies are in the repo root:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

There is no separate `backend/requirements.txt`; use the root `requirements.txt` only.

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

## 5.4. Prerendering for AI Crawlers

`npm run build` runs the normal Vite build, then automatically a prerender pass (`npm run prerender`) that renders the fully-static pages (`/architecture`, `/contact`, `/how-it-works`, `/privacy`, `/terms`, `/tps`) to real HTML via `react-dom/server` — no headless browser — and writes them into `frontend/dist/` as `<route>.html` (e.g. `dist/tps.html`).

This exists because these routes only ever render an empty `<div id="root"></div>` until client JS runs, which AI crawlers (ChatGPT, Perplexity, Claude, etc.) generally don't execute — they'd otherwise see no content at all. `vite preview`'s built-in fallback already checks for `<path>.html` before falling back to the SPA shell, so this needs no extra web-server configuration on this deployment path. If you deploy via `docker/frontend.Dockerfile` + `docker/nginx.conf` instead, nginx's `try_files` is configured to prefer the prerendered file too.

The prerender step is a safety-first, all-or-nothing pass: every route is rendered and checked (minimum text length, no leftover loading spinner, no error-page text, `<main>` present, expected JSON-LD present) in memory before anything is written. If any route fails its checks, `npm run build` exits non-zero — but `frontend/dist/` itself is left exactly as the plain Vite build produced it, so the site you already have is still fully deployable; you just won't get prerendered pages for crawlers until the failure is fixed. To see the acceptance-gate measurements without writing anything, run `PRERENDER_REPORT=1 npm run prerender` against an existing `dist/`.

Only those 6 routes are prerendered; every other route (`/dashboard`, `/market`, `/tickers/*`, etc.) is untouched and still served as the normal client-rendered SPA.

---

## 5.5. Serve Frontend with npm preview

Caddy on the gateway proxies traffic to this server.

### Run preview (accepts connections from outside)

```bash
cd /opt/flowdeck/frontend
npm run preview -- --host
```

- Listens on **port 4173** by default (or another port if 4173 is in use)
- `--host` makes it listen on all interfaces (0.0.0.0) so the gateway can reach it
- `vite.config.ts` includes `allowedHosts: true` so any Host header (e.g. `flowdeck.kour.me`) is accepted

### systemd service for production

Create `/etc/systemd/system/stock-dashboard-frontend.service`:

```ini
[Unit]
Description=Stock Dashboard Frontend (Vite preview)
After=network.target

[Service]
Type=simple
User=george
Group=george
WorkingDirectory=/opt/flowdeck/frontend

ExecStart=/usr/bin/npm run preview -- --host

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Adjust `User`/`Group` to your deploy user. Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable stock-dashboard-frontend
sudo systemctl start stock-dashboard-frontend
```

### Caddy on gateway

Configure Caddy on the gateway to proxy `/api` and `/ws` to the backend, everything else to the frontend preview, and redirect `www` and any legacy domain to the canonical `flowdeck.biz` host:

```caddy
www.flowdeck.biz {
    redir https://flowdeck.biz{uri} permanent
}

flowdeck.biz {
    @api path /api /api/* /ws /ws/*
    handle @api {
        reverse_proxy 192.168.1.110:8002
    }
    handle {
        reverse_proxy 192.168.1.110:4173
    }

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "geolocation=(), camera=(), microphone=()"
    }
}
```

Replace `192.168.1.110` with your Flowdeck server IP. Open port **4173** on the Flowdeck server firewall (or your gateway must reach it on the LAN). Without the `www` redirect, both hosts serve identical content with no canonical relationship between them, which splits search/AI-crawler trust signals across two domains instead of one.

---

## 5.6. Optional: Run Backend Manually

To run the backend directly (e.g. for testing before systemd):

```bash
cd /opt/flowdeck
source venv/bin/activate   # or: conda activate flowdeck
cd backend
python run.py
```

Or with uvicorn directly:

```bash
cd /opt/flowdeck
source venv/bin/activate
cd backend
uvicorn main:app --host 127.0.0.1 --port 8002
```

For production, use `--host 127.0.0.1` so only localhost can reach it. For development with auto-reload: `python run.py` (binds to 0.0.0.0 and enables reload).

Verify: `curl http://127.0.0.1:8002/health`

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

# Bind to all interfaces so Caddy on the gateway can reach it
ExecStart=/opt/flowdeck/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8002

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Important:** Binding to `0.0.0.0` is required so Caddy on the gateway can proxy requests. Adjust `User`/`Group` and paths to match your setup. Ensure the user has read access to `results/` and `.env`.

**Miniconda users:** Replace `ExecStart` with your conda Python path, e.g. `/home/YOUR_USER/miniconda3/envs/flowdeck/bin/python`. Ensure `User` matches the account where Miniconda is installed.

### Frontend (npm preview)

The frontend is served by npm preview (section 5.5). Caddy on the gateway proxies to it.

### Enable and start services

```bash
sudo systemctl daemon-reload
sudo systemctl enable stock-dashboard-backend stock-dashboard-frontend
sudo systemctl start stock-dashboard-backend stock-dashboard-frontend
sudo systemctl status stock-dashboard-backend stock-dashboard-frontend
```

---

## 7. SSL (Caddy on gateway)

Caddy on the gateway obtains and renews Let's Encrypt certificates automatically. Ensure your domain DNS points to the gateway IP; Caddy will handle HTTPS.

---

## 8. Cron for Daily Sync (Optional)

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

## 9. Firewall (Flowdeck server)

On the Flowdeck server, allow SSH and the ports the gateway needs to reach:

```bash
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 8002/tcp # Backend (for Caddy gateway)
sudo ufw allow 4173/tcp # Frontend preview (for Caddy gateway)
sudo ufw enable
```

Ports 80 and 443 are on the gateway machine; Caddy handles SSL there.

---

## 10. Directory Permissions

Ensure the service user can read/write where needed:

```bash
# If using www-data
sudo chown -R www-data:www-data /opt/flowdeck/results
sudo chown -R www-data:www-data /opt/flowdeck/backend
sudo chmod 640 /opt/flowdeck/.env
```

---

## 11. Environment Variables Reference

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

## 12. Verify Deployment

1. **Backend health (from server):** `curl http://127.0.0.1:8002/health`
2. **Frontend:** Open `https://your-domain.com` (or `http://` before SSL) in a browser
3. **API docs:** `https://your-domain.com/api/docs` (or `/api/redoc`) if exposed
4. **Generate report:** Search a ticker and trigger analysis to confirm end-to-end flow
5. **SEC EDGAR (optional):** For US tickers, the SEC Filings tab and SEC analyst use SEC.gov (no API key). Rate limit: 10 requests/second. Extracted sections (risk factors, MD&A) use the same LLM as analysis (OpenAI/Azure).

---

## 13. Troubleshooting

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
- Confirm frontend is running: `systemctl status stock-dashboard-frontend`
- Ensure Caddy on the gateway proxies to the correct Flowdeck server IP and ports (8002, 4173)

### Prerendered pages missing or stale (`/tps`, `/architecture`, etc. show the SPA shell instead of content)

- Check for `dist/tps.html` etc. to confirm the prerender pass actually ran and wrote files.
- If the last build's prerender step failed its acceptance gates (build would have exited non-zero), `dist/` is left as a plain Vite build (see section 5.4) — re-run `PRERENDER_REPORT=1 npm run prerender` to see why, fix the page, rebuild
- Restart `stock-dashboard-frontend` after a rebuild — `npm run preview` serves whatever was in `dist/` when it started

---

## 14. Upgrade Procedure

```bash
cd /opt/flowdeck
git pull origin main
source venv/bin/activate   # or: conda activate flowdeck
pip install -r requirements.txt
python backend/scripts/migrate_token_economy.py   # run if new DB schema (e.g. token economy) was added
cd frontend && npm ci && npm run build
sudo systemctl restart stock-dashboard-backend stock-dashboard-frontend
```

**Database migrations:** When an upgrade adds new tables or columns, run the migration script before restarting the backend. Full details: [DATABASE_MIGRATION.md](DATABASE_MIGRATION.md).

---

## Summary Checklist

- [ ] Ubuntu 22.04+, Python 3.11, Node.js 20
- [ ] Repository cloned and dependencies installed
- [ ] Root `.env` with API keys; `backend/.env` with production `CORS_ORIGINS`, `BACKEND_URL`
- [ ] Frontend built with production `VITE_API_URL` (or `''` for same-origin) via `npm run build`
- [ ] systemd service for backend (bind to 0.0.0.0 when gateway is on another host)
- [ ] Caddy on gateway configured (see section 5.5)
- [ ] npm preview and backend systemd services running
- [ ] Caddy on gateway handles SSL automatically
- [ ] Firewall on Flowdeck server: 22, 8002, 4173
- [ ] Permissions on `results/` and `.env`
- [ ] Cron or in-process daily sync (optional)
