# 📖 User Manual - Advanced Options Trading System

## Table of Contents
1. [Getting Started](#getting-started)
2. [First-Time Setup](#first-time-setup)
3. [Running the System](#running-the-system)
4. [Understanding Signals](#understanding-signals)
5. [Monitoring & Management](#monitoring--management)
6. [Risk Management](#risk-management)
7. [Troubleshooting](#troubleshooting)

---

## Getting Started

### System Requirements

- **Operating System**: macOS, Linux, or Windows
- **Python**: Version 3.10 or higher
- **RAM**: Minimum 4GB (8GB recommended)
- **Internet**: Stable connection for market data
- **Upstox Account**: Pro account with API access

### What This System Does

This trading system:
- ✅ Analyzes options market data in real-time
- ✅ Generates trading signals using 20+ strategies
- ✅ Scores signals with ML models
- ✅ Executes trades automatically (in paper or live mode)
- ✅ Manages risk with dynamic stop losses
- ✅ Tracks performance and P&L
- ✅ Provides professional dashboard interface

---

## First-Time Setup

### Step 1: Generate Upstox API Token

```bash
# Run the authentication script
python upstox_auth_working.py
```

**What happens:**
1. A browser window will open
2. Login to your Upstox account
3. Authorize the application
4. Token is automatically saved to `~/Algo/upstoxtoken.json`

**Token Validity:** 
- Access tokens expire daily
- Re-run this script each trading day
- Consider setting up automated token refresh

### Step 2: Run Quick Setup

```bash
# Run the automated setup script
python setup.py
```

**Setup performs:**
- ✓ Checks Python version
- ✓ Creates necessary directories
- ✓ Installs dependencies
- ✓ Configures environment
- ✓ Verifies Upstox token
- ✓ Offers to start the system

**Manual Setup (Alternative):**

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

### Step 3: Configure Settings

Edit `.env` file:

```env
# Trading Mode (ALWAYS START WITH PAPER)
MODE=paper

# Capital
INITIAL_CAPITAL=100000

# Risk Settings
RISK_PERCENT=3              # Max 3% daily loss
MIN_SIGNAL_STRENGTH=75      # Minimum signal score

# Features
ENABLE_ML=true
ENABLE_PAPER_TRADING=true
ENABLE_LIVE_TRADING=false   # Keep false until tested
```

**Important Configuration Tips:**

1. **Always start with paper trading**
2. **Test for at least 2 weeks before going live**
3. **Start with small capital in live mode**
4. **Monitor daily for first month**

---

## Running the System

### Option 1: Using Setup Script

```bash
python setup.py
```

Then select 'y' when prompted to start.

### Option 2: Direct Python Execution

```bash
python backend/main.py
```

### Option 3: Using Uvicorn (Development)

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 4: Using Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f trading-engine

# Stop services
docker-compose down
```

### What Happens When System Starts

```
============================================================
🚀 Initializing Advanced Options Trading System
============================================================
✓ Upstox API connection successful
✓ All components initialized successfully
============================================================
📈 Trading System Started
   Mode: PAPER
   Capital: ₹100,000
   Max Positions: 5
============================================================
```

**System is now:**
- 📡 Fetching market data every 30 seconds
- 🔍 Analyzing option chains
- 📊 Calculating PCR, Max Pain, Greeks
- 🎯 Generating trading signals
- 🤖 Scoring signals with ML
- 💼 Managing positions
- ⚠️ Monitoring risk

---

## Understanding Signals

### Signal Structure

```json
{
  "strategy": "PCR Analysis",
  "symbol": "NIFTY",
  "direction": "CALL",
  "action": "BUY",
  "strike": 21000,
  "expiry": "2024-12-26",
  "entry_price": 125.50,
  "target_price": 137.05,
  "stop_loss": 87.85,
  "strength": 82.5,
  "ml_probability": 0.78,
  "reason": "Bullish PCR: 1.45",
  "timestamp": "2024-12-11T10:30:00"
}
```

### Reading Signals

**Strategy:** Which strategy generated the signal
- High-priority: Order Flow, OI Changes, PCR Analysis
- Each strategy has a weight (50-90)

**Direction:** CALL or PUT
- CALL = Bullish (expect price to rise)
- PUT = Bearish (expect price to fall)

**Strike:** Option strike price
- Usually ATM (At The Money) or slightly ITM

**Strength:** Signal confidence (0-100)
- 90-100: Very Strong
- 80-90: Strong
- 75-80: Moderate
- Below 75: Filtered out (not shown)

**ML Probability:** Machine learning confidence (0-1)
- 0.8-1.0: High confidence
- 0.6-0.8: Moderate confidence
- Below 0.6: Low confidence

**Targets:**
- Entry Price: Current option price
- Target Price: Profit target (dynamic, 10-30%)
- Stop Loss: Risk limit (30% below entry)

---

## Monitoring & Management

### Viewing Logs

**Real-time log monitoring:**
```bash
# Follow main log
tail -f data/logs/trading_$(date +%Y%m%d).log

# Follow JSON log
tail -f data/logs/trading_$(date +%Y%m%d).json
```

**Log levels:**
- 🔵 INFO: Normal operations
- 🟡 WARNING: Attention needed
- 🔴 ERROR: Something went wrong

### API Endpoints

**Health Check:**
```bash
curl http://localhost:8000/api/health
```

**Get Current Signals:**
```bash
curl http://localhost:8000/api/signals
```

**Get Open Positions:**
```bash
curl http://localhost:8000/api/positions
```

**Get Performance Metrics:**
```bash
curl http://localhost:8000/api/performance
```

**Start/Stop Trading:**
```bash
# Start
curl -X POST http://localhost:8000/api/trading/start

# Stop
curl -X POST http://localhost:8000/api/trading/stop
```

### Accessing the Dashboard

Open browser: `http://localhost:3000`

**Dashboard shows:**
1. **Signal Monitor** (Top-Left)
   - Live signals as they're generated
   - Click to execute (paper mode)
   - Signal history

2. **Option Chain** (Top-Right)
   - Heatmap of OI distribution
   - Max pain level
   - Support/resistance

3. **Charts** (Bottom-Left)
   - Price action
   - PCR overlay
   - Volume bars

4. **Performance** (Bottom-Right)
   - P&L tracker
   - Open positions
   - Win rate
   - Risk metrics

---

## Risk Management

### Built-in Protections

**Daily Loss Limit:**
- System auto-stops if daily loss exceeds 3%
- Closes all positions
- Prevents further trading for the day

**Position Limits:**
- Max 5 concurrent positions
- Prevents over-exposure
- Ensures manageable risk

**Position Sizing:**
- 1-2% risk per trade
- Calculated based on stop loss
- Adjusted by signal strength

**Stop Loss:**
- Automatically placed on every trade
- Dynamic based on ATR
- Trailing stop available
- Force exit at 3:20 PM

### Exit Conditions

**Automatic exits when:**
1. Stop loss hit (-30%)
2. Target reached (10-30%)
3. Reversal detected
4. End of day (3:20 PM)
5. Daily loss limit reached

### Monitoring Risk

**Watch these metrics:**

```bash
# Current risk exposure
curl http://localhost:8000/api/performance | jq .capital_at_risk

# Daily P&L
curl http://localhost:8000/api/performance | jq .daily_pnl

# Win rate
curl http://localhost:8000/api/performance | jq .win_rate
```

**Ideal metrics:**
- Win Rate: >60%
- Profit Factor: >2.0
- Max Drawdown: <5%
- Avg Trade Duration: 15-45 min

---

## Troubleshooting

### Common Issues

#### 1. "Failed to connect to Upstox API"

**Solution:**
```bash
# Generate fresh token
python upstox_auth_working.py

# Verify token exists
ls -l ~/Algo/upstoxtoken.json

# Check token in config
cat config/upstox_token.json
```

#### 2. "No signals being generated"

**Possible causes:**
- Market is sideways (low volatility)
- Signal cooldown active (5 min between signals)
- Min strength threshold too high

**Check:**
```bash
# View current market state
curl http://localhost:8000/api/option-chain/NIFTY/2024-12-26

# Lower threshold temporarily
# Edit .env: MIN_SIGNAL_STRENGTH=70
```

#### 3. "Daily loss limit reached"

**This is working as designed!**
- System stopped trading to protect capital
- Review closed trades
- Analyze what went wrong
- Adjust strategy weights or thresholds

#### 4. "ML model not found"

**Normal on first run:**
```bash
# System will collect data and train automatically
# Or use paper trading to generate training data
```

#### 5. "Database connection error"

**If using Docker:**
```bash
# Restart database
docker-compose restart postgres

# Check status
docker-compose ps
```

**If local:**
```bash
# Install PostgreSQL or disable database features
# System works without DB (uses in-memory storage)
```

### Getting Help

**Check logs first:**
```bash
tail -n 100 data/logs/trading_$(date +%Y%m%d).log
```

**Common log messages:**

| Message | Meaning | Action |
|---------|---------|--------|
| "Rate limit exceeded" | Too many API calls | Wait 2 seconds, auto-retries |
| "Token expired" | Need fresh token | Run upstox_auth_working.py |
| "Max positions reached" | 5 positions open | Wait for exits or increase limit |
| "Signal strength below minimum" | Weak signal filtered | Normal, wait for better signals |

### Emergency Stop

**If system misbehaves:**

1. **Immediate stop:**
   ```bash
   # Press Ctrl+C in terminal
   # OR
   curl -X POST http://localhost:8000/api/trading/stop
   ```

2. **Check positions:**
   ```bash
   curl http://localhost:8000/api/positions
   ```

3. **Manual close on Upstox:**
   - Login to Upstox web/app
   - Close positions manually if needed

---

## Best Practices

### Daily Routine

**Morning (9:00 AM):**
1. Generate fresh Upstox token
2. Check system logs from previous day
3. Review configuration
4. Start trading system
5. Monitor first 30 minutes

**During Market Hours:**
1. Check signals every hour
2. Review open positions
3. Monitor P&L
4. Adjust if needed

**After Market Close (3:30 PM):**
1. Review day's performance
2. Check trade logs
3. Analyze winners/losers
4. Note any issues
5. Adjust strategies for tomorrow

### Going Live Checklist

**Before enabling live trading:**

- [ ] Tested in paper mode for minimum 2 weeks
- [ ] Win rate consistently >60%
- [ ] Profit factor >2.0
- [ ] Understood all 20 strategies
- [ ] Comfortable with risk management
- [ ] Have emergency stop procedure
- [ ] Start with 10% of intended capital
- [ ] Monitor closely for first week
- [ ] Keep backup capital for emergencies

**Enable live trading:**
```env
# In .env file
MODE=live
ENABLE_LIVE_TRADING=true

# Start with small capital
INITIAL_CAPITAL=10000
```

---

## Tips for Success

1. **Start Small**: Use paper trading extensively
2. **Be Patient**: Quality signals > quantity
3. **Monitor Closely**: First month needs daily review
4. **Trust the System**: Let stop losses work
5. **Keep Learning**: Analyze every trade
6. **Stay Disciplined**: Don't override system
7. **Manage Expectations**: No system is 100% accurate
8. **Have Backups**: Keep manual trading knowledge
9. **Review Regularly**: Weekly performance analysis
10. **Stay Updated**: Market conditions change

---

## Support & Resources

**Documentation:**
- README.md - Project overview
- STRATEGIES.md - Strategy details
- API.md - API reference
- DEPLOYMENT.md - Production deployment

**Logs Location:**
- Main logs: `data/logs/trading_YYYYMMDD.log`
- JSON logs: `data/logs/trading_YYYYMMDD.json`
- Trade logs: `data/trades/`

**Configuration:**
- Main config: `config/config.yaml`
- Environment: `.env`
- Token: `config/upstox_token.json`

---

**Remember: This is a sophisticated system. Take time to understand it before risking real capital.**
