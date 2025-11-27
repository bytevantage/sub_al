# 📋 Complete Strategy Reference Guide

## All 20 Strategies - Quick Reference

| # | Strategy Name | Weight | File | Description |
|---|---------------|--------|------|-------------|
| 1 | **Order Flow Imbalance** | 85 | `microstructure_strategies.py` | Detects 2:1+ buy/sell pressure, minimum 10K volume |
| 2 | **OI Change Patterns** | 80 | `oi_strategy.py` | Buildup (3+ strikes 15%+ OI) / Unwinding detection |
| 3 | **Institutional Footprint** | 80 | `institutional_strategies.py` | Tracks ₹5L+ block trades, 2:1 CALL/PUT ratio |
| 4 | **PCR Analysis** | 75 | `pcr_strategy.py` | Bullish <0.7, Bearish >1.3, Extreme 0.5/1.5 |
| 5 | **Support/Resistance from OI** | 75 | `support_resistance_strategy.py` | 2x avg OI concentration, within 0.5% proximity |
| 6 | **Gap & Go** | 75 | `microstructure_strategies.py` | Opening gap 0.5%+, first 15 minutes |
| 7 | **Hidden OI Patterns** | 75 | `pattern_strategies.py` | Stealth accumulation: 10%+ OI, <0.2% price change |
| 8 | **Greeks-Based Positioning** | 70 | `microstructure_strategies.py` | High gamma exposure, negative gamma hedge pressure |
| 9 | **IV Skew Analysis** | 70 | `iv_skew_strategy.py` | PUT/CALL ratio >1.5 or <0.67, 3%+ IV difference |
| 10 | **Time-of-Day Patterns** | 70 | `pattern_strategies.py` | Opening range (9:15-9:45), Mid-session (11-2), Closing (2:30-3:20) |
| 11 | **Liquidity Hunting** | 70 | `pattern_strategies.py` | Stop-loss sweep & 0.3% reversal detection |
| 12 | **Straddle/Strangle** | 70 | `spread_strategies.py` | Long <15% IV, Short >40% IV |
| 13 | **Iron Condor Setup** | 65 | `spread_strategies.py` | High IV (60%+), range-bound, 70% OTM probability |
| 14 | **VIX Mean Reversion** | 65 | `institutional_strategies.py` | 2 std dev from mean (16), z-score extremes |
| 15 | **Max Pain Theory** | 65 | `maxpain_strategy.py` | Distance >2% from max pain level |
| 16 | **Cross-Asset Correlations** | 65 | `analytics_strategies.py` | Bank Nifty divergence 1.5%+, USD/INR inverse correlation |
| 17 | **Butterfly Spread** | 60 | `spread_strategies.py` | Price within 0.3% of max pain, tight range |
| 18 | **Gamma Scalping** | 60 | `institutional_strategies.py` | Gamma >0.03, IV >15%, delta-neutral |
| 19 | **Sentiment Analysis (NLP)** | 60 | `analytics_strategies.py` | Sentiment score ±0.6, 70%+ confidence, 5+ sources |
| 20 | **Multi-Leg Arbitrage** | 55 | `pattern_strategies.py` | Put-call parity violations, 2%+ edge |

---

## Strategy Activation Logic

### **Tier 1: High Priority (80-85)** - Always Active
- Execute first when conditions met
- Highest capital allocation
- Strongest signals required: 85+ strength

### **Tier 2: High-Medium (70-79)** - Primary Strategies
- Core strategy set
- Good risk/reward
- Signal threshold: 75+ strength

### **Tier 3: Medium (60-69)** - Specialized
- Specific market conditions
- Complementary signals
- Signal threshold: 70+ strength

### **Tier 4: Lower (50-59)** - Opportunistic
- Rare setups
- Risk-controlled entries
- Signal threshold: 65+ strength

---

## Signal Generation Flow

```
Market Data → All 20 Strategies (Parallel Analysis)
    ↓
Generated Signals (with strength 0-100)
    ↓
ML Model Scoring (enhancement)
    ↓
Filter by Risk Manager (can_take_trade)
    ↓
Execute Top Signals (highest strength first)
```

---

## Key Thresholds Summary

| Strategy | Bullish Trigger | Bearish Trigger |
|----------|----------------|-----------------|
| PCR | <0.7 | >1.3 |
| OI Change | CALL unwinding / PUT buildup | CALL buildup / PUT unwinding |
| Order Flow | Buy:Sell >2:1 | Sell:Buy >2:1 |
| IV Skew | PUT/CALL >1.5 | PUT/CALL <0.67 |
| VIX | >2 std above mean | N/A (hedge) |
| Max Pain | Price >2% below | Price >2% above |
| Gap | Gap up 0.5%+ | Gap down 0.5%+ |
| Institutional | CALL value 2x PUT | PUT value 2x CALL |

---

## File Structure

```
backend/strategies/
├── strategy_base.py                    # Base class, Signal dataclass
├── strategy_engine.py                  # Orchestrator (initializes all 20)
│
├── pcr_strategy.py                     # PCR Analysis
├── oi_strategy.py                      # OI Change Patterns
├── maxpain_strategy.py                 # Max Pain Theory
├── support_resistance_strategy.py      # S/R from OI
├── iv_skew_strategy.py                 # IV Skew Analysis
│
├── spread_strategies.py                # Iron Condor, Butterfly, Straddle/Strangle
├── microstructure_strategies.py        # Gap & Go, Greeks, Order Flow
├── institutional_strategies.py         # Gamma Scalping, Institutional, VIX
├── pattern_strategies.py               # Time-of-Day, Arbitrage, Hidden OI, Liquidity
└── analytics_strategies.py             # Sentiment NLP, Cross-Asset
```

---

## Strategy Configuration (config.yaml)

```yaml
strategy_weights:
  order_flow_imbalance: 85
  oi_change_patterns: 80
  institutional_footprint: 80
  pcr_analysis: 75
  support_resistance_oi: 75
  gap_and_go: 75
  hidden_oi_patterns: 75
  greeks_positioning: 70
  iv_skew: 70
  time_of_day: 70
  liquidity_hunting: 70
  straddle_strangle: 70
  iron_condor: 65
  vix_mean_reversion: 65
  max_pain: 65
  cross_asset_correlation: 65
  butterfly: 60
  gamma_scalping: 60
  sentiment_nlp: 60
  multi_leg_arbitrage: 55
```

---

## Performance Tracking

Each strategy automatically logs:
- Total signals generated
- Signals taken (vs filtered by risk)
- Win rate
- Average P&L per trade
- Average signal strength
- ML model confidence

Access via:
```bash
curl http://localhost:8000/api/trades/strategy-performance?strategy_name=Order%20Flow%20Imbalance
```

---

## Testing Individual Strategies

```python
from backend.strategies.oi_strategy import OIStrategy

strategy = OIStrategy(weight=80)

market_data = {
    "spot_price": 19500,
    "option_chain": {...},
    # ... other data
}

signals = await strategy.analyze(market_data)
for signal in signals:
    print(f"{signal.direction} at {signal.strike} - Strength: {signal.strength}")
```

---

## Strategy Cooldown

- Each strategy has 5-minute cooldown after generating signal
- Prevents signal spam
- Configurable in `strategy_base.py`

---

## Disabling Strategies

In `strategy_engine.py`:
```python
# Disable a strategy
strategy.enabled = False

# Or comment out during initialization
# self.strategies.append(SentimentNLPStrategy(weight=60))
```

---

## Adding New Strategies

1. Create new file in `backend/strategies/`
2. Inherit from `BaseStrategy`
3. Implement `async def analyze(self, market_data: Dict) -> List[Signal]`
4. Import in `strategy_engine.py`
5. Add to `_initialize_strategies()` with weight
6. Update config.yaml weights

---

**All 20 strategies are production-ready and integrated! 🚀**
