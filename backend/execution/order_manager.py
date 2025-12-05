"""
Order Manager
Handles order execution and position tracking with persistence
"""

import uuid
import json
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from backend.core.timezone_utils import now_ist, to_naive_ist
from backend.core.upstox_client import UpstoxClient
from backend.execution.risk_manager import RiskManager
from backend.services.market_context import MarketContextService
from backend.core.config import config
from backend.core.logger import logger
from backend.core.logger import get_execution_logger
from backend.monitoring.prometheus_exporter import MetricsExporter
from backend.services.position_persistence import get_position_service
from backend.notifications.telegram_notifier import get_telegram_notifier

# P&L CALCULATION: LONG OPTIONS ONLY (Nov 21 locked)
# SAME FORMULA FOR CALL AND PUT: (exit - entry) * quantity
from backend.core.pnl_calculator import calculate_pnl

logger = get_execution_logger()


class OrderManager:
    """Manages order execution and positions"""
    
    def __init__(self, upstox_client: UpstoxClient, risk_manager: RiskManager, market_data=None, market_monitor=None):
        self.upstox_client = upstox_client
        self.risk_manager = risk_manager
        self.is_paper_mode = config.is_paper_mode()
        self.orders = []
        self.positions = []
        self.metrics_exporter = MetricsExporter()
        self.position_service = get_position_service()
        self.market_data = market_data  # Market feed for real-time prices
        self.feed_subscriptions = {}  # Track which positions are subscribed to feed
        
        # Market context enrichment service
        self.market_context = MarketContextService(market_monitor, market_data)
        self.telegram_notifier = get_telegram_notifier()
        
        mode = "PAPER" if self.is_paper_mode else "LIVE"
        logger.info(f"Order Manager initialized in {mode} mode")
        
        # Restore positions from database on startup
        self._restore_positions_on_startup()
    
    def _restore_positions_on_startup(self):
        """
        Restore open positions from database on system restart
        This allows positions to persist across app restarts
        """
        try:
            restored_positions = self.position_service.restore_positions()
            
            if restored_positions:
                self.positions = restored_positions
                
                # Add to risk manager and resubscribe to market feed with rate limiting
                for i, position in enumerate(restored_positions):
                    # Rebuild instrument key if missing (legacy rows) so live prices resume
                    instrument_key = position.get('instrument_key')
                    if not instrument_key:
                        symbol = position.get('symbol')
                        strike = position.get('strike_price') or position.get('strike')
                        option_type = position.get('instrument_type') or position.get('direction')
                        expiry = position.get('expiry')
                        if isinstance(expiry, str) and 'T' in expiry:
                            expiry = expiry.split('T')[0]
                        instrument_key = self._build_instrument_key(symbol, strike, option_type, expiry)
                        if instrument_key:
                            position['instrument_key'] = instrument_key
                            metadata = dict(position.get('position_metadata') or {})
                            metadata['instrument_key'] = instrument_key
                            position['position_metadata'] = metadata
                            try:
                                self.position_service.update_position_metadata(
                                    position_id=position.get('position_id') or position.get('id'),
                                    position_metadata=metadata
                                )
                            except Exception as persist_error:
                                logger.warning(f"Could not persist instrument key for position {position.get('position_id')}: {persist_error}")
                        else:
                            logger.warning(f"Unable to rebuild instrument key for position {position.get('position_id')}")

                    self.risk_manager.add_position(position)
                    # Add delay every 3 positions to avoid rate limiting
                    if i > 0 and i % 3 == 0:
                        import asyncio
                        import time
                        time.sleep(0.5)  # 500ms delay to spread out subscriptions
                    # Resubscribe to market feed for real-time updates
                    self._subscribe_position_to_feed(position)
                
                logger.info(f"✓ Restored {len(restored_positions)} open positions from database")
                
                # Log each position
                for pos in restored_positions:
                    logger.info(
                        f"  - {pos.get('symbol')} {pos.get('strike_price')} {pos.get('instrument_type')} "
                        f"@ ₹{pos.get('entry_price')} (P&L: ₹{pos.get('unrealized_pnl', 0):.2f})"
                    )
            else:
                logger.info("No open positions to restore")
                
        except Exception as e:
            logger.error(f"Error restoring positions on startup: {e}")
    
    async def execute_signal(self, signal: Dict) -> bool:
        """Execute a trading signal by creating and placing an order"""
        try:
            # DEBUG: Log incoming signal to trace strategy name
            logger.info(f"🔍 execute_signal received - strategy_id: {signal.get('strategy_id')}, strategy_name: {signal.get('strategy_name')}, strategy: {signal.get('strategy')}")
            # Calculate position size
            quantity = self.risk_manager.calculate_position_size(
                signal, signal.get('entry_price')
            )
            
            if quantity == 0:
                logger.warning("Position size is 0, skipping trade")
                return False
            
            # Create order
            order = {
                'id': str(uuid.uuid4()),
                'signal': signal,
                'quantity': quantity,
                'status': 'pending',
                'timestamp': to_naive_ist(now_ist())
            }
            
            # Execute order
            if self.is_paper_mode:
                success = await self._execute_paper_order(order)
            else:
                success = await self._execute_live_order(order)
            
            if success:
                # Create position
                position = self._create_position(order, signal)
                self.positions.append(position)
                self.risk_manager.add_position(position)
                
                logger.info(
                    f"✓ Order executed: {signal.get('direction')} "
                    f"{signal.get('symbol')} {signal.get('strike')} "
                    f"Qty: {quantity} @ ₹{signal.get('entry_price')}"
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            return False
    
    async def _execute_paper_order(self, order: Dict) -> bool:
        """
        Execute order in paper trading mode with realistic slippage and delay
        Uses spread-based slippage model and simulates partial fills
        """
        import random
        import asyncio
        import time
        
        start_time = time.time()
        logger.info(f"[PAPER] Executing order: {order['id']}")
        
        signal = order['signal']
        strategy = signal.get('strategy', 'unknown')
        side = signal.get('action', 'BUY')
        quantity = order['quantity']
        
        # Record order submitted metric
        self.metrics_exporter.record_order(strategy, side, 'MARKET', 'submitted')
        
        # Minimal delay for realistic execution
        await asyncio.sleep(0.05)  # 50ms minimal delay
        
        # Get base entry price
        base_price = signal.get('entry_price', 0)
        
        # Validate entry price - reject order if invalid
        if base_price <= 0:
            logger.error(f"[PAPER] Invalid entry price: {base_price}. Signal: {signal.get('strategy')}, Strike: {signal.get('strike_price')}")
            order['status'] = 'rejected'
            order['rejection_reason'] = 'invalid_entry_price'
            return False
        
        # Use actual market price with minimal slippage
        fill_price = base_price
        slippage = 0
        slippage_percent = 0
        spread_percent = 0
        
        # Simulate partial fills (10% chance for large orders)
        filled_quantity = quantity
        is_partial = False
        
        if quantity >= 100 and random.random() < 0.10:  # 10% chance
            fill_ratio = random.uniform(0.5, 0.9)  # Fill 50-90%
            filled_quantity = int(quantity * fill_ratio)
            is_partial = True
            logger.info(f"[PAPER] Partial fill: {filled_quantity}/{quantity} lots")
        
        order['status'] = 'partial_filled' if is_partial else 'filled'
        order['fill_price'] = round(fill_price, 2)
        order['filled_quantity'] = filled_quantity
        order['remaining_quantity'] = quantity - filled_quantity
        order['slippage'] = round(slippage, 2)
        order['slippage_percent'] = round(slippage_percent, 2)
        order['spread_percent'] = round(spread_percent, 2)
        order['is_partial'] = is_partial
        
        # Record successful fill with timing
        fill_time = time.time() - start_time
        self.metrics_exporter.record_order(strategy, side, 'MARKET', 'filled', fill_time=fill_time)
        
        logger.info(
            f"[PAPER] Order filled: {filled_quantity} lots @ ₹{fill_price:.2f} "
            f"(price: ₹{base_price:.2f}, no slippage)"
        )
        
        self.orders.append(order)
        return True
    
    async def _execute_live_order(self, order: Dict) -> bool:
        """
        Execute order in live trading mode with guardrails
        Uses best bid/ask with tolerance for limit price calculation
        """
        import asyncio
        import time
        
        start_time = time.time()
        logger.info(f"[LIVE] Executing order: {order['id']}")
        
        signal = order['signal']
        entry_price = signal.get('entry_price', 0)
        strategy = signal.get('strategy', 'unknown')
        side = signal.get('action', 'BUY')
        
        # Pre-flight validation
        if entry_price <= 0:
            logger.error(f"Invalid entry price: {entry_price}")
            self.metrics_exporter.record_order(strategy, side, 'LIMIT', 'rejected', reason='invalid_price')
            return False
        
        # Record order submitted metric
        self.metrics_exporter.record_order(strategy, side, 'LIMIT', 'submitted')
        
        # Get bid/ask spread from signal (if available)
        bid_price = signal.get('bid', entry_price * 0.98)  # Fallback to 2% below
        ask_price = signal.get('ask', entry_price * 1.02)  # Fallback to 2% above
        
        # Calculate limit price with tolerance
        # BUY: willing to pay up to ask + 2% tolerance
        # SELL: willing to receive down to bid - 2% tolerance
        tolerance_percent = 0.02  # 2% tolerance
        
        action = signal.get('action', 'BUY')
        if action == 'BUY':
            limit_price = ask_price * (1 + tolerance_percent)
        else:
            limit_price = bid_price * (1 - tolerance_percent)
        
        # Validate spread is reasonable
        spread_percent = ((ask_price - bid_price) / bid_price) * 100 if bid_price > 0 else 0
        if spread_percent > 10:  # Spread > 10%
            logger.warning(f"Wide spread detected: {spread_percent:.2f}% (bid={bid_price}, ask={ask_price})")
            # Still allow trade but log warning
        
        # Build instrument key
        instrument_key = self.upstox_client.get_instrument_key(
            exchange="NSE",
            symbol=signal.get('symbol'),
            expiry=signal.get('expiry'),
            strike=signal.get('strike'),
            option_type="CE" if signal.get('direction') == "CALL" else "PE"
        )
        
        # Retry logic with exponential backoff
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Place order on Upstox with limit price
                response = self.upstox_client.place_order(
                    instrument_token=instrument_key,
                    quantity=order['quantity'],
                    transaction_type=action,
                    order_type='LIMIT',
                    price=round(limit_price, 2),
                    product='I'  # Intraday
                )
                
                if response and response.get('status') == 'success':
                    order['status'] = 'filled'
                    order['order_id'] = response.get('data', {}).get('order_id')
                    order['fill_price'] = limit_price  # Will be updated from order status
                    order['limit_price'] = limit_price
                    order['bid_at_entry'] = bid_price
                    order['ask_at_entry'] = ask_price
                    order['spread_percent'] = spread_percent
                    order['attempts'] = attempt + 1
                    
                    # Record successful fill with timing
                    fill_time = time.time() - start_time
                    self.metrics_exporter.record_order(strategy, side, 'LIMIT', 'filled', fill_time=fill_time)
                    
                    logger.info(
                        f"[LIVE] Order placed: {order['order_id']} @ ₹{limit_price:.2f} "
                        f"(bid={bid_price:.2f}, ask={ask_price:.2f}, spread={spread_percent:.2f}%, "
                        f"attempt {attempt + 1})"
                    )
                    
                    self.orders.append(order)
                    return True
                
                else:
                    logger.warning(f"Order placement failed (attempt {attempt + 1}/{max_retries}): {response}")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    
            except Exception as e:
                logger.error(f"Error placing order (attempt {attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
        
        # Record rejection after all retries failed
        self.metrics_exporter.record_order(strategy, side, 'LIMIT', 'rejected', reason='max_retries_exceeded')
        logger.error(f"Failed to place order after {max_retries} attempts")
        return False
    
    def _create_position(self, order: Dict, signal: Dict) -> Dict:
        """Create position from filled order and save to database"""
        
        # DEBUG: Log the incoming signal to trace direction issue
        logger.info(f"🔍 _create_position received signal - direction: {signal.get('direction')}, strike: {signal.get('strike')}, symbol: {signal.get('symbol')}")
        
        # Extract option details
        direction = signal.get('direction', '')  # CALL or PUT
        strike = signal.get('strike', 0)
        symbol = signal.get('symbol', '')
        expiry = signal.get('expiry', '')
        
        # Debug logging to track missing data
        if not direction:
            logger.warning(f"⚠️  Signal missing 'direction': {signal.get('strategy')}")
        if not strike or strike == 0:
            logger.warning(f"⚠️  Signal missing 'strike': {signal.get('strategy')} - {signal}")
        
        # Extract and validate strategy name - prioritize canonical strategy_id
        from backend.strategies.strategy_mappings import normalize_strategy_name
        strategy_raw = (
            signal.get('strategy_id')
            or signal.get('strategy_name')
            or signal.get('strategy')
            or ''
        )
        if not strategy_raw or not str(strategy_raw).strip():
            logger.error(
                "🔴 Signal has empty/missing strategy! Keys: %s, Symbol: %s, Strike: %s, Signal: %s",
                list(signal.keys())[:10],
                symbol,
                strike,
                signal
            )
            strategy_name = 'unknown'  # Fallback - changed from 'default' for clarity
        else:
            # Normalize to canonical strategy_id
            strategy_name = normalize_strategy_name(str(strategy_raw).strip())
            logger.info(
                "✓ Strategy resolved: '%s' -> '%s' | Creating position for %s %s %s",
                strategy_raw,
                strategy_name,
                symbol,
                strike,
                direction
            )
        
        position = {
            'position_id': order['id'],
            'id': order['id'],
            'order_id': order.get('order_id'),
            'symbol': symbol,
            'instrument_type': direction,  # CALL or PUT
            'strike_price': strike,
            'direction': signal.get('action', 'BUY'),  # BUY or SELL
            'expiry': expiry,
            'quantity': order['quantity'],
            'entry_price': signal.get('entry_price', order.get('fill_price')),
            'current_price': signal.get('entry_price', order.get('fill_price')),
            'entry_value': signal.get('entry_price', order.get('fill_price')) * order['quantity'],
            'target_price': signal.get('target_price', signal.get('entry_price', order.get('fill_price', 0)) * 1.15),
            'stop_loss': signal.get('stop_loss', signal.get('entry_price', order.get('fill_price', 0)) * 0.85),
            'tp1': signal.get('tp1', 0),
            'tp2': signal.get('tp2', 0),
            'tp3': signal.get('tp3', signal.get('target_price', order.get('fill_price', 0) * 1.15)),
            'rr_ratio': signal.get('rr_ratio', '1:2.7'),
            'regime': signal.get('regime', 'default'),
            'risk_pct': signal.get('risk_pct', 0.95),
            'unrealized_pnl': 0.0,
            'unrealized_pnl_pct': 0.0,
            'strategy_name': strategy_name,  # Use validated strategy_name from above
            'signal_strength': signal.get('strength', 0),
            'ml_score': signal.get('ml_probability', 0),
            'entry_time': to_naive_ist(now_ist()),
            'status': 'open',
            # Capture Greeks and option data at entry
            'delta_entry': signal.get('delta', 0.0),
            'gamma_entry': signal.get('gamma', 0.0),
            'theta_entry': signal.get('theta', 0.0),
            'vega_entry': signal.get('vega', 0.0),
            'iv_entry': signal.get('iv', 20.0),
            'oi_entry': signal.get('oi', 0),
            'volume_entry': signal.get('volume', 0),
            'bid_entry': signal.get('bid', 0.0),
            'ask_entry': signal.get('ask', 0.0),
            'spot_price_entry': signal.get('spot_price', 0.0),
            'vix_entry': signal.get('vix', 0.0),
            'pcr_entry': signal.get('pcr', 0.0),
            'entry_reason': signal.get('reason', ''),
            # ML Telemetry - Save model metadata for traceability
            'model_version': signal.get('model_version'),
            'model_hash': signal.get('model_hash'),
            'features_snapshot': signal.get('features_snapshot', {}),
            # Store instrument key for market feed subscription
            'instrument_key': self._build_instrument_key(symbol, strike, direction, expiry)
        }
        
        # Enrich with market context (VIX, regime, time-of-day)
        position = self.market_context.enrich_position_entry(position)
        
        # Calculate spread_entry
        bid = signal.get('bid', 0.0)
        ask = signal.get('ask', 0.0)
        if bid > 0 and ask > 0:
            spread = ask - bid
            mid_price = (bid + ask) / 2
            position['spread_entry'] = (spread / mid_price * 100) if mid_price > 0 else 0
        else:
            position['spread_entry'] = 0.0
        
        # Save to database for persistence
        self.position_service.save_position(position)
        
        # Subscribe to market feed for this position
        self._subscribe_position_to_feed(position)
        
        logger.info(
            f"✓ Position created: {symbol} {strike} {direction} @ ₹{order.get('fill_price'):.2f} "
            f"(SL: ₹{signal.get('stop_loss', 0):.2f}, Target: ₹{signal.get('target_price', 0):.2f})"
        )
        
        # Send Telegram notification for trade entry
        try:
            trade_data = {
                'symbol': symbol,
                'instrument_type': signal.get('instrument_type', 'OPTION'),
                'strike_price': strike,
                'entry_price': order.get('fill_price', 0),
                'quantity': position['quantity'],
                'strategy_name': signal.get('strategy', 'UNKNOWN'),
                'direction': direction
            }
            asyncio.create_task(self.telegram_notifier.send_trade_entry(trade_data))
        except Exception as e:
            logger.error(f"Failed to send Telegram trade entry notification: {e}")
        
        return position
    
    async def place_order(self, order_details: Dict) -> Optional[Dict]:
        """
        Place a direct order (used by delta hedging system)
        This bypasses the signal processing and goes directly to order execution
        """
        try:
            # Create order structure similar to execute_signal
            order = {
                'id': str(uuid.uuid4()),
                'quantity': order_details.get('quantity', 0),
                'status': 'pending',
                'timestamp': to_naive_ist(now_ist())
            }
            
            # Create a signal-like dict for order execution
            signal = {
                'symbol': order_details.get('symbol'),
                'action': order_details.get('direction'),  # BUY or SELL
                'entry_price': order_details.get('price', 0),
                'strategy': order_details.get('strategy_name', 'delta_hedge'),
                'direction': 'CALL' if order_details.get('instrument_type') == 'FUTURES' else order_details.get('instrument_type', 'CALL'),
                'strike': 0,  # Not applicable for futures
                'expiry': None,  # Not applicable for futures
                'target_price': 0,
                'stop_loss': 0
            }

            # Attach signal to order so downstream execution helpers work consistently
            order['signal'] = signal
            
            # Execute order based on mode
            if self.is_paper_mode:
                success = await self._execute_paper_order(order)
            else:
                success = await self._execute_live_order(order)
            
            if success:
                # Create position record with full option contract details
                position = {
                    'id': order['id'],
                    'symbol': order_details.get('symbol'),
                    'direction': order_details.get('direction'),
                    'quantity': order_details.get('quantity'),
                    'entry_price': order.get('fill_price'),
                    'strategy_name': order_details.get('strategy_name', 'delta_hedge'),
                    'entry_time': to_naive_ist(now_ist()),
                    'status': 'open',
                    # Add option contract details for proper exit (use expected field names)
                    'strike_price': order_details.get('strike', 0),
                    'instrument_type': order_details.get('option_type', order_details.get('instrument_type', 'CE')),
                    'expiry': order_details.get('expiry', None),
                    'option_symbol': order_details.get('option_symbol', f"{order_details.get('symbol', '')}FUT")
                }
                
                # Add to positions for tracking
                self.positions.append(position)
                
                logger.info(f"✓ Hedge order placed: {order_details.get('direction')} {order_details.get('quantity')} {order_details.get('symbol')} @ ₹{order.get('fill_price'):.2f}")
                
                return {
                    'order_id': order.get('order_id', order['id']),
                    'quantity': order_details.get('quantity'),
                    'direction': order_details.get('direction'),
                    'symbol': order_details.get('symbol')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error placing direct order: {e}")
            return None
    
    def _build_instrument_key(self, symbol: str, strike: float, option_type: str, expiry: str) -> str:
        """Build instrument key for market feed subscription"""
        try:
            if not all([symbol, strike, option_type, expiry]):
                logger.warning(f"Cannot build instrument key: missing data (symbol={symbol}, strike={strike}, type={option_type}, expiry={expiry})")
                return ""
            
            # Convert CALL/PUT to CE/PE for instrument key
            opt_type = "CE" if option_type == "CALL" else "PE" if option_type == "PUT" else ""
            if not opt_type:
                logger.warning(f"Invalid option type: {option_type}")
                return ""
            
            # Build key in Upstox format: NSE_FO|NIFTY24NOV2526050CE
            # The upstox_client method expects: exchange, symbol, expiry, strike, option_type
            instrument_key = self.upstox_client.get_instrument_key(
                exchange="NSE",
                symbol=symbol,
                expiry=expiry,
                strike=strike,
                option_type=opt_type
            )
            logger.info(f"✓ Built instrument key: {instrument_key}")
            return instrument_key
        except Exception as e:
            logger.error(f"Error building instrument key: {e}")
            return ""
    
    def _subscribe_position_to_feed(self, position: Dict):
        """Subscribe position to market feed for real-time price updates"""
        try:
            instrument_key = position.get('instrument_key')
            if not instrument_key:
                logger.warning(f"Cannot subscribe position {position.get('id')}: no instrument key")
                return
            
            # Add to market feed subscription
            if hasattr(self, 'market_data') and self.market_data:
                # Subscribe to instrument
                asyncio.create_task(
                    self.market_data.subscribe_instruments([instrument_key])
                )
                
                # Register callback for price updates
                async def price_update_callback(inst_key: str, feed_data: Dict):
                    """Callback to handle real-time price updates from market feed"""
                    # Extract LTP from feed data - try multiple paths
                    ltp = None
                    
                    # Try fullFeed path (protobuf format)
                    if "fullFeed" in feed_data and "marketFF" in feed_data["fullFeed"]:
                        market_ff = feed_data["fullFeed"]["marketFF"]
                        if "ltpc" in market_ff and "ltp" in market_ff["ltpc"]:
                            ltp = float(market_ff["ltpc"]["ltp"])
                    # Try ff path
                    elif "ff" in feed_data and "marketFF" in feed_data["ff"]:
                        market_ff = feed_data["ff"]["marketFF"]
                        if "ltpc" in market_ff and "ltp" in market_ff["ltpc"]:
                            ltp = float(market_ff["ltpc"]["ltp"])
                    # Try direct ltp field
                    elif "ltp" in feed_data:
                        ltp = float(feed_data["ltp"])
                    
                    if ltp:
                        self.update_position_price_from_feed(inst_key, ltp, feed_data)
                
                self.market_data.register_price_callback(instrument_key, price_update_callback)
                
                # Store subscription mapping
                self.feed_subscriptions[instrument_key] = position.get('id')
                logger.info(f"✓ Subscribed {position.get('symbol')} {position.get('strike_price')} {position.get('instrument_type')} to market feed")
        except Exception as e:
            logger.error(f"Error subscribing position to feed: {e}")
    
    def update_position_price_from_feed(self, instrument_key: str, ltp: float, tick_data: Dict = None):
        """
        Update position price from market feed (called every second)
        This receives real-time updates from WebSocket feed
        """
        try:
            # Find position by instrument key
            position_id = self.feed_subscriptions.get(instrument_key)
            if not position_id:
                return  # Not tracking this instrument
            
            position = next((p for p in self.positions if p.get('id') == position_id), None)
            if not position:
                return
            
            # Update current price
            old_price = position.get('current_price', 0)
            position['current_price'] = ltp
            
            # Calculate P&L for options trading (LONG OPTIONS ONLY - Nov 21 locked)
            # SAME FORMULA FOR CALL AND PUT: (exit - entry) * quantity
            entry_price = position.get('entry_price', 0)
            current_price = position.get('current_price', 0)
            quantity = position.get('quantity', 0)
            instrument_type = position.get('instrument_type', 'CALL')  # CALL or PUT
            
            # OFFICIAL P&L CALCULATION: LONG OPTIONS ONLY
            # SAME FOR CALL AND PUT: (exit - entry) * quantity
            pnl = calculate_pnl(entry_price, current_price, quantity, instrument_type)
            
            position['unrealized_pnl'] = pnl
            position['unrealized_pnl_pct'] = (pnl / (entry_price * quantity) * 100) if entry_price > 0 else 0
            
            # Log price updates: first update and every 10th update (more frequent to verify feed works)
            if not hasattr(self, '_price_update_counter'):
                self._price_update_counter = {}
            self._price_update_counter[position_id] = self._price_update_counter.get(position_id, 0) + 1
            
            count = self._price_update_counter[position_id]
            if count == 1 or count % 10 == 0:
                logger.info(
                    f"💹 Price Update #{count}: "
                    f"{position.get('symbol')} {position.get('strike_price')} {position.get('instrument_type')} "
                    f"₹{old_price:.2f} → ₹{ltp:.2f} | P&L: ₹{pnl:.2f} ({position['unrealized_pnl_pct']:.2f}%)"
                )
            
            # Update Greeks if available in tick data
            if tick_data:
                position['delta_current'] = tick_data.get('delta', position.get('delta_entry', 0))
                position['gamma_current'] = tick_data.get('gamma', position.get('gamma_entry', 0))
                position['theta_current'] = tick_data.get('theta', position.get('theta_entry', 0))
                position['vega_current'] = tick_data.get('vega', position.get('vega_entry', 0))
                position['iv_current'] = tick_data.get('iv', position.get('iv_entry', 0))
            
            # NOTE: Exit decisions are now handled ONLY by risk_manager.should_exit() in main.py
            # This prevents duplicate/conflicting exit logic that was blocking TP3 closes
            # The order manager just updates prices and P&L, main loop handles exits
            
            # Save updated position to database
            self.position_service.save_position(position)
            
            # Broadcast position update to dashboard for real-time display
            try:
                from backend.api.websocket_manager import get_ws_manager
                ws_manager = get_ws_manager()
                if ws_manager and ws_manager.active_connections:
                    # Send position update with current price and P&L
                    position_update = {
                        'id': position.get('id'),
                        'symbol': position.get('symbol'),
                        'strike_price': position.get('strike_price'),
                        'option_type': position.get('instrument_type'),
                        'entry_price': position.get('entry_price'),
                        'current_price': position.get('current_price'),
                        'unrealized_pnl': position.get('unrealized_pnl', 0),
                        'pnl_percent': position.get('unrealized_pnl_pct', 0),
                        'quantity': position.get('quantity'),
                        'target_1': position.get('target_1', 0),
                        'target_2': position.get('target_2', 0),
                        'target_3': position.get('target_3', 0),
                        'stop_loss': position.get('stop_loss', 0),
                        'trailing_sl': position.get('trailing_sl', 0),
                        'strategy': position.get('strategy_name', ''),
                        'updated_at': now_ist().isoformat()
                    }
                    # Schedule async broadcast without awaiting
                    asyncio.create_task(ws_manager.broadcast_position_update(position_update))
            except Exception as ws_e:
                logger.debug(f"WebSocket broadcast failed: {ws_e}")
            
        except Exception as e:
            logger.error(f"Error updating position price from feed: {e}")
    
    async def get_positions(self) -> List[Dict]:
        """Get all open positions"""
        return self.positions
    
    async def update_position_greeks(self, position_id: str, option_data: Dict):
        """Update position Greeks from option chain data"""
        try:
            position = next((p for p in self.positions if p.get('id') == position_id), None)
            if position:
                position['delta_current'] = option_data.get('delta', position.get('delta_entry', 0))
                position['gamma_current'] = option_data.get('gamma', position.get('gamma_entry', 0))
                position['theta_current'] = option_data.get('theta', position.get('theta_entry', 0))
                position['vega_current'] = option_data.get('vega', position.get('vega_entry', 0))
                position['iv_current'] = option_data.get('iv', position.get('iv_entry', 0))
                
                # Save updated position to database
                self.position_service.save_position(position)
        except Exception as e:
            logger.error(f"Error updating position Greeks: {e}")
    
    async def close_position(self, position: Dict, exit_type: str = None):
        """Close a position and remove from database"""
        try:
            # CRITICAL FIX: Get LATEST price before closing to avoid same entry/exit price
            symbol = position.get('symbol')
            strike = position.get('strike_price')
            option_type = position.get('instrument_type')
            
            # Set exit reason if provided via exit_type parameter
            if exit_type:
                position['exit_reason'] = exit_type
            # If no exit_type, check if exit_reason was already set by risk_manager
            elif not position.get('exit_reason'):
                position['exit_reason'] = 'MANUAL_CLOSE'
            
            # Skip positions with missing critical data (corrupted data)
            if not symbol or not strike or not option_type:
                logger.error(f"🔴 CANNOT close position - missing critical data: symbol={symbol}, strike={strike}, type={option_type}")
                logger.error(f"Position data: {position}")
                # Try to recover missing data from position fields
                if not strike:
                    strike = position.get('strike_price') or position.get('strike')
                if not option_type:
                    option_type = position.get('instrument_type') or position.get('direction') or position.get('side')
                # If still missing, remove from database to prevent accumulation
                if not strike or not option_type:
                    position_id_to_remove = position.get('id') or position.get('position_id')
                    if position_id_to_remove:
                        self.positions = [p for p in self.positions if (p.get('id') != position_id_to_remove and p.get('position_id') != position_id_to_remove)]
                        self.risk_manager.remove_position(position_id_to_remove)
                        self.position_service.remove_position(position.get('position_id', position.get('id')))
                        logger.warning(f"🧹 Cleaned up corrupted position {position_id_to_remove} from database and memory")
                    return
            
            # Fetch current market price
            try:
                # Defensive check for missing strike
                if not strike or strike is None:
                    logger.warning(f"⚠️ Missing strike price for position, using entry_price as fallback")
                    position['exit_price'] = position.get('current_price', position.get('entry_price'))
                else:
                    market_state = await self.market_data.get_current_state()
                    symbol_data = market_state.get(symbol, {})
                    option_chain = symbol_data.get('option_chain', {})
                    
                    strike_str = str(int(strike))
                    if option_type == 'CALL':
                        option_data = option_chain.get('calls', {}).get(strike_str, {})
                    else:  # PUT
                        option_data = option_chain.get('puts', {}).get(strike_str, {})
                    
                    latest_ltp = option_data.get('ltp', 0)
                    
                    if latest_ltp > 0:
                        position['current_price'] = latest_ltp
                        position['exit_price'] = latest_ltp
                        logger.info(f"✓ Updated exit price to latest LTP: ₹{latest_ltp:.2f}")
                    else:
                        # Fallback to current_price if available
                        position['exit_price'] = position.get('current_price', position.get('entry_price'))
                        logger.warning(f"⚠️ Could not fetch latest LTP, using current_price: ₹{position['exit_price']:.2f}")
            except Exception as e:
                logger.error(f"Error fetching latest price before close: {e}")
                position['exit_price'] = position.get('current_price', position.get('entry_price'))
            
            logger.info(f"Closing position: {symbol} {strike or 'MISSING'} {option_type or 'MISSING'} @ ₹{position.get('exit_price', 0):.2f}")
            
            # Set exit reason based on exit_type if provided
            if exit_type:
                position['exit_reason'] = exit_type
                logger.info(f"Exit reason: {exit_type}")
            
            # Close position according to mode and capture accurate exit timestamps
            exit_timestamp = to_naive_ist(now_ist())
            if self.is_paper_mode:
                await self._close_paper_position(position)
                # _close_paper_position already sets exit_time, but ensure latest timestamp
                position['exit_time'] = exit_timestamp
            else:
                await self._close_live_position(position)
                position['exit_time'] = exit_timestamp
            
            # Broadcast updates BEFORE removing locally to keep frontend consistent
            if hasattr(self, 'websocket_manager') and self.websocket_manager:
                try:
                    await self.websocket_manager.broadcast_position_update(position)
                except Exception as e:
                    logger.warning(f"Failed to broadcast position update before removal: {e}")
            
            # Remove from in-memory positions *after* broadcasts so UI doesn’t flicker
            position_id_to_remove = position.get('id') or position.get('position_id')
            self.positions = [p for p in self.positions if (p.get('id') != position_id_to_remove and p.get('position_id') != position_id_to_remove)]
            self.risk_manager.remove_position(position_id_to_remove)
            
            # Remove from database
            self.position_service.remove_position(position.get('position_id', position.get('id')))
            
            # Broadcast trade close after DB persistence so closed list is accurate
            if hasattr(self, 'websocket_manager') and self.websocket_manager:
                try:
                    await self.websocket_manager.broadcast_trade_update(position)
                except Exception as e:
                    logger.warning(f"Failed to broadcast trade update: {e}")
            
            # Map position fields to trade fields for database recording - COMPLETE data for ML
            trade_record = {
                'id': position.get('position_id', position.get('id')),
                'symbol': position.get('symbol'),
                'direction': position.get('instrument_type'),  # CALL/PUT
                'strike': position.get('strike_price', 0),
                'expiry': position.get('expiry'),
                'entry_price': position.get('entry_price'),
                'exit_price': position.get('exit_price'),
                'quantity': position.get('quantity'),
                'pnl': position.get('pnl', 0),
                'entry_time': position.get('entry_time'),
                'exit_time': position.get('exit_time'),
                'strategy': position.get('strategy_name', position.get('strategy', 'unknown')),
                'strategy_id': position.get('strategy_name', position.get('strategy', 'unknown')),
                'signal_strength': position.get('signal_strength', 0),
                'ml_confidence': position.get('ml_score', 0),
                'target_price': position.get('target_price', 0),
                'stop_loss': position.get('stop_loss', 0),
                'exit_reason': position.get('exit_reason', 'TARGET'),
                'mode': 'PAPER' if self.is_paper_mode else 'LIVE',
                # Entry market context
                'spot_price_entry': position.get('spot_price_entry', 0),
                'vix_entry': position.get('vix_entry', 0),
                'pcr_entry': position.get('pcr_entry', 0),
                'market_regime_entry': position.get('market_regime_entry'),
                'regime_confidence': position.get('regime_confidence'),
                'entry_hour': position.get('entry_hour'),
                'entry_minute': position.get('entry_minute'),
                'day_of_week': position.get('day_of_week'),
                'is_expiry_day': position.get('is_expiry_day'),
                'days_to_expiry': position.get('days_to_expiry'),
                # Exit market context
                'spot_price_exit': position.get('spot_price_exit', 0),
                'vix_exit': position.get('vix_exit', 0),
                'pcr_exit': position.get('pcr_exit', 0),
                'market_regime_exit': position.get('market_regime_exit'),
                'exit_hour': position.get('exit_hour'),
                'exit_minute': position.get('exit_minute'),
                # Greeks at entry
                'delta_entry': position.get('delta_entry', 0.0),
                'gamma_entry': position.get('gamma_entry', 0.0),
                'theta_entry': position.get('theta_entry', 0.0),
                'vega_entry': position.get('vega_entry', 0.0),
                'iv_entry': position.get('iv_entry', 0.0),
                # Greeks at exit
                'delta_exit': position.get('delta_exit', 0.0),
                'gamma_exit': position.get('gamma_exit', 0.0),
                'theta_exit': position.get('theta_exit', 0.0),
                'vega_exit': position.get('vega_exit', 0.0),
                'iv_exit': position.get('iv_exit', 0.0),
                # Option chain at entry
                'oi_entry': position.get('oi_entry', 0),
                'volume_entry': position.get('volume_entry', 0),
                'bid_entry': position.get('bid_entry', 0.0),
                'ask_entry': position.get('ask_entry', 0.0),
                'spread_entry': position.get('spread_entry', 0.0),
                # Option chain at exit
                'oi_exit': position.get('oi_exit', 0),
                'volume_exit': position.get('volume_exit', 0),
                'bid_exit': position.get('bid_exit', 0.0),
                'ask_exit': position.get('ask_exit', 0.0),
                'spread_exit': position.get('spread_exit', 0.0),
                # ML Telemetry - CRITICAL for model tracking
                'model_version': position.get('model_version'),
                'model_hash': position.get('model_hash'),
                'features_snapshot': position.get('features_snapshot', {}),
                # Metadata
                'signal_reason': position.get('entry_reason', '')
            }
            
            # Record closed trade to trades table
            self.risk_manager.record_trade(trade_record)
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
    
    async def _close_paper_position(self, position: Dict):
        """Close position in paper mode - capture complete exit data for ML"""
        # P&L CALCULATION: LONG OPTIONS ONLY (Nov 21 locked)
        # SAME FORMULA FOR CALL AND PUT: (exit - entry) * quantity
        entry_price = position.get('entry_price', 0)
        current_price = position.get('current_price', 0)
        quantity = position.get('quantity', 0)
        instrument_type = position.get('instrument_type', 'CALL')  # CALL or PUT
        
        # OFFICIAL P&L CALCULATION: LONG OPTIONS ONLY
        # SAME FOR CALL AND PUT: (exit - entry) * quantity
        pnl = calculate_pnl(entry_price, current_price, quantity, instrument_type)
        
        position['pnl'] = pnl
        position['exit_price'] = current_price
        position['exit_time'] = to_naive_ist(now_ist())
        position['status'] = 'closed'
        position['exit_reason'] = position.get('exit_reason', 'TARGET')  # Use existing or default
        
        # CRITICAL: Capture complete market context at exit for ML training
        # Enrich with market context at exit (VIX, regime, time)
        position = self.market_context.enrich_position_exit(position)
        
        symbol = position.get('symbol')
        strike = position.get('strike_price', 0)
        option_type = position.get('instrument_type', 'CALL')
        
        exit_data_captured = False
        
        # Try multiple methods to get market data
        if symbol:
            try:
                # Method 1: Try self.market_data
                market_state = None
                if hasattr(self, 'market_data') and self.market_data is not None:
                    try:
                        market_state = self.market_data.market_state.get(symbol, {})
                    except Exception as e:
                        logger.warning(f"Could not get market state from self.market_data: {e}")
                
                # Method 2: Try global market_data_service
                if not market_state or not market_state.get('option_chain'):
                    try:
                        from backend.data.market_data import market_data_service
                        if market_data_service and hasattr(market_data_service, 'market_state'):
                            market_state = market_data_service.market_state.get(symbol, {})
                    except Exception as e:
                        logger.warning(f"Could not get market state from global service: {e}")
                
                if market_state:
                    # Spot price and market context
                    position['spot_price_exit'] = market_state.get('spot_price', 0)
                    position['vix_exit'] = market_state.get('vix', 0)
                    position['pcr_exit'] = market_state.get('pcr', 0)
                    
                    # Get option chain data at exit
                    option_chain = market_state.get('option_chain', {})
                    strike_str = str(int(strike)) if strike else None
                    
                    if strike_str and option_chain:
                        # Get option data for the specific strike
                        if option_type in ['CALL', 'CE']:
                            option_data = option_chain.get('calls', {}).get(strike_str, {})
                        else:
                            option_data = option_chain.get('puts', {}).get(strike_str, {})
                        
                        if option_data:
                            # Greeks at exit - CRITICAL FOR ML
                            position['delta_exit'] = option_data.get('delta', 0.0)
                            position['gamma_exit'] = option_data.get('gamma', 0.0)
                            position['theta_exit'] = option_data.get('theta', 0.0)
                            position['vega_exit'] = option_data.get('vega', 0.0)
                            position['iv_exit'] = option_data.get('iv', 0.0)
                            
                            # Option chain data at exit
                            position['oi_exit'] = option_data.get('oi', 0)
                            position['volume_exit'] = option_data.get('volume', 0)
                            position['bid_exit'] = option_data.get('bid', 0.0)
                            position['ask_exit'] = option_data.get('ask', 0.0)
                            
                            # Calculate spread at exit
                            bid = option_data.get('bid', 0.0)
                            ask = option_data.get('ask', 0.0)
                            if bid > 0 and ask > 0:
                                spread = ask - bid
                                mid_price = (bid + ask) / 2
                                position['spread_exit'] = (spread / mid_price * 100) if mid_price > 0 else 0
                            
                            exit_data_captured = True
                            logger.info(f"✓ Exit data captured: {symbol} {strike} {option_type} - Greeks (δ={position.get('delta_exit', 0):.4f}, γ={position.get('gamma_exit', 0):.4f}), OI={position.get('oi_exit', 0)}, Vol={position.get('volume_exit', 0)}")
                        else:
                            logger.warning(f"No option data found for {symbol} {strike} {option_type} at exit")
                    else:
                        logger.warning(f"No option chain available for {symbol} at exit")
                else:
                    logger.warning(f"No market state available for {symbol} at exit")
                    
            except Exception as e:
                logger.error(f"Error capturing exit data: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        if not exit_data_captured:
            logger.error(f"⚠️ WARNING: Exit Greeks NOT captured for {symbol} {strike} {option_type} - ML training data will be incomplete!")
        
        logger.info(f"[PAPER] Position closed - P&L: ₹{pnl:,.2f}")
        
        # Send Telegram notification for trade exit
        try:
            trade_data = {
                'symbol': position.get('symbol', 'UNKNOWN'),
                'instrument_type': position.get('instrument_type', 'OPTION'),
                'strike_price': position.get('strike_price', 0),
                'entry_price': position.get('entry_price', 0),
                'exit_price': position.get('exit_price', 0),
                'quantity': position.get('quantity', 0),
                'net_pnl': pnl,
                'pnl_percentage': (pnl / (position.get('entry_price', 1) * position.get('quantity', 1))) * 100 if position.get('entry_price') and position.get('quantity') else 0,
                'exit_type': position.get('exit_reason', 'UNKNOWN'),
                'strategy_name': position.get('strategy_name', 'UNKNOWN')
            }
            asyncio.create_task(self.telegram_notifier.send_trade_exit(trade_data))
        except Exception as e:
            logger.error(f"Failed to send Telegram trade exit notification: {e}")
    
    async def _close_live_position(self, position: Dict):
        """Close position in live mode"""
        # Place exit order
        signal = position
        
        instrument_key = self.upstox_client.get_instrument_key(
            exchange="NSE",
            symbol=signal.get('symbol'),
            expiry=signal.get('expiry'),
            strike=signal.get('strike'),
            option_type="CE" if signal.get('direction') == "CALL" else "PE"
        )
        
        # Reverse transaction type for exit
        exit_type = "SELL" if signal.get('direction') == "CALL" else "BUY"
        
        response = self.upstox_client.place_order(
            instrument_token=instrument_key,
            quantity=position['quantity'],
            transaction_type=exit_type,
            order_type='MARKET',
            product='I'
        )
        
        if response and response.get('status') == 'success':
            # P&L CALCULATION: LONG OPTIONS ONLY (Nov 21 locked)
            # SAME FORMULA FOR CALL AND PUT: (exit - entry) * quantity
            current_price = position.get('current_price', 0)
            entry_price = position.get('entry_price', 0)
            quantity = position.get('quantity', 0)
            instrument_type = position.get('instrument_type', 'CALL')  # CALL or PUT
            
            # OFFICIAL P&L CALCULATION: LONG OPTIONS ONLY
            # SAME FOR CALL AND PUT: (exit - entry) * quantity
            pnl = calculate_pnl(entry_price, current_price, quantity, instrument_type)
            
            position['pnl'] = pnl
            position['exit_price'] = current_price
            position['exit_time'] = datetime.now()
            position['status'] = 'closed'
            
            logger.info(f"[LIVE] Position closed - P&L: ₹{pnl:,.2f}")
        else:
            logger.error(f"Failed to close position: {response}")
    
    async def close_all_positions(self):
        """Close all open positions"""
        logger.info(f"Closing all positions ({len(self.positions)})")
        
        for position in self.positions.copy():
            await self.close_position(position)
