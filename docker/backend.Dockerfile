# Backend Dockerfile for Flowdeck
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
COPY pyproject.toml .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy AI engine (dependency for backend)
COPY ai_engine/ ./ai_engine/

# Copy all backend files to /app/backend
COPY backend/*.py ./backend/
COPY backend/*.json ./backend/
COPY backend/data/ ./backend/data/
COPY backend/models/ ./backend/models/
COPY backend/routers/ ./backend/routers/
COPY backend/services/ ./backend/services/
COPY backend/data_layer/ ./backend/data_layer/
COPY backend/processing/ ./backend/processing/
COPY backend/templates/ ./backend/templates/
COPY backend/TPS/ ./backend/TPS/

# Create necessary directories
RUN mkdir -p /app/data /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/backend

# Change to backend directory for execution
WORKDIR /app/backend

# Expose port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Run the application from backend directory
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]