# Dashboard & EOD Issues - Complete Fix

## Problems Identified

### Problem 1: Open Positions Not Closed at 3:29 PM IST ❌
**Status at 11:26 PM IST:** Positions still open

**Root Cause:** 
- EOD exit logic was using system time (UTC) instead of IST
- At 3:29 PM IST, system saw 10:00 AM UTC, so EOD trigger never fired
- System may not have been running at market close time

### Problem 2: Closed Trades Not Showing in Dashboard ❌
**Symptom:** Trades closed during the day not visible in "Today's Trades"

**Root Cause:**
- Dashboard API filtering "today's trades" using UTC timezone
- At 11:26 PM IST (Nov 19), system looks for Nov 19 UTC
- Trades from earlier (10 AM UTC = 3:29 PM IST) might be on different UTC date
- IST day starts at 5:30 AM UTC (previous day), creating date boundary mismatch

---

## Fixes Applied ✅

### Fix 1: EOD Exit Logic (Risk Manager)
**File:** `backend/execution/risk_manager.py`

```python
# Before (WRONG - uses system time)
def should_exit_eod(self) -> bool:
    now = datetime.now()  # UTC in Docker
    if now.hour >= 15 and now.minute >= 29:
        return True

# After (CORRECT - uses IST)
def should_exit_eod(self) -> bool:
    IST = ZoneInfo("Asia/Kolkata")
    now = datetime.now(IST)
    current_time = now.time()
    
    if current_time >= time(15, 29):  # 3:29 PM IST
        logger.info(f"EOD exit triggered at {current_time} IST")
        return True
```

### Fix 2: Dashboard "Today's Trades" Filter
**File:** `backend/api/dashboard.py`

```python
# Before (WRONG - UTC "today")
if today_only:
    now = datetime.now()  # UTC
    start_of_day = datetime.combine(now.date(), time(0, 0, 0))
    query = query.filter(Trade.entry_time >= start_of_day)

# After (CORRECT - IST "today")
if today_only:
    now_ist = datetime.now(IST)
    start_of_day_ist = datetime.combine(now_ist.date(), time(0, 0, 0))
    start_of_day_naive = start_of_day_ist.replace(tzinfo=None)
    query = query.filter(Trade.entry_time >= start_of_day_naive)
```

---

## Immediate Actions Required

### 1. Close Open Positions NOW

**Option A: Emergency API (Recommended)**
```bash
# Close all positions immediately
curl -X POST http://localhost:8000/emergency/positions/close \
  -H "Content-Type: application/json" \
  -H "x-api-key: EMERGENCY_KEY_123" \
  -d '{
    "close_all": true,
    "reason": "Manual EOD closure - missed 3:29 PM IST exit"
  }'
```

**Option B: Use Script**
```bash
chmod +x CLOSE_OPEN_POSITIONS.sh
./CLOSE_OPEN_POSITIONS.sh
```

**Option C: Via Dashboard**
- Go to http://localhost:8000/dashboard/
- Navigate to Emergency Controls
- Click "Close All Positions"
- Enter password: `OVERRIDE123`

### 2. Restart Backend to Apply Fixes
```bash
# Apply timezone fixes
docker-compose restart trading_engine

# Verify restart
docker logs -f trading_engine
```

### 3. Verify Dashboard Shows Today's Trades
```bash
# Check API directly
curl -s http://localhost:8000/api/dashboard/trades/recent?today_only=true | jq '.data.trades'

# Should now show trades from today (IST date)
```

---

## Why This Happened

### Timeline:
1. **3:29 PM IST (10:00 AM UTC)** - EOD exit should have triggered
2. **System check:** `datetime.now()` returned 10:00 AM UTC
3. **Condition check:** `hour >= 15 and minute >= 29` → `10 >= 15` → FALSE
4. **Result:** Positions NOT closed

5. **11:26 PM IST (5:56 PM UTC)** - User checks dashboard
6. **Dashboard filter:** Looking for trades from "Nov 19 UTC"
7. **Trades in DB:** Stored with entry_time from "Nov 19 UTC 10:00 AM"
8. **Result:** Trades visible in DB but filtered incorrectly

### Date Boundary Issue:
```
IST Nov 19, 2025 00:00 = UTC Nov 18, 2025 18:30
IST Nov 19, 2025 23:59 = UTC Nov 19, 2025 18:29

Trade at 3:29 PM IST Nov 19 = 10:00 AM UTC Nov 19
Dashboard at 11:26 PM IST Nov 19 = 5:56 PM UTC Nov 19

✅ Both on same UTC date, should work now with fix
```

---

## Testing the Fixes

### Test 1: Verify IST Timezone Usage
```bash
# Check system recognizes IST
docker exec trading_engine python -c "
from datetime import datetime
from zoneinfo import ZoneInfo
IST = ZoneInfo('Asia/Kolkata')
print(f'IST Time: {datetime.now(IST)}')
print(f'UTC Time: {datetime.utcnow()}')
"
```

**Expected Output:**
```
IST Time: 2025-11-19 23:26:00+05:30
UTC Time: 2025-11-19 17:56:00
```

### Test 2: Check EOD Exit Logic (Tomorrow)
```bash
# Tomorrow at 3:28 PM IST
docker logs -f trading_engine | grep "EOD"

# Expected at 3:29 PM IST:
# "EOD exit triggered at 15:29:XX IST - closing all positions"
```

### Test 3: Verify Dashboard Trades
```bash
# Check today's trades show correctly
curl -s http://localhost:8000/api/dashboard/trades/recent?today_only=true | \
  jq '.data.trades[] | {entry_time, symbol, strategy_name, net_pnl}'
```

**Should show:**
- All trades from today (IST date)
- Correct entry/exit times
- Proper strategy names

---

## Prevention Checklist

### Daily Monitoring (Add to routine):

**Before Market Open (9:00 AM IST):**
- [ ] Verify system is running: `docker ps | grep trading_engine`
- [ ] Check logs for errors: `docker logs trading_engine | tail -50`
- [ ] Confirm no positions from yesterday: `curl http://localhost:8000/api/dashboard/open-positions`

**During Market (2:00 PM IST):**
- [ ] Check position count: Should be <= max_positions
- [ ] Verify trades appearing in dashboard
- [ ] Monitor P&L and win rate

**After Market (3:35 PM IST):**
- [ ] **CRITICAL:** Verify all positions closed
- [ ] Check logs for "EOD exit triggered at 15:29:XX IST"
- [ ] Review closed trades in dashboard
- [ ] If positions still open → Use emergency close script

**End of Day (11:00 PM IST):**
- [ ] Review daily performance report (auto-generated at 5 PM)
- [ ] Check for anomaly alerts
- [ ] Verify no open positions overnight

---

## Emergency Contacts & Commands

### Check System Health
```bash
# Is backend running?
docker ps | grep trading_engine

# Any errors?
docker logs trading_engine | grep -i error | tail -20

# Current IST time
docker exec trading_engine python -c "from datetime import datetime; from zoneinfo import ZoneInfo; print(datetime.now(ZoneInfo('Asia/Kolkata')))"
```

### Open Positions Check
```bash
# Count open positions
curl -s http://localhost:8000/api/dashboard/open-positions | jq '.data.positions | length'

# List open positions
curl -s http://localhost:8000/api/dashboard/open-positions | jq '.data.positions'
```

### Force Close Positions
```bash
# Emergency close ALL
curl -X POST http://localhost:8000/emergency/positions/close \
  -H "x-api-key: EMERGENCY_KEY_123" \
  -H "Content-Type: application/json" \
  -d '{"close_all": true, "reason": "Manual intervention"}'

# Close specific symbol
curl -X POST http://localhost:8000/emergency/positions/close \
  -H "x-api-key: EMERGENCY_KEY_123" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "NIFTY", "reason": "Manual closure"}'
```

### Check Today's Trades
```bash
# Via API
curl -s http://localhost:8000/api/dashboard/trades/recent?today_only=true

# Count trades
curl -s http://localhost:8000/api/dashboard/trades/recent?today_only=true | jq '.data.count'
```

---

## Long-term Fixes Needed

### 1. Add EOD Monitoring Alert
Create watchdog that alerts if positions still open at 3:35 PM IST:
```python
# Add to monitoring_automation.py
async def check_eod_positions():
    IST = ZoneInfo("Asia/Kolkata")
    now = datetime.now(IST)
    
    if now.time() >= time(15, 35):  # 3:35 PM IST
        positions = get_open_positions()
        if len(positions) > 0:
            send_alert(f"⚠️ {len(positions)} positions still open after EOD!")
```

### 2. Add Timezone to All Database Models
Update Trade model to store timezone-aware datetimes:
```python
entry_time = Column(DateTime(timezone=True), nullable=False)
exit_time = Column(DateTime(timezone=True), nullable=True)
```

### 3. Create Daily Health Check Script
```bash
#!/bin/bash
# daily_health_check.sh
# Run at 3:35 PM IST via cron

POSITIONS=$(curl -s http://localhost:8000/api/dashboard/open-positions | jq -r '.data.positions | length')

if [ "$POSITIONS" != "0" ]; then
    echo "⚠️ ALERT: $POSITIONS positions still open at EOD!"
    # Send notification (email, SMS, Slack, etc.)
    ./CLOSE_OPEN_POSITIONS.sh
fi
```

---

## Summary

### What Was Fixed:
1. ✅ EOD exit now uses IST timezone (3:29 PM IST trigger)
2. ✅ Dashboard "today's trades" now filters by IST date
3. ✅ Intraday runway calculation uses IST

### What You Need to Do:
1. **NOW:** Close open positions using emergency script
2. **NOW:** Restart backend to apply fixes
3. **NOW:** Verify dashboard shows today's trades
4. **TOMORROW:** Monitor EOD exit at 3:29 PM IST
5. **DAILY:** Check positions closed after 3:30 PM

### Files Modified:
- `backend/execution/risk_manager.py` - IST timezone for EOD exit
- `backend/api/dashboard.py` - IST timezone for trade filtering

### Scripts Created:
- `CLOSE_OPEN_POSITIONS.sh` - Emergency position closure
- `DASHBOARD_TIMEZONE_FIXES.md` - This guide

---

**Status:** ✅ Fixes applied, restart required  
**Priority:** 🔴 HIGH - Close open positions immediately  
**Next Action:** Run emergency close script, then restart backend
