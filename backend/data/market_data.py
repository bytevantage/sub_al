"""
Market Data Manager

























































































































































































































































































































































5. Train model to predict profitable entry points4. Build features: entry Greeks, IV trends, OI divergence3. Query historical data for ML model training2. Let system run for a day to collect snapshots1. Restart Docker to create new table**Next Steps:**- ✅ `backend/data/market_data.py` - Integrated automatic snapshot saving- ✅ `backend/services/option_chain_persistence.py` - New persistence service  - ✅ `backend/database/models.py` - Added `OptionChainSnapshot` model**Files Changed:****Performance:** Zero impact on trading loop (async saves)  **Use Case:** Train ML models on complete historical option data with Greeks  **Implementation:** Automatic, non-blocking, rate-limited saves  **Solution:** Persist snapshots to database, use for ML training  **Rate Limiting:** Caused by REST API option chain fetches (no WebSocket alternative)  ## Summary---- No new API calls, just Black-Scholes math- WebSocket spot price update → recalculate Greeks → update cacheCurrently Greeks are calculated once per minute. Could improve to:### 3. **Real-time Greeks Calculation**- Good for archival data- Slower queries (need to parse JSON)- Faster writes (1 row instead of 100+)```)    spot_price=25938.7    option_chain_json=json.dumps(chain_data),  # All strikes as JSON    symbol='NIFTY',    timestamp=now,OptionChainBulkSnapshot(```pythonStore option chain as JSON blob instead of individual rows:### 2. **Compressed Storage**- Reduces DB size by 70%- High OI strikes (> 100,000 OI)- ATM ± 5 strikes (already filtered by `_filter_relevant_strikes`)Instead of saving every strike, save only:### 1. **Snapshot Aggregation**## Future Enhancements---```docker exec trading_engine python -c "from backend.database.database import init_db; init_db()"# Or manually run:# The table will be auto-created on first run by SQLAlchemy```bash**To create the new table:**## Database Migration---✅ **No Code Changes:** Strategies continue working as-is  ✅ **Auto Cleanup:** Old data automatically pruned  ✅ **Rate Limited:** Max 1 save/min to avoid DB bloat  ✅ **No Performance Impact:** Async non-blocking saves  ### For Trading System:✅ **Efficient Queries:** Indexed for fast historical lookups  ✅ **No Manual Collection:** Automatic background saving  ✅ **Context Preserved:** Spot price, OI, volume all saved together  ✅ **Time-Correlated:** Match option data at exact trade entry/exit times  ✅ **Complete Historical Data:** Every option chain fetch is saved with full Greeks  ### For ML Training:## Benefits---```        })            'signal_strength': abs(oi_change_pct) + abs(price_change_pct)            'strike': strike,            'timestamp': snapshot['timestamp'],        reversal_signals.append({    if oi_change_pct > 0.05 and price_change_pct < -0.02:    # Divergence: OI up, price down = potential reversal        price_change_pct = (snapshot['ltp'] - prev_ltp) / prev_ltp    oi_change_pct = snapshot['oi_change'] / snapshot['oi'] if snapshot['oi'] > 0 else 0for snapshot in historical_snapshots:# Get option and underlying data together```python**Question:** *"Does OI change + price divergence predict reversals?"*### 4. **OI Divergence Signals**```# Train model to detect IV expansion (risky) vs stable IV]    for s1, s2 in zip(pre_event_snapshots[:-1], pre_event_snapshots[1:])    (s2['iv'] - s1['iv']) / s1['iv'] iv_changes = [# Calculate IV rate of change)    hours_back=24    'NIFTY', 25950, 'CALL',pre_event_snapshots = persistence.get_historical_snapshots(# Get IV trends for strikes before big moves```python**Question:** *"Can we predict IV crush to avoid bad entries?"*### 3. **IV Crush Detection**```# Analyze delta decay, theta burn, etc.]    if entry_time <= s['timestamp'] <= exit_time    s for s in snapshots trade_snapshots = [# Filter to trade duration)    hours_back=int(duration_hours) + 1    trade.instrument_type,    trade.strike_price,    trade.symbol,snapshots = persistence.get_historical_snapshots(duration_hours = (exit_time - entry_time).seconds / 3600exit_time = trade.exit_timeentry_time = trade.entry_time# Get historical snapshots for a trade duration```python**Question:** *"How do successful trades' Greeks evolve vs failed ones?"*### 2. **Greeks Evolution Patterns**```        })            'pnl_percent': trade.pnl_percentage            'profit': trade.net_pnl > 0,            # Target (label)                        'moneyness': trade.strike_price / snapshot['spot_price'],            'spot_price': snapshot['spot_price'],            'oi_change': snapshot['oi_change'],            'entry_oi': snapshot['oi'],            'entry_iv': snapshot['iv'],            'entry_gamma': snapshot['gamma'],            'entry_delta': snapshot['delta'],            # Entry features        training_data.append({    if snapshot:        )        trade.entry_time        trade.instrument_type,        trade.strike_price,        trade.symbol,    snapshot = persistence.get_snapshot_at_time(for trade in trades:training_data = []# For each trade, get option snapshot at entry).all()    Trade.entry_time >= datetime.now() - timedelta(days=30)    Trade.instrument_type == 'CALL',    Trade.symbol == 'NIFTY',trades = db.query(Trade).filter(# Get all NIFTY CALL trades from last 30 days```python**Question:** *"What Greeks/IV/OI conditions lead to profitable entries?"*### 1. **Entry Point Analysis**## Use Cases for ML Training---- ✅ Complete data: All strikes, Greeks, OI, volume- ✅ Rate limited: Max 1 save per minute per symbol- ✅ Automatic: No manual intervention needed- ✅ Non-blocking: Doesn't slow down trading loop**Benefits:**```        )            )                symbol, chain_data, spot_price                self.option_chain_persistence.save_option_chain_snapshot,            asyncio.to_thread(        asyncio.create_task(    if spot_price:    # Save snapshot to database (async, non-blocking)        # ... fetch option chain from Upstox API ...async def get_option_chain(self, symbol: str, expiry: str):```python**Automatic Snapshot Saving:****File:** `backend/data/market_data.py`### 2. Integration with `MarketDataManager`---- Prevents database bloat- Keeps last 30 days by default- Automatically cleans up old data#### `cleanup_old_snapshots(days_to_keep=30)````# Now correlate entry Greeks with trade outcome for ML)    tolerance_minutes=5    target_time=trade_entry_time,    'NIFTY', 25950, 'CALL', entry_snapshot = persistence.get_snapshot_at_time(# Get option data at entrytrade_entry_time = datetime(2025, 11, 17, 11, 7, 28)# When analyzing a completed trade:```python**Example:**- **Critical for ML training:** Match option data at trade entry/exit times- Gets snapshot closest to a specific time#### `get_snapshot_at_time(symbol, strike, option_type, target_time, tolerance_minutes=5)````]    # ... more snapshots    },        'spot_price': 25938.7        'volume': 50000,        'oi_change': 5000,        'oi': 125000,        'iv': 14.97,        'vega': 12.5,        'theta': -5.2,        'gamma': 0.02,        'delta': 0.55,        'ltp': 89.40,        'timestamp': datetime(2025, 11, 17, 10, 30),    {[# Result:history = persistence.get_historical_snapshots('NIFTY', 25950, 'CALL', hours_back=24)# Get historical data for NIFTY 25950 CALL over last 24 hours```python**Example for ML Training:**- Returns list of snapshots with all Greeks and market data- Retrieves historical snapshots for ML training#### `get_historical_snapshots(symbol, strike, option_type, hours_back=24)````persistence.save_option_chain_snapshot('NIFTY', option_chain, spot_price)# Automatically called after fetching option chain```python**Example Usage:**- Saves both CALL and PUT options with all Greeks- Rate limited to **1 save per 60 seconds** per symbol to avoid DB bloat- Saves option chain snapshot to database#### `save_option_chain_snapshot(symbol, option_chain, spot_price)`**Key Methods:****File:** `backend/services/option_chain_persistence.py`### 1. New Service: `OptionChainPersistenceService`## Implementation---```);    INDEX idx_snapshot_strike_type (symbol, strike_price, option_type)    INDEX idx_snapshot_symbol_time (symbol, timestamp),    -- Indexes        spot_price FLOAT,    -- Context        iv FLOAT,  -- Implied Volatility    vega FLOAT,    theta FLOAT,    gamma FLOAT,    delta FLOAT,    -- Greeks        oi_change INTEGER,    oi INTEGER,    volume INTEGER,    ask FLOAT,    bid FLOAT,    ltp FLOAT,    -- Market data        expiry DATETIME NOT NULL,    option_type VARCHAR(4) NOT NULL, -- CALL or PUT    strike_price FLOAT NOT NULL,    symbol VARCHAR(20) NOT NULL,     -- NIFTY, SENSEX    -- Identification        timestamp DATETIME NOT NULL,    id INTEGER PRIMARY KEY,CREATE TABLE option_chain_snapshots (```sql**Schema:****Purpose:** Store historical option chain data with Greeks for ML model training### New Database Table: `option_chain_snapshots`## Solution: Persist Option Chain Snapshots---After the cache warms up (60s TTL), rate limiting reduces significantly.4. On startup, cache is empty → multiple rapid calls → **rate limiting**3. Which calls `get_option_chain()` → **REST API call** (rate limited)2. Which calls `get_instrument_data()` for NIFTY and SENSEX1. Calls `get_current_state()`Every 30 seconds, the trading loop:Upstox does **NOT provide WebSocket feeds for option chains**. Only REST API: `/v2/option/chain`**Root Cause:**- ❌ **REST API calls** - Used for option chain data - **Rate limited to 10 calls/sec by Upstox**- ✅ **WebSocket Market Feed** - Used for real-time spot prices (NIFTY, SENSEX indices) and position updates - **NO rate limiting****Answer:** YES! You identified the exact issue:**Question:** *"What is the reason for rate limiting? Are we not using market feed for everything other than fetching option chains?"*### Rate Limiting Issue## Problem StatementHandles option chain data, streaming, and historical data
"""

import asyncio
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime, timedelta
import numpy as np
from scipy.stats import norm
import pandas as pd
import numpy as np

from backend.core.upstox_client import UpstoxClient
from backend.core.logger import get_data_logger
from backend.data.proto import MarketDataFeedV3_pb2 as pb
from backend.cache.redis_cache import get_cache_manager
from backend.data.technical_indicators import TechnicalIndicators
from backend.services.option_chain_persistence import OptionChainPersistenceService
from backend.data.market_feed import MarketFeedManager
from backend.services.price_history_tracker import PriceHistoryTracker
from backend.services.technical_indicators import TechnicalIndicators as MultiTimeframeIndicators
from backend.data.iv_rank_calculator import IVRankCalculator
from backend.data.session_vwap import SessionVWAP

if TYPE_CHECKING:
    from backend.safety.market_monitor import MarketMonitor
    from backend.safety.data_monitor import MarketDataMonitor

logger = get_data_logger()


class MarketDataManager:
    """Manages market data collection and distribution"""
    
    def __init__(self, upstox_client: UpstoxClient):
        self.upstox_client = upstox_client
        self.option_chain_cache = {}
        self.price_cache = {}
        self.spot_price_cache = {}  # Cache spot prices aggressively (10s TTL)
        self.oi_cache = {}
        self.greeks_cache = {}
        self.option_chain_failure_cache = {}
        
        # Redis cache manager for performance
        self.redis_cache = get_cache_manager()
        
        # WebSocket market feed for real-time data (eliminates rate limiting)
        self.market_feed: Optional[MarketFeedManager] = None
        self.use_websocket = True  # Flag to enable/disable WebSocket
        self._websocket_connected = False
        
        # Technical indicators (legacy - for backward compatibility)
        self.technical_indicators = TechnicalIndicators()
        
        # Option chain persistence service for ML training
        self.option_chain_persistence = OptionChainPersistenceService()
        
        # Price history tracker for prev_close and OHLC data
        self.price_history_tracker = PriceHistoryTracker(upstox_client)
        
        # Multi-timeframe technical indicators
        self.multi_timeframe_indicators = MultiTimeframeIndicators(upstox_client)
        
        # Real IV Rank calculator
        self.iv_rank_calculator = IVRankCalculator(upstox_client)
        
        # Session VWAP calculator
        self.session_vwap = SessionVWAP(upstox_client)
        
        # Initialize market state to prevent downstream AttributeError
        self.market_state = {
            'NIFTY': {},
            'SENSEX': {}
        }
        
        # Optimization parameters
        self.atm_range_percent = 0.10  # ±10% from spot for strike filtering
        self.min_delta_threshold = 0.10  # Minimum |delta| to consider
        self.min_open_interest = 50  # Minimum OI for liquidity (lowered for intraday detection)
        self.min_volume = 5  # Minimum volume for active trading (lowered to catch early moves)
        self.atm_core_percent = 0.02  # ±2% from spot - always preserve these strikes
        
        # Symbol-specific expiry tracking (NIFTY and SENSEX only)
        self.expiry_config = {
            'NIFTY': ('weekly', 1),      # Weekly, Tuesday ✅
            'SENSEX': ('weekly', 3),      # Weekly, Thursday ✅
        }
        # Remove hardcoded current_expiry - calculate per symbol dynamically

        # Safety monitors
        self.market_monitor: Optional["MarketMonitor"] = None
        self.data_monitor: Optional["MarketDataMonitor"] = None

    async def initialize_websocket_feed(self):
        """Initialize WebSocket market feed for real-time data"""
        try:
            if not self.use_websocket:
                logger.info("WebSocket feed disabled, using REST API polling")
                return
            
            # Get access token from upstox client
            access_token = self.upstox_client.access_token
            
            # Initialize market feed manager
            self.market_feed = MarketFeedManager(access_token)
            
            # Determine instruments to subscribe based on config
            from backend.core.config import config
            instruments = config.get("instruments", [])
            
            instrument_keys = []
            for inst in instruments:
                symbol = inst.get("symbol")
                if symbol == "NIFTY":
                    instrument_keys.append("NSE_INDEX|Nifty 50")
                elif symbol == "BANKNIFTY":
                    instrument_keys.append("NSE_INDEX|Nifty Bank")
                elif symbol == "SENSEX":
                    instrument_keys.append("BSE_INDEX|SENSEX")
            
            if not instrument_keys:
                logger.warning("No instruments configured for WebSocket feed")
                return
            
            # Connect and subscribe
            await self.market_feed.connect(instrument_keys, mode="full")
            self._websocket_connected = True
            logger.info(f"✓ WebSocket feed initialized for {len(instrument_keys)} instruments")
            
        except Exception as e:
            logger.error(f"Failed to initialize WebSocket feed: {e}")
            logger.info("Falling back to REST API polling")
            self.use_websocket = False
            self._websocket_connected = False

    async def subscribe_instruments(self, instrument_keys: List[str]):
        """Subscribe to additional instruments in the market feed"""
        try:
            if not self.use_websocket or not self._websocket_connected or not self.market_feed:
                logger.error(
                    f"❌ Cannot subscribe to instruments: WebSocket not connected! "
                    f"(use_websocket={self.use_websocket}, connected={self._websocket_connected}, "
                    f"feed={self.market_feed is not None})"
                )
                # Try to reconnect if market feed exists but disconnected
                if self.market_feed and not self._websocket_connected:
                    logger.info("Attempting to reconnect market feed...")
                    # Get instruments from config for reconnection
                    from backend.core.config import config
                    instruments = config.get("instruments", [])
                    instrument_keys_base = []
                    for inst in instruments:
                        symbol = inst.get("symbol")
                        if symbol == "NIFTY":
                            instrument_keys_base.append("NSE_INDEX|Nifty 50")
                        elif symbol == "BANKNIFTY":
                            instrument_keys_base.append("NSE_INDEX|Nifty Bank")
                        elif symbol == "SENSEX":
                            instrument_keys_base.append("BSE_INDEX|SENSEX")
                    
                    if instrument_keys_base:
                        try:
                            await self.market_feed.connect(instrument_keys_base, mode="full")
                            self._websocket_connected = True
                            logger.info("✓ Market feed reconnected successfully")
                        except Exception as e:
                            logger.error(f"Failed to reconnect market feed: {e}")
                            self.use_websocket = False
                            self._websocket_connected = False
                            return
                
                if not self._websocket_connected:
                    logger.warning("⚠️ WebSocket unavailable, using REST API fallback")
                    return
            
            # Subscribe new instruments
            await self.market_feed.subscribe(instrument_keys, mode="full")
            logger.info(f"✓ Subscribed to {len(instrument_keys)} additional instruments")
            
        except Exception as e:
            logger.error(f"Error subscribing to instruments: {e}")
            # Don't disable WebSocket for subscription errors, just log them
    
    def register_price_callback(self, instrument_key: str, callback):
        """Register callback for real-time price updates on specific instrument"""
        try:
            if not self.market_feed:
                logger.warning("Market feed not initialized, cannot register callback")
                return
            
            # Register callback with market feed
            self.market_feed.register_callback(instrument_key, callback)
            logger.info(f"✓ Registered price callback for {instrument_key}")
        except Exception as e:
            logger.error(f"Error registering price callback: {e}")

    def set_monitors(
        self,
        market_monitor: Optional["MarketMonitor"] = None,
        data_monitor: Optional["MarketDataMonitor"] = None
    ):
        """Attach safety monitors for market condition and data quality."""
        self.market_monitor = market_monitor
        self.data_monitor = data_monitor
        
    def _get_current_weekly_expiry(self, symbol: str = 'SENSEX') -> str:
        """
        Get current expiry for the given symbol
        
        Args:
            symbol: Trading symbol (NIFTY, BANKNIFTY, or SENSEX)
            
        Returns:
            Expiry date in YYYY-MM-DD format
            
        Expiry Schedule:
        - NIFTY: Every Tuesday (weekly) ✅
        - BANKNIFTY: Last Thursday of month (monthly)
        - SENSEX: Every Thursday (weekly) ✅
        """
        today = datetime.now()
        expiry_type, target_weekday = self.expiry_config.get(symbol, ('weekly', 3))
        
        if expiry_type == 'monthly':
            # BANKNIFTY - Last Thursday of the month
            expiry = self._get_last_thursday_of_month(today)
            return expiry
        else:
            # NIFTY (Tuesday) or SENSEX (Thursday) - Weekly
            days_ahead = target_weekday - today.weekday()
            
            # If today is the expiry day, check if market has closed (3:30 PM IST)
            if days_ahead == 0:
                # Today is expiry day - check time
                # Use 3:30 PM IST as cutoff (15:30)
                if today.hour >= 15 and today.minute >= 30:
                    # Market closed, use next week's expiry
                    days_ahead = 7
                # else: use today's expiry (days_ahead stays 0)
            elif days_ahead < 0:
                # Expiry day has passed this week, get next week
                days_ahead += 7
                
            expiry = today + timedelta(days=days_ahead)
            return expiry.strftime("%Y-%m-%d")
    
    def _get_last_thursday_of_month(self, reference_date: datetime) -> str:
        """
        Get the last Thursday of the current or next month
        
        Args:
            reference_date: Reference date
            
        Returns:
            Last Thursday in YYYY-MM-DD format
        """
        # Start with the last day of current month
        if reference_date.month == 12:
            last_day = datetime(reference_date.year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(reference_date.year, reference_date.month + 1, 1) - timedelta(days=1)
        
        # Find the last Thursday
        # Thursday is weekday 3 (Mon=0, Thu=3)
        days_back = (last_day.weekday() - 3) % 7
        last_thursday = last_day - timedelta(days=days_back)
        
        # If last Thursday has passed, get next month's last Thursday
        if last_thursday < reference_date:
            # Move to next month
            if last_day.month == 12:
                next_month_last = datetime(last_day.year + 1, 2, 1) - timedelta(days=1)
            else:
                next_month_last = datetime(last_day.year, last_day.month + 2, 1) - timedelta(days=1)
            
            days_back = (next_month_last.weekday() - 3) % 7
            last_thursday = next_month_last - timedelta(days=days_back)
        
        return last_thursday.strftime("%Y-%m-%d")
    
    async def get_current_state(self) -> Dict[str, Any]:
        """
        Get current market state for NIFTY and SENSEX
        Updates self.market_state with fresh data including timestamps
        """
        try:
            state = {}
            
            # Get data for Nifty
            nifty_data = await self.get_instrument_data("NIFTY")
            if nifty_data:
                # Ensure PCR is present and derive from option_chain if missing
                if 'pcr' not in nifty_data or nifty_data.get('pcr') in (None, 0):
                    oc = nifty_data.get('option_chain') or {}
                    total_call = oc.get('total_call_oi') or oc.get('total_call_oi', 0)
                    total_put = oc.get('total_put_oi') or oc.get('total_put_oi', 0)
                    try:
                        nifty_data['pcr'] = (total_put / total_call) if total_call and total_call > 0 else oc.get('pcr', 1.0)
                    except Exception:
                        nifty_data['pcr'] = oc.get('pcr', 1.0)

                state["NIFTY"] = nifty_data
                # market_state already updated in get_instrument_data()
            
            # Get data for Sensex
            sensex_data = await self.get_instrument_data("SENSEX")
            if sensex_data:
                # If SENSEX lacks PCR, prefer NIFTY's PCR (production rule)
                if 'pcr' not in sensex_data or sensex_data.get('pcr') in (None, 0):
                    nifty_pcr = state.get('NIFTY', {}).get('pcr')
                    if nifty_pcr:
                        sensex_data['pcr'] = nifty_pcr
                    else:
                        oc = sensex_data.get('option_chain') or {}
                        total_call = oc.get('total_call_oi') or 0
                        total_put = oc.get('total_put_oi') or 0
                        try:
                            sensex_data['pcr'] = (total_put / total_call) if total_call and total_call > 0 else oc.get('pcr', 1.0)
                        except Exception:
                            sensex_data['pcr'] = oc.get('pcr', 1.0)

                state["SENSEX"] = sensex_data
                # market_state already updated in get_instrument_data()
            
            # Add freshness indicator
            state["last_update"] = datetime.now()
            state["is_stale"] = False
            # Log final published PCRs for observability
            try:
                logger.info(
                    f"PUBLISHED MARKET STATE: NIFTY_pcr={state.get('NIFTY',{}).get('pcr')} | SENSEX_pcr={state.get('SENSEX',{}).get('pcr')}"
                )
            except Exception:
                pass
            
            return state
            
        except Exception as e:
            logger.error(f"Error getting current state: {e}")
            return {"is_stale": True, "last_update": None}
    
    async def get_instrument_data(self, symbol: str) -> Optional[Dict]:
        """Get complete data for an instrument"""
        try:
            # Get spot price
            spot_price = await self.get_spot_price(symbol)
            if not spot_price:
                return None
            
            # Get symbol-specific expiry
            symbol_expiry = self._get_current_weekly_expiry(symbol)
            
            # Get option chain
            option_chain = await self.get_option_chain(symbol, symbol_expiry)
            
            # Calculate ATM strike
            atm_strike = self._calculate_atm_strike(spot_price, symbol)
            
            # Get ITM/OTM options around ATM
            strikes = self._get_relevant_strikes(atm_strike, symbol)
            
            # Get multi-timeframe technical analysis
            instrument_key = self._get_index_instrument_key(symbol)
            try:
                multi_timeframe = await self.multi_timeframe_indicators.get_multi_timeframe_analysis(
                    instrument_key,
                    timeframes=['5minute', '15minute', '1hour']
                )
                logger.info(f"✓ Multi-timeframe analysis fetched for {symbol}")
            except Exception as e:
                logger.error(f"✗ Failed to fetch multi-timeframe analysis for {symbol}: {e}")
                multi_timeframe = None
            
            # Get historical data for ML Strategy (last 60 bars of 1-minute candles)
            try:
                historical_response = self.upstox_client.get_intraday_candles(
                    instrument_key, 
                    '1minute'
                )
                logger.debug(f"Historical response for {symbol}: {historical_response}")
                if historical_response and 'data' in historical_response and 'candles' in historical_response['data']:
                    # Convert to list of OHLCV dicts
                    historical_data = []
                    data_list = list(historical_response['data']['candles'])  # Convert to list first
                    
                    # Get last 60 bars (most recent)
                    recent_candles = data_list[-60:] if len(data_list) > 60 else data_list
                    
                    for candle in recent_candles:
                        # V3 API returns list format: [timestamp, open, high, low, close, volume, oi]
                        if isinstance(candle, list) and len(candle) >= 6:
                            historical_data.append({
                                'open': float(candle[1]),
                                'high': float(candle[2]),
                                'low': float(candle[3]),
                                'close': float(candle[4]),
                                'volume': int(candle[5]) if len(candle) > 5 else 0,
                                'timestamp': candle[0],
                                'oi': int(candle[6]) if len(candle) > 6 else 0
                            })
                        elif isinstance(candle, dict):
                            historical_data.append({
                                'open': candle.get('open', 0),
                                'high': candle.get('high', 0),
                                'low': candle.get('low', 0),
                                'close': candle.get('close', 0),
                                'volume': candle.get('volume', 0),
                                'timestamp': candle.get('timestamp', ''),
                                'oi': candle.get('oi', 0)
                            })
                    logger.info(f"✓ Fetched {len(historical_data)} historical bars for {symbol} (V3 API)")
                else:
                    historical_data = []
                    logger.warning(f"No historical data available for {symbol}")
            except Exception as e:
                logger.error(f"Failed to fetch historical data for {symbol}: {e}")
                historical_data = []
            
            # Extract technical indicators from multi_timeframe
            # Use 5minute data if 1hour is not available (more responsive for intraday)
            technical_indicators = {}
            if multi_timeframe:
                if '1hour' in multi_timeframe and multi_timeframe['1hour']:
                    technical_indicators = multi_timeframe['1hour']
                elif '5minute' in multi_timeframe and multi_timeframe['5minute']:
                    technical_indicators = multi_timeframe['5minute']
                    logger.info(f"Using 5minute indicators for {symbol} (1hour not available)")
                elif '15minute' in multi_timeframe and multi_timeframe['15minute']:
                    technical_indicators = multi_timeframe['15minute']
                    logger.info(f"Using 15minute indicators for {symbol} (5minute/1hour not available)")
            
            # Ensure VIX and ADX are included if available from any timeframe
            if not technical_indicators.get('vix') and multi_timeframe:
                for tf in ['5minute', '15minute', '1hour']:
                    if multi_timeframe.get(tf) and multi_timeframe[tf].get('vix'):
                        technical_indicators['vix'] = multi_timeframe[tf]['vix']
                        break
            if not technical_indicators.get('adx') and multi_timeframe:
                for tf in ['5minute', '15minute', '1hour']:
                    if multi_timeframe.get(tf) and multi_timeframe[tf].get('adx'):
                        technical_indicators['adx'] = multi_timeframe[tf]['adx']
                        break
            
            # Add real Session VWAP (resets daily at 9:15 AM IST)
            try:
                session_vwap_data = await self.session_vwap.get_session_vwap(symbol)
                technical_indicators['vwap'] = session_vwap_data['vwap']
                technical_indicators['vwap_deviation_pct'] = session_vwap_data['vwap_deviation_pct']
                technical_indicators['session_volume'] = session_vwap_data['total_volume']
                technical_indicators['session_range_pct'] = session_vwap_data['session_range_pct']
                logger.info(f"✅ Session VWAP for {symbol}: ₹{session_vwap_data['vwap']:.2f} "
                          f"(Deviation: {session_vwap_data['vwap_deviation_pct']:.3f}%)")
            except Exception as e:
                logger.error(f"Failed to get session VWAP for {symbol}: {e}")
                # Fallback to historical VWAP if session VWAP fails
                if historical_data:
                    total_pv = 0
                    total_volume = 0
                    for candle in historical_data[-20:]:  # Use last 20 candles
                        typical_price = (candle['high'] + candle['low'] + candle['close']) / 3
                        volume = candle.get('volume', 1)
                        total_pv += typical_price * volume
                        total_volume += volume
                    if total_volume > 0:
                        technical_indicators['vwap'] = total_pv / total_volume
                        technical_indicators['vwap_deviation_pct'] = 0
                        technical_indicators['session_volume'] = total_volume
                        technical_indicators['session_range_pct'] = 0
                        logger.info(f"⚠️ Using fallback VWAP for {symbol}: ₹{technical_indicators['vwap']:.2f}")
                else:
                    technical_indicators['vwap'] = spot_price
                    technical_indicators['vwap_deviation_pct'] = 0
                    technical_indicators['session_volume'] = 0
                    technical_indicators['session_range_pct'] = 0
            
            # Add real IV Rank
            try:
                iv_rank_data = await self.iv_rank_calculator.get_real_iv_rank(symbol)
                technical_indicators['iv_rank'] = iv_rank_data['iv_rank']
                technical_indicators['iv_percentile'] = iv_rank_data['iv_percentile']
                technical_indicators['current_iv'] = iv_rank_data['current_iv']
                logger.info(f"✅ Real IV Rank for {symbol}: {iv_rank_data['iv_rank']:.1f}%")
            except Exception as e:
                logger.error(f"Failed to get real IV Rank for {symbol}: {e}")
                technical_indicators['iv_rank'] = 50
                technical_indicators['iv_percentile'] = 50
                technical_indicators['current_iv'] = 18.0
            
            # Add other default indicators if missing
            if 'sma_20' not in technical_indicators:
                technical_indicators['sma_20'] = spot_price
            if 'sma_50' not in technical_indicators:
                technical_indicators['sma_50'] = spot_price
            if 'rsi' not in technical_indicators:
                technical_indicators['rsi'] = 50
            if 'vwap' not in technical_indicators:
                technical_indicators['vwap'] = spot_price
            
            # Build instrument data
            data = {
                "symbol": symbol,
                "spot_price": spot_price,
                "atm_strike": atm_strike,
                "expiry": symbol_expiry,
                "option_chain": option_chain,
                "strikes": strikes,
                "multi_timeframe": multi_timeframe,
                "technical_indicators": technical_indicators,
                "iv_rank": multi_timeframe.get('1hour', {}).get('indicators', {}).get('iv_rank', 50) if multi_timeframe else 50,
                "historical_data": historical_data,  # Add historical data for ML Strategy
                "timestamp": datetime.now().isoformat()
            }
            
            # Add timestamp to option chain for freshness validation
            if option_chain:
                option_chain['timestamp'] = datetime.now().isoformat()
                option_chain['fetch_time'] = datetime.now()
            
            # Populate market_state for downstream strategies and Greeks calculation
            self.market_state[symbol] = {
                'spot_price': spot_price,
                'atm_strike': atm_strike,
                'expiry': symbol_expiry,
                'option_chain': option_chain,
                'pcr': option_chain.get('pcr', 1.0) if option_chain else 1.0,  # Fixed: use 1.0 as neutral default
                'max_pain': option_chain.get('max_pain', 0) if option_chain else 0,
                'historical_data': historical_data,  # Add historical data for ML Strategy
                'total_call_oi': option_chain.get('total_call_oi', 0) if option_chain else 0,
                'total_put_oi': option_chain.get('total_put_oi', 0) if option_chain else 0,
                'total_oi': option_chain.get('total_oi', 0) if option_chain else 0,
                'multi_timeframe': multi_timeframe,
                'technical_indicators': technical_indicators,
                'iv_rank': technical_indicators.get('iv_rank', 50),  # Use real IV Rank from technical_indicators
                'timestamp': datetime.now()
            }
            
            return self.market_state[symbol]
            
        except Exception as e:
            logger.error(f"Error getting instrument data for {symbol}: {e}")
            return None
    
    async def get_spot_price(self, symbol: str) -> Optional[float]:
        """Get spot price for underlying - uses Redis + in-memory caching to prevent rate limiting"""
        
        # Check Redis cache first
        if self.redis_cache.is_available():
            cached_price = self.redis_cache.get_spot_price(symbol)
            if cached_price is not None:
                logger.debug(f"✓ Redis cache hit: spot price for {symbol}: {cached_price}")
                return cached_price
        
        # Check in-memory cache - 5 second TTL for rate limiting safety
        cache_key = f"spot_{symbol}"
        if cache_key in self.spot_price_cache:
            cached_data = self.spot_price_cache[cache_key]
            # Defensive check for cache structure
            if not isinstance(cached_data, dict) or 'timestamp' not in cached_data or 'price' not in cached_data:
                logger.warning(f"Corrupted cache entry for {symbol}, removing and refetching")
                del self.spot_price_cache[cache_key]
            else:
                cache_age = (datetime.now() - cached_data['timestamp']).total_seconds()
                if cache_age < 5:  # 5 second cache - BALANCED for rate limiting
                    logger.debug(f"Using cached spot price for {symbol}: {cached_data['price']} (age: {cache_age:.1f}s)")
                    return cached_data['price']
        
        instrument_key = self._get_index_instrument_key(symbol)
        
        # Try WebSocket feed first
        if self.use_websocket and self._websocket_connected and self.market_feed:
            try:
                price = self.market_feed.get_spot_price(instrument_key)
                if price is not None:
                    logger.debug(f"✓ Spot price for {symbol}: {price} (WebSocket)")
                    # Cache it in both Redis and memory
                    self.redis_cache.set_spot_price(symbol, price)
                    self.spot_price_cache[cache_key] = {'price': price, 'timestamp': datetime.now()}
                    return price
                else:
                    logger.debug(f"No WebSocket data yet for {symbol}, falling back to REST")
            except Exception as e:
                logger.warning(f"WebSocket price fetch failed for {symbol}: {e}, using REST")
        
        # Fallback to REST API
        price = await self._get_spot_price_rest(symbol)
        if price:
            # Cache REST API result in both Redis and memory
            self.redis_cache.set_spot_price(symbol, price)
            self.spot_price_cache[cache_key] = {'price': price, 'timestamp': datetime.now()}
        return price
    
    async def _get_spot_price_rest(self, symbol: str) -> Optional[float]:
        """Get spot price using REST API (fallback method)"""
        try:
            # Map symbol to instrument key
            instrument_key = self._get_index_instrument_key(symbol)
            
            # Get LTP
            response = self.upstox_client.get_ltp([instrument_key])
            
            if response and 'data' in response:
                # Upstox returns key with colon instead of pipe
                # e.g., sent "NSE_INDEX|Nifty 50" but get back "NSE_INDEX:Nifty 50"
                response_key = instrument_key.replace('|', ':')
                data = response['data'].get(response_key, {})
                last_price = data.get('last_price')
                logger.info(f"✓ Spot price for {symbol}: {last_price}")
                return last_price
            
            logger.warning(f"No spot price data for {symbol}: response={response}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting spot price for {symbol}: {e}")
            return None
    
    async def get_option_chain(self, symbol: str, expiry: str) -> Optional[Dict]:
        """
        Get option chain for finding new opportunities - uses Redis + in-memory caching
        Note: Position price updates now use direct LTP API calls for better performance
        """
        cache_key = f"{symbol}_{expiry}"
        
        # Check Redis cache first
        if self.redis_cache.is_available():
            cached_chain = self.redis_cache.get_option_chain(symbol, expiry)
            if cached_chain is not None:
                logger.debug(f"✓ Redis cache hit: option chain for {symbol} {expiry}")
                return cached_chain
        
        # Check in-memory cache - 5s cache for rate limiting safety
        if cache_key in self.option_chain_cache:
            cached = self.option_chain_cache[cache_key]
            # Defensive check for cache structure
            if not isinstance(cached, dict) or 'timestamp' not in cached or 'data' not in cached:
                logger.warning(f"Corrupted option chain cache entry for {symbol}, removing and refetching")
                del self.option_chain_cache[cache_key]
            else:
                age = (datetime.now() - cached['timestamp']).total_seconds()
                if age < 10:  # 10 second cache - SAFE for rate limiting (3 req/s limit)
                    logger.debug(f"Using cached option chain for {symbol} (age: {age:.1f}s)")
                    # Add timestamp to cached data
                    if cached['data'] and isinstance(cached['data'], dict):
                        cached['data']['timestamp'] = cached['timestamp'].isoformat()
                        cached['data']['fetch_time'] = cached['timestamp']
                    return cached['data']
                else:
                    logger.debug(f"Cache expired for {symbol} (age: {age:.1f}s), fetching fresh data")
                    # Don't return cached data, continue to fetch fresh data
        
        # Throttle repeated failures to avoid hammering API
        failure_key = (symbol, expiry)
        last_failure_time = self.option_chain_failure_cache.get(failure_key)
        if last_failure_time:
            seconds_since_failure = (datetime.now() - last_failure_time).total_seconds()
            if seconds_since_failure < 20:
                logger.warning(
                    f"Skipping option chain request for {symbol} {expiry} - last failure {seconds_since_failure:.1f}s ago"
                )
                cached_entry = self.option_chain_cache.get(cache_key)
                return cached_entry['data'] if cached_entry else None
        
        try:
            instrument_key = self._get_index_instrument_key(symbol)
            response = self.upstox_client.get_option_chain(instrument_key, expiry)
            
            # If calculated expiry returns empty data, try fallback expiry
            if not response or not response.get('data') or len(response['data']) == 0:
                logger.warning(f"No option chain data for {symbol} expiry {expiry}, trying fallback")
                # Try multiple fallback expiries for SENSEX (which has different expiry cycles)
                fallback_expries = ['2025-11-25', '2025-11-27', '2025-12-02', '2025-12-31']
                response_data = None
                
                for fallback_expiry in fallback_expries:
                    logger.info(f"Trying fallback expiry {fallback_expiry} for {symbol}")
                    response = self.upstox_client.get_option_chain(instrument_key, fallback_expiry)
                    if response and 'data' in response and len(response['data']) > 0:
                        logger.info(f"✓ Using fallback expiry {fallback_expiry} for {symbol}")
                        response_data = response
                        break
                
                if not response_data:
                    logger.error(f"No option chain data available for {symbol} even with multiple fallbacks")
                    # For SENSEX, try with NIFTY format as last resort
                    if symbol == "SENSEX":
                        logger.warning("Trying alternative SENSEX instrument format...")
                        try:
                            alt_instrument_key = "BSE_INDEX|SENSEX"
                            response = self.upstox_client.get_option_chain(alt_instrument_key, fallback_expries[0])
                            if response and 'data' in response and len(response['data']) > 0:
                                logger.info(f"✓ SENSEX data found with alternative instrument format")
                                response_data = response
                        except Exception as e:
                            logger.error(f"Alternative SENSEX format failed: {e}")
                    
                    if not response_data:
                        return None
                else:
                    response = response_data
            
            if response and 'data' in response:
                # Process full chain
                chain_data = self._process_option_chain(response['data'])
                
                # Get spot price for filtering
                spot_price = await self.get_spot_price(symbol)
                
                # Filter to relevant strikes only (optimization)
                if spot_price:
                    chain_data = self._filter_relevant_strikes(chain_data, spot_price, symbol)
                    
                    # Enrich with price history (prev_close, OHLC)
                    chain_data = await self.price_history_tracker.update_option_prices(chain_data, symbol)
                    
                    logger.info(
                        f"Filtered {symbol} option chain: "
                        f"{len(chain_data['calls'])} calls, "
                        f"{len(chain_data['puts'])} puts "
                        f"(spot: {spot_price})"
                    )
                    
                    # Save snapshot to database (async, non-blocking)
                    asyncio.create_task(
                        asyncio.to_thread(
                            self.option_chain_persistence.save_option_chain_snapshot,
                            symbol,
                            chain_data,
                            spot_price
                        )
                    )
                
                # Add timestamp to chain_data for freshness validation
                if chain_data and isinstance(chain_data, dict):
                    chain_data['timestamp'] = datetime.now().isoformat()
                    chain_data['fetch_time'] = datetime.now()
                
                # Cache it in both Redis and memory
                self.option_chain_cache[cache_key] = {
                    'data': chain_data,
                    'timestamp': datetime.now()
                }
                # Also cache in Redis for cross-process sharing
                self.redis_cache.set_option_chain(symbol, expiry, chain_data)
                if failure_key in self.option_chain_failure_cache:
                    del self.option_chain_failure_cache[failure_key]
                
                return chain_data
        
        except Exception as e:
            logger.error(f"Error getting option chain: {e}")
            self.option_chain_failure_cache[failure_key] = datetime.now()
            return None
    
    def _filter_relevant_strikes(self, option_chain: Dict, spot_price: float, symbol: str) -> Dict:
        """Filter option chain to only relevant strikes for intraday trading"""
        
        # Log what strikes we received from Upstox (for debugging missed opportunities)
        all_call_strikes = sorted([float(s) for s in option_chain.get('calls', {}).keys()])
        all_put_strikes = sorted([float(s) for s in option_chain.get('puts', {}).keys()])
        
        # Check for specific strikes of interest (debugging)
        target_strikes = [25850, 25900, 25800]  # Near current ATM
        for target in target_strikes:
            if str(int(target)) in option_chain.get('puts', {}):
                put_data = option_chain['puts'][str(int(target))]
                logger.info(
                    f"{symbol} {target} PE in raw data: LTP={put_data.get('ltp', 0)}, "
                    f"OI={put_data.get('oi', 0)}, Vol={put_data.get('volume', 0)}"
                )
        
        if all_call_strikes or all_put_strikes:
            logger.info(
                f"{symbol} raw strikes from Upstox: "
                f"Calls {min(all_call_strikes) if all_call_strikes else 'none'}-"
                f"{max(all_call_strikes) if all_call_strikes else 'none'} ({len(all_call_strikes)}), "
                f"Puts {min(all_put_strikes) if all_put_strikes else 'none'}-"
                f"{max(all_put_strikes) if all_put_strikes else 'none'} ({len(all_put_strikes)}) | "
                f"Spot: {spot_price:.1f}"
            )
        
        # Calculate ATM range
        lower_bound = spot_price * (1 - self.atm_range_percent)
        upper_bound = spot_price * (1 + self.atm_range_percent)
        
        filtered = {
            'calls': {},
            'puts': {},
            'pcr': 0,
            'max_pain': 0
        }
        
        call_count_before = len(option_chain.get('calls', {}))
        put_count_before = len(option_chain.get('puts', {}))
        
        # Filter calls
        for strike_str, call_data in option_chain.get('calls', {}).items():
            strike_price = float(strike_str)  # Convert string key to float for comparison
            
            # Skip if outside ATM range
            if strike_price < lower_bound or strike_price > upper_bound:
                continue
            
            # Always preserve strikes in core ATM region (±2%) - these are critical for intraday moves
            is_core_atm = (spot_price * (1 - self.atm_core_percent) <= strike_price <= spot_price * (1 + self.atm_core_percent))
            
            if is_core_atm:
                # Core ATM strikes: keep regardless of OI/volume (capture early price spikes)
                filtered['calls'][strike_str] = call_data
                continue
                
            # For strikes outside core ATM, apply liquidity filters
            # Skip if low liquidity
            if call_data.get('oi', 0) < self.min_open_interest:
                continue
                
            # For very low volume, skip unless in wider ATM region (±5%)
            if call_data.get('volume', 0) < self.min_volume:
                if not (spot_price * 0.95 <= strike_price <= spot_price * 1.05):
                    continue
            
            filtered['calls'][strike_str] = call_data  # Keep string key
        
        # Filter puts (similar logic)
        for strike_str, put_data in option_chain.get('puts', {}).items():
            strike_price = float(strike_str)  # Convert string key to float for comparison
            
            # Debug specific strikes
            if int(strike_price) in [25850, 25900]:
                logger.info(f"{symbol} Processing {strike_str} PE: strike={strike_price}, lower={lower_bound:.0f}, upper={upper_bound:.0f}")
            
            # Skip if outside ATM range
            if strike_price < lower_bound or strike_price > upper_bound:
                if int(strike_price) in [25850, 25900]:
                    logger.warning(f"{symbol} FILTERED OUT {strike_str} PE: Outside range {lower_bound:.0f}-{upper_bound:.0f}")
                continue
            
            # Always preserve strikes in core ATM region (±2%) - these are critical for intraday moves
            is_core_atm = (spot_price * (1 - self.atm_core_percent) <= strike_price <= spot_price * (1 + self.atm_core_percent))
            
            if is_core_atm:
                # Core ATM strikes: keep regardless of OI/volume (capture early price spikes)
                logger.debug(f"{symbol} Keeping {strike_str} PE (core ATM): LTP={put_data.get('ltp')}, OI={put_data.get('oi')}")
                filtered['puts'][strike_str] = put_data
                continue
                
            # For strikes outside core ATM, apply liquidity filters
            # Skip if low liquidity
            if put_data.get('oi', 0) < self.min_open_interest:
                if int(float(strike_str)) in [25850, 25900, 25800]:  # Debug specific strikes
                    logger.warning(f"{symbol} FILTERED OUT {strike_str} PE: OI={put_data.get('oi')} < {self.min_open_interest}")
                continue
                
            # For very low volume, skip unless in wider ATM region (±5%)
            if put_data.get('volume', 0) < self.min_volume:
                if not (spot_price * 0.95 <= strike_price <= spot_price * 1.05):
                    if int(float(strike_str)) in [25850, 25900, 25800]:  # Debug specific strikes
                        logger.warning(f"{symbol} FILTERED OUT {strike_str} PE: Vol={put_data.get('volume')} < {self.min_volume}, outside ±5%")
                    continue
            
            filtered['puts'][strike_str] = put_data  # Keep string key
            if int(float(strike_str)) in [25850, 25900, 25800]:  # Debug specific strikes
                logger.info(f"{symbol} KEPT {strike_str} PE (passed filters): LTP={put_data.get('ltp')}, OI={put_data.get('oi')}, Vol={put_data.get('volume')}")
        
        # Recalculate PCR with filtered data
        total_call_oi = sum(call_data.get('oi', 0) for call_data in filtered['calls'].values())
        total_put_oi = sum(put_data.get('oi', 0) for put_data in filtered['puts'].values())
        
        if total_call_oi > 0:
            filtered['pcr'] = total_put_oi / total_call_oi
        else:
            filtered['pcr'] = option_chain.get('pcr', 0)
        
        # Add PCR logging for debugging
        logger.info(f"🔍 PCR Calculation for {symbol}: Call OI={total_call_oi:,}, Put OI={total_put_oi:,}, PCR={filtered['pcr']:.3f}")
        
        # Add total OI to filtered data
        filtered['total_call_oi'] = total_call_oi
        filtered['total_put_oi'] = total_put_oi
        filtered['total_oi'] = total_call_oi + total_put_oi
        
        # Recalculate Max Pain with filtered strikes
        filtered['max_pain'] = self._calculate_max_pain(filtered)
        
        # Log filtering effectiveness with ATM range details
        call_reduction = ((call_count_before - len(filtered['calls'])) / call_count_before * 100) if call_count_before > 0 else 0
        put_reduction = ((put_count_before - len(filtered['puts'])) / put_count_before * 100) if put_count_before > 0 else 0
        
        # Calculate core ATM range for logging
        core_atm_lower = spot_price * (1 - self.atm_core_percent)
        core_atm_upper = spot_price * (1 + self.atm_core_percent)
        
        # Check if specific strikes made it through
        target_strikes_kept = [s for s in ['25850', '25900', '25800'] if s in filtered['puts']]
        if target_strikes_kept:
            logger.info(f"{symbol} ✅ Target strikes KEPT: {target_strikes_kept}")
        else:
            target_strikes_in_original = [s for s in ['25850', '25900', '25800'] if s in option_chain.get('puts', {})]
            if target_strikes_in_original:
                logger.warning(f"{symbol} ❌ Target strikes LOST: {target_strikes_in_original} (were in original, not in filtered)")
        
        logger.info(
            f"{symbol} strike filtering: Calls {call_count_before}→{len(filtered['calls'])} "
            f"({call_reduction:.0f}% reduction), Puts {put_count_before}→{len(filtered['puts'])} "
            f"({put_reduction:.0f}% reduction) | "
            f"Core ATM: {core_atm_lower:.0f}-{core_atm_upper:.0f}, "
            f"Full range: {lower_bound:.0f}-{upper_bound:.0f}"
        )
        
        return filtered
    
    def _process_option_chain(self, raw_data: List[Dict]) -> Dict:
        """Process raw option chain data from Upstox into a structured form."""
        processed = {
            'calls': {},
            'puts': {},
            'pcr': 0,
            'max_pain': 0,
            'metadata': {
                'processed_at': datetime.now().isoformat(),
                'total_strikes': 0,
                'invalid_count': 0
            }
        }

        total_call_oi = 0
        total_put_oi = 0
        invalid_count = 0

        for item in raw_data:
            try:
                strike_price = item.get('strike_price')
                if strike_price is None or strike_price <= 0:
                    invalid_count += 1
                    continue

                strike_key = str(int(strike_price))

                if 'call_options' in item:
                    call = item['call_options']
                    market_data = call.get('market_data', {})
                    if not self._validate_option_data(market_data):
                        invalid_count += 1
                        continue

                    option_greeks = call.get('option_greeks', {})
                    processed['calls'][strike_key] = {
                        'instrument_key': call.get('instrument_key', ''),
                        'ltp': float(market_data.get('ltp', 0)),
                        'oi': int(market_data.get('oi', 0)),
                        'volume': int(market_data.get('volume', 0)),
                        'iv': float(option_greeks.get('iv', 0)),
                        'delta': float(option_greeks.get('delta', 0)),
                        'gamma': float(option_greeks.get('gamma', 0)),
                        'theta': float(option_greeks.get('theta', 0)),
                        'vega': float(option_greeks.get('vega', 0)),
                        'bid': float(market_data.get('bid_price', 0)),
                        'ask': float(market_data.get('ask_price', 0)),
                        'oi_change': int(market_data.get('oi', 0) - market_data.get('prev_oi', 0)),
                        'strike': float(strike_price)
                    }
                    total_call_oi += int(market_data.get('oi', 0))

                if 'put_options' in item:
                    put = item['put_options']
                    market_data = put.get('market_data', {})
                    if not self._validate_option_data(market_data):
                        invalid_count += 1
                        continue

                    option_greeks = put.get('option_greeks', {})
                    processed['puts'][strike_key] = {
                        'instrument_key': put.get('instrument_key', ''),
                        'ltp': float(market_data.get('ltp', 0)),
                        'oi': int(market_data.get('oi', 0)),
                        'volume': int(market_data.get('volume', 0)),
                        'iv': float(option_greeks.get('iv', 0)),
                        'delta': float(option_greeks.get('delta', 0)),
                        'gamma': float(option_greeks.get('gamma', 0)),
                        'theta': float(option_greeks.get('theta', 0)),
                        'vega': float(option_greeks.get('vega', 0)),
                        'bid': float(market_data.get('bid_price', 0)),
                        'ask': float(market_data.get('ask_price', 0)),
                        'oi_change': int(market_data.get('oi', 0) - market_data.get('prev_oi', 0)),
                        'strike': float(strike_price)
                    }
                    total_put_oi += int(market_data.get('oi', 0))

            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid option data at strike {item.get('strike_price')}: {e}")
                invalid_count += 1
                continue

        if total_call_oi > 0:
            processed['pcr'] = total_put_oi / total_call_oi

        processed['total_call_oi'] = total_call_oi
        processed['total_put_oi'] = total_put_oi
        processed['total_oi'] = total_call_oi + total_put_oi
        processed['max_pain'] = self._calculate_max_pain(processed)

        processed['metadata']['total_strikes'] = len(processed['calls']) + len(processed['puts'])
        processed['metadata']['invalid_count'] = invalid_count

        if invalid_count > 0:
            logger.warning(f"Skipped {invalid_count} invalid option entries during processing")

        return processed

    def _validate_option_data(self, option_data: Dict) -> bool:
        """Validate option data has required fields with reasonable values."""
        try:
            required_fields = ['ltp', 'oi']
            if not all(field in option_data for field in required_fields):
                logger.debug(f"Missing required fields. Has: {list(option_data.keys())}")
                return False

            ltp = float(option_data.get('ltp', 0))
            if ltp < 0:
                logger.debug(f"Negative LTP: {ltp}")
                return False

            oi = float(option_data.get('oi', 0))
            if oi < 0:
                logger.debug(f"Negative OI: {oi}")
                return False

            if ltp == 0:
                logger.debug(f"Zero LTP option (illiquid) - OI: {oi}")

            return True

        except (ValueError, TypeError) as e:
            logger.debug(f"Validation exception: {e}")
            return False

    def _calculate_max_pain(self, option_data: Dict) -> float:
        """Calculate max pain strike."""
        try:
            strikes = set(option_data['calls'].keys()) | set(option_data['puts'].keys())
            min_pain = float('inf')
            max_pain_strike = 0

            for strike_str in strikes:
                strike = float(strike_str)
                pain = 0

                for call_strike_str, call_data in option_data['calls'].items():
                    call_strike = float(call_strike_str)
                    if strike > call_strike:
                        pain += (strike - call_strike) * call_data['oi']

                for put_strike_str, put_data in option_data['puts'].items():
                    put_strike = float(put_strike_str)
                    if strike < put_strike:
                        pain += (put_strike - strike) * put_data['oi']

                if pain < min_pain:
                    min_pain = pain
                    max_pain_strike = strike

            return max_pain_strike

        except Exception as e:
            logger.error(f"Error calculating max pain: {e}")
            return 0.0

    async def update_option_chain(self):
        """Update option chain data for NIFTY and SENSEX only."""
        await self.get_instrument_data("NIFTY")
        await self.get_instrument_data("SENSEX")
        logger.debug("Option chain updated for NIFTY and SENSEX")

    async def calculate_greeks(self):
        """Calculate Greeks for all options using Black-Scholes model."""
        try:
            rate = 0.10

            for symbol in ['NIFTY', 'SENSEX']:
                if symbol not in self.market_state:
                    continue

                spot = self.market_state[symbol].get('spot_price', 0)
                if spot <= 0:
                    continue

                option_chain = self.market_state[symbol].get('option_chain', {})
                
                if not option_chain or not isinstance(option_chain, dict):
                    continue
                
                # Process strikes in option chain
                chain_data = option_chain.get('option_chain', [])
                if not chain_data:
                    continue
                    
                for strike_data in chain_data:
                    strike = strike_data.get('strike_price', 0)
                    if strike <= 0:
                        continue
                    
                    # Get days to expiry
                    dte = 7  # Default weekly  
                    time_to_expiry = max(dte / 365.0, 0.001)
                    rate = 0.07  # Risk-free rate
                    
                    # Calculate Greeks for PUT options
                    put_data = strike_data.get('PE', {})
                    if put_data:
                        iv = put_data.get('iv', 20) / 100
                        
                        greeks = self._black_scholes_greeks(
                            S=spot,
                            K=strike,
                            T=time_to_expiry,
                            r=rate,
                            sigma=iv,
                            option_type='put'
                        )

                        put_data['delta'] = greeks['delta']
                        put_data['gamma'] = greeks['gamma']
                        put_data['theta'] = greeks['theta']
                        put_data['vega'] = greeks['vega']
                        put_data['rho'] = greeks['rho']

        except Exception as e:
            logger.error(f"Error calculating Greeks: {e}")

    def _black_scholes_greeks(self, S: float, K: float, T: float, r: float,
                              sigma: float, option_type: str) -> Dict[str, float]:
        """Calculate Black-Scholes Greeks for calls and puts."""
        try:
            if sigma <= 0:
                sigma = 0.01
            if T <= 0:
                T = 0.001

            d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)

            if option_type == 'call':
                delta = norm.cdf(d1)
                theta = ((-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                         - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365)
                rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100
            else:
                delta = -norm.cdf(-d1)
                theta = ((-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                         + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365)
                rho = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100

            gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
            vega = S * norm.pdf(d1) * np.sqrt(T) / 100

            return {
                'delta': round(delta, 4),
                'gamma': round(gamma, 6),
                'theta': round(theta, 4),
                'vega': round(vega, 4),
                'rho': round(rho, 4)
            }

        except Exception as e:
            logger.error(f"Error in Black-Scholes calculation: {e}")
            return {
                'delta': 0.0,
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0,
                'rho': 0.0
            }

    def get_greeks(self, symbol: str, strike: float, option_type: str) -> Dict[str, float]:
        """Get cached Greeks for a specific option if available."""
        try:
            option_chain = self.market_state.get(symbol, {}).get('option_chain', {})

            if option_type.upper() == 'CALL':
                option_data = option_chain.get('calls', {}).get(str(strike), {})
            else:
                option_data = option_chain.get('puts', {}).get(str(strike), {})

            return {
                'delta': option_data.get('delta', 0.0),
                'gamma': option_data.get('gamma', 0.0),
                'theta': option_data.get('theta', 0.0),
                'vega': option_data.get('vega', 0.0),
                'rho': option_data.get('rho', 0.0)
            }

        except Exception as e:
            logger.error(f"Error getting Greeks: {e}")
            return {
                'delta': 0.0,
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0,
                'rho': 0.0
            }

    def _get_index_instrument_key(self, symbol: str) -> str:
        """Get instrument key for index."""
        mapping = {
            "NIFTY": "NSE_INDEX|Nifty 50",
            "BANKNIFTY": "NSE_INDEX|Nifty Bank",
            "SENSEX": "BSE_INDEX|SENSEX"
        }
        return mapping.get(symbol, "NSE_INDEX|Nifty 50")

    def _calculate_atm_strike(self, spot_price: float, symbol: str) -> float:
        """Calculate ATM strike for supported indices."""
        if symbol == "NIFTY":
            step = 50
        elif symbol == "BANKNIFTY":
            step = 100
        else:
            step = 100

        return round(spot_price / step) * step

    def _get_relevant_strikes(self, atm_strike: float, symbol: str) -> List[float]:
        """Get list of relevant strikes around ATM."""
        return self.get_relevant_strikes(atm_strike, symbol, include_atm=True)

    def get_relevant_strikes(self, atm_strike: float, symbol: str,
                              include_atm: bool = True, span: int = None) -> List[float]:
        """Public helper to fetch available strikes around ATM."""
        strikes = []
        step = self._get_strike_step(symbol)
        spread = span if span is not None else self._get_strike_spread(symbol)

        lower = atm_strike - (spread * step)
        upper = atm_strike + (spread * step)

        current = lower
        while current <= upper:
            strike = round(current, 2)
            if include_atm or strike != atm_strike:
                strikes.append(strike)
            current += step

        if include_atm and atm_strike not in strikes:
            strikes.append(atm_strike)

        return sorted(set(strikes))

    def _get_strike_step(self, symbol: str) -> float:
        if symbol == "NIFTY":
            return 50
        elif symbol == "BANKNIFTY":
            return 100
        else:
            return 100

    def _get_strike_spread(self, symbol: str) -> int:
        if symbol == "NIFTY":
            return 10
        elif symbol == "BANKNIFTY":
            return 10
        else:
            return 10
