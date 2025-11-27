# Complete Trading System Guide - SRB-Algo

## 📋 Table of Contents
1. [System Architecture](#system-architecture)
2. [Trading Flow](#trading-flow)
3. [Strategy Framework](#strategy-framework)
4. [Entry Logic](#entry-logic)
5. [Exit Logic](#exit-logic)
6. [Risk Management](#risk-management)
7. [Parameters & Configuration](#parameters--configuration)
8. [Market Regimes](#market-regimes)
9. [Position Management](#position-management)
10. [Monitoring & Logging](#monitoring--logging)

---

## 🏗️ System Architecture

### Core Components
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   SAC Agent     │───▶│  Strategy Zoo    │───▶│  Signal Engine  │
│ (Meta-Controller)│    │  (6 Strategies)  │    │  (Signal Gen)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Entry Timing    │───▶│  Risk Manager    │───▶│ Order Manager   │
│ (Pullback Wait) │    │ (Position Sizing)│    │ (Execution)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Market Data     │    │  Position DB     │    │  Upstox API     │
│ (Real-time)     │    │  (PostgreSQL)    │    │  (Broker)       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Data Flow
1. **Market Data** → Real-time prices, option chain, technical indicators
2. **SAC Agent** → Selects optimal strategy every 30 seconds
3. **Strategy Zoo** → Generates trading signals
4. **Entry Timing** → Waits for optimal entry points
5. **Risk Manager** → Validates and sizes positions
6. **Order Manager** → Executes trades via Upstox API
7. **Position DB** → Tracks all open/closed positions

---

## 🔄 Trading Flow

### Main Trading Loop (Every 30 seconds)
```python
1. Fetch Market State
   ├── Option Chain Data
   ├── Technical Indicators
   ├── VIX & Market Sentiment
   └── Volume Profile

2. SAC Strategy Selection
   ├── Analyze Market Regime
   ├── Score Available Strategies
   └── Select Top Strategy

3. Signal Generation
   ├── Run Selected Strategy
   ├── Generate Entry Signals
   └── Calculate Targets & Stops

4. Entry Timing Check
   ├── VWAP Deviation Analysis
   ├── Momentum Confirmation
   └── Queue if Extended

5. Risk Validation
   ├── Position Size Calculation
   ├── Daily Loss Limits
   └── Correlation Checks

6. Order Execution
   ├── Paper/Live Mode
   ├── Slippage Simulation
   └── Position Creation

7. Position Monitoring
   ├── Real-time P&L Updates
   ├── Exit Condition Checks
   └── Trade Closure
```

---

## 🎯 Strategy Framework

### Active Strategies (6)
1. **Gamma Scalping**
   - Focus: Gamma exposure management
   - Best: High volatility, trending markets
   
2. **IV Rank Trading**
   - Focus: Implied volatility mean reversion
   - Best: Extreme IV levels
   
3. **VWAP Deviation**
   - Focus: Price reversion to VWAP
   - Best: Range-bound markets
   
4. **Default Strategy**
   - Focus: Balanced approach
   - Best: All market conditions
   
5. **Quantum Edge V2**
   - Focus: Advanced technical patterns
   - Best: Strong trends
   
6. **Quantum Edge**
   - Focus: Momentum & volume analysis
   - Best: Breakout scenarios

### SAC Meta-Controller
```python
Selection Process:
├── Regime Detection (5 types)
├── Strategy Scoring (0-100)
├── Weight Adjustment (regime-based)
└── Final Selection (top strategy)
```

---

## 📥 Entry Logic

### Entry Timing Manager
**Purpose**: Wait for optimal entry points instead of chasing prices

### VWAP-Based Pullback Detection
```python
# Threshold Parameters
CALL_THRESHOLD = 0.3%    # Wait if price > 0.3% above VWAP
PUT_THRESHOLD = 0.3%     # Wait if price < 0.3% below VWAP

# Logic
if direction == 'CALL':
    if deviation > 0.3%:
        WAIT for pullback to VWAP
    else:
        ENTER now

if direction == 'PUT':
    if deviation < -0.3%:
        WAIT for bounce to VWAP
    else:
        ENTER now
```

### Pending Signal Queue
```python
# Queue Parameters
MAX_WAIT_TIME = 120 seconds    # 2 minutes timeout
QUEUE_CHECK_INTERVAL = 30s     # Check with main loop

# Process
1. Add to pending queue if extended
2. Check every 30 seconds for pullback
3. Enter immediately if:
   ├── Price returns to VWAP zone
   ├── Timeout reached (120s)
   └── Error in timing check
```

### Entry Quality Factors
```python
# Signal Strength Components
Base Signal Score: 0-50
VWAP Proximity: +0-20 points
Momentum Alignment: +0-20 points
Time of Day: +5-10 points

# Total Score: 0-100
> 80: Excellent entry
60-79: Good entry
40-59: Fair entry
< 40: Poor entry
```

---

## 📤 Exit Logic

### Tiered Profit Taking (TP1/TP2/TP3)
```python
# Position Scaling
TP1: Scale out 40% (move SL to breakeven)
TP2: Scale out 35% (move SL to TP1)
TP3: Close remaining 25% (final exit)

# Target Calculation (from risk_reward_config.py)
tp1 = entry_price + risk_amount * rr_ratio * 0.40
tp2 = entry_price + risk_amount * rr_ratio * 0.75
tp3 = entry_price + risk_amount * rr_ratio * 1.00
```

### Regime-Based Exit Behavior
```python
# Strong Trend Regimes (high_confidence, monster_day)
TP1: Scale 40%, hold 60% for bigger gains
SL: Move to breakeven + 0.5% buffer

# Choppy Regime (chop_regime)
TP1: Take full profit (close 100%)
Reason: Avoid reversals in choppy markets

# Normal Regime
TP1: Scale 40%, hold 60%
SL: Move to breakeven + 0.1% buffer
```

### Stop Loss Management
```python
# Initial Stop Loss
Dynamic calculation based on:
├── VIX volatility adjustment
├── Regime-based risk per trade
└── Distance from entry

# Trailing Stop Loss
Trigger: 10% profit reached
Action: Move SL to 50% of profit
Update: Continuous as price rises

# Effective SL = Max(Initial SL, Trailing SL)
```

### Exit Reasons Tracking
```python
Exit Types:
├── TP3_TARGET           # Final profit target hit
├── TP2_PARTIAL_SCALE    # Partial profit taking
├── TP1_PARTIAL_SCALE_*  # Regime-specific scaling
├── TP1_FULL_PROFIT_CHOPPY # Full exit in choppy market
├── TRAILING_STOP_HIT    # Profit protection
├── STOP_LOSS_HIT        # Initial stop loss
├── EOD                  # End of day close
├── DAILY_LIMIT_HIT      # Daily loss limit
└── MANUAL_CLOSE         # Manual intervention
```

---

## ⚠️ Risk Management

### Position Sizing
```python
# Risk Per Trade (Dynamic)
Base Risk: 1% of capital
Regime Adjustment:
├── STRONG_TREND_LOW_VOL: 2%
├── RANGING_LOW_VOL: 1.5%
├── TRENDING_MODERATE_VOL: 1%
├── MEAN_REVERSION: 1%
└── HIGH_VOLATILITY: 0.5%

# Position Size Calculation
position_size = (capital * risk_pct) / (entry_price - stop_loss)
```

### Daily Loss Limits
```python
# Intraday Runway (Dynamic)
Base Limit: 4% of capital
Regime Adjustment:
├── STRONG_TREND_LOW_VOL: 10%
├── RANGING_LOW_VOL: 6%
├── TRENDING_MODERATE_VOL: 4%
├── MEAN_REVERSION: 4%
└── HIGH_VOLATILITY: 2%

# Trading Halt
if daily_pnl < -runway:
    STOP all trading for day
```

### Correlation Limits
```python
# Maximum Exposure
Per Symbol: 20% of capital
Per Strategy: 30% of capital
Total Directional: 50% of capital
```

---

## 📊 Market Regimes

### 5 Regime Types
```python
1. STRONG_TREND_LOW_VOL
   ├── Characteristics: Strong directional move, low volatility
   ├── Risk: 2% per trade, 10% daily limit
   └── Strategy Bias: Trend-following

2. RANGING_LOW_VOL
   ├── Characteristics: Sideways market, low volatility
   ├── Risk: 1.5% per trade, 6% daily limit
   └── Strategy Bias: Mean reversion

3. TRENDING_MODERATE_VOL
   ├── Characteristics: Moderate trend, normal volatility
   ├── Risk: 1% per trade, 4% daily limit
   └── Strategy Bias: Balanced

4. MEAN_REVERSION
   ├── Characteristics: Range-bound, reversal patterns
   ├── Risk: 1% per trade, 4% daily limit
   └── Strategy Bias: Contrarian

5. HIGH_VOLATILITY
   ├── Characteristics: High volatility, erratic moves
   ├── Risk: 0.5% per trade, 2% daily limit
   └── Strategy Bias: Conservative
```

### Regime Detection
```python
# Indicators Used
├── VIX (Volatility Index)
├── ADX (Average Directional Index)
├── Price Action Patterns
└── Volume Analysis

# Detection Frequency: Every 30 seconds
# Transition Rules: Minimum 3 confirmations
```

---

## 📈 Position Management

### Position Lifecycle
```python
1. Signal Generation
   ├── Strategy creates signal
   ├── Entry price calculated
   └── Targets/SL set

2. Entry Timing
   ├── VWAP deviation check
   ├── Queue if extended
   └── Execute on pullback

3. Position Creation
   ├── Size calculation
   ├── Risk validation
   └── Order execution

4. Monitoring
   ├── Real-time price updates
   ├── P&L calculation
   └── Exit condition checks

5. Exit Execution
   ├── TP1/TP2/TP3 scaling
   ├── Stop loss hits
   └── Position closure

6. Post-Trade Analysis
   ├── Performance metrics
   ├── Strategy feedback
   └── Learning updates
```

### Position Data Structure
```python
position = {
    # Basic Info
    'id': 'uuid',
    'symbol': 'NIFTY',
    'strike_price': 26000,
    'instrument_type': 'CALL',
    'strategy_name': 'Gamma Scalping',
    
    # Entry Details
    'entry_price': 150.25,
    'entry_time': '2025-11-27 10:30:00',
    'quantity': 100,
    'direction': 'BUY',
    
    # Exit Details
    'target_price': 180.00,
    'stop_loss': 135.00,
    'tp1': 165.00,
    'tp2': 175.00,
    'tp3': 180.00,
    'trailing_sl': 145.00,
    
    # Current State
    'current_price': 160.50,
    'unrealized_pnl': 1025.00,
    'unrealized_pnl_pct': 6.82,
    'position_metadata': {
        'tp1_hit': True,
        'tp2_hit': False,
        'tp3_hit': False
    },
    
    # Exit Info
    'exit_reason': None,
    'exit_price': None,
    'exit_time': None,
    
    # Greeks (Options)
    'delta_entry': 0.45,
    'gamma_entry': 0.02,
    'theta_entry': -0.15,
    'vega_entry': 0.30,
    'delta_current': 0.52,
    'gamma_current': 0.025,
    'theta_current': -0.14,
    'vega_current': 0.28,
    'iv_entry': 18.5,
    'iv_current': 19.2
}
```

---

## ⚙️ Parameters & Configuration

### Entry Timing Parameters
```python
# VWAP Thresholds
CALL_VWAP_THRESHOLD = 0.3%     # Wait if > this above VWAP
PUT_VWAP_THRESHOLD = 0.3%      # Wait if > this below VWAP

# Queue Management
MAX_WAIT_TIME = 120 seconds     # Timeout for pullback
QUEUE_CHECK_INTERVAL = 30s      # Main loop frequency

# Quality Scoring
BASE_SIGNAL_SCORE = 0-50
VWAP_PROXIMITY_BONUS = 0-20
MOMENTUM_ALIGNMENT_BONUS = 0-20
TIME_OF_DAY_BONUS = 5-10
```

### Exit Parameters
```python
# Profit Taking (Scaling Percentages)
TP1_SCALE_PERCENT = 40%        # Scale out at TP1
TP2_SCALE_PERCENT = 35%        # Scale out at TP2
TP3_SCALE_PERCENT = 25%        # Close at TP3

# Target Calculations
TP1_MULTIPLIER = 0.40          # 40% of risk:reward
TP2_MULTIPLIER = 0.75          # 75% of risk:reward
TP3_MULTIPLIER = 1.00          # 100% of risk:reward

# Stop Loss Buffers
BREAKEVEN_BUFFER_STRONG = 0.5% # Strong regime buffer
BREAKEVEN_BUFFER_NORMAL = 0.1% # Normal regime buffer
TP1_BUFFER = 0.5%              # TP1 buffer for SL move

# Trailing Stop
TRAILING_TRIGGER_PCT = 10%     # Trigger at 10% profit
TRAILING_LOCK_PCT = 50%        # Lock 50% of profit
```

### Risk Parameters
```python
# Base Risk Per Trade
BASE_RISK_PCT = 1.0%           # 1% of capital

# Regime Adjustments
STRONG_TREND_RISK = 2.0%
RANGING_RISK = 1.5%
TRENDING_RISK = 1.0%
MEAN_REVERSION_RISK = 1.0%
HIGH_VOL_RISK = 0.5%

# Daily Loss Limits
BASE_DAILY_LIMIT = 4.0%
STRONG_TREND_DAILY = 10.0%
RANGING_DAILY = 6.0%
TRENDING_DAILY = 4.0%
MEAN_REVERSION_DAILY = 4.0%
HIGH_VOL_DAILY = 2.0%

# Correlation Limits
MAX_PER_SYMBOL = 20.0%
MAX_PER_STRATEGY = 30.0%
MAX_DIRECTIONAL = 50.0%
```

### Market Data Parameters
```python
# Option Chain
STRIKE_INTERVAL = 50           # Strike price intervals
EXPIRY_DAYS = 7               # Days to expiry focus

# Technical Indicators
VWAP_PERIOD = 390              # 1 trading day (minutes)
RSI_PERIOD = 14               # RSI calculation period
MACD_FAST = 12                # MACD fast EMA
MACD_SLOW = 26                # MACD slow EMA
MACD_SIGNAL = 9               # MACD signal line

# Volume Analysis
VOLUME_MA_PERIOD = 20         # Volume moving average
MIN_VOLUME_RATIO = 0.3        # Minimum volume for entry
```

### Timing Parameters
```python
# Trading Hours
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"
SQUARE_OFF_TIME = "15:20"

# Session Adjustments
OPENING_HOUR_PATIENCE = 1.5x   # More patient at open
CLOSING_HOUR_PATIENCE = 1.3x   # More patient at close
LUNCH_HOUR_PATIENCE = 0.8x     # Less patient at lunch

# Strategy Selection
SAC_UPDATE_INTERVAL = 30s       # SAC agent frequency
STRATEGY_ROTATION = True        # Enable strategy rotation
RANDOM_EXPLORATION = True       # Exploration mode (no trained model)
```

---

## 📊 Monitoring & Logging

### Key Metrics Tracked
```python
# Performance Metrics
Total P&L
Win Rate
Average Win/Loss
Profit Factor
Sharpe Ratio
Max Drawdown

# Trading Metrics
Total Trades
Daily Trade Count
Average Holding Period
Slippage Analysis
Execution Quality

# Risk Metrics
Daily Loss Utilization
Position Correlation
Regime Distribution
Strategy Performance
```

### Log Levels & Messages
```python
# Entry Logs
"🔍 execute_signal received - strategy: Gamma Scalping"
"⏳ Signal queued for better entry: NIFTY 26000 CALL"
"✅ Entry timing good: NIFTY 26000 CALL - price +0.1% from VWAP"

# Exit Logs
"🎯🎯🎯 TP3 TARGET HIT for NIFTY! Entry: ₹150.25 → Current: ₹180.50"
"🔔 TP3 EXIT EXECUTED: Position abc123 will be closed immediately"
"✅ Trailing stop loss hit for NIFTY - Profit protected!"

# Risk Logs
"❌ Risk manager blocked signal 1: Gamma Scalping NIFTY"
"⚠️ Daily loss limit approaching: 85% utilized"
"🛑 Trading halted for day - daily loss limit exceeded"

# System Logs
"🔄 SAC selected strategy: VWAP Deviation (score: 85/100)"
"📊 Market regime changed: TRENDING_MODERATE_VOL → HIGH_VOLATILITY"
"🧹 Cleaned up corrupted position abc123 from database"
```

### Dashboard Metrics
```python
# Real-time Display
Open Positions (count & P&L)
Daily Performance
Regime Status
Active Strategy
Risk Utilization
Recent Signals
Trade History
```

---

## 🔄 Complete Trade Example

### Scenario: NIFTY 26000 CALL - Gamma Scalping Strategy

#### 1. Market Conditions
```
Time: 10:30 AM
NIFTY Spot: 26,150
VIX: 18.5 (moderate volatility)
Regime: TRENDING_MODERATE_VOL
VWAP: 26,120
```

#### 2. Signal Generation
```
Strategy: Gamma Scalping
Signal: BUY NIFTY 26000 CALL
Entry Price: ₹150.25
Targets: TP1=165, TP2=175, TP3=180
Stop Loss: ₹135
RR Ratio: 2.0
Signal Strength: 75/100
```

#### 3. Entry Timing Check
```
Current Option Price: ₹152.50
VWAP Deviation: +1.0% (extended above VWAP)
Decision: WAIT for pullback
Action: Add to pending queue
Wait Time: 120 seconds
```

#### 4. Entry Execution (After 45 seconds)
```
Option Price: ₹149.75 (pulled back to VWAP)
Decision: ENTER NOW
Order: BUY 100 lots @ ₹149.75
Position Size: ₹14,975
Risk: 1% of capital (₹1,000)
```

#### 5. Position Monitoring
```
10:45 AM: Price ₹155.50 (+3.8% P&L)
11:15 AM: Price ₹165.25 (TP1 hit!)
├── Scale out 40 lots (40%)
├── P&L locked: ₹620
├── SL moved to ₹150.75 (breakeven + 0.5%)
└── Remaining: 60 lots

11:45 AM: Price ₹175.50 (TP2 hit!)
├── Scale out 35 lots (35%)
├── P&L locked: ₹1,340 total
├── SL moved to ₹165.75 (TP1 + buffer)
└── Remaining: 25 lots

12:30 PM: Price ₹180.25 (TP3 hit!)
├── Close remaining 25 lots (25%)
├── Final P&L: ₹1,887 total
└── Position closed
```

#### 6. Trade Summary
```
Entry: ₹149.75
Exit: ₹180.25
Profit: ₹30.50 per lot (20.4%)
Total Profit: ₹1,887
Holding Time: 2 hours
Exit Reason: TP3_TARGET
```

---

## 🎯 Key Success Factors

### 1. **Patience in Entry**
- Wait for VWAP pullbacks instead of chasing
- Dynamic timeout based on market conditions
- Quality scoring for signal prioritization

### 2. **Disciplined Scaling**
- Consistent TP1/TP2/TP3 profit taking
- Regime-based exit adjustments
- Trailing stop for profit protection

### 3. **Adaptive Risk Management**
- Dynamic position sizing by regime
- Daily loss limits with runway
- Correlation controls

### 4. **Strategy Flexibility**
- SAC agent selects optimal strategy
- Regime-specific adjustments
- Continuous learning and adaptation

### 5. **Comprehensive Monitoring**
- Real-time P&L tracking
- Detailed exit reason logging
- Performance analytics

---

## 📋 Quick Reference

### Entry Checklist
- [ ] Signal generated by selected strategy
- [ ] VWAP deviation within acceptable range
- [ ] Momentum confirmation (MACD/RSI)
- [ ] Volume profile sufficient
- [ ] Risk manager approval
- [ ] Position size calculated
- [ ] Order executed

### Exit Checklist
- [ ] TP1/TP2/TP3 levels monitored
- [ ] Trailing stop updates applied
- [ ] Stop loss levels respected
- [ ] Exit reason logged
- [ ] Position closed
- [ ] Performance recorded

### Daily Routine
- [ ] Market regime assessment
- [ ] Risk limits check
- [ ] Strategy performance review
- [ ] P&L analysis
- [ ] System health check

---

*This guide represents the complete trading system architecture and operational parameters as of November 27, 2025. All parameters are actively tested and optimized for the Indian options market.*
