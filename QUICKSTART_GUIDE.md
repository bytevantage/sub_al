# Trading System Quick Start Guide

**Date**: November 12, 2025

## 🚀 Quick Launch Steps

### Step 1: Fetch Fresh Upstox Token

**Option A: Using Python Script (Recommended)**
```bash
# Run the authentication script
python upstox_auth_working.py
```

This will:
1. Open browser to Upstox authorization page
2. Login with your Upstox credentials
3. Automatically save token to `~/Algo/upstoxtoken.json`
4. Create backup at `~/Algo/upstoxtoken_backup.json`

**Option B: Manual Token Placement**
```bash
# If you already have a token, place it at:
~/Algo/upstoxtoken.json

# Or in project directory:
config/upstox_token.json
```

**Token Format** (JSON):
```json
{
  "access_token": "eyJ0eXAi...",
  "token_type": "Bearer",
  "expires_in": 86400,
  "created_at": 1699776000
}
```

---

### Step 2: Start the System

**Option A: Docker Compose (Full Stack)**
```bash
# Start all services (database, redis, backend, frontend, monitoring)
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

**Option B: Local Development**
```bash
# Terminal 1: Start PostgreSQL & Redis
docker-compose up -d postgres redis

# Terminal 2: Start Backend
cd /Users/srbhandary/Documents/Projects/srb-algo
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 3: Start Frontend Dashboard
cd frontend/dashboard
python -m http.server 3000
```

---

### Step 3: Access Dashboard

**Dashboard URL**: http://localhost:3000 (or http://localhost:80 if using nginx)

**Available Endpoints**:
- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health
- **Metrics**: http://localhost:8000/metrics
- **Grafana**: http://localhost:3001 (user: admin, pass: admin)

---

### Step 4: Verify System

**Check 1: Health Endpoint**
```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "mode": "paper",
  "trading_active": true
}
```

**Check 2: Metrics Endpoint**
```bash
curl http://localhost:8000/metrics
```

Should show Prometheus metrics with incrementing counters:
```
# HELP trades_total Total number of trades
# TYPE trades_total counter
trades_total{strategy="pcr_analysis",side="BUY",status="closed"} 5.0
```

**Check 3: Database Records**
```bash
# Connect to PostgreSQL
docker exec -it trading_db psql -U trading_user -d trading_db

# Check trades table
SELECT trade_id, symbol, entry_time, net_pnl, strategy_name 
FROM trades 
ORDER BY entry_time DESC 
LIMIT 10;

# Check daily performance
SELECT date, total_trades, net_pnl, win_rate 
FROM daily_performance 
ORDER BY date DESC 
LIMIT 7;

# Exit psql
\q
```

**Check 4: API Trade History**
```bash
curl http://localhost:8000/api/trades/history
```

---

## 📊 Dashboard Features

### Main Dashboard Sections

1. **Circuit Breaker Status**
   - Shows if trading is active or halted
   - Emergency stop button (requires password)
   - Reset circuit breaker option

2. **Market Condition**
   - Current NIFTY/BANKNIFTY levels
   - VIX and PCR values
   - Market trend indicators

3. **Daily P&L**
   - Today's profit/loss
   - Total trades count
   - Win rate percentage

4. **Open Positions**
   - Live positions with P&L
   - Close all positions button
   - Individual position management

5. **Risk Metrics**
   - Current drawdown
   - Position sizing
   - Strategy allocation
   - Circuit breaker triggers

6. **Data Quality Monitor**
   - Feed health status
   - Stale data warnings
   - API response times

7. **Manual Controls**
   - Place manual orders
   - Enable override mode
   - View system logs

8. **P&L Curve Chart**
   - Intraday profit/loss graph
   - Real-time updates via WebSocket

---

## 🔧 Troubleshooting

### Token Issues

**Problem**: "Failed to load Upstox token"

**Solution**:
```bash
# Check if token file exists
ls -la ~/Algo/upstoxtoken.json

# If missing, run auth script
python upstox_auth_working.py

# Verify token format
cat ~/Algo/upstoxtoken.json | python -m json.tool
```

### Database Connection Issues

**Problem**: Backend can't connect to PostgreSQL

**Solution**:
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Start PostgreSQL
docker-compose up -d postgres

# Test connection
docker exec -it trading_db psql -U trading_user -d trading_db -c "SELECT 1;"

# Check logs
docker-compose logs postgres
```

### Frontend Not Loading

**Problem**: Dashboard shows blank page or connection error

**Solution**:
```bash
# Check if backend is running
curl http://localhost:8000/api/health

# If backend is down, restart
docker-compose restart trading-engine

# Or run locally
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Check frontend files
ls -la frontend/dashboard/

# Serve frontend locally
cd frontend/dashboard
python -m http.server 3000
```

### WebSocket Connection Failing

**Problem**: Dashboard shows "Connecting..." status

**Solution**:
```bash
# Check WebSocket endpoint
wscat -c ws://localhost:8000/ws

# If wscat not installed:
npm install -g wscat

# Check backend logs for WebSocket errors
docker-compose logs trading-engine | grep -i websocket
```

### No Trades in Database

**Problem**: Empty trades table after running system

**Solution**:
```bash
# Check if trading is active
curl http://localhost:8000/api/health

# Check if signals are being generated
curl http://localhost:8000/api/signals

# Check logs for errors
docker-compose logs trading-engine | grep -i "error\|trade"

# Verify market hours (NSE: 9:15 AM - 3:30 PM IST)
date

# Check if paper trading mode is enabled
grep -i "mode" config/config.yaml
```

---

## 🔐 Security Notes

### Emergency Stop Password

The emergency stop button requires a password. Default: `emergency123`

To change:
```python
# In frontend/dashboard/dashboard.js
function executeEmergencyStop() {
    const password = document.getElementById('emergency-password').value;
    if (password !== 'YOUR_NEW_PASSWORD') {
        alert('Invalid password');
        return;
    }
    // ...
}
```

### API Access

For production deployment, add authentication:
```python
# In backend/main.py
from fastapi.security import HTTPBearer
from fastapi import Depends, HTTPException

security = HTTPBearer()

async def verify_token(credentials = Depends(security)):
    if credentials.credentials != "your-api-key":
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials

@app.get("/api/protected", dependencies=[Depends(verify_token)])
async def protected_route():
    return {"message": "Authorized"}
```

---

## 📈 Monitoring Setup

### Prometheus Metrics

Access Prometheus: http://localhost:9090

**Key Metrics to Monitor**:
- `trades_total` - Total trades by strategy
- `pnl_total` - Cumulative P&L
- `signal_strength_avg` - Average signal quality
- `circuit_breaker_triggers` - Number of halts
- `api_response_time_seconds` - API latency

**Sample Queries**:
```promql
# Trades per hour
rate(trades_total[1h])

# Average P&L per strategy
avg by (strategy) (pnl_total)

# Win rate percentage
(winning_trades / total_trades) * 100
```

### Grafana Dashboards

Access Grafana: http://localhost:3001 (admin/admin)

**Import Dashboard**:
1. Click "+" → Import
2. Upload `monitoring/grafana/trading_dashboard.json`
3. Select Prometheus as data source

---

## 🚦 Running in Production

### Pre-Production Checklist

- [ ] Fresh Upstox token fetched and validated
- [ ] Database migrations applied
- [ ] Regression tests passed
- [ ] Data quality monitors active
- [ ] Circuit breaker thresholds configured
- [ ] Emergency stop procedure documented
- [ ] Monitoring alerts configured
- [ ] Backup strategy in place

### Production Deployment

```bash
# 1. Build production images
docker-compose -f docker-compose.prod.yml build

# 2. Run migrations
docker-compose -f docker-compose.prod.yml run backend alembic upgrade head

# 3. Start services
docker-compose -f docker-compose.prod.yml up -d

# 4. Verify health
curl https://your-domain.com/api/health

# 5. Monitor logs
docker-compose -f docker-compose.prod.yml logs -f --tail=100
```

### Live Trading Mode

**⚠️ WARNING**: Test thoroughly in paper mode first!

```yaml
# config/config.yaml
mode: live  # Change from 'paper' to 'live'

risk:
  max_daily_loss: 5000  # Set conservative limits
  max_position_size: 50000
  max_positions: 3
```

---

## 📞 Support

### Log Locations
- **Backend**: `logs/trading_system.log`
- **Docker**: `docker-compose logs -f trading-engine`
- **Database**: `docker-compose logs postgres`

### Debug Commands
```bash
# Enable verbose logging
export LOG_LEVEL=DEBUG
uvicorn backend.main:app --reload --log-level debug

# Check all environment variables
docker-compose config

# Test API endpoints
curl -v http://localhost:8000/api/health
curl -v http://localhost:8000/metrics
curl -v http://localhost:8000/api/performance
```

### Common Error Codes
- **500**: Backend error (check logs)
- **503**: Service unavailable (check if backend is running)
- **401**: Authentication failed (check token)
- **404**: Endpoint not found (check API docs)

---

## 📚 Additional Resources

- **API Documentation**: http://localhost:8000/docs
- **Feature Documentation**: See `PRODUCTION_FEATURES_SUMMARY.md`
- **Critical Fixes**: See `CRITICAL_FIXES_SUMMARY.md`
- **Architecture**: See `docs/architecture.md`

---

## ✅ Success Criteria

System is working correctly if:

1. ✅ Health endpoint returns `{"status": "healthy"}`
2. ✅ Metrics endpoint shows incrementing trade counters
3. ✅ PostgreSQL trades table has records
4. ✅ `/api/trades/history` returns data
5. ✅ Dashboard shows live updates
6. ✅ WebSocket connection status shows "Connected"
7. ✅ No critical data quality issues in logs
8. ✅ Daily performance aggregation runs at 6 PM

---

**Last Updated**: November 12, 2025
**System Version**: v1.0.0
