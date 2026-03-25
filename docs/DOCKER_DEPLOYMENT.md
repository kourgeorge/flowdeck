# Docker Deployment Guide for Flowdeck

This guide covers deploying Flowdeck using Docker and Docker Compose for local development, testing, and production environments.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Docker Compose Deployment](#docker-compose-deployment)
3. [Manual Docker Deployment](#manual-docker-deployment)
4. [Production Considerations](#production-considerations)
5. [Environment Configuration](#environment-configuration)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- Docker 20.10+ installed
- Docker Compose 2.0+ installed
- At least 4GB RAM available
- 10GB free disk space

### 1. Clone and Configure

```bash
# Clone the repository
git clone <your-repo-url>
cd flowdeck

# Copy environment file
cp .env.example .env

# Edit .env with your API keys
nano .env  # or use your preferred editor
```

### 2. Start Services

```bash
# Build and start all services
docker compose -f docker/compose.yml up -d

# View logs
docker compose -f docker/compose.yml logs -f

# Check status
docker compose -f docker/compose.yml ps
```

### 3. Access Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8002
- **API Docs**: http://localhost:8002/docs

### 4. Stop Services

```bash
# Stop services
docker compose -f docker/compose.yml down

# Stop and remove volumes (WARNING: deletes data)
docker compose -f docker/compose.yml down -v
```

---

## Docker Compose Deployment

### Architecture

The `docker/compose.yml` file defines three services:

1. **backend**: FastAPI application (port 8002)
2. **frontend**: React app with Nginx (port 80)
3. **redis**: Optional caching layer (port 6379)

### Configuration

Edit `docker/compose.yml` to customize:

```yaml
services:
  backend:
    environment:
      - ENABLE_DAILY_SYNC=true  # Enable scheduled analysis
      - ENABLE_DIGEST_SCHEDULER=true  # Enable email digests
    ports:
      - "8002:8002"  # Change external port if needed
```

### Volume Management

Data is persisted in:
- `./data`: Database and application data
- `./logs`: Application logs
- `redis-data`: Redis cache (Docker volume)

```bash
# Backup data
tar -czf flowdeck-backup-$(date +%Y%m%d).tar.gz data/

# Restore data
tar -xzf flowdeck-backup-20260324.tar.gz
```

### Scaling Services

```bash
# Scale backend to 3 instances
docker compose -f docker/compose.yml up -d --scale backend=3

# Note: You'll need a load balancer for multiple backend instances
```

---

## Manual Docker Deployment

### Build Images

```bash
# Build backend
docker build -t flowdeck-backend:latest -f docker/backend.Dockerfile .

# Build frontend
docker build -t flowdeck-frontend:latest -f docker/frontend.Dockerfile .
```

### Run Backend

```bash
docker run -d \
  --name flowdeck-backend \
  -p 8002:8002 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e OPENAI_API_KEY=your-key \
  -e ALPHA_VANTAGE_API_KEY=your-key \
  -e JWT_SECRET=your-secret \
  --restart unless-stopped \
  flowdeck-backend:latest
```

### Run Frontend

```bash
docker run -d \
  --name flowdeck-frontend \
  -p 80:80 \
  --link flowdeck-backend:backend \
  --restart unless-stopped \
  flowdeck-frontend:latest
```

### Run Redis (Optional)

```bash
docker run -d \
  --name flowdeck-redis \
  -p 6379:6379 \
  -v redis-data:/data \
  --restart unless-stopped \
  redis:7-alpine redis-server --appendonly yes
```

---

## Production Considerations

### 1. Use Production-Grade Database

Replace SQLite with PostgreSQL:

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: flowdeck
      POSTGRES_USER: flowdeck
      POSTGRES_PASSWORD: secure-password
    volumes:
      - postgres-data:/var/lib/postgresql/data
    restart: unless-stopped

  backend:
    environment:
      - DATABASE_URL=postgresql://flowdeck:secure-password@postgres:5432/flowdeck
    depends_on:
      - postgres
```

### 2. Enable HTTPS

Use a reverse proxy like Nginx or Traefik:

```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./docker/nginx.conf:/etc/nginx/conf.d/default.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - frontend
      - backend
```

### 3. Set Resource Limits

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### 4. Health Checks

Already configured in `docker/compose.yml`:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### 5. Logging Configuration

```yaml
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 6. Security Best Practices

```bash
# Use secrets for sensitive data
echo "your-secret-key" | docker secret create jwt_secret -

# Run as non-root user (add to Dockerfile)
USER 1000:1000

# Scan images for vulnerabilities
docker scan flowdeck-backend:latest
```

---

## Environment Configuration

### Required Variables

```bash
# Minimum required for basic operation
OPENAI_API_KEY=sk-...
ALPHA_VANTAGE_API_KEY=...
JWT_SECRET=...  # Generate with: openssl rand -hex 32
```

### Optional Features

```bash
# Google OAuth
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:3003/auth/callback

# PayPal Payments
PAYPAL_CLIENT_ID=...
PAYPAL_CLIENT_SECRET=...
PAYPAL_MODE=sandbox  # or 'live'

# Email Notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@yourdomain.com

# Redis Caching
REDIS_URL=redis://redis:6379/0
```

### Development vs Production

**Development** (`.env.development`):
```bash
DEBUG=true
LOG_LEVEL=DEBUG
CORS_ORIGINS=http://localhost:3003,http://localhost:80
ENABLE_DAILY_SYNC=false
```

**Production** (`.env.production`):
```bash
DEBUG=false
LOG_LEVEL=INFO
CORS_ORIGINS=https://yourdomain.com
ENABLE_DAILY_SYNC=true
ENABLE_DIGEST_SCHEDULER=true
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose -f docker/compose.yml logs backend
docker compose -f docker/compose.yml logs frontend

# Check container status
docker compose -f docker/compose.yml ps

# Inspect container
docker inspect flowdeck-backend
```

### Port Already in Use

```bash
# Find process using port 8002
lsof -i :8002  # macOS/Linux
netstat -ano | findstr :8002  # Windows

# Change port in docker/compose.yml
ports:
  - "8003:8002"  # Use 8003 externally
```

### Database Issues

```bash
# Access database
docker compose -f docker/compose.yml exec backend sqlite3 /app/data/flowdeck.db

# Reset database (WARNING: deletes all data)
docker compose -f docker/compose.yml down -v
rm -rf data/flowdeck.db
docker compose -f docker/compose.yml up -d
```

### Memory Issues

```bash
# Check resource usage
docker stats

# Increase Docker memory limit (Docker Desktop)
# Settings → Resources → Memory → Increase to 8GB

# Or set limits in docker/compose.yml
deploy:
  resources:
    limits:
      memory: 4G
```

### Network Issues

```bash
# Check network
docker network ls
docker network inspect flowdeck-network

# Recreate network
docker compose -f docker/compose.yml down
docker network prune
docker compose -f docker/compose.yml up -d
```

### Image Build Fails

```bash
# Clear build cache
docker builder prune -a

# Build with no cache
docker compose -f docker/compose.yml build --no-cache

# Check disk space
docker system df
docker system prune -a  # Clean up unused data
```

### Frontend Can't Connect to Backend

1. Check backend is running: `docker compose -f docker/compose.yml ps`
2. Check backend health: `curl http://localhost:8002/health`
3. Verify `docker/nginx.conf` has the correct backend URL
4. Check browser console for CORS errors
5. Verify CORS_ORIGINS includes frontend URL

### Performance Issues

```bash
# Monitor resources
docker stats

# Check logs for errors
docker compose -f docker/compose.yml logs --tail=100 backend

# Increase resources in docker/compose.yml
resources:
  limits:
    cpus: '4'
    memory: 8G
```

---

## Useful Commands

```bash
# View logs
docker compose -f docker/compose.yml logs -f [service]

# Execute command in container
docker compose -f docker/compose.yml exec backend bash
docker compose -f docker/compose.yml exec backend python -c "print('Hello')"

# Restart specific service
docker compose -f docker/compose.yml restart backend

# Update images
docker compose -f docker/compose.yml pull
docker compose -f docker/compose.yml up -d

# Clean up
docker compose -f docker/compose.yml down --rmi all --volumes --remove-orphans

# Export/Import images
docker save flowdeck-backend:latest | gzip > flowdeck-backend.tar.gz
docker load < flowdeck-backend.tar.gz
```

---

## Next Steps

- For IBM Cloud deployment, see [IBM_CLOUD_DEPLOYMENT.md](./IBM_CLOUD_DEPLOYMENT.md)
- For production deployment on VPS, see [DEPLOYMENT.md](./DEPLOYMENT.md)
- For development setup, see [README.md](../README.md)

---

## Support

For Docker-specific issues:
- Docker Documentation: https://docs.docker.com/
- Docker Compose Documentation: https://docs.docker.com/compose/

For Flowdeck application issues:
- Check application logs
- Review environment configuration
- Open an issue on GitHub
