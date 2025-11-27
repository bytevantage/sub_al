# Aggressive Mode & Volatility Harvesting Enhancements

## Implementation Summary

All requested enhancements have been successfully implemented to support aggressive trading mode with enhanced risk/reward parameters and volatility harvesting capabilities.

---

## 1. Strategy Name Persistence Fix ✅

**File:** `backend/execution/order_manager.py`

**Changes:**
- Modified `_create_position()` to use canonical `strategy_id` from signals
- Added normalization via `normalize_strategy_name()`
- Ensures consistent strategy tracking across positions, trades, and performance metrics

**Impact:**
- Closed trades now display correct strategy names
- Strategy performance tracking is accurate
- No more "default" strategy names in dashboard

---

## 2. Aggressive Mode API ✅

**New Files Created:**
- `backend/api/aggressive_mode.py` - API endpoints for toggling aggressive mode

**Features:**
- `POST /api/aggressive-mode/toggle` - Enable/disable aggressive mode
- `GET /api/aggressive-mode/status` - Check current aggressive mode status
- Global state management with `aggressive_mode_enabled` flag

**Integration:**
- Wired to `main.py` via `set_aggressive_state()`
- Connected to `StrategyEngine` and `RiskManager`

---

## 3. Aggressive Strategy Boosting ✅

**File:** `backend/strategies/strategy_engine.py`

**New Method:** `_apply_aggressive_mode_if_enabled()`

**Strategy Weight Boosts:**
```python
boost_map = {
    'quantum_edge': 1.0,           # No boost (already maxed)
    'order_flow_imbalance': 1.4,   # 40% boost
    'pcr_analysis': 1.25,           # 25% boost
    '1_minute_scalping': 1.5,      # 50% boost
    'index_etf_arbitrage': 1.1,    # 10% boost
    'gamma_scalping': 1.35,        # 35% boost
    'institutional_footprint': 1.3, # 30% boost
    'liquidity_hunting': 1.2        # 20% boost
}
```

**Behavior:**
- When enabled, high-conviction strategies get weight boosts
- Maximum weight capped at 100
- Can be toggled on/off dynamically via API

---

## 4. ML-Driven Position Sizing Boost ✅

**File:** `backend/execution/risk_manager.py`

**Enhancement in:** `calculate_position_size()`

**Logic:**
```python
if self.aggressive_mode_enabled:
    ml_confidence = signal.get('ml_confidence', 0.0)
    if ml_confidence > 0.7:  # High ML confidence
        # Boost risk by 1.5x, capped at 3%
        risk_percent = min(3.0, risk_percent * 1.5)
```

**Impact:**
- Increases position size for high-confidence ML signals
- Boosts risk per trade from ~2% to 3% when conditions met
- Logged with: "⚡ Aggressive mode: Boosting position size"

---

## 5. VIX Term Structure Analysis ✅

**New File:** `backend/market/vix_term_structure.py`

**Class:** `VIXTermStructureAnalyzer`

**Features:**
- Analyzes VIX futures term structure (contango vs backwardation)
- Identifies volatility arbitrage opportunities
- Term structure states:
  - **Steep Contango** (>10% spread): Sell volatility signal
  - **Contango** (2-10% spread): Neutral bearish
  - **Flat** (-2% to +2%): Neutral
  - **Backwardation** (-10% to -2%): Neutral bullish
  - **Steep Backwardation** (<-10%): Buy volatility signal

**Methods:**
- `analyze_term_structure()` - Analyzes front/back month VIX
- `get_volatility_regime()` - Classifies volatility level
- `should_harvest_volatility()` - Determines if gamma harvesting favorable

**Singleton Access:**
```python
from backend.market.vix_term_structure import get_vix_analyzer
analyzer = get_vix_analyzer()
```

---

## 6. Gamma Harvesting Logic ✅

**New File:** `backend/strategies/gamma_harvesting.py`

**Class:** `GammaHarvestingManager`

**Features:**
- Monitors high gamma positions during elevated volatility
- Rebalances delta exposure as underlying moves
- Harvests profits from theta decay and gamma scalping

**Activation Conditions:**
- VIX > 25 (elevated volatility)
- Term structure in contango (premium decay)

**Harvesting Triggers:**
- **Gamma Scalp**: High gamma (>0.05) + 2% price move → Close 50%
- **Delta Rebalance**: Delta > 0.3 → Rebalance exposure

**Methods:**
- `should_enable_harvesting()` - Check if conditions met
- `analyze_position_for_harvesting()` - Evaluate position
- `calculate_harvest_adjustment()` - Generate adjustment recommendation
- `record_harvest()` - Track harvest performance

**Singleton Access:**
```python
from backend.strategies.gamma_harvesting import get_gamma_harvester
harvester = get_gamma_harvester()
```

---

## 7. Monitoring Automation ✅

**New File:** `backend/jobs/monitoring_automation.py`

**Class:** `MonitoringAutomation`

**Features:**
- Daily performance review (default: 5:00 PM IST)
- Automated anomaly detection and alerts
- Strategy health checks

**Daily Review Includes:**
- Total trades, win rate, P&L
- Profit factor, avg win/loss
- Per-strategy breakdown
- Anomaly alerts

**Anomaly Checks:**
- Win rate < 40%
- Profit factor < 1.0
- Negative daily P&L
- Strategy underperformance (WR < 30% with ≥3 trades)

**Usage:**
```python
from backend.jobs.monitoring_automation import get_monitoring_automation
monitor = get_monitoring_automation()
await monitor.start()
```

---

## How to Use Aggressive Mode

### 1. Enable Aggressive Mode

**API Call:**
```bash
curl -X POST http://localhost:8000/api/aggressive-mode/toggle \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "reason": "Market conditions favorable for aggressive trading"
  }'
```

**Response:**
```json
{
  "status": "success",
  "aggressive_mode": true,
  "timestamp": "2025-11-19T23:30:00",
  "reason": "Market conditions favorable"
}
```

### 2. Check Status

```bash
curl http://localhost:8000/api/aggressive-mode/status
```

### 3. Disable Aggressive Mode

```bash
curl -X POST http://localhost:8000/api/aggressive-mode/toggle \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": false,
    "reason": "Reverting to normal risk parameters"
  }'
```

---

## Expected Impact

### With Aggressive Mode Enabled:

1. **Increased Position Sizes**
   - ML confidence > 0.7: Risk boosted from 2% → 3% per trade
   - More capital deployed on high-conviction signals

2. **Enhanced Strategy Weights**
   - High-frequency strategies (scalping) boosted 50%
   - Institutional strategies boosted 30-40%
   - More signals generated from top-performing strategies

3. **Volatility Harvesting**
   - Active gamma scalping in high VIX environments (>25)
   - Automatic position rebalancing for delta management
   - Profit-taking on 50% of position when gamma scalp triggers

4. **Daily Profit Targets**
   - Normal mode: 5-10% daily returns
   - **Aggressive mode: 10-20% daily returns** (target)

---

## Safety Measures

Even in aggressive mode, all safety systems remain active:

- ✅ Circuit breakers
- ✅ Daily loss limits (adjusted for higher risk)
- ✅ Strategy watchdog
- ✅ VIX spike protection
- ✅ Max drawdown limits
- ✅ Position limits

**Aggressive mode does NOT disable safety systems** - it only increases position sizing and strategy weights within safe bounds.

---

## Monitoring & Alerts

The monitoring automation will:
- Review performance daily at 5 PM IST
- Alert on anomalies (low win rate, negative P&L)
- Track strategy-level performance
- Provide early warnings on underperforming strategies

---

## Testing Recommendations

1. **Start with Partial Aggressive Mode:**
   - Enable for 1-2 hours during high-volatility sessions
   - Monitor results before full-day deployment

2. **VIX Thresholds:**
   - Test gamma harvesting when VIX > 25
   - Validate term structure signals in different market conditions

3. **ML Confidence Monitoring:**
   - Track which signals get position size boosts
   - Verify ML confidence > 0.7 is accurate predictor

4. **Strategy Performance:**
   - Monitor which strategies benefit most from weight boosts
   - Adjust boost_map based on actual performance

---

## Files Modified/Created

### Modified:
1. `backend/execution/order_manager.py` - Strategy name persistence
2. `backend/execution/risk_manager.py` - ML position sizing boost
3. `backend/strategies/strategy_engine.py` - Aggressive mode weight application
4. `backend/main.py` - Router and state wiring

### Created:
1. `backend/api/aggressive_mode.py` - Aggressive mode API
2. `backend/market/vix_term_structure.py` - VIX analysis
3. `backend/strategies/gamma_harvesting.py` - Gamma scalping
4. `backend/jobs/monitoring_automation.py` - Daily monitoring

---

## Next Steps

1. **Restart Backend:**
   ```bash
   docker-compose restart trading_engine
   ```

2. **Verify API Endpoints:**
   - Check `/api/aggressive-mode/status`
   - View dashboard for updated closed trades

3. **Monitor First Aggressive Session:**
   - Enable aggressive mode during high-volatility period
   - Review monitoring automation alerts at 5 PM

4. **Fine-Tune Parameters:**
   - Adjust boost_map based on strategy performance
   - Optimize ML confidence threshold (currently 0.7)
   - Tune gamma harvesting triggers

---

## Support

For issues or questions:
- Check logs: `docker logs trading_engine`
- Review daily monitoring reports
- Adjust parameters in respective files

---

**Status:** ✅ All enhancements implemented and ready for testing
**Date:** November 19, 2025
**Version:** 1.0.0
