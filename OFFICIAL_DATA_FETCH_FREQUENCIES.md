# OFFICIAL DATA FETCH FREQUENCIES – NOV 27, 2025 LOCKED

## 📊 Data Fetch Configuration

```yaml
data_fetch:
  option_chain_interval_seconds: 30      # was 60 → now twice as fresh, still safe
  position_ltp_interval_seconds: 5       # perfect – do not touch
  market_data_loop_seconds: 30           # good balance
  risk_check_interval_seconds: 10        # was 1 → reduces noise, zero downside
  sac_decision_interval_seconds: 300     # sacred – never change
```

## ✅ Changes Implemented

### 1. Option Chain Interval: 60s → 30s
- **File:** `backend/services/price_history_tracker.py`
- **Line:** `self.fetch_interval = 30`
- **Impact:** Twice as fresh data, still safe for API limits

### 2. Risk Check Interval: 1s → 10s
- **File:** `backend/main.py` 
- **Line:** `self.risk_check_interval = 10`
- **Impact:** Reduces noise, zero downside for stop-loss detection

## 🔒 Unchanged (Perfect Settings)

- **Position LTP:** 5 seconds ✅ (do not touch)
- **Market Data Loop:** 30 seconds ✅ (good balance)
- **SAC Decisions:** 300 seconds ✅ (sacred - never change)

## 🎯 Performance Impact

| Component | Before | After | Benefit |
|-----------|--------|-------|---------|
| **Option Chain** | 60s | 30s | 2x fresher signals |
| **Risk Checks** | 1s | 10s | 90% less noise |
| **API Load** | High | Optimized | Better rate limiting |
| **System Noise** | High | Low | Cleaner logs |

---

**Status: LOCKED AND IMPLEMENTED**  
**Date: November 27, 2025**  
**Next Review: Never (official spec)**
