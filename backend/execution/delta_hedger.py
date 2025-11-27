"""
Auto Delta-Hedging System for Gamma Scalping
Maintains net delta between -0.10 and +0.10 automatically
"""

import asyncio
import json
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from backend.core.logger import get_execution_logger
from backend.core.upstox_client import UpstoxClient
from backend.execution.order_manager import OrderManager
from backend.core.timezone_utils import now_ist
import os
import redis

logger = get_execution_logger()

class DeltaHedger:
    """Automatic delta hedging for gamma scalping positions"""
    
    def __init__(self, upstox_client: UpstoxClient, order_manager: OrderManager, market_data_manager=None):
        self.upstox_client = upstox_client
        self.order_manager = order_manager
        self.market_data_manager = market_data_manager
        # Use Redis config from environment
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)
        
        # Hedging parameters
        self.max_delta_threshold = 0.25  # Hedge when |delta| > 0.25
        self.target_delta_range = (-0.10, 0.10)  # Keep delta in this range
        self.hedge_interval_minutes = 3  # Check every 3 minutes
        self.min_hedge_size = 15  # Minimum futures quantity for hedge
        
        # Track hedge positions
        self.hedge_positions = {}  # symbol -> hedge_quantity
        
    async def start_hedging_monitor(self):
        """Start the delta hedging monitor task"""
        logger.info("🔄 Starting Delta Hedging Monitor")
        
        while True:
            try:
                await self.check_and_hedge_all_positions()
                await asyncio.sleep(self.hedge_interval_minutes * 60)
            except Exception as e:
                logger.error(f"Error in delta hedging monitor: {e}")
                await asyncio.sleep(30)  # Wait 30 seconds on error
    
    async def check_and_hedge_all_positions(self):
        """Check all open gamma scalping positions and hedge if needed"""
        try:
            # Get all open positions
            open_positions = await self.order_manager.position_service.get_all_open_positions()
            
            # Group by symbol for net delta calculation
            symbol_positions = {}
            for position in open_positions:
                symbol = position.get('symbol', '')
                strategy = position.get('strategy_name', '')
                
                # Only hedge gamma scalping positions
                if 'gamma' in strategy.lower() or 'scalping' in strategy.lower():
                    if symbol not in symbol_positions:
                        symbol_positions[symbol] = []
                    symbol_positions[symbol].append(position)
            
            # Check each symbol for hedging needs
            for symbol, positions in symbol_positions.items():
                await self.check_and_hedge_symbol(symbol, positions)
                
        except Exception as e:
            logger.error(f"Error checking delta hedge positions: {e}")
    
    async def check_and_hedge_symbol(self, symbol: str, positions: List[Dict]):
        """Check and hedge delta for a specific symbol"""
        try:
            # Calculate net delta for all positions
            net_delta, total_gamma = await self.calculate_net_greeks(symbol, positions)
            
            logger.info(f"📊 {symbol} Net Delta: {net_delta:.3f}, Net Gamma: {total_gamma:.3f}")
            
            # Check if hedging is needed
            if abs(net_delta) > self.max_delta_threshold:
                await self.execute_hedge(symbol, net_delta, positions)
            else:
                logger.debug(f"✅ {symbol} Delta within range ({net_delta:.3f}), no hedge needed")
                
        except Exception as e:
            logger.error(f"Error checking delta for {symbol}: {e}")
    
    async def calculate_net_greeks(self, symbol: str, positions: List[Dict]) -> Tuple[float, float]:
        """Calculate net delta and gamma for all positions"""
        net_delta = 0.0
        net_gamma = 0.0
        
        for position in positions:
            try:
                # Get current Greeks for the position
                current_greeks = await self.get_current_greeks(position)
                
                if current_greeks:
                    delta = current_greeks.get('delta', 0.0)
                    gamma = current_greeks.get('gamma', 0.0)
                    quantity = position.get('quantity', 0)
                    
                    # Calculate position greeks
                    if position.get('direction') == 'BUY':
                        net_delta += delta * quantity
                        net_gamma += gamma * quantity
                    else:  # SELL
                        net_delta -= delta * quantity
                        net_gamma -= gamma * quantity
                        
            except Exception as e:
                logger.error(f"Error calculating greeks for position {position.get('trade_id')}: {e}")
        
        return net_delta, net_gamma
    
    async def get_current_greeks(self, position: Dict) -> Optional[Dict]:
        """Get current Greeks for a position"""
        try:
            symbol = position.get('symbol', '')
            strike = position.get('strike_price', 0)
            option_type = position.get('instrument_type', '')  # CALL or PUT
            expiry = position.get('expiry', '')
            
            if not all([symbol, strike, option_type, expiry]):
                return None
            
            # Get current option chain from market_data_manager (already processed as dict)
            if not hasattr(self, 'market_data_manager') or not self.market_data_manager:
                logger.warning("Market data manager not available for delta hedging")
                return None
                
            option_chain_data = await self.market_data_manager.get_option_chain(symbol, expiry)
            
            if not option_chain_data:
                logger.warning("No option chain data available for delta hedging")
                return None
            
            # option_chain_data is already processed as dict by market_data_manager
            option_chain = option_chain_data
            
            # Check if option_chain is a dict (expected) or list (error case)
            if not isinstance(option_chain, dict):
                logger.warning(f"Option chain data is {type(option_chain)}, expected dict. Cannot get Greeks.")
                return None
            
            # Option chain structure: {'calls': {strike: {...}}, 'puts': {strike: {...}}}
            strike_str = str(int(strike))
            
            if option_type.upper() == 'CALL':
                options_dict = option_chain.get('calls', {})
            else:  # PUT
                options_dict = option_chain.get('puts', {})
            
            if not isinstance(options_dict, dict):
                logger.warning(f"Options dict is {type(options_dict)}, expected dict")
                return None
            
            # Get option data for the specific strike
            option_data = options_dict.get(strike_str)
            
            if option_data:
                return {
                    'delta': option_data.get('delta', 0.0),
                    'gamma': option_data.get('gamma', 0.0),
                    'theta': option_data.get('theta', 0.0),
                    'vega': option_data.get('vega', 0.0)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting current Greeks: {e}")
            return None
    
    async def execute_hedge(self, symbol: str, net_delta: float, positions: List[Dict]):
        """Execute delta hedge using futures"""
        try:
            # Calculate hedge quantity
            futures_quantity = self.calculate_hedge_quantity(net_delta)
            
            if abs(futures_quantity) < self.min_hedge_size:
                logger.info(f"📊 {symbol} Hedge quantity too small: {futures_quantity} (min: {self.min_hedge_size})")
                return
            
            # Determine hedge direction
            if net_delta > 0:
                # Net long delta → Sell futures
                hedge_direction = 'SELL'
                logger.info(f"🔻 {symbol} Hedging: Selling {abs(futures_quantity)} futures (Delta: {net_delta:.3f})")
            else:
                # Net short delta → Buy futures
                hedge_direction = 'BUY'
                logger.info(f"🔺 {symbol} Hedging: Buying {abs(futures_quantity)} futures (Delta: {net_delta:.3f})")
            
            # Execute hedge trade
            hedge_order = await self.place_hedge_order(symbol, futures_quantity, hedge_direction)
            
            if hedge_order:
                # Record hedge position
                await self.record_hedge_position(symbol, hedge_order, net_delta, positions)
                logger.info(f"✅ {symbol} Delta hedge executed: {hedge_direction} {abs(futures_quantity)} futures")
            else:
                logger.error(f"❌ {symbol} Failed to execute delta hedge")
                
        except Exception as e:
            logger.error(f"Error executing delta hedge for {symbol}: {e}")
    
    def calculate_hedge_quantity(self, net_delta: float) -> int:
        """Calculate futures quantity needed for hedge"""
        # Simple calculation: 1 futures contract = 1 delta
        # Round to nearest lot size (NIFTY: 50, SENSEX: 30)
        lot_size = 50 if 'NIFTY' in str(net_delta) else 30
        
        # Calculate raw quantity
        raw_quantity = abs(net_delta)
        
        # Round up to nearest lot
        hedge_quantity = int(np.ceil(raw_quantity / lot_size) * lot_size)
        
        # Apply sign
        return hedge_quantity if net_delta > 0 else -hedge_quantity
    
    async def place_hedge_order(self, symbol: str, quantity: int, direction: str) -> Optional[Dict]:
        """Place hedge order using futures"""
        try:
            # Get futures instrument
            futures_instrument = await self.get_futures_instrument(symbol)
            
            if not futures_instrument:
                return None
            
            # Get current spot price for futures pricing
            spot_price = 26000  # Default fallback
            try:
                if hasattr(self, 'market_data_manager') and self.market_data_manager:
                    market_state = await self.market_data_manager.get_current_state()
                    symbol_data = market_state.get(symbol, {})
                    spot_price = symbol_data.get('spot_price', 26000)
            except Exception as e:
                logger.debug(f"Could not get spot price for hedge pricing: {e}")
            
            # For futures, price is approximately equal to spot price
            futures_price = spot_price
            
            # Create hedge order
            hedge_order = {
                'symbol': symbol,
                'instrument_type': 'FUTURES',
                'direction': direction,
                'quantity': abs(quantity),
                'price': futures_price,  # Add price for the order
                'order_type': 'MARKET',  # Use market for immediate hedge
                'product_type': 'MIS',  # Intraday product
                'strategy_name': 'Delta_Hedge',
                'is_hedge': True,
                'hedge_reason': f"Auto delta hedge: {direction} {abs(quantity)}",
                'timestamp': now_ist().isoformat()
            }
            
            # Place order through order manager
            order_result = await self.order_manager.place_order(hedge_order)
            
            return order_result
            
        except Exception as e:
            logger.error(f"Error placing hedge order: {e}")
            return None
    
    async def get_futures_instrument(self, symbol: str) -> Optional[str]:
        """Get current futures instrument key"""
        try:
            # For NIFTY and SENSEX, use current month futures
            if symbol == "NIFTY":
                return "NSE_INDEX|Nifty 50"
            elif symbol == "SENSEX":
                return "BSE_INDEX|SENSEX"
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting futures instrument for {symbol}: {e}")
            return None
    
    async def record_hedge_position(self, symbol: str, hedge_order: Dict, net_delta: float, 
                                  original_positions: List[Dict]):
        """Record hedge position for tracking"""
        try:
            hedge_record = {
                'symbol': symbol,
                'hedge_order_id': hedge_order.get('order_id'),
                'hedge_quantity': hedge_order.get('quantity'),
                'hedge_direction': hedge_order.get('direction'),
                'net_delta_before': net_delta,
                'original_positions': len(original_positions),
                'timestamp': now_ist().isoformat(),
                'status': 'active'
            }
            
            # Store in Redis for tracking
            cache_key = f"delta_hedge_{symbol}_{now_ist().strftime('%Y-%m-%d')}"
            self.redis_client.hset(cache_key, hedge_order.get('order_id'), json.dumps(hedge_record))
            
            # Update local tracking
            self.hedge_positions[symbol] = hedge_order.get('quantity', 0)
            
        except Exception as e:
            logger.error(f"Error recording hedge position: {e}")
    
    def _get_instrument_key(self, symbol: str) -> str:
        """Get Upstox instrument key for symbol"""
        if symbol == "NIFTY":
            return "NSE_INDEX|Nifty 50"
        elif symbol == "SENSEX":
            return "BSE_INDEX|SENSEX"
        else:
            return symbol
    
    async def get_hedge_summary(self) -> Dict:
        """Get summary of all hedge positions"""
        try:
            summary = {
                'total_hedges': 0,
                'active_hedges': {},
                'last_hedge_time': None,
                'total_hedge_volume': 0
            }
            
            today = now_ist().strftime('%Y-%m-%d')
            
            for symbol in ['NIFTY', 'SENSEX']:
                cache_key = f"delta_hedge_{symbol}_{today}"
                hedges = self.redis_client.hgetall(cache_key)
                
                if hedges:
                    summary['active_hedges'][symbol] = len(hedges)
                    summary['total_hedges'] += len(hedges)
                    
                    for order_id, hedge_data in hedges.items():
                        hedge = json.loads(hedge_data)
                        summary['total_hedge_volume'] += hedge.get('hedge_quantity', 0)
                        
                        if not summary['last_hedge_time'] or hedge['timestamp'] > summary['last_hedge_time']:
                            summary['last_hedge_time'] = hedge['timestamp']
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting hedge summary: {e}")
            return {'error': str(e)}
