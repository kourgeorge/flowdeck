#!/bin/bash
# Setup script for Docker deployment
# This script prepares the environment for running Flowdeck with Docker

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Flowdeck Docker Setup ===${NC}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker from: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    echo "Please install Docker Compose from: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${YELLOW}Step 1: Creating required directories${NC}"
mkdir -p data logs
chmod 755 data logs
echo "✓ Created data/ and logs/ directories"

echo -e "${YELLOW}Step 2: Setting up environment file${NC}"
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✓ Created .env from .env.example"
        echo -e "${YELLOW}⚠ Please edit .env and add your API keys before starting${NC}"
    else
        echo -e "${RED}Error: .env.example not found${NC}"
        exit 1
    fi
else
    echo "✓ .env file already exists"
fi

echo -e "${YELLOW}Step 3: Checking .env configuration${NC}"
if grep -q "your-openai-api-key-here" .env 2>/dev/null; then
    echo -e "${RED}⚠ Warning: .env still contains placeholder values${NC}"
    echo "Please update the following in .env:"
    echo "  - OPENAI_API_KEY"
    echo "  - ALPHA_VANTAGE_API_KEY"
    echo "  - JWT_SECRET"
    read -p "Press Enter to continue anyway, or Ctrl+C to exit and configure..."
else
    echo "✓ .env appears to be configured"
fi

echo -e "${YELLOW}Step 4: Creating .gitignore entries${NC}"
if ! grep -q "^data/$" .gitignore 2>/dev/null; then
    echo "data/" >> .gitignore
    echo "logs/" >> .gitignore
    echo "✓ Added data/ and logs/ to .gitignore"
else
    echo "✓ .gitignore already configured"
fi

echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo "Next steps:"
echo "  1. Review and update .env with your API keys"
echo "  2. Start services: docker compose -f docker/compose.yml up -d"
echo "  3. View logs: docker compose -f docker/compose.yml logs -f"
echo "  4. Access frontend: http://localhost:3000"
echo "  5. Access backend: http://localhost:8002"
echo ""
echo "For more information, see docs/DOCKER_DEPLOYMENT.md"

# Made with Bob
