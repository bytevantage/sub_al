# Safety Systems - Implementation Complete

## Overview

**Status:** ✅ CRITICAL SAFETY FEATURES IMPLEMENTED

This document describes the comprehensive safety systems that protect the trading system from catastrophic losses and operational failures. These features are **MANDATORY** before any live trading.

---

## Implemented Systems

### 1. ✅ Circuit Breaker System (`circuit_breaker.py`)

**Purpose:** Auto-disable trading when risk limits are breached

**Features:**
- **Daily Loss Limit:** Auto-stops trading when daily loss hits 3% (configurable)
- **Position Limits:** Prevents over-positioning beyond max_positions
- **VIX Spike Detection:** Halts trading when VIX > 40
- **IV Shock Detection:** Stops on sudden IV changes >50%
- **Emergency Kill Switch:** Immediate manual stop with `emergency_stop()`
- **Manual Override:** Protected override with password for critical situations
- **Persistent State:** Survives restarts - requires manual reset after trip
- **Daily Reset:** Auto-resets daily triggers at market open

**States:**
- `ACTIVE` - Normal trading allowed
- `TRIPPED` - Auto-disabled due to trigger
- `EMERGENCY_STOP` - Manual emergency stop (requires password to reset)
- `MARKET_HALT` - Exchange halted
- `MANUAL_DISABLE` - Manually disabled

**Usage:**
```python
from backend.safety import CircuitBreaker

# Initialize
breaker = CircuitBreaker(config['safety']['circuit_breaker'])

# Check before trading
if not breaker.is_trading_allowed():
    logger.error("Trading is disabled by circuit breaker")
    return

# Check daily loss
if breaker.check_daily_loss(daily_pnl=-3500, initial_capital=100000):
    # Circuit breaker tripped
    close_all_positions()
    
# Emergency stop
breaker.emergency_stop("Manual intervention required")

# Reset (requires reason)
breaker.reset("Issue resolved, resuming trading")

# Reset emergency stop (requires password)
breaker.reset("Catastrophic event resolved", override_password="OVERRIDE123")
```

**State File:** `data/circuit_breaker_state.json`

---

### 2. ✅ Order Validator - Fat-Finger Prevention (`order_validator.py`)

**Purpose:** Prevent costly fat-finger errors before order submission

**Validations:**
- **Order Size:** Max 5 lots per order (configurable)
- **Price Bands:** Rejects orders ±5% from LTP
- **Price Sanity:** Min ₹0.05, Max ₹1,000
- **Quantity Checks:** Must be multiple of lot size
- **Capital Limits:** Max ₹50k per trade
- **Duplicate Prevention:** Blocks identical orders within 5 seconds
- **Stop-Loss Validation:** Ensures stops are logical and not too wide/tight

**Usage:**
```python
from backend.safety import OrderValidator, ValidationResult

validator = OrderValidator(config['safety']['order_validator'])

# Validate order
result, error = validator.validate_order(
    symbol="NIFTY",
    quantity=75,  # 1 lot
    price=150.50,
    side="BUY",
    ltp=150.00,
    lot_size=75,
    available_capital=50000
)

if result != ValidationResult.VALID:
    logger.error(f"Order rejected: {error}")
    return False
    
# Validate stop-loss
is_valid, error = validator.validate_stop_loss(
    entry_price=150.00,
    stop_loss=135.00,  # 10% stop
    side="BUY"
)
```

**Rejection Reasons:**
- `REJECTED_SIZE` - Order too large
- `REJECTED_PRICE` - Price outside bands
- `REJECTED_QUANTITY` - Invalid quantity
- `REJECTED_CAPITAL` - Insufficient capital
- `REJECTED_DUPLICATE` - Duplicate order

---

### 3. ✅ Slippage Model (`slippage_model.py`)

**Purpose:** Realistic paper trading that matches live performance

**Components:**
- **Bid-Ask Spread:** 0.05% (5 bps) - always incurred when crossing spread
- **Market Impact:** 0.1-0.5% based on liquidity (OI thresholds)
- **Volatility Slippage:** Extra cost during high IV (>30%)
- **Time-of-Day:** 50% extra slippage during market open/close
- **Transaction Costs:**
  - Brokerage: 0.03% (capped at ₹20 per order)
  - STT: 0.05% on sell side only
  - Exchange charges: 0.05%
  - GST: 18% on brokerage + exchange
  - Stamp duty: 0.003% on buy side

**Usage:**
```python
from backend.safety import SlippageModel

model = SlippageModel(config['safety']['slippage'])

# Calculate execution price with slippage
execution = model.calculate_execution_price(
    theoretical_price=150.00,
    side="BUY",
    quantity=75,
    open_interest=25000,  # Low liquidity
    iv=35,  # High volatility
    timestamp=datetime.now()
)

# Result:
# {
#     'execution_price': 150.75,  # Paid more due to slippage
#     'theoretical_price': 150.00,
#     'slippage_amount': 0.75,
#     'slippage_percent': 0.5,
#     'breakdown': {...}
# }

# Calculate transaction costs
costs = model.calculate_transaction_costs(
    trade_value=11250,  # 75 qty @ 150
    side="BUY"
)

# Net P&L (after all costs)
net_pnl = model.calculate_net_pnl(
    entry_value=11250,
    exit_value=12000,
    quantity=75,
    entry_slippage=entry_exec,
    exit_slippage=exit_exec
)
```

**Expected Impact:**
- **Low Liquidity:** 0.3-0.7% total slippage per trade
- **High Liquidity:** 0.1-0.3% total slippage per trade
- **Round-Trip Costs:** ~0.2-1.5% (slippage + transaction costs)

---

### 4. ✅ Rate Limiter (`rate_limiter.py`)

**Purpose:** Prevent order rejections due to API rate limits

**Features:**
- **Token Bucket:** 10 requests/second, 5 orders/second (Upstox limits)
- **Exponential Backoff:** 1s → 2s → 4s → 8s on 429 errors
- **Order Queue:** Queues orders with priority when limit hit
- **Automatic Retry:** Retries with delays on rate limit errors
- **Max Backoff:** Caps at 60 seconds
- **Request Tracking:** Monitors API usage over time

**Usage:**
```python
from backend.safety import RateLimiter

limiter = RateLimiter(config['safety']['rate_limiter'])

# Execute with automatic rate limiting
result = await limiter.execute_with_retry(
    upstox_client.place_order,
    instrument_token="NSE_FO|12345",
    quantity=75,
    token_type='order',  # Use order tokens
    max_retries=3
)

# Queue order (processes when tokens available)
await limiter.queue_order(
    place_order_func,
    instrument_token="NSE_FO|12345",
    quantity=75,
    priority=10  # Higher = executed first
)

# Get stats
stats = limiter.get_stats()
# {
#     'request_tokens_available': 8,
#     'order_tokens_available': 5,
#     'requests_last_minute': 45,
#     'consecutive_429s': 0,
#     'backoff_active': False
# }
```

**Backoff Schedule:**
- 1st 429: Wait 1 second
- 2nd 429: Wait 2 seconds
- 3rd 429: Wait 4 seconds
- 4th 429: Wait 8 seconds
- 5th+ 429: Wait 16-60 seconds (capped)

---

### 5. ✅ Market Data Monitor (`data_monitor.py`)

**Purpose:** Ensure data quality and detect streaming failures

**Checks:**
- **Freshness:** Rejects data >5s old (warning), >10s old (critical)
- **Completeness:** Ensures LTP, bid, ask, volume present
- **Reasonableness:** Validates bid ≤ LTP ≤ ask, positive prices, spread <20%
- **IV Validation:** Checks 0% < IV < 200%
- **Quality Scoring:** 0.0-1.0 score based on issues
- **Streaming Health:** Monitors % of symbols with healthy data

**Quality Levels:**
- `EXCELLENT` (0.9-1.0) - Fresh, complete, valid data
- `GOOD` (0.7-0.9) - Slightly delayed but usable
- `POOR` (0.5-0.7) - Stale or incomplete
- `FAILED` (<0.5) - Unusable

**Usage:**
```python
from backend.safety import MarketDataMonitor, DataQuality

monitor = MarketDataMonitor(config['safety']['data_monitor'])

# Register alert callback
async def alert_handler(alert_data):
    logger.critical(f"Data alert: {alert_data}")
    send_sms(alert_data)
    
monitor.register_alert_callback(alert_handler)

# Validate data
is_valid, quality, error = await monitor.validate_data(
    symbol="NIFTY24600CE",
    data={
        'ltp': 150.50,
        'bid': 150.00,
        'ask': 151.00,
        'volume': 25000,
        'iv': 18.5
    },
    timestamp=datetime.now()
)

if not is_valid:
    logger.error(f"Data validation failed: {error}")
    # Use cached data or skip trade
    
# Check streaming health
if not await monitor.check_streaming_health():
    logger.error("Streaming health critical - stopping trading")
    circuit_breaker.trip(...)
    
# Get report
report = monitor.get_quality_report()
```

**Actions on Failure:**
- 3 consecutive failures → Trigger alerts (SMS/email/Telegram)
- Consider fallback data provider
- May trigger circuit breaker if critical

---

### 6. ✅ Position Manager (`position_manager.py`)

**Purpose:** Track capital allocation and prevent over-leveraging

**Features:**
- **Capital Limits:**
  - Max 80% capital utilization
  - Max 40% per strategy
  - Max 20% per position
- **Real-time Margin Tracking:** Used vs available
- **Strategy Allocation:** Per-strategy capital monitoring
- **Concentration Checks:** Prevents over-allocation
- **Exposure Reports:** Detailed breakdown of allocations

**Usage:**
```python
from backend.safety import PositionManager

pm = PositionManager(config['safety']['position_manager'])

# Check before adding position
position_value = 75 * 150  # ₹11,250
if not pm.can_add_position(position_value, strategy="gamma_scalping"):
    logger.error("Position rejected - allocation limits exceeded")
    return
    
# Add position
success = pm.add_position({
    'id': 'pos_123',
    'strategy': 'gamma_scalping',
    'quantity': 75,
    'entry_price': 150.00,
    ...
})

# Update prices (for unrealized P&L)
pm.update_position_price('pos_123', current_price=155.00)

# Remove position (on exit)
pm.remove_position('pos_123')

# Check concentration
is_over, reason = pm.is_over_concentrated()
if is_over:
    logger.warning(f"Over-concentrated: {reason}")
    
# Get exposure report
report = pm.get_exposure_report()
# {
#     'total_capital': 100000,
#     'used_margin': 45000,
#     'available_margin': 55000,
#     'utilization_percent': 45,
#     'strategy_breakdown': {
#         'gamma_scalping': {
#             'allocation': 20000,
#             'allocation_percent': 20,
#             'num_positions': 2,
#             'unrealized_pnl': 850
#         }
#     }
# }
```

---

## Configuration (config.yaml)

All safety systems are configured in `config/config.yaml` under the `safety` section:

```yaml
safety:
  circuit_breaker:
    daily_loss_limit_percent: 3
    max_positions: 5
    vix_threshold: 40
    iv_shock_percent: 50
    override_password: "OVERRIDE123"  # CHANGE THIS!
    
  order_validator:
    max_lots_per_order: 5
    price_band_percent: 5
    max_capital_per_trade: 50000
    
  slippage:
    base_slippage_bps: 10
    high_vol_slippage_bps: 50
    # ... (full config in file)
    
  rate_limiter:
    max_requests_per_second: 10
    max_orders_per_second: 5
    
  data_monitor:
    stale_threshold_seconds: 5
    critical_threshold_seconds: 10
    
  position_manager:
    total_capital: 100000
    max_capital_utilization: 0.8
```

---

## Integration Example

Here's how to integrate all safety systems into the main trading loop:

```python
from backend.safety import (
    CircuitBreaker, OrderValidator, SlippageModel,
    RateLimiter, MarketDataMonitor, PositionManager
)

# Initialize all safety systems
circuit_breaker = CircuitBreaker(config['safety']['circuit_breaker'])
order_validator = OrderValidator(config['safety']['order_validator'])
slippage_model = SlippageModel(config['safety']['slippage'])
rate_limiter = RateLimiter(config['safety']['rate_limiter'])
data_monitor = MarketDataMonitor(config['safety']['data_monitor'])
position_manager = PositionManager(config['safety']['position_manager'])

async def trading_loop():
    while True:
        # 1. Check circuit breaker
        if not circuit_breaker.is_trading_allowed():
            logger.error("Trading disabled by circuit breaker")
            await asyncio.sleep(60)
            continue
            
        # 2. Get market data
        market_data = await get_market_data()
        
        # 3. Validate data quality
        is_valid, quality, error = await data_monitor.validate_data(
            symbol, market_data
        )
        if not is_valid:
            logger.error(f"Invalid data: {error}")
            continue
            
        # 4. Generate signal
        signal = strategy.generate_signal(market_data)
        if not signal:
            continue
            
        # 5. Calculate position size
        position_value = signal['quantity'] * signal['entry_price']
        
        # 6. Check position manager
        if not position_manager.can_add_position(
            position_value, signal['strategy']
        ):
            logger.error("Position rejected - allocation limits")
            continue
            
        # 7. Validate order
        result, error = order_validator.validate_order(
            symbol=signal['symbol'],
            quantity=signal['quantity'],
            price=signal['entry_price'],
            side="BUY",
            ltp=market_data['ltp'],
            lot_size=75,
            available_capital=position_manager.available_margin
        )
        
        if result != ValidationResult.VALID:
            logger.error(f"Order invalid: {error}")
            continue
            
        # 8. Calculate realistic execution price (paper mode)
        if is_paper_mode:
            execution = slippage_model.calculate_execution_price(
                theoretical_price=signal['entry_price'],
                side="BUY",
                quantity=signal['quantity'],
                open_interest=market_data.get('oi'),
                iv=market_data.get('iv')
            )
            actual_entry_price = execution['execution_price']
        else:
            actual_entry_price = signal['entry_price']
            
        # 9. Execute with rate limiting
        order_result = await rate_limiter.execute_with_retry(
            place_order,
            signal,
            token_type='order',
            max_retries=3
        )
        
        if not order_result:
            logger.error("Order execution failed")
            continue
            
        # 10. Add position to tracker
        position_manager.add_position({
            'id': order_result['id'],
            'strategy': signal['strategy'],
            'quantity': signal['quantity'],
            'entry_price': actual_entry_price,
            ...
        })
        
        # 11. Check daily P&L and circuit breaker
        daily_pnl = calculate_daily_pnl()
        if circuit_breaker.check_daily_loss(daily_pnl, initial_capital):
            logger.critical("Daily loss limit hit - closing all positions")
            await close_all_positions()
            break
```

---

## Remaining Tasks

### HIGH Priority (Implement Next)

**6. Circuit Breakers for Market Shocks**
- VIX monitoring service
- Market halt detection
- Auto position squaring option

**7. Enhanced Position Management**
- Integration with existing RiskManager
- Greek-based risk metrics
- Portfolio Greeks aggregation

### MEDIUM Priority

**8. Partial Fill & Order Lifecycle**
- Order state machine
- Partial fill handling
- Cancellation retry logic
- Re-entry cooldown

**9. Trade Reconciliation**
- Broker statement import
- Position matching
- Discrepancy alerts

**10. Emergency Controls Dashboard**
- FastAPI endpoints
- Emergency stop button
- Position overview
- Manual override UI

---

## Testing Recommendations

### Unit Tests
```bash
# Test each safety system independently
pytest backend/safety/test_circuit_breaker.py
pytest backend/safety/test_order_validator.py
pytest backend/safety/test_slippage_model.py
pytest backend/safety/test_rate_limiter.py
pytest backend/safety/test_data_monitor.py
pytest backend/safety/test_position_manager.py
```

### Integration Tests
```bash
# Test safety systems together
pytest tests/integration/test_safety_integration.py
```

### Simulation Tests
1. **Circuit Breaker:** Simulate -3% loss → verify auto-stop
2. **Order Validator:** Submit 10-lot order → verify rejection
3. **Slippage Model:** Compare paper vs live P&L over 100 trades
4. **Rate Limiter:** Send 50 orders/second → verify queuing
5. **Data Monitor:** Inject stale data → verify alerts
6. **Position Manager:** Attempt 90% capital use → verify rejection

---

## Production Readiness

### ✅ Implemented (Phase 1)
- [x] Circuit breaker with daily loss limits
- [x] Fat-finger prevention
- [x] Slippage modeling
- [x] Rate limiting
- [x] Data quality monitoring
- [x] Position management

### ⚠️ Remaining (Phase 2)
- [ ] Market shock circuit breakers
- [ ] Advanced position management (Greeks)
- [ ] Partial fill handling
- [ ] Trade reconciliation
- [ ] Emergency dashboard

### Deployment Checklist
- [ ] Update `override_password` in config.yaml
- [ ] Configure alert callbacks (SMS/email/Telegram)
- [ ] Set correct capital limits
- [ ] Test all safety systems in paper mode for 1 week
- [ ] Verify circuit breaker triggers correctly
- [ ] Test emergency stop procedure
- [ ] Document incident response procedures
- [ ] Set up monitoring and logging
- [ ] Create runbook for common scenarios

---

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review circuit breaker state in `data/circuit_breaker_state.json`
3. Get quality report from `MarketDataMonitor.get_quality_report()`
4. Check exposure with `PositionManager.get_exposure_report()`

---

**Last Updated:** 2024
**Version:** 1.0
**Status:** Phase 1 Complete ✅
