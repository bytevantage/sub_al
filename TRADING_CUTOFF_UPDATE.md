# Trading Cutoff Time Update - 3:25 PM IST

## Summary
Successfully updated the trading system to stop ALL trading activities at 3:25 PM IST instead of 3:30 PM IST.

## Changes Made

### 1. Core Trading Loop (backend/main.py)
- Updated market close time from 15:30 to 15:25 in trading_loop
- Added market hours check to market_data_loop with 5-minute sleep after 3:25 PM
- Updated _calculate_optimal_interval to use 15:25 as close time

### 2. Timezone Utilities (backend/core/timezone_utils.py)
- Updated is_market_hours() to close at 15:25
- Updated is_after_market_close() to trigger at 15:25
- Updated should_exit_eod() to trigger at 15:25
- Updated market_close_time() and eod_exit_time() functions

### 3. Production Locks (backend/config/production_locks.py)
- Updated market_close_time from 15:30 to 15:25
- force_eod_exit_time already correctly set to 15:25

### 4. API Endpoints
- emergency_controls.py: Updated comment to reflect 3:25 PM
- market_data.py: Updated is_market_open() to close at 15:25
- production_lock_simple.py: Updated market_close_time to "15:25"

### 5. Risk Management
- risk_manager.py: Updated trading session duration from 375 to 370 minutes
- market_monitor.py: Updated market hours check to 15:25

### 6. Monitoring & Health Checks
- Health monitor continues to work and detects trading loop is paused after 3:25 PM
- Emergency position closure still works if positions remain open after EOD

## Verification
- Created test_trading_cutoff.py to verify correct behavior
- All tests pass:
  - 3:24 PM: Trading allowed ✅
  - 3:25 PM: Trading stops ✅
  - 3:26 PM: Trading stopped ✅
  - 3:30 PM: Trading stopped ✅

## Current Status
- Trading loop correctly pauses at 3:25 PM IST
- Market data updates stop after 3:25 PM (5-minute intervals)
- EOD exit triggers at 3:25 PM to close positions
- Health monitor detects system is paused after market close
- No new trades will be placed after 3:25 PM

## Files Modified
1. backend/main.py
2. backend/core/timezone_utils.py
3. backend/config/production_locks.py
4. backend/api/emergency_controls.py
5. backend/api/market_data.py
6. backend/api/production_lock_simple.py
7. backend/execution/risk_manager.py
8. backend/safety/market_monitor.py

The system now fully complies with the requirement: **NO TRADING AFTER 3:25 PM IST**.
