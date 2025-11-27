# Trading System Strategy Overview

## Total Strategies: 20 + ML Model

All strategies analyze **option chain data** (strikes, PCR, OI, IV, Greeks) to generate trading signals.

---

## 📊 Strategy Categories

### 1. **Open Interest (OI) Analysis** (4 strategies)
Located in: `backend/strategies/oi_strategy.py`, `pattern_strategies.py`

1. **OIStrategy** - Analyzes Call/Put OI concentrations at strikes
2. **HiddenOIStrategy** - Detects institutional accumulation patterns
3. **LiquidityHuntingStrategy** - Identifies liquidity sweeps at key strikes
4. **MaxPainStrategy** (`maxpain_strategy.py`) - Calculates max pain strike from OI distribution

**Option Chain Data Used:**
- Call OI per strike
- Put OI per strike  
- OI changes across strikes
- Strike distribution

---

### 2. **Market Sentiment** (3 strategies)
Located in: `backend/strategies/pcr_strategy.py`, `institutional_strategies.py`

5. **PCRStrategy** - Put-Call Ratio analysis
   - Bullish: PCR > 1.3 (puts heavy)
   - Bearish: PCR < 0.7 (calls heavy)

6. **VIXMeanReversionStrategy** - VIX-based fear/greed signals

7. **SentimentNLPStrategy** (`analytics_strategies.py`) - News sentiment analysis

**Option Chain Data Used:**
- Total Call OI
- Total Put OI
- PCR calculation
- IV levels

---

### 3. **Greeks & Volatility** (3 strategies)
Located in: `backend/strategies/microstructure_strategies.py`, `iv_skew_strategy.py`

8. **GreeksPositioningStrategy** - Delta/Gamma exposure analysis

9. **IVSkewStrategy** - Implied Volatility skew across strikes
   - Detects call/put skew anomalies
   - IV premium opportunities

10. **GammaScalpingStrategy** (`institutional_strategies.py`) - Gamma hedging signals

**Option Chain Data Used:**
- Delta, Gamma, Theta, Vega per strike
- IV per strike
- IV skew curve
- ATM vs OTM IV spread

---

### 4. **Institutional Footprints** (3 strategies)
Located in: `backend/strategies/institutional_strategies.py`, `microstructure_strategies.py`

11. **InstitutionalFootprintStrategy** - Large block order detection

12. **OrderFlowStrategy** - Order flow imbalance tracking

13. **GapAndGoStrategy** - Gap up/down momentum plays

**Option Chain Data Used:**
- OI changes (institutional build-up)
- Volume vs OI ratio
- Bid-ask spreads
- Large orders at strikes

---

### 5. **Multi-Leg Spreads** (3 strategies)
Located in: `backend/strategies/spread_strategies.py`

14. **IronCondorStrategy** - Range-bound markets
   - Sells OTM Call + Put
   - Buys further OTM protection

15. **ButterflyStrategy** - Neutral outlook, low IV
   - Exploits strike clustering

16. **StraddleStrangleStrategy** - High volatility plays
   - ATM straddle (same strike)
   - Strangle (different strikes)

**Option Chain Data Used:**
- Strike prices
- IV across strikes
- OI at key strikes
- Premium collection opportunities

---

### 6. **Intraday Patterns** (3 strategies)
Located in: `backend/strategies/pattern_strategies.py`, `support_resistance_strategy.py`

17. **TimeOfDayStrategy** - Opening/closing range breakouts

18. **MultiLegArbitrageStrategy** - Mispricing between strikes/expiries

19. **SupportResistanceStrategy** - Technical S/R levels with OI confirmation

**Option Chain Data Used:**
- Strike prices as S/R levels
- OI walls (heavy resistance/support)
- Intraday strike liquidity

---

### 7. **Cross-Asset Analysis** (1 strategy)
Located in: `backend/strategies/analytics_strategies.py`

20. **CrossAssetCorrelationStrategy** - NIFTY vs BANKNIFTY divergence
   - Detects relative strength/weakness
   - Cross-index arbitrage

**Option Chain Data Used:**
- NIFTY option chain
- SENSEX option chain
- PCR comparison
- IV spread between indices

---

## 🤖 ML Model (XGBoost)
Located in: `backend/ml/model_manager.py`

**Purpose:** Scores all strategy signals (0-1 probability)

**Features Used from Option Chain:**
- Signal strength (from strategy)
- Entry price
- **PCR** (Put-Call Ratio)
- Spot price
- **IV** (Implied Volatility)
- **OI** (Open Interest)
- Greeks (Delta, Gamma, Theta, Vega)

**Training Data:** Historical trades with outcomes (win/loss)

**Model:** XGBoost Classifier
- Min 100 samples to train
- 80/20 train-test split
- F1 score evaluation

---

## 📈 Complete Data Flow

```
1. Upstox API
   └─> Option Chain (PCR, Call/Put OI, Strikes, IV, Greeks)
        ↓
2. Market Data Service (backend/api/market_data.py)
   └─> Fetches & structures option chain data
        ↓
3. Strategy Engine (backend/strategies/strategy_engine.py)
   └─> Runs all 20 strategies in parallel
   └─> Each strategy analyzes option chain strikes
   └─> Generates signals with strength scores (0-100)
        ↓
4. ML Model Manager (backend/ml/model_manager.py)
   └─> Extracts features (PCR, IV, OI, Greeks)
   └─> XGBoost scores signals (0-1 probability)
        ↓
5. Risk Manager (backend/execution/risk_manager.py)
   └─> Validates position limits
   └─> Checks portfolio exposure
        ↓
6. Order Manager (backend/execution/order_manager.py)
   └─> Executes paper/live trades
   └─> Creates Trade records in database
        ↓
7. Dashboard Display
   └─> Shows today's trades with P&L
   └─> Real-time updates every 2 seconds
```

---

## 🎯 Key Strategy Features

### All Strategies Consume Option Chain Data:
✅ **PCR** (Put-Call Ratio) - Sentiment indicator  
✅ **Call OI per Strike** - Resistance levels  
✅ **Put OI per Strike** - Support levels  
✅ **IV per Strike** - Premium pricing  
✅ **Greeks** (Delta, Gamma, Theta, Vega) - Risk metrics  
✅ **Strike Prices** - Entry/exit targets  
✅ **Expiry Dates** - Time decay analysis  

### Strategy Execution:
- Run in **parallel** every 30 seconds (trading loop)
- Each generates 0-N signals per cycle
- Signals scored by ML model
- Top signals executed if risk allows
- All trades logged to database

### Dashboard Visibility:
- **Market Overview:** NIFTY, SENSEX, VIX, breadth
- **Option Chain:** PCR, Call/Put OI, next expiry
- **Sector Performance:** 6 major sectors
- **Today's Trades:** Entry/exit, P&L, strategy used
- **Open Positions:** Live MTM tracking
- **Risk Metrics:** Exposure, win rate, max drawdown

---

## 📝 Strategy Configuration

All strategies inherit from `BaseStrategy` with:
- **Weight** (importance 0-100)
- **Cooldown Period** (prevents overtrading)
- **Signal Rate Limiting**
- **Target/Stop Loss Calculation**

Configured in: `backend/strategies/strategy_engine.py`

---

**Last Updated:** November 12, 2025
