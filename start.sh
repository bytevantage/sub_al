#!/bin/bash
# Trading System Startup Script
# Automatically clears ports and starts the system

set -e

echo "🚀 Starting Trading System..."
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to kill process on port
kill_port() {
    local port=$1
    local pid=$(lsof -ti:$port 2>/dev/null)
    
    if [ ! -z "$pid" ]; then
        echo -e "${YELLOW}⚠️  Port $port is in use by PID $pid${NC}"
        echo -e "${YELLOW}   Killing process...${NC}"
        kill -9 $pid 2>/dev/null || sudo kill -9 $pid 2>/dev/null || true
        sleep 1
        echo -e "${GREEN}✓ Port $port cleared${NC}"
    else
        echo -e "${GREEN}✓ Port $port is available${NC}"
    fi
}

# Step 1: Stop any existing containers
echo -e "${BLUE}1. Stopping existing containers...${NC}"
docker-compose down --remove-orphans 2>/dev/null || true
docker stop trading_engine trading_db trading_redis 2>/dev/null || true
docker rm trading_engine trading_db trading_redis 2>/dev/null || true

# Step 2: Clean up orphaned containers
echo ""
echo -e "${BLUE}2. Cleaning up orphaned containers...${NC}"
docker ps -aq --filter "name=trading-prometheus" --filter "name=trading-node-exporter" --filter "name=trading_grafana" | xargs -r docker rm -f 2>/dev/null || true

# Step 3: Check and clear required ports
echo ""
echo -e "${BLUE}3. Checking and clearing ports...${NC}"
kill_port 8000  # Backend API

# Note: PostgreSQL (5432) and Redis (6379) are now internal only
# They don't conflict with host ports anymore

# Step 4: Build the latest image
echo ""
echo -e "${BLUE}4. Building Docker image...${NC}"
docker build -t srb-algo-trading-engine:latest -f docker/Dockerfile.backend .

# Step 5: Start the system
echo ""
echo -e "${BLUE}5. Starting containers...${NC}"
docker-compose up -d

# Step 6: Wait for services to be healthy
echo ""
echo -e "${BLUE}6. Waiting for services to start...${NC}"
sleep 5

# Check if services are running
if docker ps | grep -q trading_engine; then
    echo ""
    echo -e "${GREEN}✅ Trading System Started Successfully!${NC}"
    echo ""
    echo -e "${BLUE}📊 Dashboard:${NC} http://localhost:8000/dashboard"
    echo -e "${BLUE}📡 API:${NC} http://localhost:8000/docs"
    echo -e "${BLUE}❤️  Health:${NC} http://localhost:8000/health"
    echo ""
    echo -e "${YELLOW}View logs:${NC} docker-compose logs -f trading-engine"
    echo -e "${YELLOW}Stop system:${NC} docker-compose down"
    echo ""
else
    echo ""
    echo -e "${RED}❌ Failed to start Trading System${NC}"
    echo -e "${YELLOW}Check logs:${NC} docker-compose logs"
    exit 1
fi
