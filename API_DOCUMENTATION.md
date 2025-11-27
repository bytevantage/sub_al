# 🔌 Complete API Endpoints Documentation

## Base URL
```
http://localhost:8000
```

---

## 📊 Trade History Endpoints

### 1. Get Trade History
**Endpoint:** `GET /api/trades/history`

**Description:** Retrieve trade history with comprehensive filtering options

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | string | No | - | Start date (YYYY-MM-DD) |
| `end_date` | string | No | - | End date (YYYY-MM-DD) |
| `strategy` | string | No | - | Filter by strategy name (case-insensitive) |
| `status` | string | No | - | OPEN, CLOSED, CANCELLED |
| `symbol` | string | No | - | NIFTY, BANKNIFTY |
| `min_pnl` | float | No | - | Minimum P&L filter |
| `max_pnl` | float | No | - | Maximum P&L filter |
| `winning_only` | boolean | No | false | Show only winning trades |
| `losing_only` | boolean | No | false | Show only losing trades |
| `limit` | integer | No | 100 | Max results (≤1000) |
| `offset` | integer | No | 0 | Pagination offset |

**Example Request:**
```bash
curl "http://localhost:8000/api/trades/history?start_date=2025-11-01&strategy=Order%20Flow&winning_only=true&limit=50"
```

**Response:**
```json
{
  "total": 150,
  "limit": 50,
  "offset": 0,
  "trades": [
    {
      "trade_id": "TRD20251111093015",
      "entry_time": "2025-11-11T09:30:15",
      "exit_time": "2025-11-11T10:45:30",
      "symbol": "NIFTY",
      "instrument_type": "CALL",
      "strike_price": 19500,
      "entry_price": 150.50,
      "exit_price": 185.75,
      "quantity": 50,
      "gross_pnl": 1762.50,
      "net_pnl": 1712.50,
      "pnl_percentage": 23.44,
      "strategy_name": "Order Flow Imbalance",
      "signal_strength": 88.5,
      "status": "CLOSED",
      "is_winning_trade": true,
      "hold_duration_minutes": 75,
      "exit_type": "TARGET",
      "signal_reason": "Strong buy flow imbalance 3.2:1, Volume: 25,450",
      "exit_reason": "Target reached at 185.75"
    }
  ]
}
```

---

### 2. Get Trade Statistics
**Endpoint:** `GET /api/trades/statistics`

**Description:** Aggregated trading statistics with strategy breakdown

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | string | No | Filter start date |
| `end_date` | string | No | Filter end date |
| `strategy` | string | No | Specific strategy filter |

**Example Request:**
```bash
curl "http://localhost:8000/api/trades/statistics?start_date=2025-11-01"
```

**Response:**
```json
{
  "overview": {
    "total_trades": 150,
    "winning_trades": 95,
    "losing_trades": 55,
    "win_rate": 63.33,
    "total_pnl": 45000.50,
    "profit_factor": 1.82,
    "average_profit": 850.25,
    "average_loss": 320.15,
    "average_hold_minutes": 45.5
  },
  "best_trade": {
    "trade_id": "TRD20251105141520",
    "strategy": "Order Flow Imbalance",
    "pnl": 2500.00,
    "entry_time": "2025-11-05T14:15:20"
  },
  "worst_trade": {
    "trade_id": "TRD20251107101015",
    "strategy": "Gamma Scalping",
    "pnl": -850.00,
    "entry_time": "2025-11-07T10:10:15"
  },
  "strategy_breakdown": {
    "Order Flow Imbalance": {
      "total_trades": 25,
      "winning_trades": 18,
      "win_rate": 72.0,
      "total_pnl": 8500.00
    },
    "PCR Analysis": {
      "total_trades": 20,
      "winning_trades": 13,
      "win_rate": 65.0,
      "total_pnl": 4200.00
    }
  }
}
```

---

### 3. Get Daily Performance
**Endpoint:** `GET /api/trades/daily-performance`

**Description:** Daily aggregated performance metrics

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `days` | integer | No | 30 | Number of days (≤365) |

**Example Request:**
```bash
curl "http://localhost:8000/api/trades/daily-performance?days=7"
```

**Response:**
```json
{
  "days": 7,
  "records": [
    {
      "date": "2025-11-11",
      "total_trades": 12,
      "winning_trades": 8,
      "losing_trades": 4,
      "win_rate": 66.67,
      "net_pnl": 3250.50,
      "max_profit": 850.00,
      "max_loss": -320.00,
      "profit_factor": 2.15,
      "best_strategy": "Order Flow Imbalance",
      "worst_strategy": "Butterfly Spread"
    }
  ]
}
```

---

### 4. Get Strategy Performance
**Endpoint:** `GET /api/trades/strategy-performance`

**Description:** Strategy-wise performance tracking over time

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `strategy_name` | string | No | - | Specific strategy |
| `days` | integer | No | 30 | Number of days (≤365) |

**Example Request:**
```bash
curl "http://localhost:8000/api/trades/strategy-performance?strategy_name=Order%20Flow%20Imbalance&days=30"
```

**Response:**
```json
{
  "strategy": "Order Flow Imbalance",
  "days": 30,
  "records": [
    {
      "strategy_name": "Order Flow Imbalance",
      "date": "2025-11-11",
      "total_signals": 15,
      "trades_taken": 8,
      "winning_trades": 6,
      "win_rate": 75.0,
      "total_pnl": 2500.00,
      "average_signal_strength": 82.5
    }
  ]
}
```

---

### 5. Get Trade Details
**Endpoint:** `GET /api/trades/{trade_id}`

**Description:** Complete details of a specific trade

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `trade_id` | string | Yes | Unique trade identifier |

**Example Request:**
```bash
curl "http://localhost:8000/api/trades/TRD20251111093015"
```

**Response:**
```json
{
  "trade_id": "TRD20251111093015",
  "entry_time": "2025-11-11T09:30:15",
  "exit_time": "2025-11-11T10:45:30",
  "symbol": "NIFTY",
  "instrument_type": "CALL",
  "strike_price": 19500,
  "entry_price": 150.50,
  "exit_price": 185.75,
  "quantity": 50,
  "gross_pnl": 1762.50,
  "brokerage": 30.00,
  "taxes": 20.00,
  "net_pnl": 1712.50,
  "pnl_percentage": 23.44,
  "strategy_name": "Order Flow Imbalance",
  "signal_strength": 88.5,
  "ml_score": 0.85,
  "spot_price_entry": 19485.50,
  "spot_price_exit": 19532.25,
  "iv_entry": 18.5,
  "iv_exit": 19.2,
  "delta_entry": 0.52,
  "gamma_entry": 0.035,
  "theta_entry": -12.5,
  "vega_entry": 8.2,
  "target_price": 185.00,
  "stop_loss_price": 135.00,
  "max_profit_reached": 190.50,
  "max_loss_reached": 148.00,
  "risk_amount": 775.00,
  "risk_reward_ratio": 2.27,
  "status": "CLOSED",
  "is_winning_trade": true,
  "hold_duration_minutes": 75,
  "exit_type": "TARGET",
  "signal_reason": "Strong buy flow imbalance 3.2:1, Volume: 25,450",
  "exit_reason": "Target reached at 185.75",
  "notes": null,
  "tags": "high-confidence,morning-session"
}
```

---

### 6. Export to CSV
**Endpoint:** `GET /api/trades/export/csv`

**Description:** Export trade history to CSV file for Excel analysis

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | string | No | Filter start date |
| `end_date` | string | No | Filter end date |
| `strategy` | string | No | Strategy filter |

**Example Request:**
```bash
curl "http://localhost:8000/api/trades/export/csv?start_date=2025-11-01" -o trades.csv
```

**Response:** CSV file download with headers:
```
Trade ID,Entry Date,Entry Time,Exit Date,Exit Time,Symbol,Type,Strike,Entry Price,Exit Price,Quantity,Gross P&L,Brokerage,Taxes,Net P&L,P&L %,Strategy,Signal Strength,Exit Type,Hold Minutes,Spot Entry,Spot Exit,IV Entry,IV Exit,Signal Reason,Exit Reason
```

---

## 📈 Other System Endpoints

### 7. Health Check
**Endpoint:** `GET /api/health`

**Response:**
```json
{
  "status": "healthy",
  "mode": "paper",
  "trading_active": true
}
```

---

### 8. Get Current Positions
**Endpoint:** `GET /api/positions`

**Response:**
```json
{
  "positions": [
    {
      "symbol": "NIFTY",
      "strike": 19500,
      "type": "CALL",
      "quantity": 50,
      "entry_price": 150.50,
      "current_price": 165.25,
      "unrealized_pnl": 737.50,
      "strategy": "Order Flow Imbalance"
    }
  ]
}
```

---

### 9. Get Performance Metrics
**Endpoint:** `GET /api/performance`

**Response:**
```json
{
  "daily_pnl": 3250.50,
  "total_trades": 12,
  "win_rate": 66.67,
  "profit_factor": 2.15
}
```

---

### 10. Get Option Chain
**Endpoint:** `GET /api/option-chain/{symbol}/{expiry}`

**Example:**
```bash
curl "http://localhost:8000/api/option-chain/NIFTY/2025-11-14"
```

---

## 🔄 WebSocket Endpoint

### Real-time Updates
**Endpoint:** `ws://localhost:8000/ws`

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'signal') {
    console.log('New signal:', data.data);
  }
  
  if (data.type === 'market_data') {
    console.log('Market update:', data.data);
  }
};
```

---

## 📝 Common Use Cases

### 1. Today's Trades
```bash
curl "http://localhost:8000/api/trades/history?start_date=$(date +%Y-%m-%d)&limit=100"
```

### 2. Winning Trades from Best Strategy
```bash
curl "http://localhost:8000/api/trades/history?strategy=Order%20Flow%20Imbalance&winning_only=true"
```

### 3. Last Week Performance
```bash
curl "http://localhost:8000/api/trades/daily-performance?days=7"
```

### 4. Export November Trades
```bash
curl "http://localhost:8000/api/trades/export/csv?start_date=2025-11-01&end_date=2025-11-30" -o november_trades.csv
```

### 5. Strategy Comparison
```bash
# Get performance for each strategy
curl "http://localhost:8000/api/trades/strategy-performance?days=30"
```

### 6. Large P&L Trades
```bash
# Trades with P&L > ₹1000
curl "http://localhost:8000/api/trades/history?min_pnl=1000"

# Trades with P&L < -₹500 (losses)
curl "http://localhost:8000/api/trades/history?max_pnl=-500"
```

---

## 🔐 Error Responses

All endpoints return appropriate HTTP status codes:

**200 OK** - Successful request
```json
{
  "total": 10,
  "trades": [...]
}
```

**404 Not Found** - Trade not found
```json
{
  "detail": "Trade TRD20251111093015 not found"
}
```

**500 Internal Server Error** - Server error
```json
{
  "detail": "Error fetching trade history: Database connection failed"
}
```

**503 Service Unavailable** - Database not available
```json
{
  "detail": "Database not available"
}
```

---

## 📚 Interactive Documentation

Access interactive Swagger UI documentation:
```
http://localhost:8000/docs
```

Access ReDoc documentation:
```
http://localhost:8000/redoc
```

Both provide:
- Try-it-out functionality
- Request/response schemas
- Example values
- Authentication info

---

## 🎯 Best Practices

### 1. Pagination
Always use `limit` and `offset` for large datasets:
```bash
# First page
curl "http://localhost:8000/api/trades/history?limit=50&offset=0"

# Second page
curl "http://localhost:8000/api/trades/history?limit=50&offset=50"
```

### 2. Date Filtering
Use ISO format dates (YYYY-MM-DD):
```bash
curl "http://localhost:8000/api/trades/history?start_date=2025-11-01&end_date=2025-11-30"
```

### 3. URL Encoding
Encode special characters in query parameters:
```bash
# Space → %20
curl "http://localhost:8000/api/trades/history?strategy=Order%20Flow%20Imbalance"
```

### 4. Response Handling
```python
import requests

response = requests.get(
    "http://localhost:8000/api/trades/history",
    params={"start_date": "2025-11-01", "winning_only": True}
)

if response.status_code == 200:
    data = response.json()
    for trade in data["trades"]:
        print(f"{trade['trade_id']}: ₹{trade['net_pnl']}")
```

---

**All endpoints are production-ready and fully functional! 🚀**
