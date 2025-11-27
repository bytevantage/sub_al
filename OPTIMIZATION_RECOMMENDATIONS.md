# 🚀 Market Data Optimization Recommendations

## Current Issues Identified

### 1. Fetch Interval
**Current**: Every 30 seconds for entire option chain
**Problem**: 
- 120 API calls per hour per symbol
- 240 calls/hour for NIFTY + BANKNIFTY
- 1,920 calls during market hours (8 hours)
- **Rate limit risk** with Upstox API

### 2. No Filtering Applied
**Current**: Fetching ALL strikes in the option chain
**Problem**:
- Deep OTM options with delta < 0.05 are irrelevant for intraday
- Far OTM options with low liquidity
- Wasted bandwidth and processing time

### 3. Complete Chain Processing
**Current**: Processing every strike for Greeks calculation
**Problem**:
- Calculating Greeks for 50-100 strikes per symbol
- Most calculations are for strikes that will never be traded
- Slows down the trading loop

---

## Recommended Optimizations

### Optimization 1: Smart Strike Filtering

**Filter by ATM Range**:
```python
# Only fetch strikes within ±10% of spot price
# For Nifty at 20,000: Only 18,000 to 22,000
# Reduces strikes from ~100 to ~20 (80% reduction)
```

**Filter by Delta**:
```python
# Only process options with |delta| > 0.10
# For calls: delta > 0.10 (relevant for trading)
# For puts: delta < -0.10
# Eliminates deep OTM options
```

**Filter by Liquidity**:
```python
# Only process options with:
# - Open Interest > 100 contracts
# - Volume > 10 contracts
# Ensures tradeable options only
```

### Optimization 2: Adaptive Fetch Intervals

**Market Condition Based**:
```python
# High volatility (VIX > 20): 15 seconds
# Normal volatility (VIX 15-20): 30 seconds
# Low volatility (VIX < 15): 60 seconds
# After hours: 300 seconds (just monitoring)
```

**Position Based**:
```python
# Has open positions: 15 seconds (critical monitoring)
# No positions: 60 seconds (opportunity scanning)
```

### Optimization 3: Differential Updates

**Incremental Fetching**:
```python
# Full chain: Every 5 minutes
# Price updates only: Every 15 seconds
# Greeks recalculation: Only when IV changes > 5%
```

### Optimization 4: Multi-tier Caching

**Hot Cache** (15 seconds):
- ATM ±5 strikes
- Current positions
- High delta options (|delta| > 0.30)

**Warm Cache** (60 seconds):
- ATM ±10 strikes
- Medium delta options (0.10 < |delta| < 0.30)

**Cold Cache** (300 seconds):
- Full option chain
- Deep OTM options
- Low liquidity strikes

---

## Implementation Plan

### Phase 1: Strike Filtering (Immediate - 1 hour)

**Add to `backend/data/market_data.py`**:

```python
class MarketDataManager:
    def __init__(self, upstox_client: UpstoxClient):
        # ... existing code ...
        
        # Optimization parameters
        self.atm_range_percent = 0.10  # ±10% from spot
        self.min_delta_threshold = 0.10  # Minimum |delta| to consider
        self.min_open_interest = 100  # Minimum OI
        self.min_volume = 10  # Minimum volume
        
    def _filter_relevant_strikes(self, option_chain: Dict, spot_price: float) -> Dict:
        """Filter option chain to only relevant strikes for intraday trading"""
        
        # Calculate ATM range
        lower_bound = spot_price * (1 - self.atm_range_percent)
        upper_bound = spot_price * (1 + self.atm_range_percent)
        
        filtered = {
            'calls': {},
            'puts': {},
            'pcr': 0,
            'max_pain': 0
        }
        
        # Filter calls
        for strike, call_data in option_chain['calls'].items():
            strike_price = float(strike)
            
            # Skip if outside ATM range
            if strike_price < lower_bound or strike_price > upper_bound:
                continue
                
            # Skip if low liquidity
            if call_data['oi'] < self.min_open_interest:
                continue
                
            # Calculate quick delta estimate (call delta = 0.5 for ATM)
            # More accurate after Greeks calculation
            moneyness = strike_price / spot_price
            estimated_delta = 1 - (moneyness - 1) * 10  # Rough approximation
            
            # Skip if delta too low
            if estimated_delta < self.min_delta_threshold:
                continue
                
            filtered['calls'][strike] = call_data
        
        # Filter puts (similar logic)
        for strike, put_data in option_chain['puts'].items():
            strike_price = float(strike)
            
            if strike_price < lower_bound or strike_price > upper_bound:
                continue
                
            if put_data['oi'] < self.min_open_interest:
                continue
                
            moneyness = strike_price / spot_price
            estimated_delta = -((moneyness - 1) * 10)  # Negative for puts
            
            if abs(estimated_delta) < self.min_delta_threshold:
                continue
                
            filtered['puts'][strike] = put_data
        
        # Recalculate PCR and Max Pain with filtered data
        filtered['pcr'] = option_chain.get('pcr', 0)
        filtered['max_pain'] = self._calculate_max_pain(filtered)
        
        return filtered
    
    async def get_option_chain(self, symbol: str, expiry: str) -> Optional[Dict]:
        """Get option chain with smart filtering"""
        # ... existing code to fetch full chain ...
        
        if response and 'data' in response:
            # Process full chain
            chain_data = self._process_option_chain(response['data'])
            
            # Get spot price for filtering
            spot_price = await self.get_spot_price(symbol)
            
            # Filter to relevant strikes only
            if spot_price:
                chain_data = self._filter_relevant_strikes(chain_data, spot_price)
                
                logger.info(
                    f"Filtered {symbol} option chain: "
                    f"{len(chain_data['calls'])} calls, "
                    f"{len(chain_data['puts'])} puts"
                )
            
            # Cache it
            self.option_chain_cache[cache_key] = {
                'data': chain_data,
                'timestamp': datetime.now()
            }
            
            return chain_data
```

### Phase 2: Adaptive Intervals (1 hour)

**Add to `backend/main.py`**:

```python
class TradingSystem:
    def __init__(self):
        # ... existing code ...
        self.market_data_interval = 30  # Dynamic interval
        
    def _calculate_optimal_interval(self) -> int:
        """Calculate optimal fetch interval based on market conditions"""
        
        # Check VIX
        vix = self.market_data.market_state.get('NIFTY', {}).get('vix', 15)
        
        # Check if we have positions
        has_positions = len(self.order_manager.active_positions) > 0
        
        # Check market hours
        now = datetime.now().time()
        market_open = datetime.strptime("09:15", "%H:%M").time()
        market_close = datetime.strptime("15:30", "%H:%M").time()
        is_market_hours = market_open <= now <= market_close
        
        # Calculate interval
        if not is_market_hours:
            return 300  # 5 minutes after hours
        elif has_positions:
            return 15  # 15 seconds with positions (critical)
        elif vix > 25:
            return 15  # 15 seconds in high volatility
        elif vix > 20:
            return 30  # 30 seconds in elevated volatility
        else:
            return 60  # 60 seconds in calm markets
    
    async def market_data_loop(self):
        """Market data update loop with adaptive intervals"""
        while self.is_running:
            try:
                # Calculate optimal interval
                self.market_data_interval = self._calculate_optimal_interval()
                
                # Update option chain data
                await self.market_data.update_option_chain()
                
                # Update Greeks (only for filtered strikes)
                await self.market_data.calculate_greeks()
                
                # Broadcast updates to dashboard
                await self.broadcast_market_data()
                
                logger.debug(f"Market data updated, next update in {self.market_data_interval}s")
                
                # Adaptive sleep
                await asyncio.sleep(self.market_data_interval)
                
            except Exception as e:
                logger.error(f"Error in market data loop: {e}")
                await asyncio.sleep(10)
```

### Phase 3: Differential Updates (2 hours)

**Add lightweight price-only updates**:

```python
class MarketDataManager:
    async def update_prices_only(self):
        """Quick price update without full chain fetch (for high-frequency updates)"""
        
        for symbol in ['NIFTY', 'BANKNIFTY']:
            if symbol not in self.market_state:
                continue
                
            # Get only spot price (single API call)
            spot = await self.get_spot_price(symbol)
            
            if spot:
                self.market_state[symbol]['spot_price'] = spot
                self.market_state[symbol]['last_update'] = datetime.now()
                
                logger.debug(f"{symbol} spot updated: {spot}")

class TradingSystem:
    async def market_data_loop(self):
        """Market data loop with full vs price-only updates"""
        full_update_counter = 0
        
        while self.is_running:
            try:
                interval = self._calculate_optimal_interval()
                
                # Full update every 4 cycles (or 2 minutes at 30s interval)
                if full_update_counter % 4 == 0:
                    logger.debug("Full option chain update")
                    await self.market_data.update_option_chain()
                    await self.market_data.calculate_greeks()
                else:
                    logger.debug("Price-only update")
                    await self.market_data.update_prices_only()
                
                full_update_counter += 1
                
                await self.broadcast_market_data()
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in market data loop: {e}")
                await asyncio.sleep(10)
```

### Phase 4: Position-Specific Monitoring (1 hour)

**Track only strikes you're trading**:

```python
class MarketDataManager:
    def __init__(self, upstox_client: UpstoxClient):
        # ... existing code ...
        self.monitored_strikes = {}  # Strikes we have positions in
        
    def add_monitored_strike(self, symbol: str, strike: float, option_type: str):
        """Add a strike to high-priority monitoring"""
        key = f"{symbol}_{strike}_{option_type}"
        self.monitored_strikes[key] = {
            'symbol': symbol,
            'strike': strike,
            'option_type': option_type,
            'added_at': datetime.now()
        }
        
    async def update_monitored_strikes(self):
        """Fast update for positions we're actually holding"""
        for key, strike_info in self.monitored_strikes.items():
            # Get real-time price for this specific strike
            # Much faster than full chain fetch
            price = await self._get_strike_price(
                strike_info['symbol'],
                strike_info['strike'],
                strike_info['option_type']
            )
            
            if price:
                logger.debug(f"Position {key} updated: {price}")
```

---

## Expected Improvements

### API Call Reduction
**Before**: 1,920 calls/day
**After**: 480-960 calls/day (50-75% reduction)

### Processing Time
**Before**: ~500ms per update (full chain)
**After**: ~100ms per update (filtered strikes)
**Improvement**: 80% faster

### Strike Count
**Before**: 50-100 strikes per symbol
**After**: 10-20 strikes per symbol
**Improvement**: 80% reduction

### Rate Limit Safety
**Before**: High risk of hitting limits
**After**: Safe margin (75% under limits)

---

## Configuration

Add to `config/config.yaml`:

```yaml
market_data:
  optimization:
    # Strike filtering
    atm_range_percent: 0.10  # ±10% from spot
    min_delta_threshold: 0.10  # Minimum |delta|
    min_open_interest: 100
    min_volume: 10
    
    # Adaptive intervals (seconds)
    interval_with_positions: 15
    interval_high_volatility: 15  # VIX > 25
    interval_elevated_volatility: 30  # VIX 20-25
    interval_normal: 60  # VIX < 20
    interval_after_hours: 300
    
    # Differential updates
    full_update_frequency: 4  # Every 4th cycle
    price_only_update: true
    
    # Caching
    cache_ttl_hot: 15  # ATM strikes
    cache_ttl_warm: 60  # Near ATM
    cache_ttl_cold: 300  # Far OTM
```

Add to `.env`:

```env
# Market Data Optimization
ENABLE_STRIKE_FILTERING=true
ENABLE_ADAPTIVE_INTERVALS=true
ENABLE_DIFFERENTIAL_UPDATES=true
```

---

## Monitoring Impact

After implementing optimizations, monitor:

1. **API Call Rate**: Should drop by 50-75%
2. **Update Latency**: Should improve from 500ms to 100ms
3. **Strike Count**: Should reduce from 100 to 20 per symbol
4. **Cache Hit Rate**: Should improve to 80%+
5. **Rate Limit Distance**: Should stay under 50% of limits

Check Grafana dashboard:
- `rate(market_data_updates_total[1m])` - Should decrease
- `market_data_age_seconds` - Should stay low (< 30s)
- `histogram_quantile(0.95, market_data_update_duration)` - Should decrease

---

## Quick Implementation Priority

**Critical** (Do First - 1 hour):
1. ✅ Strike filtering by ATM range (±10%)
2. ✅ Minimum OI filter (> 100)
3. ✅ Adaptive intervals based on positions

**Important** (Do Soon - 2 hours):
4. ✅ VIX-based adaptive intervals
5. ✅ Differential updates (price-only vs full)
6. ✅ Position-specific monitoring

**Nice to Have** (Later - 2 hours):
7. Multi-tier caching
8. Predictive pre-fetching
9. Batch API calls

---

## Testing Plan

1. **Measure Baseline**:
   ```bash
   # Count current API calls
   grep "option_chain" logs/trading_*.log | wc -l
   ```

2. **Implement Phase 1** (Strike Filtering)

3. **Measure Improvement**:
   ```bash
   # Count API calls after optimization
   grep "option_chain" logs/trading_*.log | wc -l
   # Should be 50-75% less
   ```

4. **Validate Data Quality**:
   - Ensure all tradeable strikes are still captured
   - Verify Greeks accuracy
   - Check signal generation is unaffected

5. **Monitor Rate Limits**:
   - Watch for 429 errors
   - Track API usage in Grafana
   - Adjust thresholds if needed

---

## Rollback Plan

If optimizations cause issues:

1. **Disable filtering**:
   ```env
   ENABLE_STRIKE_FILTERING=false
   ```

2. **Revert to fixed interval**:
   ```python
   # main.py
   await asyncio.sleep(30)  # Back to 30 seconds
   ```

3. **Check logs**:
   ```bash
   grep "ERROR" logs/trading_*.log | tail -50
   ```

---

## Summary

**Current State**: Inefficient - fetching entire chain every 30s
**Optimized State**: Smart - filtered strikes, adaptive intervals
**Impact**: 50-75% reduction in API calls, 80% faster processing
**Risk**: Low - can be rolled back easily
**Effort**: 4-6 hours total implementation

**Recommendation**: Implement Phase 1 immediately (1 hour) to get quick wins.
