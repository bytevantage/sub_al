# Quick Aggressive Mode Guide

## Toggle Aggressive Mode

### Enable
```bash
curl -X POST http://localhost:8000/api/aggressive-mode/toggle \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "reason": "High volatility session"}'
```

### Disable
```bash
curl -X POST http://localhost:8000/api/aggressive-mode/toggle \
  -H "Content-Type: application/json" \
  -d '{"enabled": false, "reason": "Reverting to normal"}'
```

### Check Status
```bash
curl http://localhost:8000/api/aggressive-mode/status
```

---

## What Changes in Aggressive Mode

### 1. Position Sizing
- **Normal:** 2% risk per trade
- **Aggressive (ML confidence > 0.7):** 3% risk per trade (1.5x boost)

### 2. Strategy Weights
- Scalping: +50% weight
- Institutional Footprint: +30% weight
- Order Flow: +40% weight
- PCR Analysis: +25% weight
- Gamma Scalping: +35% weight

### 3. Volatility Harvesting
- **Enabled when:** VIX > 25 + Contango term structure
- **Actions:**
  - Gamma scalping on 2% price moves
  - Delta rebalancing when Δ > 0.3
  - Auto profit-taking (50% position)

---

## Expected Results

| Metric | Normal Mode | Aggressive Mode |
|--------|-------------|-----------------|
| Daily Return Target | 5-10% | 10-20% |
| Risk per Trade | 1-2% | 2-3% |
| Max Positions | 5-8 | 8-12 |
| Strategy Signals | Moderate | High |

---

## Safety Systems (Always Active)

✅ Circuit breakers  
✅ Daily loss limits  
✅ VIX spike protection  
✅ Max drawdown limits  
✅ Strategy watchdog  

**Aggressive mode does NOT bypass safety!**

---

## Monitoring

- **Daily Review:** 5:00 PM IST
- **Alerts:** Win rate < 40%, Profit factor < 1.0, Negative P&L
- **Logs:** `docker logs trading_engine | grep "⚡"`

---

## Quick Test

1. Enable aggressive mode (see above)
2. Check status endpoint
3. Observe increased signal generation
4. Monitor position sizes in dashboard
5. Review daily monitoring report at 5 PM

---

## Disable If:

- Daily loss > 5%
- Win rate drops below 40%
- VIX > 40 (crisis mode)
- Multiple strategy failures

---

## Files for Reference

- API: `backend/api/aggressive_mode.py`
- Position Sizing: `backend/execution/risk_manager.py:256`
- Strategy Weights: `backend/strategies/strategy_engine.py:122`
- VIX Analysis: `backend/market/vix_term_structure.py`
- Gamma Harvesting: `backend/strategies/gamma_harvesting.py`

---

**Quick Status Check:**
```bash
# Is aggressive mode enabled?
curl -s http://localhost:8000/api/aggressive-mode/status | jq '.aggressive_mode_enabled'

# Current strategy weights
curl -s http://localhost:8000/api/ml-strategy/strategy-weights | jq '.weights'
```
