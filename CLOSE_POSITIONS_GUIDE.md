# How to Close Open Positions - Step by Step

## Current Situation
- 3 NIFTY 26000 CE positions still open
- Market closed 8+ hours ago at 3:30 PM IST
- Unrealized profit: ₹4,524.75
- Need to close positions and restart backend with timezone fixes

---

## Method 1: Via Emergency API (RECOMMENDED) ⚡

**Prerequisites:** Backend must be running

### Step 1: Check if backend is running
```bash
curl -s http://localhost:8000/api/dashboard/risk-metrics > /dev/null && echo "✓ Backend is running" || echo "✗ Backend is NOT running"
```

### Step 2: If not running, start it
```bash
cd /Users/srbhandary/Documents/Projects/srb-algo
./start.sh
sleep 5  # Wait for backend to initialize
```

### Step 3: Run the close script
```bash
chmod +x close_via_api.sh
./close_via_api.sh
```

**What it does:**
1. Checks backend is running
2. Shows you the open positions
3. Asks for confirmation
4. Closes all positions via emergency API
5. Verifies closure

---

## Method 2: Direct ORM Access 🐍

**Use this if:** Backend is running but API method fails

```bash
cd /Users/srbhandary/Documents/Projects/srb-algo
python3 close_positions_orm.py
```

**What it does:**
1. Uses backend's database connection directly
2. Works with PostgreSQL or any configured database
3. Creates proper trade records
4. Deletes position records

---

## Method 3: Manual via curl 📡

**Direct API call - fastest if you know backend is running**

```bash
curl -X POST http://localhost:8000/emergency/positions/close \
  -H "Content-Type: application/json" \
  -H "x-api-key: EMERGENCY_KEY_123" \
  -d '{
    "close_all": true,
    "reason": "Manual EOD closure - market closed at 3:30 PM IST"
  }'
```

**Verify closure:**
```bash
curl -s http://localhost:8000/api/dashboard/open-positions | jq '.data.positions | length'
# Should return: 0
```

---

## Method 4: Via Dashboard UI 🖥️

1. Open browser: http://localhost:8000/dashboard/
2. Navigate to Emergency Controls
3. Click "Close All Positions"
4. Enter emergency password: `OVERRIDE123`
5. Confirm closure

---

## Troubleshooting

### Error: "Backend not running"

**Solution:** Start the backend first
```bash
cd /Users/srbhandary/Documents/Projects/srb-algo
./start.sh

# Wait 5-10 seconds for initialization
sleep 10

# Then try closing positions again
```

### Error: "Connection refused" or "Cannot connect to database"

**Check logs:**
```bash
tail -50 backend/logs/trading.log
```

**Common issues:**
1. Database not started
2. Wrong database credentials
3. Port already in use

**Quick fix:** Restart backend
```bash
./stop.sh
sleep 3
./start.sh
```

### Error: "Invalid API key"

The emergency API key is defined in `backend/api/emergency_controls.py`

**Default key:** `EMERGENCY_KEY_123`

If changed, update the curl command with the new key.

---

## After Closing Positions

### Step 1: Verify Positions Closed
```bash
curl -s http://localhost:8000/api/dashboard/open-positions | jq '.'
```

**Expected:**
```json
{
  "status": "success",
  "data": {
    "positions": [],
    "totals": {
      "count": 0,
      ...
    }
  }
}
```

### Step 2: Check Closed Trades
```bash
curl -s http://localhost:8000/api/dashboard/trades/recent?today_only=false&limit=5 | jq '.data.trades[] | {symbol, strike_price, net_pnl, exit_time, exit_reason}'
```

**Should show:** The 3 NIFTY positions with `exit_reason: "MANUAL"`

### Step 3: Restart Backend with Timezone Fixes
```bash
cd /Users/srbhandary/Documents/Projects/srb-algo
./stop.sh
sleep 3
./start.sh
```

### Step 4: Verify Timezone Fixes Applied
```bash
# Check timestamp is in IST (should show +05:30)
curl -s http://localhost:8000/api/dashboard/risk-metrics | jq '.data.timestamp'
```

**Expected:** `"2025-11-19T23:55:00+05:30"` (or current IST time)

---

## If All Methods Fail

### Last Resort: Stop trading, restart fresh

```bash
# Stop backend
./stop.sh

# Backup database (if PostgreSQL)
pg_dump -U trading_user trading_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Check for any stuck processes
ps aux | grep python | grep backend
# Kill any stuck processes if found

# Start fresh
./start.sh

# Positions should be reloaded from database
# Try closing via API again
```

---

## Understanding Your Database Setup

### Check what database you're using:

```bash
# Look at config
grep -A 5 "database:" config/config.yaml

# Or check environment variables
env | grep DB_
```

**Common setups:**
1. **PostgreSQL** (Production) - Requires PostgreSQL server running
2. **SQLite** (Development) - File-based, simpler
3. **TimescaleDB** (Advanced) - PostgreSQL extension for time-series

---

## Quick Decision Tree

```
Is backend running?
├─ NO → Start it: ./start.sh → Try Method 1
└─ YES
   ├─ Can you access dashboard? (http://localhost:8000/dashboard/)
   │  ├─ YES → Use Method 4 (Dashboard UI)
   │  └─ NO → Check logs: tail backend/logs/trading.log
   │
   └─ Try methods in order: 1 → 2 → 3
```

---

## Success Criteria

After closing positions, you should have:
- ✅ 0 open positions
- ✅ 3 new closed trades in trade history
- ✅ Total P&L recorded (~₹4,524)
- ✅ Backend running with timezone fixes
- ✅ IST timestamps in all API responses

---

## Tomorrow's Verification

**Critical test at 3:29 PM IST:**

```bash
# Watch logs (start this at 3:28 PM)
tail -f backend/logs/trading.log | grep -i "eod\|exit"
```

**Expected at 3:29 PM IST:**
```
EOD exit triggered at 15:29:XX IST - closing all positions
⚠️ EOD exit triggered - closing all positions
```

**Verify at 3:31 PM IST:**
```bash
curl http://localhost:8000/api/dashboard/open-positions | jq '.data.positions | length'
# Must be: 0
```

---

## Support Files Created

1. **close_via_api.sh** - Automated API-based closure (Method 1)
2. **close_positions_orm.py** - Direct database closure (Method 2)  
3. **COMPREHENSIVE_TIMEZONE_FIXES.md** - Technical details of timezone fixes
4. **CLOSE_POSITIONS_AND_RESTART.md** - Original quick guide

---

**Start with Method 1 (close_via_api.sh) - it's the safest and most reliable.**
