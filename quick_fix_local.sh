#!/bin/bash

echo "🚀 Quick Fix - Running Locally (Skip Docker)"
echo "════════════════════════════════════════════════"
echo ""

# 1. Stop Docker containers
echo "1️⃣ Stopping Docker containers..."
docker-compose down 2>/dev/null || true

# 2. Install PyTorch locally (fast)
echo ""
echo "2️⃣ Installing PyTorch locally..."
pip install --quiet torch==2.1.0 --index-url https://download.pytorch.org/whl/cpu
pip install --quiet pytorch-forecasting==1.0.0

# 3. Restart system locally
echo ""
echo "3️⃣ Restarting system locally..."
pkill -f "python.*backend.main" 2>/dev/null || true
sleep 2

# Start backend
nohup python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload > data/logs/backend_$(date +%Y%m%d).log 2>&1 &
echo "✅ Backend started on port 8000"

sleep 3

# 4. Verify
echo ""
echo "4️⃣ Verifying..."
python -c "import torch; print(f'✅ PyTorch {torch.__version__}')"

echo ""
echo "════════════════════════════════════════════════"
echo "✅ System running locally"
echo ""
echo "📊 Dashboard: http://localhost:3000"
echo "🔍 Logs: tail -f data/logs/backend_*.log"
echo ""
