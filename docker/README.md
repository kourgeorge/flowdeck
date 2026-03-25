# Docker Quick Start Guide

This guide helps you quickly get Flowdeck running with Docker.

## Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- At least 4GB RAM available
- 10GB free disk space

## Quick Start (3 Steps)

### 1. Run Setup Script

```bash
./docker/setup.sh
```

This will:
- Create required `data/` and `logs/` directories
- Copy `.env.example` to `.env`
- Configure `.gitignore`

### 2. Configure Environment

Edit `.env` and add your API keys:

```bash
# Required
OPENAI_API_KEY=sk-your-key-here
ALPHA_VANTAGE_API_KEY=your-key-here
JWT_SECRET=$(openssl rand -hex 32)

# Optional (for full features)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
PAYPAL_CLIENT_ID=your-paypal-client-id
PAYPAL_CLIENT_SECRET=your-paypal-client-secret
```

### 3. Start Services

```bash
docker compose -f docker/compose.yml up -d
```

## Access Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8002
- **API Documentation**: http://localhost:8002/docs

## Common Commands

```bash
# View logs
docker compose -f docker/compose.yml logs -f

# Stop services
docker compose -f docker/compose.yml down

# Restart a service
docker compose -f docker/compose.yml restart backend

# Rebuild after code changes
docker compose -f docker/compose.yml up -d --build

# Check status
docker compose -f docker/compose.yml ps
```

## Troubleshooting

### Permission Denied Error

If you see "permission denied" when starting:

```bash
mkdir -p data logs
chmod 755 data logs
docker compose -f docker/compose.yml up -d
```

### Port Already in Use

Change ports in `docker/compose.yml`:

```yaml
services:
  backend:
    ports:
      - "8003:8002"  # Use 8003 instead of 8002
  frontend:
    ports:
      - "8080:80"    # Use 8080 instead of 80
```

### Container Won't Start

Check logs for errors:

```bash
docker compose -f docker/compose.yml logs backend
docker compose -f docker/compose.yml logs frontend
```

## Next Steps

- For detailed Docker documentation, see [../docs/DOCKER_DEPLOYMENT.md](../docs/DOCKER_DEPLOYMENT.md)
- For IBM Cloud deployment, see [../docs/IBM_CLOUD_DEPLOYMENT.md](../docs/IBM_CLOUD_DEPLOYMENT.md)
- For development setup without Docker, see [../README.md](../README.md)

## Support

- Check logs: `docker compose -f docker/compose.yml logs -f`
- Verify configuration: `cat .env`
- Test backend: `curl http://localhost:8002/health`
- Test frontend: `curl http://localhost:3000/health`
