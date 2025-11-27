# 🔴 ENGINE INDICATOR STATUS - TROUBLESHOOTING

**Date**: November 20, 2025 @ 1:50 PM IST

---

## 🔴 **CURRENT ISSUE**

**Symptom**: ENGINE indicator blinks red on dashboard  
**Root Cause**: Trading system not fully initialized

---

## 📊 **HEALTH CHECK RESULTS**

```json
{
    "status": "healthy",
    "mode": "paper",
    "trading_active": false,  ← ❌ Should be true
    "loops_alive": true,      ← ✅ Working
    "last_heartbeat_seconds": 29  ← ✅ Fresh
}
```

**Analysis**:
- ✅ System is running
- ✅ Heartbeat is working (loops alive)
- ❌ Trading is not active (`trading_active: false`)

---

## 🔍 **ROOT CAUSE ANALYSIS**

### **Why is `trading_active: false`?**

From `/api/health` logic:
```python
trading_active = trading_system.is_running and loops_alive
```

**Current State**:
- `is_running`: **FALSE** ← This is the problem!
- `loops_alive`: **TRUE**

### **Why is `is_running: false`?**

The `is_running` flag is set to `True` in `TradingSystem.start()`, **BUT**:

Components not initialized:
- `market_data`: **None**
- `risk_manager`: **None**
- `performance_aggregator`: **None**

This means the system is in **degraded mode** (dashboard only, no trading).

---

## 🚨 **WHY ARE COMPONENTS NOT INITIALIZED?**

The `initialize()` method has two paths:

1. **Full Mode** (with Upstox token) ✅ Trading enabled
2. **Degraded Mode** (no token) ❌ Dashboard only

**Most Likely**: System is starting in degraded mode because:
- No Upstox token found
- OR token expired
- OR failed to connect to Upstox API

---

## ✅ **SOLUTION**

### **Option 1: Authenticate with Upstox** (Required for live trading)

```bash
cd /Users/srbhandary/Documents/Projects/srb-algo
python3 upstox_auth_working.py
```

This will:
1. Open browser for Upstox login
2. Get access token
3. Save to `data/upstox_token.txt`
4. Restart trading engine

### **Option 2: Force Start Trading** (If token already exists)

```bash
curl -X POST http://localhost:8000/api/trading/start
```

Then restart:
```bash
docker restart trading_engine
```

---

## 📋 **VERIFICATION STEPS**

### **Step 1: Check Token**
```bash
cat data/upstox_token.txt
```

**Expected**: Long alphanumeric string  
**If empty/missing**: Run `upstox_auth_working.py`

### **Step 2: Check System Status**
```bash
curl http://localhost:8000/api/health | python3 -m json.tool
```

**Expected**:
```json
{
    "trading_active": true,  ← Should be true
    "loops_alive": true
}
```

### **Step 3: Check Logs**
```bash
docker logs trading_engine --tail 50 | grep "Trading System Started"
```

**Expected**: See "📈 Trading System Started"

---

## 🎯 **EXPECTED BEHAVIOR AFTER FIX**

### **Health Check**
```json
{
    "status": "healthy",
    "mode": "paper",
    "trading_active": true,   ✅ GREEN
    "loops_alive": true,      ✅ GREEN
    "last_heartbeat_seconds": 5
}
```

### **Dashboard**
- ENGINE indicator: 🟢 **SOLID GREEN**
- Trading loops: **ACTIVE**
- Strategies: **GENERATING SIGNALS**

---

## 📝 **SUMMARY**

| Component | Status | Notes |
|-----------|--------|-------|
| **Docker Container** | ✅ Running | `trading_engine` up |
| **Database** | ✅ Connected | PostgreSQL operational |
| **Heartbeat** | ✅ Working | Loops are alive |
| **Trading Loops** | ✅ Working | Background tasks running |
| **Components Init** | ❌ Failed | market_data, risk_manager = None |
| **Upstox Token** | ❓ Unknown | Need to verify |
| **is_running Flag** | ❌ False | System in degraded mode |

---

## 🔧 **NEXT ACTIONS**

1. **Check if token exists**: `cat data/upstox_token.txt`
2. **If no token**: Run `python3 upstox_auth_working.py`
3. **If token exists**: Restart engine `docker restart trading_engine`
4. **Verify**: `curl http://localhost:8000/api/health`

---

**Status**: 🔴 **DEGRADED MODE** - Dashboard works, trading disabled  
**Fix**: Authenticate with Upstox OR restart with valid token

---

*Generated: November 20, 2025 @ 1:50 PM IST*
