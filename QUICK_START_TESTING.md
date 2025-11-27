# 🚀 Quick Start Testing Guide

## Prerequisites Checklist

Before running the system, ensure:

- ✅ Python 3.10+ installed
- ✅ All requirements installed: `pip install -r requirements.txt`
- ✅ PostgreSQL running (optional, system works without it)
- ✅ Redis running (for caching)
- ✅ Upstox API credentials configured

---

## Step 1: Start the Trading System

```bash
python backend/main.py
```

**Expected Output:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Creating database tables...
INFO:     Database tables created successfully
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**✅ Verification:** Server starts without errors and all 20 strategies initialize

---

## Step 2: Verify All 20 Strategies Loaded

Check the console output for strategy initialization:

**Expected Console Logs:**
```
Initializing strategies...
✓ PCR Analysis Strategy (weight: 75)
✓ OI Analysis Strategy (weight: 80)
✓ Max Pain Strategy (weight: 65)
✓ Support Resistance Strategy (weight: 75)
✓ IV Skew Strategy (weight: 70)
✓ Iron Condor Strategy (weight: 65)
✓ Butterfly Strategy (weight: 60)
✓ Straddle/Strangle Strategy (weight: 70)
✓ Gap and Go Strategy (weight: 75)
✓ Greeks Positioning Strategy (weight: 70)
✓ Order Flow Strategy (weight: 85)
✓ Gamma Scalping Strategy (weight: 60)
✓ Institutional Footprint Strategy (weight: 80)
✓ VIX Mean Reversion Strategy (weight: 65)
✓ Time of Day Strategy (weight: 70)
✓ Multi-Leg Arbitrage Strategy (weight: 55)
✓ Hidden OI Strategy (weight: 75)
✓ Liquidity Hunting Strategy (weight: 70)
✓ Sentiment NLP Strategy (weight: 60)
✓ Cross Asset Correlation Strategy (weight: 65)

Total strategies loaded: 20
```

**✅ Verification:** All 20 strategies appear in logs

---

## Step 3: Test API Health

```bash
curl http://localhost:8000/api/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "mode": "paper",
  "trading_active": true
}
```

**✅ Verification:** Status is "healthy"

---

## Step 4: Test Trade History Endpoint (Empty Initially)

```bash
curl http://localhost:8000/api/trades/history
```

**Expected Response:**
```json
{
  "total": 0,
  "limit": 100,
  "offset": 0,
  "trades": []
}
```

**✅ Verification:** Endpoint responds (empty list is normal initially)

---

## Step 5: Test Statistics Endpoint

```bash
curl http://localhost:8000/api/trades/statistics
```

**Expected Response:**
```json
{
  "overview": {
    "total_trades": 0,
    "winning_trades": 0,
    "losing_trades": 0,
    "win_rate": 0,
    "total_pnl": 0,
    "profit_factor": 0,
    "average_profit": 0,
    "average_loss": 0,
    "average_hold_minutes": 0
  },
  "best_trade": null,
  "worst_trade": null,
  "strategy_breakdown": {}
}
```

**✅ Verification:** Returns zero statistics initially

---

## Step 6: Test Interactive Documentation

Open in browser:
```
http://localhost:8000/docs
```

**Expected:** Swagger UI with all endpoints visible

**Test from UI:**
1. Click on "GET /api/trades/history"
2. Click "Try it out"
3. Click "Execute"
4. See response with empty trades list

**✅ Verification:** Swagger UI loads and responds

---

## Step 7: Monitor Real-time Market Data

Watch the console for market data updates (every 1 second):

**Expected Console Output:**
```
[2025-11-11 09:30:15] Market Update:
  NIFTY: 19485.50 (IV: 18.5%, PCR: 0.85)
  BANKNIFTY: 44520.25 (IV: 20.2%, PCR: 0.92)

[2025-11-11 09:30:16] Signal Generated:
  Strategy: Order Flow Imbalance
  Symbol: NIFTY
  Strike: 19500 CALL
  Strength: 88.5
  Reason: Strong buy flow 3.2:1, Volume: 25,450
```

**✅ Verification:** Real-time market updates appear

---

## Step 8: Check Strategy Signals

Watch for strategy signal generation:

**Expected Console Output:**
```
[09:35:22] ✓ PCR Strategy: BULLISH signal (PCR: 0.68 < 0.70)
[09:36:15] ✓ OI Strategy: BEARISH signal (19600 CE: +25K OI, 19500 PE: +18K OI)
[09:37:45] ✓ Order Flow: BULLISH signal (Buy/Sell: 3.5:1, Volume: 45K)
[09:38:10] ✗ Max Pain: No signal (Price 19485 vs MaxPain 19450, within 0.3%)
```

**✅ Verification:** Strategies analyze data and generate signals

---

## Step 9: Test Database Integration (If PostgreSQL Running)

### Create Test Trade Manually

```python
# Run in Python console or create test_trade.py
from backend.database import db, Trade
from datetime import datetime

# Get session
session = db.get_session()

# Create test trade
test_trade = Trade(
    trade_id="TEST001",
    entry_time=datetime.now(),
    symbol="NIFTY",
    instrument_type="CALL",
    strike_price=19500,
    entry_price=150.50,
    quantity=50,
    strategy_name="Order Flow Imbalance",
    signal_strength=88.5,
    status="OPEN"
)

session.add(test_trade)
session.commit()
print(f"Created test trade: {test_trade.trade_id}")
session.close()
```

### Verify via API

```bash
curl http://localhost:8000/api/trades/history
```

**Expected Response:**
```json
{
  "total": 1,
  "trades": [
    {
      "trade_id": "TEST001",
      "symbol": "NIFTY",
      "strike_price": 19500,
      "entry_price": 150.50,
      "strategy_name": "Order Flow Imbalance",
      "status": "OPEN"
    }
  ]
}
```

**✅ Verification:** Test trade appears in API response

---

## Step 10: Test CSV Export

```bash
curl "http://localhost:8000/api/trades/export/csv" -o test_export.csv
```

**Expected:** Creates `test_export.csv` with headers:
```
Trade ID,Entry Date,Entry Time,Exit Date,Exit Time,Symbol,Type,Strike,Entry Price,Exit Price,Quantity,Gross P&L,Brokerage,Taxes,Net P&L,P&L %,Strategy,Signal Strength,Exit Type,Hold Minutes,Spot Entry,Spot Exit,IV Entry,IV Exit,Signal Reason,Exit Reason
TEST001,2025-11-11,09:30:15,,,NIFTY,CALL,19500,150.50,,50,,,,,,Order Flow Imbalance,88.5,,,,,,,,
```

**Open in Excel:**
```bash
open test_export.csv  # macOS
```

**✅ Verification:** CSV opens in Excel with proper columns

---

## Troubleshooting

### Issue: "Database not available"

**Solution 1: Run without database**
- System works fine without PostgreSQL
- Trades won't be persisted, but real-time trading works

**Solution 2: Configure PostgreSQL**
```bash
# Install PostgreSQL
brew install postgresql

# Start service
brew services start postgresql

# Create database
createdb trading_system

# Update config.yaml
database:
  url: "postgresql://localhost:5432/trading_system"
```

---

### Issue: "Redis connection failed"

**Solution:**
```bash
# Install Redis
brew install redis

# Start service
brew services start redis

# Verify
redis-cli ping  # Should return PONG
```

---

### Issue: "Strategies not generating signals"

**Possible Causes:**
1. Market hours (signals only during 9:15 AM - 3:30 PM IST)
2. Insufficient market data (wait 5-10 minutes for data accumulation)
3. Market conditions not meeting strategy thresholds

**Check:**
```bash
# View strategy thresholds
cat STRATEGY_REFERENCE.md
```

---

### Issue: "Upstox API authentication failed"

**Solution:**
```bash
# Run auth script
python upstox_auth_working.py

# Copy access token to config.yaml
upstox:
  access_token: "YOUR_TOKEN_HERE"
```

---

## Next Steps

### 1. Enable Database Logging (Production Use)

Edit `backend/order_manager.py`:

```python
from backend.database import db, Trade
from datetime import datetime

def execute_signal(self, signal):
    # Execute trade...
    position = self._execute_trade(...)
    
    # Create database record
    if db.get_session():
        trade = Trade(
            trade_id=position['trade_id'],
            entry_time=datetime.now(),
            symbol=signal.symbol,
            instrument_type=signal.signal_type.upper(),
            strike_price=signal.strike_price,
            entry_price=signal.entry_price,
            quantity=signal.quantity,
            strategy_name=signal.strategy,
            signal_strength=signal.strength,
            ml_score=signal.ml_score,
            spot_price_entry=market_data['spot_price'],
            iv_entry=market_data['iv'],
            signal_reason=signal.reason,
            status="OPEN"
        )
        session = db.get_session()
        session.add(trade)
        session.commit()
        session.close()
```

---

### 2. Monitor Live Performance

```bash
# Watch console for:
✓ Strategy signals
✓ Trade executions
✓ Position updates
✓ P&L changes

# Or use API endpoints:
watch -n 5 'curl -s http://localhost:8000/api/trades/statistics | jq'
```

---

### 3. Review Daily Performance

```bash
# Get today's stats
curl "http://localhost:8000/api/trades/statistics?start_date=$(date +%Y-%m-%d)" | jq

# Export for Excel analysis
curl "http://localhost:8000/api/trades/export/csv?start_date=$(date +%Y-%m-%d)" -o today_trades.csv
```

---

## Testing Checklist

- [ ] Server starts without errors
- [ ] All 20 strategies load successfully
- [ ] Health endpoint responds
- [ ] Trade history endpoint accessible
- [ ] Statistics endpoint works
- [ ] Swagger UI loads at /docs
- [ ] Market data updates appear in console
- [ ] Strategy signals generate
- [ ] Database connection works (if PostgreSQL running)
- [ ] CSV export creates valid Excel file

**If all checkmarks complete: System is ready for production! 🎉**

---

## Performance Benchmarks

**Expected Performance:**
- Strategy analysis: <50ms per cycle
- Signal generation: <100ms per signal
- API response time: <100ms (without database), <500ms (with database)
- Market data refresh: 1 second interval
- Database write: <50ms per trade

**Monitor with:**
```bash
# API response times
time curl http://localhost:8000/api/trades/history

# Strategy cycle time (check console logs)
[09:30:15] Analysis completed in 42ms
```

---

## Support

**Documentation:**
- `ALL_STRATEGIES_COMPLETE.md` - Complete feature documentation
- `STRATEGY_REFERENCE.md` - Strategy threshold reference
- `IMPLEMENTATION_COMPLETE.md` - Implementation details
- `API_DOCUMENTATION.md` - Full API reference

**Common Commands:**
```bash
# Start system
python backend/main.py

# Test API
curl http://localhost:8000/api/health

# View docs
open http://localhost:8000/docs

# Export trades
curl http://localhost:8000/api/trades/export/csv -o trades.csv
```

---

**Happy Trading! 📈🚀**
