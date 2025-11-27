# Bug Status Report - 12 Nov 2025

## ✅ FIXED Issues (6/14)

### 1. ✅ detect_reversal Implementation
**Status:** FIXED  
**File:** `backend/strategies/strategy_engine.py`  
**Fix:** Implemented full reversal detection logic with:
- Price movement checks (>2% adverse)
- PCR reversal signals (>1.2 for calls, <0.8 for puts)
- OI build-up detection (>10k change in opposite direction)

**No longer returns False** - now performs actual analysis.

---

### 2. ✅ market_state Initialization
**Status:** FIXED  
**File:** `backend/data/market_data.py` (line 31)  
**Fix:** Added initialization in `__init__`:
```python
self.market_state = {
    'NIFTY': {},
    'SENSEX': {}
}
```
AttributeError resolved.

---

### 3. ✅ Strike Key Consistency
**Status:** FIXED  
**File:** `backend/data/market_data.py`  
**Fix:** Standardized all strike storage to strings:
- `_process_option_chain`: `strike = str(item.get('strike_price'))`
- `_filter_relevant_strikes`: Converts to float for comparison, keeps string keys
- `calculate_greeks`: Uses `strike_str` throughout

---

### 4. ✅ Database Models Present
**Status:** FIXED  
**Files:** 
- `backend/database/models.py` - Trade, DailyPerformance, StrategyPerformance models exist
- `backend/database/database.py` - get_db() dependency implemented
- `backend/database/__init__.py` - Proper exports configured

---

### 5. ✅ Risk Manager Capital Info
**Status:** FIXED  
**File:** `backend/execution/risk_manager.py`  
**Fix:** Added `get_capital_info()` method returning:
- total, used, available capital
- utilization percentage
- daily_pnl, initial_capital

---

### 6. ✅ EOD Exit Logic Enhanced
**Status:** FIXED  
**File:** `backend/execution/risk_manager.py`  
**Fix:** Added `should_exit_eod()` method with corrected logic:
```python
if now.hour >= 15 and now.minute >= 25:
    return True
```
Changed from 15:20 to 15:25 for safer exit timing.

---

## ⚠️ PARTIALLY FIXED (2/14)

### 7. ⚠️ market_state Population
**Status:** PARTIALLY FIXED  
**File:** `backend/data/market_data.py`  
**Current State:**
- market_state initialized ✅
- `calculate_greeks()` reads from `self.market_state[symbol]` (lines 414, 418) ✅
- **ISSUE:** `update_option_chain()` doesn't populate `self.market_state[symbol]`

**What's Missing:**
After fetching option data in `get_instrument_data()`, need to store:
```python
self.market_state[symbol] = {
    'spot_price': spot,
    'option_chain': filtered_chain,
    'pcr': filtered_chain.get('pcr'),
    'vix': vix,
    'timestamp': datetime.now()
}
```

**Impact:** Greeks calculation and strategies will get empty data.

---

### 8. ⚠️ Live MTM Tracking
**Status:** PARTIALLY FIXED  
**File:** `backend/execution/risk_manager.py`  
**Current State:**
- `calculate_live_mtm()` method added ✅
- `update_position_mtm()` method added ✅
- **ISSUE:** No periodic caller in main.py risk monitoring loop

**What's Missing:** In `risk_monitoring_loop()`:
```python
for position in self.risk_manager.open_positions:
    current_price = await self.market_data.get_option_price(position['symbol'], position['strike'])
    self.risk_manager.update_position_mtm(position, current_price)
```

**Impact:** Drawdown checks are blind intra-day.

---

## ❌ NOT FIXED (6/14)

### 9. ❌ Strategy Weight Conflicts
**Status:** NOT FIXED  
**File:** `backend/strategies/strategy_engine.py` (line 60)  
**Issue:** 
```python
self.strategies.append(SupportResistanceStrategy(weight=75))  # Should be 50-59 per README
```
**Expected:** Weight should be 50-59 (Tier 4) per README.  
**Actual:** Weight is 75 (conflicts with Tier 2)

**Impact:** Signal ranking distorted, higher priority than intended.

**Fix Needed:**
```python
self.strategies.append(SupportResistanceStrategy(weight=55))  # Tier 4: 50-59
```

---

### 10. ❌ Option Chain Key Type in Strategies
**Status:** NOT FIXED  
**File:** `backend/strategies/pcr_strategy.py` (line 120)  
**Issue:**
```python
atm_strike = data.get('atm_strike')  # Could be float or string
option_data = option_chain['calls'].get(atm_strike, {})  # Keys are strings now
```

**Problem:** If `atm_strike` is float, lookup fails (keys are strings after fix #3).

**Fix Needed:**
```python
atm_strike = str(data.get('atm_strike'))  # Force to string
option_data = option_chain['calls'].get(atm_strike, {})
```

**Impact:** Returns empty dict, entry_price becomes 0, bogus signals.

---

### 11. ❌ Paper Trading Realism
**Status:** NOT FIXED  
**File:** `backend/execution/order_manager.py` (line 77-82)  
**Issue:**
```python
async def _execute_paper_order(self, order: Dict) -> bool:
    order['status'] = 'filled'
    order['fill_price'] = order['signal'].get('entry_price')  # No slippage
    return True
```

**Missing:**
- Slippage simulation (add 0.5-2% to entry_price)
- Fill delay (random 100-500ms)
- Bid-ask spread consideration

**Impact:** Unrealistic P&L, ML model trained on perfect fills.

---

### 12. ❌ Live Order Guardrails
**Status:** NOT FIXED  
**File:** `backend/execution/order_manager.py` (line 85-115)  
**Issue:**
```python
response = self.upstox_client.place_order(
    order_type='MARKET',  # Always market orders
    # No limit price
    # No spread check
    # No retry logic
)
```

**Missing:**
- Limit price from signal (signal.get('entry_price') * 1.05)
- Spread check (reject if spread > 5%)
- Retry with exponential backoff
- Pre-flight validation

**Impact:** Slippage in live trading, failed orders dropped silently.

---

### 13. ❌ Position Size Division by Zero
**Status:** NOT FIXED  
**File:** `backend/execution/risk_manager.py` (line 72)  
**Issue:**
```python
risk_per_lot = entry_price - stop_loss
if risk_per_lot <= 0:
    return 0  # Returns 0 quantity
```

**Problem:** When stop_loss equals entry_price (common with missing data), function returns 0 instead of using default risk.

**Fix Needed:**
```python
stop_loss = signal.get('stop_loss', entry_price * 0.7)
if stop_loss >= entry_price:
    stop_loss = entry_price * 0.7  # Force 30% stop if invalid
risk_per_lot = entry_price - stop_loss
```

**Impact:** Trades rejected due to 0 quantity.

---

### 14. ❌ BankNifty Symbol Support
**Status:** NOT FIXED  
**File:** `backend/data/market_data.py`  
**Issue:** README advertises BankNifty support, but:
```python
self.expiry_config = {
    'NIFTY': ('weekly', 1),
    'SENSEX': ('weekly', 3)
    # BANKNIFTY missing
}
```

**Fix Needed:**
```python
self.expiry_config = {
    'NIFTY': ('weekly', 1),      # Tuesday
    'BANKNIFTY': ('weekly', 4),  # Thursday (last of month)
    'SENSEX': ('weekly', 3)      # Thursday
}
```

Update loops to include BANKNIFTY:
```python
for symbol in ['NIFTY', 'BANKNIFTY', 'SENSEX']:
```

**Impact:** System can't trade BankNifty despite README claims.

---

## 🔍 Additional Issues Found

### 15. ❌ ML Training Pipeline Gaps
**Status:** NOT FIXED  
**Files:** `backend/ml/model_manager.py`  
**Issues:**
- No ingestion of live trade outcomes into training_df
- No scheduler calling train_model() for incremental learning
- Feature extraction assumes data exists (will crash if missing)

---

### 16. ❌ Dashboard Update Frequency Mismatch
**Status:** NOT FIXED  
**Issue:** README claims "1-minute heatmap updates" but:
- `market_data_loop()` uses adaptive sleep (15-300s)
- No WebSocket feed for real-time updates
- Only `broadcast_market_data()` every 30-60s

---

## 📊 Summary

| Category | Fixed | Partially | Not Fixed | Total |
|----------|-------|-----------|-----------|-------|
| Critical | 3 | 1 | 4 | 8 |
| High | 2 | 1 | 2 | 5 |
| Medium | 1 | 0 | 2 | 3 |
| **Total** | **6** | **2** | **6** | **14** |

**System Status:** 🟡 **PARTIALLY PRODUCTION-READY**

## 🎯 Priority Fixes Needed

1. **HIGH:** Populate `self.market_state` in `update_option_chain()` (Issue #7)
2. **HIGH:** Fix strike key type in `pcr_strategy.py` (Issue #10)
3. **HIGH:** Fix strategy weights to match README (Issue #9)
4. **MEDIUM:** Add BankNifty support (Issue #14)
5. **MEDIUM:** Add live MTM tracking loop (Issue #8)
6. **LOW:** Add slippage to paper trading (Issue #11)

## ✅ Recommended Next Steps

1. Address Issues #7, #9, #10 (30 minutes)
2. Test with live data feed
3. Add BankNifty support (15 minutes)
4. Enhance order guardrails (1 hour)
5. Full integration test

**Estimated Time to Production-Ready:** 2-3 hours
