#!/bin/bash

# Verification Script - Checks if all fixes are working

echo "════════════════════════════════════════════════════════════"
echo "🔍 Verifying Trading System Setup"
echo "════════════════════════════════════════════════════════════"
echo ""

# Check if running in Docker or local
if command -v docker &> /dev/null && docker ps | grep -q trading_engine; then
    echo "✅ Running in Docker mode"
    DOCKER_MODE=true
    PYTHON_CMD="docker exec trading_engine python"
else
    echo "✅ Running in local mode"
    DOCKER_MODE=false
    PYTHON_CMD="python"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "1️⃣  Checking PyTorch Installation"
echo "─────────────────────────────────────────────────────────────"

if $PYTHON_CMD -c "import torch; print(f'✅ PyTorch {torch.__version__} installed')" 2>/dev/null; then
    echo "✅ PyTorch OK"
else
    echo "❌ PyTorch NOT installed"
    echo "   Fix: pip install torch==2.1.0 --index-url https://download.pytorch.org/whl/cpu"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "2️⃣  Checking pytorch-forecasting"
echo "─────────────────────────────────────────────────────────────"

if $PYTHON_CMD -c "import pytorch_forecasting; print('✅ pytorch-forecasting installed')" 2>/dev/null; then
    echo "✅ pytorch-forecasting OK"
else
    echo "⚠️  pytorch-forecasting NOT installed (optional for TFT models)"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "3️⃣  Checking Config - SAC Controller"
echo "─────────────────────────────────────────────────────────────"

if grep -q "sac_meta_controller:" config/config.yaml && grep -A 1 "sac_meta_controller:" config/config.yaml | grep -q "enabled: true"; then
    echo "✅ SAC Meta-Controller enabled"
else
    echo "❌ SAC Meta-Controller NOT enabled"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "4️⃣  Checking Config - Active Strategies"
echo "─────────────────────────────────────────────────────────────"

STRATEGIES=$(grep -A 2 "quantum_edge:\|gamma_scalping:\|vwap_deviation:\|iv_rank_trading:" config/config.yaml | grep "enabled: true" | wc -l)
echo "✅ Found $STRATEGIES active strategies (expected: 5-6)"

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "5️⃣  Checking Recent Logs - Strategy Resolution"
echo "─────────────────────────────────────────────────────────────"

if [ -f "data/logs/trading_$(date +%Y%m%d).log" ]; then
    STRATEGY_LOGS=$(grep "Strategy resolved" data/logs/trading_$(date +%Y%m%d).log 2>/dev/null | wc -l)
    if [ "$STRATEGY_LOGS" -gt 0 ]; then
        echo "✅ Found $STRATEGY_LOGS strategy resolution logs"
        echo ""
        echo "Recent strategy resolutions:"
        grep "Strategy resolved" data/logs/trading_$(date +%Y%m%d).log 2>/dev/null | tail -3
    else
        echo "⚠️  No strategy resolution logs yet (system may not have executed trades)"
    fi
else
    echo "⚠️  No log file for today"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "6️⃣  Checking Token Status"
echo "─────────────────────────────────────────────────────────────"

if [ -f "config/upstox_token.json" ]; then
    TOKEN_AGE=$(python3 -c "
import json, datetime
try:
    with open('config/upstox_token.json') as f:
        data = json.load(f)
    created = datetime.datetime.fromtimestamp(data.get('created_at', 0))
    now = datetime.datetime.now()
    hours_old = (now - created).total_seconds() / 3600
    print(f'{hours_old:.1f}h old')
except:
    print('unknown')
" 2>/dev/null)
    echo "✅ Token file exists ($TOKEN_AGE)"
else
    echo "❌ Token file missing"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "7️⃣  Checking API Endpoint"
echo "─────────────────────────────────────────────────────────────"

if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "✅ Backend API responding on port 8000"
else
    echo "❌ Backend API not responding (is system running?)"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "8️⃣  Checking Dashboard"
echo "─────────────────────────────────────────────────────────────"

if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Dashboard accessible on port 3000"
else
    echo "⚠️  Dashboard not accessible (may be served by backend on port 8000)"
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ Verification Complete"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "📊 Summary:"
echo "   - PyTorch: Check above"
echo "   - SAC Controller: Check above"
echo "   - Strategies: $STRATEGIES active"
echo "   - Token: Check above"
echo ""
echo "🚀 Next steps:"
echo "   1. Restart system if needed: ./launch_system.sh"
echo "   2. Monitor logs: tail -f data/logs/trading_*.log"
echo "   3. Open dashboard: http://localhost:3000"
echo ""
