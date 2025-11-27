#!/bin/bash

echo "🔧 Complete System Restart Script"
echo "=================================="
echo ""

# Step 1: Kill Docker if hung
echo "1️⃣  Stopping Docker Desktop..."
killall Docker 2>/dev/null || echo "   Docker not running"
sleep 3

# Step 2: Start Docker
echo ""
echo "2️⃣  Starting Docker Desktop..."
open -a Docker
echo "   ⏳ Waiting for Docker to start (30 seconds)..."
sleep 30

# Step 3: Verify Docker is running
echo ""
echo "3️⃣  Checking Docker status..."
if docker ps > /dev/null 2>&1; then
    echo "   ✅ Docker is running"
else
    echo "   ❌ Docker failed to start"
    echo "   Please manually start Docker Desktop from Applications"
    exit 1
fi

# Step 4: Start trading system
echo ""
echo "4️⃣  Starting trading system..."
cd "$(dirname "$0")"
./start.sh

# Step 5: Verify system
echo ""
echo "5️⃣  Verifying system..."
sleep 10

echo ""
echo "📊 Checking APIs..."

# Health check
if curl -s http://localhost:8000/api/health | grep -q "healthy"; then
    echo "   ✅ API Health: OK"
else
    echo "   ❌ API Health: FAILED"
fi

# Trades check
if curl -s http://localhost:8000/api/trades/today 2>&1 | grep -q -v "error\|Error"; then
    echo "   ✅ Trades API: OK"
else
    echo "   ❌ Trades API: FAILED"
fi

# Positions check
if curl -s http://localhost:8000/api/positions 2>&1 | grep -q -v "Internal Server Error"; then
    echo "   ✅ Positions API: OK"
else
    echo "   ❌ Positions API: FAILED"
fi

echo ""
echo "🎉 System restart complete!"
echo ""
echo "📊 Dashboard: http://localhost:8000/dashboard/"
echo "📝 Logs: docker logs -f trading_engine"
echo ""
echo "See FIX_ALL_ISSUES.md for detailed verification"
