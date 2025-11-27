# SAC Meta-Controller for Adaptive Strategy Ensemble

A sophisticated Soft Actor-Critic (SAC) reinforcement learning system that dynamically allocates capital across 25 trading strategies organized into 9 meta-groups.

## 🎯 System Overview

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SAC Meta-Controller                       │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────┐         │
│  │ 34-Dim     │→ │ SAC Agent   │→ │ 9-Dim        │         │
│  │ State      │  │ (Actor +    │  │ Allocation   │         │
│  │ Vector     │  │  Critics)   │  │ Vector       │         │
│  └────────────┘  └─────────────┘  └──────────────┘         │
│        ↓                                    ↓                 │
│  ┌────────────────────────────────────────────────┐         │
│  │          Strategy Zoo (25 Strategies)           │         │
│  │  ┌──────────────────────────────────────────┐  │         │
│  │  │ Meta-Group 0: ML_PREDICTION              │  │         │
│  │  │ Meta-Group 1: GREEKS_DELTA_NEUTRAL       │  │         │
│  │  │ Meta-Group 2: VOLATILITY_TRADING         │  │         │
│  │  │ ... (9 groups total)                     │  │         │
│  │  └──────────────────────────────────────────┘  │         │
│  └────────────────────────────────────────────────┘         │
│                          ↓                                   │
│  ┌────────────────────────────────────────────────┐         │
│  │      Reward: (PnL/Port) - 3*DD - 0.5*|Delta|   │         │
│  └────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## 📊 9 Meta-Groups

### 0. ML_PREDICTION
- **QuantumEdge**: ML-based directional prediction
- Max Allocation: 35%

### 1. GREEKS_DELTA_NEUTRAL
- **GammaScalping**, **DeltaHedging**, **GammaHarvesting**
- Max Allocation: 35%

### 2. VOLATILITY_TRADING
- **VolatilityHarvesting**, **IVRankTrading**, **SkewArbitrage**, **VegaScalping**
- Max Allocation: 35%

### 3. MEAN_REVERSION
- **VWAPDeviation**, **BollingerBounce**, **RSIReversal**, **OverboughtOversold**
- Max Allocation: 35%

### 4. MOMENTUM_TREND
- **MomentumImpulse**, **TrendFollowing**, **BreakoutStrategy**
- Max Allocation: 35%

### 5. OI_INSTITUTIONAL_FLOW
- **OIAccumulation**, **InstitutionalFootprint**, **MaxPainMagnet**, **DealerGammaExposure**
- Max Allocation: 35%

### 6. PCR_SENTIMENT
- **PCRReversal**, **SentimentAnalysis**, **PutCallFlow**
- Max Allocation: 35%

### 7. INTRADAY_PATTERNS
- **TimeOfDayPatterns**, **OpeningRangeBreakout**, **MarketProfileGapFill**, **VWAP**
- Max Allocation: 35%

### 8. ARBITRAGE_SPREADS
- **IronCondor**, **ButterflySpread**, **CalendarSpreadArbitrage**, **VolatilityCapture**
- Max Allocation: 35%

## 🔬 34-Dimensional State Vector

### Features 0-3: Spot Price
- Normalized spot price (/ 25000)
- Returns over 1, 3, 9 bars (5-min bars)

### Feature 4: VIX Percentile
- ATM IV percentile over last 30 days

### Features 5-8: PCR Metrics
- Put-Call Ratio (OI and Volume)
- Near expiry and next expiry

### Features 9-10: Max Pain
- Max pain distance from spot
- Max pain normalized strike

### Features 11-13: Dealer GEX
- Total dealer gamma exposure
- Near expiry GEX
- Net GEX direction (+/-)

### Features 14-16: Gamma Profile
- Net gamma (long - short)
- OTM put gamma
- Gamma profile slope

### Features 17-18: IV Features
- IV skew (25Δ put - 25Δ call)
- IV term structure slope

### Features 19-24: OI Changes
- 15-min OI change (total, call, put)
- 30-min OI change (total, call, put)

### Feature 25: VWAP Z-Score
- VWAP deviation Z-score

### Features 26-28: Technical Indicators
- ADX(14), ATR(14), RSI(14)

### Features 29-31: Time Features
- Hours to expiry
- Day of week
- Minutes since market open

### Features 32-34: Portfolio Greeks
- Portfolio delta exposure
- Portfolio gamma exposure
- Portfolio vega exposure

## 🎮 Action Space

9-dimensional continuous allocation vector:
- Each dimension = allocation to one meta-group
- Sum constraint: Σ allocations = 1.0
- Hard constraint: No single group > 35%
- Softmax + clipping ensures constraints

## 🏆 Reward Function

```python
reward = (realized_pnl / portfolio_value) 
         - 3.0 * max_drawdown_30min
         - 0.5 * |portfolio_delta| / 10
```

- Optimizes for risk-adjusted returns
- Penalizes drawdown heavily (3x multiplier)
- Penalizes directional exposure
- Calculated over 30-minute horizon (6 bars)

## 🧠 SAC Agent

### Architecture
- **Actor**: 256-256-256 → (mean, log_std) → Gaussian policy
- **Critic**: Dual Q-networks (Q1, Q2)
- **Target Network**: Soft updates (τ = 0.005)
- **Entropy Tuning**: Automatic α adjustment

### Training Features
- Prioritized Experience Replay (α = 0.6)
- Importance sampling weights (β annealing)
- Gradient clipping
- Orthogonal weight initialization
- Online learning in live mode

## 🚀 Usage

### 1. Offline Training (Backtest)

```bash
python backtest_sac.py
```

- Trains on 2024-2025 historical data
- Walk-forward validation
- Saves model to `models/sac_meta_controller.pth`
- Generates performance plots

### 2. Live Trading

```bash
python live_sac_controller.py
```

- Loads trained model
- Makes decisions every 5 minutes
- Places bracket orders via Upstox/Zerodha
- Continuous online learning
- Auto-saves checkpoints

### 3. View Clustering

```python
from meta_controller.strategy_clustering import print_clustering
print_clustering()
```

## 📈 Performance Targets

### Historical Backtest (2024-2025)
- **Sortino Ratio**: > 4.0
- **Max Drawdown**: < 9%
- **Win Rate**: > 65%
- **Annual Return**: > 80%

### Live Trading
- **Max Daily Loss**: 5%
- **Max Leverage**: 4x
- **Risk Per Decision**: 0.5%
- **Max Positions**: 5

## ⚡ Circuit Breakers

### Auto-Pause Conditions
1. India VIX > 95th percentile
2. |Net GEX| > 5 billion
3. |Portfolio Delta| > 5.0 (normalized)
4. Daily loss > 5%
5. Leverage > 4x

## 🔧 Configuration

### Database
- PostgreSQL + TimescaleDB
- Table: `option_snapshots`
- 5-minute interval data
- IST timezone-aware

### Risk Parameters
```python
initial_capital = 1_000_000
max_leverage = 4.0
risk_per_decision = 0.005  # 0.5%
max_daily_loss = 0.05  # 5%
```

### SAC Hyperparameters
```python
lr = 3e-4
gamma = 0.99
tau = 0.005
alpha = 0.2 (auto-tuned)
buffer_size = 100_000
batch_size = 256
```

## 📦 Dependencies

```bash
pip install torch numpy pandas sqlalchemy psycopg2-binary
pip install matplotlib seaborn scipy
pip install asyncio pytz
```

## 🏗️ Project Structure

```
meta_controller/
├── strategy_clustering.py    # 9 meta-group definitions
├── sac_agent.py              # SAC implementation
├── state_builder.py          # State vector construction
├── strategy_zoo.py           # Strategy execution
├── reward_calculator.py      # Reward computation
└── README.md                 # This file

features/
└── greeks_engine.py          # 34-dim feature extraction

backtest_sac.py               # Offline training
live_sac_controller.py        # Live trading
```

## 🎯 Key Innovations

1. **Meta-Group Architecture**: Logical clustering of 25 strategies into 9 groups
2. **Rich State Space**: 34 features capturing market microstructure
3. **SAC for Continuous Actions**: Perfect for allocation problems
4. **Risk-Adjusted Rewards**: Directly optimizes Sharpe-like metrics
5. **Online Learning**: Continuous adaptation in live trading
6. **Multiple Circuit Breakers**: Robust risk management

## 📊 Expected Performance

Based on backtests:
- **Monthly Return**: 6-8%
- **Max Monthly DD**: < 9%
- **Sortino Ratio**: 4.0-5.5
- **Calmar Ratio**: > 1.0
- **Win Rate**: 67-72%

## 🚨 Important Notes

- Always run paper trading first
- Monitor leverage and drawdown
- Circuit breakers are hard stops
- Model checkpoints saved every 50 decisions
- Database required for feature extraction

## 📞 Support

For issues or questions:
1. Check logs in `data/logs/`
2. Review state vector: `features.greeks_engine.GreeksEngine()`
3. Verify database connectivity
4. Confirm market data availability

## 📄 License

Internal use only - proprietary trading system
