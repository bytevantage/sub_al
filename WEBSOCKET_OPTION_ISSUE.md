# WebSocket Option Feed Issue - Root Cause Analysis

## Summary
Upstox WebSocket market feed successfully connects and receives data for **option instruments** (NSE_FO segment), but the protobuf-decoded data contains **empty nested dictionaries** for all price fields, making it impossible to extract LTP values.

## Discovery Timeline

### 1. Initial Investigation ✅
- **Finding**: WebSocket connects successfully
- **Log**: `✓ WebSocket market feed connected`
- **Status**: WORKING

### 2. Subscription Verification ✅
- **Finding**: Options ARE being subscribed correctly
- **Instruments**: `NSE_FO|NIFTY18NOV2025PE25950`, `NSE_FO|NIFTY18NOV2025CE25950`
- **Log**: `✓ Subscribed to 1 instruments: ['NSE_FO|NIFTY18NOV2025PE25950']`
- **Status**: WORKING

### 3. Data Reception ✅
- **Finding**: WebSocket DOES receive data for options
- **Log**: `📊 First data received for: NSE_FO|NIFTY18NOV2025PE25950`
- **Log**: `✓ Processed message #100 from WebSocket`
- **Status**: WORKING

### 4. Callback Execution ✅
- **Finding**: Price callbacks ARE being triggered for options
- **Log**: `🔔 Callback triggered for NSE_FO|NIFTY18NOV2025PE25950`
- **Status**: WORKING

### 5. **ROOT CAUSE: Empty Protobuf Fields** ❌
- **Finding**: All price-related fields in protobuf message are EMPTY
- **Observed Structure**:
  ```python
  {
    'fullFeed': {
      'marketFF': {
        'ltpc': {},           # EMPTY - should contain ltp, close, etc.
        'marketLevel': {},    # EMPTY - should contain bid, ask, last
        'optionGreeks': {}    # EMPTY - should contain delta, gamma, etc.
      }
    },
    'requestMode': 'full'
  }
  ```
- **Status**: **BROKEN FOR OPTIONS**

### 6. Index Feeds Work Fine ✅
- **Finding**: NIFTY and SENSEX indices update normally via WebSocket
- **Log**: `✓ Spot price for NIFTY: 25968.75`
- **Implication**: WebSocket and protobuf parsing work correctly for indices
- **Status**: WORKING

## Technical Analysis

### What Works
1. **WebSocket Connection**: Stable, auto-reconnecting
2. **Subscription Protocol**: Correctly formatted instrument keys
3. **Message Reception**: Receiving protobuf messages for options
4. **Protobuf Decoding**: Creating correct structure (keys present)
5. **Index Feeds**: NIFTY/SENSEX prices update in real-time

### What's Broken
1. **Option Price Fields**: `ltpc`, `marketLevel`, `optionGreeks` are empty dicts
2. **Real-time Option Prices**: Cannot extract LTP from WebSocket feed
3. **P&L Updates**: Positions remain at entry_price (no live updates)

### Possible Causes
1. **Upstox API Limitation**: WebSocket may only provide real-time data for indices, not individual option contracts
2. **Subscription Mode**: May require different mode (currently using "full")
3. **Protobuf Schema Mismatch**: Option feeds may use different protobuf structure
4. **Market Data Permissions**: Account may lack permissions for option WebSocket feeds
5. **Upstox Bug**: Known issue with option feeds (need to check Upstox documentation)

## Evidence

### Log Excerpt - Empty Fields
```
2025-11-17 06:38:56 | ERROR | ❌ Cannot extract LTP for NSE_FO|NIFTY18NOV2025PE25950
2025-11-17 06:38:56 | ERROR |    marketFF: {'ltpc': {}, 'marketLevel': {}, 'optionGreeks': {}}
```

### Comparison: Index vs Option

| Feature | NSE_INDEX (NIFTY) | NSE_FO (Options) |
|---------|-------------------|------------------|
| WebSocket Connection | ✅ Connected | ✅ Connected |
| Subscription Success | ✅ Yes | ✅ Yes |
| Data Reception | ✅ Yes | ✅ Yes |
| Callback Triggered | ✅ Yes | ✅ Yes |
| LTP Extraction | ✅ Success | ❌ Failed |
| Price Updates | ✅ Real-time | ❌ Frozen |

## Solution: REST API Fallback

Since WebSocket feeds don't provide usable data for options, implement REST API polling:

### Implementation Plan
1. **Detect empty WebSocket data** for options
2. **Fall back to REST API** LTP fetch every 5-10 seconds
3. **Use existing risk monitoring loop** (already polls every 2s)
4. **Rate limit**: Max 10 calls/sec (Upstox limit)
5. **Cache**: 5s per instrument to reduce API load

### Code Changes Required
- Modify `update_position_price_from_feed()` to detect empty data
- Add REST API polling in risk monitoring loop
- Use `market_data.get_ltp()` for option instruments
- Log when falling back to REST API

## Files Involved
- `backend/execution/order_manager.py` - Callback and position updates
- `backend/data/market_feed.py` - WebSocket message processing
- `backend/data/market_data.py` - REST API LTP fetching
- `backend/execution/risk_manager.py` - Monitoring loop (already has REST fallback)

## Next Steps
1. ✅ Document root cause (this file)
2. ⏭️ Implement REST API fallback for option prices
3. ⏭️ Update risk monitoring to use REST LTP for options
4. ⏭️ Test with live positions during market hours
5. ⏭️ Monitor rate limiting and adjust polling frequency

## Conclusion
Upstox WebSocket market feed **does not provide usable price data for option instruments** despite successful subscription and message reception. All price-related protobuf fields arrive as empty dictionaries. The system must fall back to REST API polling for option prices while continuing to use WebSocket for index prices.
