# EOD Exit Fix - IST Timezone Issue

## Problem Identified ⚠️

**Issue:** Open trades were not being closed at 3:29 PM IST as expected.

**Root Cause:** The `should_exit_eod()` method in `backend/execution/risk_manager.py` was using `datetime.now()` without timezone specification, which defaults to the system's local time (UTC in Docker containers).

### Timeline Example:
- **Expected:** Close positions at 3:29 PM IST (15:29 IST)
- **Actual:** System time at 3:29 PM IST = 10:00 AM UTC
- **Result:** EOD condition `now.hour >= 15 and now.minute >= 29` never triggered

---

## Fix Applied ✅

### Changes Made:

**File:** `backend/execution/risk_manager.py`

1. **Added IST timezone import:**
```python
from zoneinfo import ZoneInfo
```

2. **Fixed `should_exit_eod()` method:**
```python
def should_exit_eod(self) -> bool:
    # Use IST timezone for accurate market hours
    IST = ZoneInfo("Asia/Kolkata")
    now = datetime.now(IST)
    current_time = now.time()
    
    # Exit all positions after 3:29 PM IST to avoid expiry risk
    eod_exit_time = time(15, 29)  # 3:29 PM
    
    if current_time >= eod_exit_time:
        logger.info(f"EOD exit triggered at {current_time.strftime('%H:%M:%S')} IST - closing all positions")
        return True
    return False
```

3. **Fixed `calculate_intraday_runway()` method:**
```python
def calculate_intraday_runway(self) -> float:
    # Use IST timezone for accurate market hours
    IST = ZoneInfo("Asia/Kolkata")
    now = datetime.now(IST).time()
    # ... rest of logic
```

---

## Testing Recommendations

### 1. Verify EOD Exit Time
```bash
# Check logs around 3:29 PM IST
docker logs trading_engine | grep "EOD exit triggered"
```

**Expected Output:**
```
EOD exit triggered at 15:29:XX IST - closing all positions
⚠️ EOD exit triggered - closing all positions
```

### 2. Manual Test (Before Market Close)
```python
# In Python shell (around 3:28 PM IST)
from backend.execution.risk_manager import RiskManager
from backend.core.config import config

risk_mgr = RiskManager(config.get('risk'))
print(risk_mgr.should_exit_eod())  # Should return False

# Wait until 3:29 PM IST
print(risk_mgr.should_exit_eod())  # Should return True
```

### 3. Check Current IST Time
```bash
# Verify system is using correct timezone
docker exec trading_engine python -c "from datetime import datetime; from zoneinfo import ZoneInfo; print(datetime.now(ZoneInfo('Asia/Kolkata')))"
```

---

## Impact

### Before Fix:
- ❌ Positions remained open past 3:29 PM IST
- ❌ Exposed to overnight risk
- ❌ Potential expiry-day losses
- ❌ Manual intervention required to close positions

### After Fix:
- ✅ Positions automatically close at 3:29 PM IST
- ✅ Proper risk management at EOD
- ✅ No overnight exposure
- ✅ Accurate intraday runway calculations

---

## Related Methods Fixed

Both time-sensitive methods now use IST timezone:

1. **`should_exit_eod()`** - EOD exit trigger (3:29 PM IST)
2. **`calculate_intraday_runway()`** - Loss budget calculation based on time of day

---

## Monitoring

Add this to your daily checklist:

1. **Check EOD Exit Logs:**
   ```bash
   # Should see this every trading day at 3:29 PM IST
   docker logs --since 3:25PM trading_engine | grep "EOD exit"
   ```

2. **Verify No Open Positions After 3:30 PM:**
   ```bash
   curl http://localhost:8000/api/dashboard/open-positions
   # Should return empty array after 3:30 PM IST
   ```

3. **Check Closed Trades:**
   ```bash
   # Verify positions closed at 3:29 PM
   curl http://localhost:8000/api/trades/history?date=$(date +%Y-%m-%d)
   # Look for exit_type: "EOD" with exit_time around 15:29 IST
   ```

---

## Prevention

To prevent similar timezone issues in the future:

1. **Always use IST for market operations:**
   ```python
   from zoneinfo import ZoneInfo
   IST = ZoneInfo("Asia/Kolkata")
   now = datetime.now(IST)
   ```

2. **Never use bare `datetime.now()` for market logic**

3. **Add timezone tests:**
   - Verify EOD exit at 3:29 PM IST
   - Test intraday calculations across different times
   - Validate market open/close logic

---

## Next Steps

1. **Restart Backend:**
   ```bash
   docker-compose restart trading_engine
   ```

2. **Monitor Tomorrow:**
   - Watch logs at 3:29 PM IST
   - Verify all positions close automatically
   - Check dashboard shows "EOD" as exit reason

3. **If Issues Persist:**
   - Check Docker container timezone: `docker exec trading_engine date`
   - Verify Python timezone support: `docker exec trading_engine python -c "from zoneinfo import ZoneInfo; print(ZoneInfo('Asia/Kolkata'))"`
   - Review logs for any errors

---

## Status: ✅ Fixed

**Date:** November 19, 2025, 11:22 PM IST  
**Issue:** EOD exit not triggering at correct IST time  
**Resolution:** Added proper IST timezone handling to time-sensitive methods  
**Action Required:** Restart backend to apply changes
