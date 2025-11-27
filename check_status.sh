#!/bin/bash

# Quick command to check token status and system health

echo "═══════════════════════════════════════════════════════════"
echo "🔍 Trading System Status Check"
echo "═══════════════════════════════════════════════════════════"
echo ""

# 1. Token Status
echo "1️⃣  Upstox Token Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "$HOME/Algo/upstoxtoken.json" ]; then
    TOKEN_AGE=$(python3 -c "
import json, time
with open('$HOME/Algo/upstoxtoken.json') as f:
    data = json.load(f)
    age_hours = (time.time() - data.get('created_at', 0)) / 3600
    print(f'{age_hours:.1f}')
")
    
    if (( $(echo "$TOKEN_AGE < 24" | bc -l) )); then
        echo "✅ Token is VALID (age: ${TOKEN_AGE}h)"
    else
        echo "❌ Token is EXPIRED (age: ${TOKEN_AGE}h)"
        echo "   Run: python3 upstox_auth_working.py"
    fi
else
    echo "❌ Token not found at ~/Algo/upstoxtoken.json"
    echo "   Run: python3 upstox_auth_working.py"
fi
echo ""

# 2. Docker Services
echo "2️⃣  Docker Services"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if docker ps | grep -q "trading_db"; then
    echo "✅ PostgreSQL: Running"
else
    echo "❌ PostgreSQL: Not running"
    echo "   Run: docker-compose up -d postgres"
fi

if docker ps | grep -q "trading_redis"; then
    echo "✅ Redis: Running"
else
    echo "❌ Redis: Not running"
    echo "   Run: docker-compose up -d redis"
fi
echo ""

# 3. Backend Service
echo "3️⃣  Backend Service (Port 8000)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    if curl -s http://localhost:8000/api/health | grep -q "healthy"; then
        echo "✅ Backend: Running and healthy"
    else
        echo "⚠️  Backend: Running but not responding correctly"
    fi
else
    echo "❌ Backend: Not running"
    echo "   Run: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"
fi
echo ""

# 4. Frontend Service
echo "4️⃣  Frontend Service (Port 3000)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "✅ Frontend: Running"
else
    echo "❌ Frontend: Not running"
    echo "   Run: cd frontend/dashboard && python3 -m http.server 3000"
fi
echo ""

# 5. Database Check
echo "5️⃣  Database Records"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if docker ps | grep -q "trading_db"; then
    TRADE_COUNT=$(docker exec trading_db psql -U trading_user -d trading_db -t -c "SELECT COUNT(*) FROM trades;" 2>/dev/null | xargs)
    if [ -n "$TRADE_COUNT" ]; then
        echo "✅ Trades in database: $TRADE_COUNT"
    else
        echo "⚠️  Could not query trades table (might not exist yet)"
    fi
else
    echo "❌ Cannot check database (PostgreSQL not running)"
fi
echo ""

# 6. API Endpoints
echo "6️⃣  API Endpoints Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    # Test /api/health
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "✅ /api/health - OK"
    else
        echo "❌ /api/health - FAIL"
    fi
    
    # Test /metrics
    if curl -s http://localhost:8000/metrics | grep -q "trades_total"; then
        echo "✅ /metrics - OK (Prometheus metrics active)"
    else
        echo "⚠️  /metrics - No trade metrics yet"
    fi
    
    # Test /api/trades/history
    if curl -s http://localhost:8000/api/trades/history > /dev/null 2>&1; then
        echo "✅ /api/trades/history - OK"
    else
        echo "❌ /api/trades/history - FAIL"
    fi
else
    echo "❌ Backend not running - cannot test endpoints"
fi
echo ""

# Summary
echo "═══════════════════════════════════════════════════════════"
echo "📊 Quick Links"
echo "═══════════════════════════════════════════════════════════"
echo "Dashboard:  http://localhost:3000"
echo "API Docs:   http://localhost:8000/docs"
echo "Health:     http://localhost:8000/api/health"
echo "Metrics:    http://localhost:8000/metrics"
echo "Trades:     http://localhost:8000/api/trades/history"
echo ""
echo "🚀 To launch everything: ./launch_system.sh"
echo ""
