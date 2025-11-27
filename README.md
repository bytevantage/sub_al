# 🚀 Advanced Intraday Options Trading System

A production-ready, ML-powered algorithmic options trading platform for **Nifty and Sensex** with real-time analysis, automated execution, reconciliation, and professional analytics dashboard.

> **Supported Indices**: Currently supports **Nifty 50** and **Sensex** indices only. BankNifty support is not yet implemented.

## 📋 Table of Contents

- [Features](#features)
- [System Architecture](#system-architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Trading Strategies](#trading-strategies)
- [API Documentation](#api-documentation)
- [Dashboard](#dashboard)
- [Deployment](#deployment)

## ✨ Features

### Core Capabilities
- **20 Trading Strategies** - PCR Analysis, Max Pain, OI Patterns, Greeks, Order Flow, and more
  - **Implementation Status**: Varies by strategy (see Trading Strategies section)
  - High-priority strategies (Order Flow, OI Patterns, Reversal Detection) are fully implemented
- **ML-Powered Signals** - XGBoost/LightGBM models with incremental learning and technical indicators
- **Real-Time Execution** - Sub-second order placement and monitoring
- **Risk Management** - Dynamic stop-loss, position sizing, daily limits, correlation analysis
- **Reversal Detection** - Smart exit logic based on market conditions
- **Trade Reconciliation** - Automated broker statement comparison and discrepancy detection
- **Analytics Dashboard** - Comprehensive performance analytics with REST API endpoints
- **Paper Trading** - Test strategies without risk
- **Professional Dashboard** - 4-panel real-time trading interface

### Technical Features
- FastAPI backend with WebSocket streaming
- PostgreSQL + TimescaleDB for time-series data
- Redis caching for real-time performance
- Docker-based deployment
- Comprehensive logging and monitoring
- Backtesting engine with performance analytics
- Technical indicators (RSI, MACD, Bollinger Bands, ATR, correlations)
- Daily trade reconciliation with broker statements
- Advanced analytics API for dashboards and reporting

## 🏗️ System Architecture

```
srb-algo/
├── backend/                    # Python FastAPI backend
│   ├── api/                   # API endpoints
│   │   ├── analytics.py      # Analytics endpoints (NEW)
│   │   └── ...               # Other API routers
│   ├── core/                  # Core utilities
│   │   ├── config.py         # Configuration management
│   │   ├── logger.py         # Logging system
│   │   └── upstox_client.py  # Upstox API wrapper
│   ├── data/                  # Data layer
│   │   ├── market_data.py    # Market data manager (with technical indicators)
│   │   ├── technical_indicators.py  # Technical indicator calculations (NEW)
│   │   ├── websocket_feed.py # WebSocket streaming
│   │   └── database.py       # Database models
│   ├── strategies/            # Trading strategies
│   │   ├── strategy_base.py  # Base strategy class
│   │   ├── pcr_strategy.py   # PCR-based strategy
│   │   ├── oi_strategy.py    # OI-based strategy
│   │   ├── greeks_strategy.py # Greeks-based strategy
│   │   └── strategy_engine.py # Strategy orchestrator
│   ├── ml/                    # Machine learning
│   │   ├── features.py       # Feature engineering
│   │   ├── models.py         # ML models
│   │   ├── trainer.py        # Model training
│   │   └── model_manager.py  # Model lifecycle
│   ├── execution/             # Order execution
│   │   ├── order_manager.py  # Order management
│   │   ├── position_tracker.py # Position tracking
│   │   ├── risk_manager.py   # Risk management
│   │   └── paper_trading.py  # Paper trading simulator
│   ├── jobs/                  # Background jobs
│   │   └── reconciliation_job.py  # Trade reconciliation (NEW)
│   ├── utils/                 # Utilities
│   │   ├── greeks.py         # Black-Scholes calculations
│   │   ├── indicators.py     # Technical indicators
│   │   └── helpers.py        # Helper functions
│   └── main.py                # Application entry point
│
├── frontend/                   # React TypeScript dashboard
│   ├── src/
│   │   ├── components/       # React components
│   │   │   ├── SignalMonitor.tsx
│   │   │   ├── OptionChainHeatmap.tsx
│   │   │   ├── ChartPanel.tsx
│   │   │   └── PerformanceMetrics.tsx
│   │   ├── hooks/            # Custom hooks
│   │   ├── services/         # API services
│   │   └── App.tsx           # Main app component
│   └── package.json
│
├── config/                     # Configuration files
│   ├── config.yaml           # Main configuration
│   └── upstox_token.json     # Upstox access token
│
├── models/                     # ML models (persistent storage)
│   └── model_v1.pkl
│
├── data/                       # Data storage
│   ├── logs/                 # Application logs
│   ├── trades/               # Trade history
│   └── historical/           # Historical market data
│
├── docker/                     # Docker configurations
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
│
├── tests/                      # Test suite
│   ├── test_strategies.py
│   ├── test_execution.py
│   └── test_ml.py
│
├── docs/                       # Documentation
│   ├── API.md                # API documentation
│   ├── STRATEGIES.md         # Strategy details
│   ├── DEPLOYMENT.md         # Deployment guide
│   └── USER_MANUAL.md        # User manual
│
├── requirements.txt            # Python dependencies
├── .env.example               # Environment template
├── upstox_auth_working.py     # Token generation script
└── README.md                  # This file
```

### Key Architecture Components

**Market Data Layer**
- Real-time price feeds with WebSocket streaming
- Technical indicators (RSI, MACD, Bollinger Bands, ATR)
- Price history tracking for indicator calculations
- Multi-instrument correlation analysis

**Strategy Engine**
- 20 trading strategies with configurable weights
- ML-powered signal generation with 100+ features
- Signal aggregation and confidence scoring
- Strategy performance tracking

**Execution Layer**
- Order management with retry logic
- Position tracking with P&L calculation
- Dynamic risk management and stop-loss
- Paper trading simulation

**Analytics & Reconciliation**
- Daily trade reconciliation with broker statements
- Performance analytics API endpoints
- Drawdown analysis and equity curve tracking
- Strategy-level breakdown and heatmaps

**Data Persistence**
- PostgreSQL for trade history and positions
- TimescaleDB for time-series market data
- Redis for real-time caching
- ML model persistence

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+
- Docker & Docker Compose (optional)
- Upstox Pro account with API access

### Step 1: Generate Upstox Token

```bash
# Run the authentication script
python upstox_auth_working.py

# Token will be saved to ~/Algo/upstoxtoken.json
# Copy it to the project config directory
cp ~/Algo/upstoxtoken.json config/upstox_token.json
```

### Step 2: Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies (optional)
cd frontend
npm install
cd ..
```

### Step 3: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env file
nano .env
```

Configure the following:
```env
MODE=paper                    # Start with paper trading
INITIAL_CAPITAL=100000
RISK_PERCENT=3
MIN_SIGNAL_STRENGTH=75
```

### Step 4: Set Up Database (Optional for basic usage)

```bash
# Using Docker
docker-compose up -d postgres redis

# Or install locally
# PostgreSQL and Redis setup instructions in docs/DEPLOYMENT.md
```

### Step 5: Run the System

```bash
# Start the trading system
python backend/main.py

# The API will be available at http://localhost:8000
# Dashboard at http://localhost:3000 (if frontend is running)
```

### Step 6: Monitor Trading

```bash
# View logs
tail -f data/logs/trading_*.log

# Check API health
curl http://localhost:8000/api/health

# View signals
curl http://localhost:8000/api/signals
```

## ⚙️ Configuration

### Main Configuration (`config/config.yaml`)

```yaml
trading:
  mode: "paper"              # paper or live
  initial_capital: 100000
  max_positions: 5
  signal_cooldown_seconds: 300

risk:
  daily_loss_limit_percent: 3
  per_trade_risk_percent: 1
  min_signal_strength: 75

profit_targets:
  base_target_percent: 10
  strong_signal_target_percent: 30
  high_volatility_multiplier: 1.5
```

### Strategy Weights

Adjust strategy importance in `config/config.yaml`:

```yaml
strategy_weights:
  order_flow_imbalance: 85      # Highest priority
  oi_change_patterns: 80
  pcr_analysis: 75
  institutional_footprint: 75
  reversal_detection: 90        # For exits
  max_pain_theory: 65
  # ... more strategies
```

## 📊 Trading Strategies

> **Note**: Strategy implementation status varies. Core strategies are fully implemented, while some specialized strategies are in development or planned for future releases.

### High-Priority Strategies (Fully Implemented)

1. **Order Flow Imbalance (85%)** - Detects institutional buying/selling
2. **OI Change Patterns (80%)** - Identifies buildup/unwinding
3. **PCR Analysis (75%)** - Put-Call Ratio sentiment
4. **Institutional Footprint (75%)** - Large order tracking
5. **Reversal Detection (90%)** - Smart exit signals

### Medium-Priority Strategies (Implementation Status: Varies)

6. Max Pain Theory - Partially implemented
7. IV Skew Analysis - In development
8. Gamma Scalping - Planned
9. VIX Mean Reversion - Planned
10. Greeks-Based Positioning - Core implementation complete

### Supporting Strategies (Implementation Status: Varies)

11. Support/Resistance from OI - Partially implemented
12. Gap & Go Strategy - Planned
13. Iron Condor Detection - Planned
14. Butterfly Spread Detection - Planned
15. Straddle/Strangle Opportunities - Planned
16. Time-of-Day Patterns - Partially implemented
17. Multi-Leg Arbitrage - Planned
18. Sentiment Analysis (NLP) - Planned
19. Cross-Asset Correlations - Core implementation complete
20. Liquidity Hunting - Planned

### Technical Indicators (Fully Implemented)

All strategies have access to comprehensive technical indicators:
- **RSI (Relative Strength Index)** - 14-period default, overbought/oversold detection
- **MACD (Moving Average Convergence Divergence)** - 12/26/9 parameters with histogram
- **Bollinger Bands** - 20-period SMA with 2σ bands, width and %B calculation
- **ATR (Average True Range)** - 14-period volatility measurement
- **Returns & Volatility** - Rolling calculations for risk analysis
- **Correlations** - Multi-instrument correlation (20-period rolling)
- **Feature Vectors for ML** - Combined indicators with time-based features

## 🤖 Machine Learning

### Model Training

```bash
# Train models from historical data
python backend/ml/trainer.py --data data/historical/ --output models/

# Models automatically retrain:
# - Daily at 3:30 PM (after market close)
# - Every 20 trades (incremental learning)
```

### Feature Engineering

The ML system uses 100+ features:
- **Price-based**: Returns, volatility, momentum
- **Volume**: Volume ratios, VWAP deviation
- **OI**: OI changes, PCR, max pain distance
- **Greeks**: Delta, gamma, theta, vega
- **Technical Indicators**: RSI, MACD, Bollinger Bands, ATR
- **Order Flow**: Bid-ask spread, order imbalance
- **Time-based**: Hour of day, minutes to expiry, day of week
- **Correlations**: Multi-instrument correlation metrics

### Technical Indicators Integration

The system automatically calculates and updates technical indicators:
```python
# Technical indicators are calculated on every price update
indicators = {
    'rsi': 45.2,                    # RSI (0-100)
    'macd': {'value': 1.5, 'signal': 1.2, 'histogram': 0.3},
    'bollinger_bands': {
        'upper': 19500, 'middle': 19450, 'lower': 19400,
        'width': 100, 'percent_b': 0.65
    },
    'atr': 85.3,                    # Average True Range
    'returns': 0.012,               # Recent returns
    'volatility': 0.15,             # Rolling volatility
    'correlations': {
        'NIFTY-SENSEX': 0.85       # Cross-instrument correlations
    }
}
```

## 📡 API Documentation

### REST Endpoints

#### Core Trading Endpoints
```http
GET  /api/health                    # Health check
GET  /api/signals                   # Recent signals
GET  /api/positions                 # Current positions
GET  /api/performance               # Performance metrics
GET  /api/option-chain/{symbol}/{expiry}  # Option chain data
POST /api/trading/start             # Start trading
POST /api/trading/stop              # Stop trading
```

#### Analytics Endpoints (NEW)

**P&L Analysis**
```http
GET /api/analytics/pnl?period=day
# Returns: P&L by period (day/week/month/all) with daily breakdown
# Response: { "total_pnl": 5234.50, "daily": [...], "period": "day" }
```

**Drawdown Analysis**
```http
GET /api/analytics/drawdown?limit=100
# Returns: Equity curve with peak/trough analysis
# Response: { "current_drawdown_pct": 2.3, "max_drawdown_pct": 4.1, 
#            "equity_curve": [...], "peak": 105234, "trough": 101000 }
```

**Strategy Heatmap**
```http
GET /api/analytics/strategy-heatmap
# Returns: Strategy x hour performance matrix
# Response: { "heatmap": [[...], [...]], "hours": [9, 10, ...], 
#            "strategies": ["pcr_analysis", "oi_change_patterns", ...] }
```

**Performance Summary**
```http
GET /api/analytics/performance-summary
# Returns: Overall metrics (today/week/month)
# Response: { "today": {...}, "week": {...}, "month": {...}, 
#            "total_trades": 123, "win_rate": 0.68 }
```

**Strategy Breakdown**
```http
GET /api/analytics/strategy-breakdown
# Returns: Per-strategy statistics
# Response: { "strategies": [
#   { "name": "order_flow_imbalance", "trades": 45, "win_rate": 0.72, 
#     "total_pnl": 3245.50, "avg_pnl": 72.12 },
#   ...
# ]}
```

**Trade History**
```http
GET /api/analytics/trade-history?start_date=2024-01-01&end_date=2024-01-31
# Returns: Paginated trade history with filters
# Response: { "trades": [...], "total": 234, "page": 1, "limit": 50 }
```

### WebSocket Endpoint

```javascript
// Connect to real-time feed
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case 'signal':
      console.log('New signal:', data.data);
      break;
    case 'market_data':
      console.log('Market update:', data.data);
      break;
  }
};
```

## 🖥️ Dashboard

### 4-Panel Layout

**Panel 1: Signal Monitor (Top-Left)**
- Live signal feed with strategy names
- ML probability scores
- Entry/exit prices
- One-click execution buttons

**Panel 2: Option Chain Heatmap (Top-Right)**
- Strike prices with OI heatmap
- Call/Put OI comparison
- Max pain indicator
- Support/resistance levels

**Panel 3: Charts & Analytics (Bottom-Left)**
- Real-time 1-minute candles
- PCR overlay
- Volume bars
- Entry/exit markers

**Panel 4: Performance Metrics (Bottom-Right)**
- Live P&L
- Open positions table
- Win rate gauge
- Risk metrics

### Dashboard Features

- Dark mode (default)
- Real-time WebSocket updates
- Customizable layouts
- Sound alerts
- Mobile responsive

## 🐳 Docker Deployment

### Using Docker Compose

```bash
# Build and start all services
docker-compose up -d

# Services included:
# - trading-engine (FastAPI backend)
# - postgres (Database)
# - redis (Cache)
# - frontend (React dashboard)
# - nginx (Reverse proxy)
# - grafana (Monitoring)
```

### Environment Variables for Docker

```bash
# Copy and configure
cp .env.example .env

# Build containers
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f trading-engine

# Stop services
docker-compose down
```

## 🔒 Risk Management

### Position Sizing
- Signal strength weighted (75-95%)
- Max 5 concurrent positions
- Per-trade risk: 1-2% of capital

### Stop Loss
- Dynamic based on ATR
- Trailing stop with reversal detection
- Force close at 3:20 PM

### Daily Limits
- Max loss: 3% of capital
- Auto-pause trading if limit hit
- Position review every 10 seconds

### Correlation Risk Management
- Multi-instrument correlation tracking
- Position adjustment based on correlation thresholds
- Diversification enforcement across strategies

### Trade Reconciliation (NEW)
- **Daily reconciliation at 6:00 PM** - Compares local trades with broker statements
- **Discrepancy detection** - Identifies missing trades, extra trades, P&L mismatches
- **Tolerance thresholds**:
  - P&L: ±₹1.00
  - Price: ±0.5%
- **Automatic alerts** - Notifies on discrepancies via logging system
- **Manual review** - Generates reconciliation reports for audit trail

## 📈 Performance Tracking

### Key Metrics

- **Win Rate**: Target >60%
- **Profit Factor**: Target >2.0
- **Max Drawdown**: Keep <5%
- **Avg Trade Duration**: 15-45 minutes
- **Daily Signals**: 5-8 quality signals

### Monitoring

```bash
# View performance
curl http://localhost:8000/api/performance

# Check positions
curl http://localhost:8000/api/positions

# View analytics summary
curl http://localhost:8000/api/analytics/performance-summary

# Get P&L for today
curl http://localhost:8000/api/analytics/pnl?period=day

# Get drawdown analysis
curl http://localhost:8000/api/analytics/drawdown

# Real-time logs
tail -f data/logs/trading_$(date +%Y%m%d).log
```

### Analytics Dashboard Integration

The analytics endpoints support dashboard visualization:
- **Time-series charts** - Equity curve, daily P&L
- **Heatmaps** - Strategy performance by time of day
- **Summary cards** - Win rate, profit factor, total P&L
- **Strategy comparison** - Side-by-side strategy performance
- **Trade journal** - Detailed trade history with filters

## 🧪 Testing

### Paper Trading

Always start with paper trading:

```python
# In .env or config.yaml
MODE=paper
ENABLE_LIVE_TRADING=false
```

Paper trading runs in parallel with live mode logic but doesn't execute real orders.

### Backtesting

```bash
# Run backtest on historical data
python backend/ml/backtester.py \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --capital 100000 \
  --strategies all
```

## 📚 Additional Documentation

- [API Reference](docs/API.md) - Complete API documentation
- [Strategy Details](docs/STRATEGIES.md) - In-depth strategy explanations
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment
- [User Manual](docs/USER_MANUAL.md) - Complete user guide

## ⚠️ Disclaimer

This trading system is for educational purposes. Always:
- Start with paper trading
- Test thoroughly before live trading
- Understand all risks involved
- Never trade with money you can't afford to lose
- Consult with a financial advisor

**Important Notes**:
- Currently supports **Nifty 50** and **Sensex** indices only
- Strategy implementation status varies (see Trading Strategies section)
- Trade reconciliation requires manual review of discrepancies
- Technical indicators require minimum 20 data points for accurate calculations
- ML models require retraining with sufficient historical data

## 🤝 Contributing

This is a personal trading system. Use at your own risk.

## 📄 License

Private Project - All Rights Reserved

## 🆘 Support

For issues or questions:
1. Check the logs in `data/logs/`
2. Review configuration in `config/config.yaml`
3. Ensure Upstox token is valid
4. Verify all dependencies are installed
5. Check analytics endpoints for performance insights
6. Review reconciliation reports for trade accuracy

---

**Built with ❤️ for algorithmic trading**

**Version**: 2.0.0  
**Last Updated**: January 2025  
**Status**: Production-ready with comprehensive analytics and reconciliation
