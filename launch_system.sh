#!/bin/bash

# Trading System Launcher Script
# This script helps you launch the complete trading system

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Define ports
BACKEND_PORT=8000
FRONTEND_PORT=3737
POSTGRES_PORT=5432
REDIS_PORT=6379

echo "═══════════════════════════════════════════════════════════"
echo "🚀 Trading System Launcher"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Function to clear ports
clear_ports() {
    echo "🧹 Clearing ports if in use..."
    
    # Kill processes on backend port
    if lsof -Pi :$BACKEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "  Stopping process on port $BACKEND_PORT..."
        kill $(lsof -t -i:$BACKEND_PORT) 2>/dev/null || true
        sleep 1
    fi
    
    # Kill processes on frontend port
    if lsof -Pi :$FRONTEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "  Stopping process on port $FRONTEND_PORT..."
        kill $(lsof -t -i:$FRONTEND_PORT) 2>/dev/null || true
        sleep 1
    fi
    
    # Kill local PostgreSQL if running (not Docker)
    if lsof -Pi :$POSTGRES_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        LOCAL_PG=$(lsof -i :$POSTGRES_PORT | grep -v "docker" | grep "postgres" || true)
        if [ ! -z "$LOCAL_PG" ]; then
            echo "  Stopping local PostgreSQL on port $POSTGRES_PORT..."
            pg_ctl -D /Library/PostgreSQL/*/data stop 2>/dev/null || sudo -u postgres pg_ctl -D /Library/PostgreSQL/*/data stop 2>/dev/null || true
            sleep 2
        fi
    fi
    
    # Kill local Redis if running (not Docker)
    if lsof -Pi :$REDIS_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        LOCAL_REDIS=$(lsof -i :$REDIS_PORT | grep -v "docker" | grep "redis" || true)
        if [ ! -z "$LOCAL_REDIS" ]; then
            echo "  Stopping local Redis on port $REDIS_PORT..."
            redis-cli shutdown 2>/dev/null || kill $(lsof -t -i:$REDIS_PORT) 2>/dev/null || true
            sleep 1
        fi
    fi
    
    echo "✅ Ports cleared"
    echo ""
}

# Function to check if token is valid
check_token() {
    if [ -f "$HOME/Algo/upstoxtoken.json" ]; then
        TOKEN_AGE=$(python3 -c "
import json, time
with open('$HOME/Algo/upstoxtoken.json') as f:
    data = json.load(f)
    age_hours = (time.time() - data.get('created_at', 0)) / 3600
    print(int(age_hours))
")
        
        if [ "$TOKEN_AGE" -lt 24 ]; then
            echo "✅ Token is valid (age: ${TOKEN_AGE}h)"
            return 0
        else
            echo "⚠️  Token is expired (age: ${TOKEN_AGE}h)"
            return 1
        fi
    else
        echo "❌ Token not found"
        return 1
    fi
}

# Function to fetch fresh token
fetch_token() {
    echo ""
    echo "📡 Fetching fresh Upstox token..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "1. Browser will open automatically"
    echo "2. Login with your Upstox credentials"
    echo "3. Click 'Authorize' to grant access"
    echo "4. Token will be saved automatically"
    echo ""
    read -p "Press Enter to start authentication server..."
    
    # Start auth server
    python3 upstox_auth_working.py
}

# Function to start docker services
start_docker() {
    echo ""
    echo "🐳 Starting Docker services..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check if PostgreSQL is running
    if ! docker ps | grep -q "trading_db"; then
        echo "Starting PostgreSQL database..."
        docker-compose up -d postgres
        echo "Waiting for database to be ready..."
        sleep 5
    else
        echo "✅ PostgreSQL already running"
    fi
    
    # Check if Redis is running
    if ! docker ps | grep -q "trading_redis"; then
        echo "Starting Redis cache..."
        docker-compose up -d redis
        sleep 2
    else
        echo "✅ Redis already running"
    fi
    
    echo "✅ Docker services ready"
}

# Function to start backend
start_backend() {
    echo ""
    echo "🔧 Starting Trading Engine (Backend)..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check if backend is already running
    if lsof -Pi :3737 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "⚠️  Port 3737 already in use. Stopping existing process..."
        kill $(lsof -t -i:3737) 2>/dev/null || true
        sleep 2
    fi
    
    echo "Starting dashboard on http://localhost:3737"
    echo "API Docs: http://localhost:8000/docs"
    echo ""
    
    # Start backend in background
    nohup uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 > logs/backend.log 2>&1 &
    BACKEND_PID=$!
    echo "Backend PID: $BACKEND_PID"
    
    # Wait for backend to be ready
    echo "Waiting for backend to start..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
            echo "✅ Backend is ready!"
            break
        fi
        sleep 1
        echo -n "."
    done
    echo ""
}

# Function to start frontend
start_frontend() {
    echo ""
    echo "🎨 Starting Dashboard (Frontend)..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check if frontend is already running
    if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "⚠️  Port 3000 already in use. Stopping existing process..."
        kill $(lsof -t -i:3000) 2>/dev/null || true
        sleep 2
    fi
    
    cd frontend/dashboard
    echo "Starting dashboard on http://localhost:3000"
    echo ""
    
    # Start frontend in background
    nohup python3 -m http.server 3737 > ../../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo "Frontend PID: $FRONTEND_PID"
    
    cd ../..
    sleep 2
    echo "✅ Dashboard is ready!"
}

# Function to verify system
verify_system() {
    echo ""
    echo "🔍 Verifying System..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Test health endpoint
    echo -n "1. Health Check: "
    if curl -s http://localhost:8000/api/health | grep -q "healthy"; then
        echo "✅ PASS"
    else
        echo "❌ FAIL"
    fi
    
    # Test metrics endpoint
    echo -n "2. Metrics Endpoint: "
    if curl -s http://localhost:8000/metrics | grep -q "trades_total"; then
        echo "✅ PASS"
    else
        echo "❌ FAIL"
    fi
    
    # Test database connection
    echo -n "3. Database Connection: "
    if docker exec trading_db psql -U trading_user -d trading_db -c "SELECT 1;" > /dev/null 2>&1; then
        echo "✅ PASS"
    else
        echo "❌ FAIL"
    fi
    
    # Test dashboard
    echo -n "4. Dashboard: "
    if curl -s http://localhost:3737 | grep -q "Trading System Dashboard"; then
        echo "✅ PASS"
    else
        echo "❌ FAIL"
    fi
    
    echo ""
}

# Function to show URLs
show_urls() {
    echo "═══════════════════════════════════════════════════════════"
    echo "✅ Trading System is READY!"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "📊 Access Points:"
    echo "  • Dashboard:   http://localhost:3737"
    echo "  • API Docs:    http://localhost:8000/docs"
    echo "  • Health:      http://localhost:8000/api/health"
    echo "  • Metrics:     http://localhost:8000/metrics"
    echo "  • Grafana:     http://localhost:3001 (admin/admin)"
    echo ""
    echo "📋 Logs:"
    echo "  • Backend:     tail -f logs/backend.log"
    echo "  • Frontend:    tail -f logs/frontend.log"
    echo "  • Docker:      docker-compose logs -f"
    echo ""
    echo "🛑 Stop System:"
    echo "  • All:         docker-compose down"
    echo "  • Backend:     kill \$(lsof -t -i:8000)"
    echo "  • Frontend:    kill \$(lsof -t -i:3737)"
    echo ""
}

# Main execution
main() {
    # Create logs directory
    mkdir -p logs
    
    # Check token
    if ! check_token; then
        echo ""
        read -p "Do you want to fetch a fresh token? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            fetch_token
        else
            echo "⚠️  WARNING: System may not work without a valid token!"
            read -p "Continue anyway? (y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo "Exiting..."
                exit 1
            fi
        fi
    fi
    
    # Clear ports before starting
    clear_ports
    
    # Start services
    start_docker
    start_backend
    start_frontend
    
    # Verify
    sleep 3
    verify_system
    
    # Show URLs
    show_urls
    
    # Open browser
    echo "🌐 Opening dashboard in browser..."
    if command -v open &> /dev/null; then
        open http://localhost:3737
    elif command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:3737
    fi
}

# Run main
main
