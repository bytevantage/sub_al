# Smart Watchlist API Documentation

## Overview
The Smart Watchlist API combines **20+ trading strategies** with **ML predictions** and **option chain analysis** to recommend high-probability profitable strikes.

---

## Endpoints

### 1. Get Recommended Strikes

**GET** `/api/watchlist/recommended-strikes`

Analyzes option chain with all strategies and ML model to recommend best strikes.

#### Query Parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `symbol` | string | `NIFTY` | NIFTY, SENSEX, or BANKNIFTY |
| `min_ml_score` | float | `0.65` | Minimum ML confidence (0-1) |
| `min_strategy_strength` | float | `70.0` | Minimum strategy strength (0-100) |
| `min_strategies_agree` | int | `3` | Minimum strategies that must agree |
| `option_type` | string | `None` | CALL or PUT (or both if None) |

#### Example Request:
```bash
curl "http://localhost:8000/api/watchlist/recommended-strikes?symbol=NIFTY&min_ml_score=0.7&min_strategies_agree=5"
```

#### Response Structure:
```json
{
  "status": "success",
  "timestamp": "2025-11-12T14:30:00",
  "symbol": "NIFTY",
  "filters_applied": {
    "min_ml_score": 0.65,
    "min_strategy_strength": 70.0,
    "min_strategies_agree": 3,
    "option_type": "BOTH"
  },
  "market_context": {
    "spot_price": 25875.80,
    "pcr": 1.31,
    "sentiment": "Bullish",
    "sentiment_reason": "PCR 1.31 indicates Put accumulation",
    "vix": 12.11,
    "vix_status": "Low volatility - Consider buying options",
    "expiry": "2025-11-14",
    "total_call_oi": 94600000,
    "total_put_oi": 123800000
  },
  "analysis_summary": {
    "total_signals_generated": 156,
    "unique_strikes_analyzed": 89,
    "strikes_passed_filters": 12,
    "strategies_active": 20
  },
  "recommended_strikes": [
    {
      "strike": "25900",
      "direction": "CALL",
      "composite_score": 87.5,
      "num_strategies": 8,
      "avg_strength": 82.3,
      "ml_score": 0.85,
      "ml_confidence": 0.92,
      "entry_price": 125.50,
      "target_price": 175.00,
      "stop_loss": 100.00,
      "risk_reward_ratio": 1.94,
      "current_ltp": 127.20,
      "iv": 18.5,
      "oi": 5420000,
      "volume": 128450,
      "oi_change": 12.3,
      "supporting_strategies": [
        "OI Strategy",
        "PCR Analysis",
        "Gamma Scalping",
        "Greeks Positioning",
        "Order Flow",
        "Time of Day",
        "Institutional Footprint",
        "Support Resistance"
      ],
      "reasons": [
        "Strong Call OI build-up at 25900",
        "PCR 1.31 indicates bullish sentiment",
        "Gamma squeeze potential above 25900",
        "Institutional buying detected",
        "Break of resistance at 25875"
      ],
      "signals": [
        {
          "strategy": "OI Strategy",
          "strength": 85.2,
          "reason": "Call OI increased by 15% at strike 25900"
        }
      ]
    }
  ]
}
```

---

### 2. Get Top Picks

**GET** `/api/watchlist/top-picks`

Get best N picks across multiple symbols.

#### Query Parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `symbols` | string | `NIFTY,SENSEX` | Comma-separated symbols |
| `limit` | int | `5` | Top N picks per symbol |

#### Example Request:
```bash
curl "http://localhost:8000/api/watchlist/top-picks?symbols=NIFTY,SENSEX,BANKNIFTY&limit=3"
```

#### Response:
```json
{
  "status": "success",
  "timestamp": "2025-11-12T14:30:00",
  "picks": {
    "NIFTY": {
      "spot_price": 25875.80,
      "sentiment": "Bullish",
      "pcr": 1.31,
      "top_picks": [
        {
          "strike": "25900",
          "direction": "CALL",
          "composite_score": 87.5,
          "num_strategies": 8,
          "entry_price": 125.50,
          "target_price": 175.00,
          "risk_reward_ratio": 1.94
        }
      ]
    },
    "SENSEX": {
      "spot_price": 84466.51,
      "sentiment": "Bullish",
      "pcr": 1.28,
      "top_picks": []
    }
  }
}
```

---

### 3. Get Strategy Consensus

**GET** `/api/watchlist/strategy-consensus/{symbol}/{strike}`

Get detailed consensus for a specific strike showing which strategies agree.

#### Path Parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `symbol` | string | NIFTY, SENSEX, or BANKNIFTY |
| `strike` | string | Strike price (e.g., "25900") |

#### Query Parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `direction` | string | `CALL` | CALL or PUT |

#### Example Request:
```bash
curl "http://localhost:8000/api/watchlist/strategy-consensus/NIFTY/25900?direction=CALL"
```

#### Response:
```json
{
  "status": "success",
  "consensus": {
    "strike": "25900",
    "direction": "CALL",
    "supporting_strategies": 8,
    "total_strategies": 20,
    "consensus_percentage": 40.0,
    "signals": [
      {
        "strategy": "OI Strategy",
        "strength": 85.2,
        "reason": "Call OI increased by 15% at strike 25900",
        "entry_price": 125.50,
        "target": 175.00,
        "stop_loss": 100.00
      },
      {
        "strategy": "PCR Analysis",
        "strength": 78.5,
        "reason": "Bullish PCR: 1.31",
        "entry_price": 125.50,
        "target": 170.00,
        "stop_loss": 105.00
      }
    ]
  }
}
```

---

## Data Flow

```
1. Frontend calls /api/watchlist/recommended-strikes?symbol=NIFTY
   ↓
2. Backend fetches live market data + option chain from Upstox
   ↓
3. Runs all 20 strategies in parallel
   ├─ OI Strategy
   ├─ PCR Strategy
   ├─ Gamma Scalping
   ├─ IV Skew
   ├─ Greeks Positioning
   ├─ Institutional Footprint
   ├─ Order Flow
   ├─ Max Pain
   ├─ Hidden OI
   ├─ Liquidity Hunting
   ├─ Time of Day
   ├─ Support Resistance
   ├─ Gap and Go
   ├─ Multi-Leg Arbitrage
   ├─ Iron Condor
   ├─ Butterfly
   ├─ Straddle/Strangle
   ├─ VIX Mean Reversion
   ├─ Cross-Asset Correlation
   └─ Sentiment NLP
   ↓
4. Each strategy generates signals with strength scores (0-100)
   ↓
5. Groups signals by strike price
   ↓
6. ML Model (XGBoost) scores each strike (0-1 probability)
   - Features: PCR, IV, OI, Greeks, signal strength
   ↓
7. Applies filters:
   - Minimum ML score
   - Minimum strategy strength
   - Minimum strategies agreeing
   ↓
8. Enriches with option chain data:
   - Current LTP, IV, OI, Volume, OI Change
   ↓
9. Calculates composite score:
   - ML Score × 0.4
   - Strategy Strength × 0.3
   - Number of Strategies × 0.2
   - Risk-Reward Ratio × 0.1
   ↓
10. Ranks strikes by composite score
   ↓
11. Returns top 20 recommendations
   ↓
12. Dashboard displays in sortable table
```

---

## Composite Score Formula

```python
composite_score = (
    ml_score * 0.4 +                           # ML confidence (0-1)
    (avg_strategy_strength / 100) * 0.3 +      # Strategy strength (0-100)
    (min(num_strategies / 10, 1.0)) * 0.2 +    # Number of strategies (capped at 10)
    (min(risk_reward_ratio / 3, 1.0)) * 0.1    # R:R ratio (capped at 3:1)
) * 100
```

**Score Interpretation:**
- **80-100**: High confidence - Strong buy signal
- **65-79**: Medium confidence - Consider entry
- **<65**: Low confidence - Wait for better setup

---

## Strategy Weights

Each strategy contributes based on its strength score (0-100):

| Strategy Category | Weight | Examples |
|-------------------|--------|----------|
| OI Analysis | High (80-100) | OI Strategy, Hidden OI, Max Pain |
| Market Sentiment | High (75-95) | PCR Strategy, VIX Mean Reversion |
| Greeks & Volatility | Medium (70-85) | IV Skew, Gamma Scalping |
| Institutional | Medium (70-80) | Institutional Footprint, Order Flow |
| Spreads | Low-Medium (60-75) | Iron Condor, Butterfly |
| Intraday Patterns | Low-Medium (65-80) | Time of Day, Gap and Go |

---

## Dashboard Display

The Smart Watchlist section on the dashboard shows:

**Summary Stats:**
- Spot Price
- Market Sentiment (Bullish/Bearish/Neutral)
- PCR
- Number of Recommendations

**Recommendations Table:**
| Column | Description |
|--------|-------------|
| Rank | Position in sorted list (1, 2, 3...) |
| Strike | Strike price |
| Type | CALL or PUT badge (color-coded) |
| Score | Composite score (0-100) with color badge |
| Strategies | Number of strategies agreeing |
| Entry | Recommended entry price |
| Target | Target profit price |
| Stop Loss | Stop loss price |
| R:R | Risk-reward ratio (e.g., 1.9:1) |
| IV | Current implied volatility |
| OI | Open interest (formatted as 5.4M) |
| Top Reasons | First 2 reasons from strategies |

**Color Coding:**
- 🟢 Green: CALL options, high scores, good R:R
- 🔴 Red: PUT options, low scores, poor R:R
- 🟡 Yellow: Medium scores, average R:R

---

## Usage Example

### Python:
```python
import requests

# Get NIFTY recommendations
response = requests.get(
    'http://localhost:8000/api/watchlist/recommended-strikes',
    params={
        'symbol': 'NIFTY',
        'min_ml_score': 0.7,
        'min_strategy_strength': 75,
        'min_strategies_agree': 5
    }
)

data = response.json()

# Print top 3 picks
for i, strike in enumerate(data['recommended_strikes'][:3], 1):
    print(f"{i}. Strike {strike['strike']} {strike['direction']}")
    print(f"   Score: {strike['composite_score']}")
    print(f"   Entry: ₹{strike['entry_price']:.2f}")
    print(f"   Target: ₹{strike['target_price']:.2f}")
    print(f"   R:R: {strike['risk_reward_ratio']:.1f}:1")
    print(f"   Strategies: {strike['num_strategies']}")
    print()
```

### JavaScript (Dashboard):
```javascript
async function updateWatchlist() {
    const symbol = document.getElementById('watchlist-symbol').value;
    
    const response = await fetch(
        `${API_BASE_URL}/api/watchlist/recommended-strikes?symbol=${symbol}&min_ml_score=0.65`
    );
    
    const data = await response.json();
    displayWatchlistTable(data.recommended_strikes);
}
```

---

## Error Handling

**HTTP Status Codes:**
- `200 OK`: Success
- `404 Not Found`: Symbol not found
- `500 Internal Server Error`: Processing error

**Error Response:**
```json
{
  "detail": "Failed to fetch option chain"
}
```

---

## Performance

- **Response Time**: 2-5 seconds (depending on market data fetch)
- **Strategies Executed**: 20 in parallel
- **Option Chain Analysis**: 50-200 strikes per symbol
- **ML Inference**: <100ms per signal
- **Caching**: Not implemented (future enhancement)

---

## Future Enhancements

1. ✅ **Backtesting**: Historical performance of recommended strikes
2. ✅ **Real-time Updates**: WebSocket stream for live updates
3. ✅ **Custom Filters**: User-defined strategy weights
4. ✅ **Alerting**: Push notifications for high-score strikes
5. ✅ **Paper Trading Integration**: One-click trade execution

---

**Last Updated**: November 12, 2025
