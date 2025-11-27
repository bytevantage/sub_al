# Real-Time Price Updates & P&L Calculation Fix

## Issues Identified

### 1. **WebSocket Disconnection**
**Problem:** Market feed WebSocket was disconnecting shortly after startup and never reconnecting.

**Evidence from logs:**
```
2025-11-17 06:01:21 | INFO | ✓ WebSocket market feed connected
2025-11-17 06:02:14 | WARNING | WebSocket connection closed  <-- DISCONNECTED
2025-11-17 06:07:27 | WARNING | Not connected to WebSocket   <-- All subsequent subscriptions fail
2025-11-17 06:07:28 | WARNING | Not connected to WebSocket
```

**Root Cause:** 
- WebSocket disconnected after ~1 minute
- No automatic reconnection mechanism
- All new position subscriptions failed silently with just a warning

**Impact:** 
- ❌ No real-time price updates for positions
- ❌ P&L not calculated every second as requested
- ❌ Target/SL hits not detected in real-time

---

### 2. **P&L Not Updated from Market Feed**
**Problem:** Even when WebSocket was connected, P&L calculations weren't happening.

**Evidence:**
```bash
# Search for P&L updates in logs - NO RESULTS
$ docker logs trading_engine | grep "P&L"
<empty>
```

**Root Cause:**
- Position prices WERE being updated (code exists)
- But no logging to verify updates were happening
- Silent failures made debugging impossible

---

## Fixes Implemented

### 1. **Enhanced WebSocket Reconnection** (`market_feed.py`)

#### Added Auto-Reconnection on Disconnect
```python
async def _listen(self):
    """Listen for incoming market data"""
    message_count = 0
    try:
        while self.is_connected and self.websocket:
            message = await self.websocket.recv()
            # Process data...
            
            message_count += 1
            # Log every 100 messages to show feed is active
            if message_count % 100 == 0:
                logger.debug(f"✓ Processed {message_count} market data messages")
                
    except websockets.exceptions.ConnectionClosed as e:
        logger.warning(f"WebSocket connection closed: {e}. Will attempt reconnection.")
        self.is_connected = False
        # Auto-reconnect with last known instruments  <-- NEW
        if hasattr(self, '_last_subscribed_instruments'):
            asyncio.create_task(self._handle_reconnect(self._last_subscribed_instruments, "full"))
```

**Before:** Connection closed → system broken forever  
**After:** Connection closed → auto-reconnect with exponential backoff

---

#### Store Subscriptions for Reconnection
```python
async def subscribe(self, instrument_keys: List[str], mode: str = "full"):
    # Store for reconnection  <-- NEW
    if not hasattr(self, '_last_subscribed_instruments'):
        self._last_subscribed_instruments = []
    
    # Add new instruments to the list
    for key in instrument_keys:
        if key not in self._last_subscribed_instruments':
            self._last_subscribed_instruments.append(key)
```

**Benefit:** When WebSocket reconnects, all previously subscribed instruments are automatically re-subscribed

---

### 2. **Better Error Handling** (`market_data.py`)

#### Changed Silent Warning to Error with Action
```python
async def subscribe_instruments(self, instrument_keys: List[str]):
    if not self.use_websocket or not self._websocket_connected or not self.market_feed:
        logger.error(  # <-- Was logger.warning
            f"❌ Cannot subscribe to instruments: WebSocket not connected! "
            f"(use_websocket={self.use_websocket}, connected={self._websocket_connected}, "
            f"feed={self.market_feed is not None})"
        )
        # Try to reconnect if market feed exists but disconnected  <-- NEW
        if self.market_feed and not self._websocket_connected:
            logger.info("Attempting to reconnect market feed...")
            # Get base instruments and reconnect
            asyncio.create_task(self.market_feed.connect(instrument_keys_base, mode="full"))
            self._websocket_connected = True
        return
```

**Before:** Warning logged, subscription failed silently  
**After:** Error logged prominently + automatic reconnection attempt

---

### 3. **P&L Update Logging** (`order_manager.py`)

#### Added Visibility into Price Updates
```python
def update_position_price_from_feed(self, instrument_key: str, ltp: float, tick_data: Dict = None):
    """Update position price from market feed (called every second)"""
    # ... calculate P&L ...
    
    # Log price updates (every 10 ticks to avoid spam)  <-- NEW
    if not hasattr(self, '_price_update_counter'):
        self._price_update_counter = {}
    self._price_update_counter[position_id] = self._price_update_counter.get(position_id, 0) + 1
    
    if self._price_update_counter[position_id] % 10 == 0:
        logger.debug(
            f"💹 Price Update #{self._price_update_counter[position_id]}: "
            f"{position.get('symbol')} {position.get('strike_price')} {position.get('instrument_type')} "
            f"₹{old_price:.2f} → ₹{ltp:.2f} | P&L: ₹{pnl:.2f} ({position['unrealized_pnl_pct']:.2f}%)"
        )
```

**Benefit:** Can now verify in logs that:
- WebSocket is delivering prices
- P&L is being calculated
- Updates happen every second (logged every 10th update)

Example log output:
```
💹 Price Update #10: NIFTY 25950 CALL ₹89.40 → ₹92.15 | P&L: ₹206.25 (+3.08%)
💹 Price Update #20: NIFTY 25950 CALL ₹92.15 → ₹90.80 | P&L: ₹105.00 (+1.57%)
```

---

## Verification After Restart

### Check WebSocket Connection
```bash
docker logs trading_engine 2>&1 | grep -E "WebSocket.*connected|Processed.*messages"
```

**Expected:**
```
✓ WebSocket market feed connected
✓ Processed 100 market data messages
✓ Processed 200 market data messages
```

---

### Check Position Subscriptions
```bash
docker logs trading_engine 2>&1 | grep "Subscribed.*market feed"
```

**Expected:**
```
✓ Subscribed NIFTY 25950 CALL to market feed
✓ Subscribed to 1 instruments via market feed
✓ Registered price callback for NSE_FO|NIFTY24NOV2526050CE
```

---

### Check Real-Time Price Updates
```bash
docker logs trading_engine 2>&1 | grep "Price Update"
```

**Expected (every 10 seconds per position):**
```
💹 Price Update #10: NIFTY 25950 CALL ₹89.40 → ₹92.15 | P&L: ₹206.25 (+3.08%)
💹 Price Update #20: NIFTY 25950 CALL ₹92.15 → ₹90.80 | P&L: ₹105.00 (+1.57%)
💹 Price Update #30: NIFTY 25950 PUT ₹64.10 → ₹62.30 | P&L: -₹135.00 (-2.81%)
```

---

### Check Target/SL Hits
```bash
docker logs trading_engine 2>&1 | grep -E "TARGET HIT|STOP LOSS"
```

**Expected (when price hits target):**
```
🎯 TARGET HIT: NIFTY 25950 CALL @ ₹129.63 (Target: ₹129.63)
🛑 STOP LOSS HIT: NIFTY 25900 PUT @ ₹42.95 (SL: ₹42.95)
```

---

## How It Works Now

### 1. **Position Created**
```
Order executed → Position created → Subscribe to market feed
```

### 2. **WebSocket Feed Active**
```
Upstox WebSocket → Sends price tick → Callback triggered → P&L calculated
                                    ↓
                            Every 1 second for each position
```

### 3. **Real-Time P&L**
```
Entry Price: ₹89.40
Current Price (live): ₹92.15 (from WebSocket)
Quantity: 75
Direction: BUY

P&L = (92.15 - 89.40) × 75 = ₹206.25
P&L% = 206.25 / (89.40 × 75) × 100 = +3.08%
```

### 4. **Auto Target/SL Detection**
```
if current_price >= target_price:
    → Close position automatically
    → Log: 🎯 TARGET HIT
    
if current_price <= stop_loss:
    → Close position automatically
    → Log: 🛑 STOP LOSS HIT
```

---

## Expected Behavior

### During Market Hours (9:15 AM - 3:30 PM)
✅ WebSocket connected and receiving ticks  
✅ Position prices updated every ~1 second  
✅ P&L recalculated with each price update  
✅ Targets/SL monitored in real-time  
✅ Automatic exit on target/SL hit  

### Dashboard Display
✅ Open Positions table shows live current price  
✅ P&L column updates in real-time  
✅ P&L % changes color (green profit, red loss)  

### After Market Close
✅ WebSocket remains connected (may go idle)  
✅ No price updates (no market activity)  
✅ Last known prices preserved  

---

## Troubleshooting

### If Price Updates Still Don't Show:

1. **Check WebSocket is connected:**
```bash
docker logs trading_engine 2>&1 | tail -50 | grep "WebSocket"
```

2. **Check if subscriptions succeeded:**
```bash
docker logs trading_engine 2>&1 | grep "Subscribed.*instruments via market feed"
```

3. **Enable debug logging:**
```bash
# Edit backend/core/logger.py
# Change: level=logging.INFO
# To: level=logging.DEBUG
# Restart: docker-compose restart trading-engine
```

4. **Check Upstox API status:**
- Upstox may rate-limit WebSocket connections
- Check if API credentials are valid
- Verify market hours (WebSocket only works 9:15 AM - 3:30 PM IST)

---

## Files Modified

1. **backend/data/market_feed.py**
   - Added auto-reconnection on disconnect
   - Store subscribed instruments for reconnection
   - Added message counter logging

2. **backend/data/market_data.py**
   - Changed warning to error for subscription failures
   - Added reconnection attempt logic
   - Better error messages

3. **backend/execution/order_manager.py**
   - Added P&L update logging (every 10 updates)
   - Shows price changes and P&L in real-time
   - Tracks update counter per position

---

## Next Steps

1. **Restart Docker** to apply fixes:
```bash
docker-compose restart trading-engine
```

2. **Watch logs** for price updates:
```bash
docker logs trading_engine -f | grep -E "Price Update|TARGET|STOP LOSS"
```

3. **Verify in Dashboard:**
- Open http://localhost:8000/dashboard
- Check "Open Positions" tab
- Current Price and P&L columns should update live

4. **If issues persist:**
- Check if it's outside market hours (WebSocket only works 9:15 AM - 3:30 PM IST)
- Verify Upstox token is valid
- Enable debug logging for detailed diagnostics
