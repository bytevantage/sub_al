"""
Position Reconciliation + Orphan Trade Killer
Compares broker positions vs internal book every 60 seconds
"""

import asyncio
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from backend.core.logger import get_execution_logger
from backend.core.upstox_client import UpstoxClient
from backend.execution.order_manager import OrderManager
from backend.database.database import db
from backend.database.models import Trade
import os
import redis

logger = get_execution_logger()

class PositionReconciler:
    """Reconciles broker positions with internal book and kills orphans"""
    
    def __init__(self, upstox_client: UpstoxClient, order_manager: OrderManager):
        self.upstox_client = upstox_client
        self.order_manager = order_manager
        # Use Redis config from environment
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)
        
        # Reconciliation parameters
        self.reconciliation_interval_seconds = 60  # Check every 60 seconds
        self.orphan_kill_timeout_minutes = 5  # Kill orphans after 5 minutes
        
        # Track reconciliation state
        self.last_reconciliation_time = None
        self.orphan_positions_killed = 0
        self.reconciliation_errors = 0
        
    async def start_reconciliation_monitor(self):
        """Start the position reconciliation monitor task"""
        logger.info("🔄 Starting Position Reconciliation Monitor")
        
        while True:
            try:
                await self.reconcile_positions()
                await asyncio.sleep(self.reconciliation_interval_seconds)
            except Exception as e:
                logger.error(f"Error in position reconciliation: {e}")
                self.reconciliation_errors += 1
                await asyncio.sleep(30)  # Wait 30 seconds on error
    
    async def reconcile_positions(self):
        """Reconcile broker positions with internal book"""
        try:
            now = datetime.now()
            self.last_reconciliation_time = now
            
            # Get broker positions
            broker_positions = await self.get_broker_positions()
            
            # Get internal positions
            internal_positions = await self.get_internal_positions()
            
            # Compare and find orphans
            orphans = self.find_orphan_positions(broker_positions, internal_positions)
            
            # Kill orphan positions
            if orphans:
                logger.warning(f"🚨 Found {len(orphans)} orphan positions - killing immediately")
                for orphan in orphans:
                    await self.kill_orphan_position(orphan)
                    self.orphan_positions_killed += 1
            
            # Log reconciliation status
            await self.log_reconciliation_status(broker_positions, internal_positions, orphans)
            
        except Exception as e:
            logger.error(f"Error during position reconciliation: {e}")
    
    async def get_broker_positions(self) -> List[Dict]:
        """Get current positions from broker"""
        try:
            # Get positions from Upstox API
            positions_response = self.upstox_client.get_positions()
            
            if not positions_response or 'data' not in positions_response:
                return []
            
            broker_positions = []
            for pos in positions_response['data']:
                # Only include open positions with quantity
                if pos.get('quantity', 0) != 0:
                    broker_positions.append({
                        'instrument_token': pos.get('instrument_token'),
                        'symbol': pos.get('symbol', ''),
                        'quantity': pos.get('quantity', 0),
                        'product': pos.get('product', ''),
                        'average_price': pos.get('average_price', 0),
                        'ltp': pos.get('ltp', 0),
                        'pnl': pos.get('pnl', 0),
                        'source': 'broker'
                    })
            
            logger.debug(f"📊 Broker positions: {len(broker_positions)}")
            return broker_positions
            
        except Exception as e:
            logger.error(f"Error getting broker positions: {e}")
            return []
    
    async def get_internal_positions(self) -> List[Dict]:
        """Get positions from internal book"""
        try:
            # Get open positions from database
            open_trades = await self.order_manager.position_service.get_all_open_positions()
            
            internal_positions = []
            for trade in open_trades:
                internal_positions.append({
                    'trade_id': trade.get('trade_id'),
                    'symbol': trade.get('symbol', ''),
                    'quantity': trade.get('quantity', 0),
                    'direction': trade.get('direction', ''),
                    'entry_price': trade.get('entry_price', 0),
                    'strategy_name': trade.get('strategy_name', ''),
                    'source': 'internal'
                })
            
            logger.debug(f"📚 Internal positions: {len(internal_positions)}")
            return internal_positions
            
        except Exception as e:
            logger.error(f"Error getting internal positions: {e}")
            return []
    
    def find_orphan_positions(self, broker_positions: List[Dict], 
                            internal_positions: List[Dict]) -> List[Dict]:
        """
        Find positions that exist in broker but not in internal book
        
        Args:
            broker_positions: Positions from broker
            internal_positions: Positions from internal book
            
        Returns:
            List of orphan positions
        """
        orphans = []
        
        # Create lookup for internal positions
        internal_lookup = {}
        for pos in internal_positions:
            key = f"{pos['symbol']}_{pos['quantity']}"
            internal_lookup[key] = pos
        
        # Check each broker position
        for broker_pos in broker_positions:
            symbol = broker_pos.get('symbol', '')
            quantity = abs(broker_pos.get('quantity', 0))
            
            # Try to find matching internal position
            key = f"{symbol}_{quantity}"
            
            if key not in internal_lookup:
                # This is an orphan position
                broker_pos['orphan_reason'] = 'Not found in internal book'
                broker_pos['orphan_time'] = datetime.now().isoformat()
                orphans.append(broker_pos)
        
        return orphans
    
    async def kill_orphan_position(self, orphan: Dict):
        """
        Immediately close an orphan position
        
        Args:
            orphan: Orphan position details
        """
        try:
            symbol = orphan.get('symbol', '')
            quantity = abs(orphan.get('quantity', 0))
            
            # Determine direction (opposite of broker position)
            broker_quantity = orphan.get('quantity', 0)
            direction = 'SELL' if broker_quantity > 0 else 'BUY'
            
            logger.warning(f"💀 Killing orphan position: {symbol} {direction} {quantity} lots")
            
            # Create emergency exit order
            exit_order = {
                'symbol': symbol,
                'direction': direction,
                'quantity': quantity,
                'order_type': 'MARKET',  # Use market for immediate exit
                'product_type': 'MIS',  # Intraday product
                'strategy_name': 'Orphan_Killer',
                'is_emergency': True,
                'orphan_reason': orphan.get('orphan_reason', 'Unknown'),
                'timestamp': datetime.now().isoformat()
            }
            
            # Place exit order
            order_result = await self.order_manager.place_order(exit_order)
            
            if order_result:
                # Log orphan kill
                await self.log_orphan_kill(orphan, order_result)
                logger.info(f"✅ Orphan position killed: {symbol} {direction} {quantity}")
            else:
                logger.error(f"❌ Failed to kill orphan position: {symbol}")
                
        except Exception as e:
            logger.error(f"Error killing orphan position: {e}")
    
    async def log_orphan_kill(self, orphan: Dict, order_result: Dict):
        """Log orphan position kill for audit trail"""
        try:
            kill_record = {
                'orphan_position': orphan,
                'kill_order': order_result,
                'kill_time': datetime.now().isoformat(),
                'total_orphans_killed': self.orphan_positions_killed + 1
            }
            
            # Store in Redis for tracking
            cache_key = f"orphan_kills_{datetime.now().strftime('%Y-%m-%d')}"
            self.redis_client.lpush(cache_key, json.dumps(kill_record))
            self.redis_client.expire(cache_key, 7 * 24 * 3600)  # Keep for 7 days
            
        except Exception as e:
            logger.error(f"Error logging orphan kill: {e}")
    
    async def log_reconciliation_status(self, broker_positions: List[Dict], 
                                      internal_positions: List[Dict], 
                                      orphans: List[Dict]):
        """Log reconciliation status"""
        try:
            status = {
                'timestamp': self.last_reconciliation_time.isoformat(),
                'broker_positions_count': len(broker_positions),
                'internal_positions_count': len(internal_positions),
                'orphans_found': len(orphans),
                'total_orphans_killed': self.orphan_positions_killed,
                'reconciliation_errors': self.reconciliation_errors,
                'status': 'healthy' if len(orphans) == 0 else 'orphans_detected'
            }
            
            # Store daily status
            cache_key = f"reconciliation_status_{datetime.now().strftime('%Y-%m-%d')}"
            self.redis_client.set(cache_key, json.dumps(status), ex=24*3600)
            
            # Log summary
            if len(orphans) == 0:
                logger.info(f"✅ Position reconciliation healthy: "
                           f"Broker={len(broker_positions)}, Internal={len(internal_positions)}")
            else:
                logger.warning(f"⚠️ Position reconciliation: "
                             f"Broker={len(broker_positions)}, Internal={len(internal_positions)}, "
                             f"Orphans={len(orphans)}")
                
        except Exception as e:
            logger.error(f"Error logging reconciliation status: {e}")
    
    async def get_reconciliation_summary(self) -> Dict:
        """Get summary of reconciliation activity"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = f"reconciliation_status_{today}"
            
            status_data = self.redis_client.get(cache_key)
            if status_data:
                return json.loads(status_data)
            
            # Return current status if no cached data
            return {
                'timestamp': datetime.now().isoformat(),
                'broker_positions_count': 0,
                'internal_positions_count': 0,
                'orphans_found': 0,
                'total_orphans_killed': self.orphan_positions_killed,
                'reconciliation_errors': self.reconciliation_errors,
                'status': 'unknown',
                'last_reconciliation': self.last_reconciliation_time.isoformat() if self.last_reconciliation_time else None
            }
            
        except Exception as e:
            logger.error(f"Error getting reconciliation summary: {e}")
            return {'error': str(e)}
    
    async def force_reconciliation(self) -> Dict:
        """Force immediate reconciliation"""
        try:
            await self.reconcile_positions()
            return await self.get_reconciliation_summary()
        except Exception as e:
            logger.error(f"Error in force reconciliation: {e}")
            return {'error': str(e)}
