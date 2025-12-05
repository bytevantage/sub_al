#!/usr/bin/env python3
"""
Position Price Updater - Real-time Position Price Updates
Updates position prices every 5 seconds using WebSocket or API
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from backend.core.logger import get_logger
from backend.core.upstox_client import UpstoxClient
from backend.execution.order_manager import OrderManager
from backend.data.market_data import MarketDataManager

logger = get_logger(__name__)

class PositionPriceUpdater:
    """Dedicated real-time position price updater"""
    
    def __init__(self, upstox_client: UpstoxClient, order_manager: OrderManager, 
                 market_data_manager: MarketDataManager):
        self.upstox_client = upstox_client
        self.order_manager = order_manager
        self.market_data_manager = market_data_manager
        
        # Use OFFICIAL data fetch frequency from config
        from backend.main import config
        self.update_interval_seconds = config.get('data_fetch.position_ltp_seconds', 5)  # Official: 5 seconds
        
        # Tracking
        self.last_update_time = None
        self.update_count = 0
        self.error_count = 0
        
    async def start_price_updates(self):
        """Start continuous position price updates"""
        logger.info(f"🔄 Starting Real-time Position Price Updater ({self.update_interval_seconds}s interval)")
        
        while True:
            try:
                await self.update_all_position_prices()
                await asyncio.sleep(self.update_interval_seconds)
            except Exception as e:
                logger.error(f"Error in position price update: {e}")
                self.error_count += 1
                await asyncio.sleep(10)  # Wait longer on error
    
    async def update_all_position_prices(self):
        """Update all open positions with current prices"""
        
        # Get open positions from risk manager
        positions = self.order_manager.risk_manager.open_positions
        
        if not positions:
            logger.debug("No open positions to update")
            return
        
        logger.debug(f"Updating prices for {len(positions)} open positions")
        
        # Group positions by symbol for efficient API calls
        symbol_groups = {}
        for position in positions:
            symbol = position.get('symbol')
            if symbol:
                if symbol not in symbol_groups:
                    symbol_groups[symbol] = []
                symbol_groups[symbol].append(position)
        
        # Update each symbol group
        total_updated = 0
        for symbol, position_list in symbol_groups.items():
            try:
                updated = await self.update_symbol_positions(symbol, position_list)
                total_updated += updated
            except Exception as e:
                logger.error(f"Error updating {symbol} positions: {e}")
        
        if total_updated > 0:
            logger.info(f"✓ Updated {total_updated}/{len(positions)} position prices")
        
        self.update_count += 1
        self.last_update_time = datetime.now()
    
    async def update_symbol_positions(self, symbol: str, positions: List[Dict]) -> int:
        """Update all positions for a specific symbol"""
        
        # Get current market state (has option chain data)
        try:
            market_state = await self.market_data_manager.get_current_state()
            symbol_data = market_state.get(symbol, {})
            option_chain = symbol_data.get('option_chain', {})
        except Exception as e:
            logger.error(f"Error fetching market state for {symbol}: {e}")
            return 0
        
        updated_count = 0
        
        for position in positions:
            try:
                # Get position details
                strike = position.get('strike_price') or position.get('strike')
                option_type = position.get('instrument_type') or position.get('direction')
                
                if not strike or not option_type:
                    continue
                
                # Get LTP from option chain
                strike_str = str(int(strike))
                options_dict = option_chain.get('calls' if option_type.upper() in ['CALL', 'CE'] else 'puts', {})
                option_data = options_dict.get(strike_str, {})
                
                current_ltp = option_data.get('ltp', 0)
                
                if current_ltp > 0:
                    # Update position price
                    position_id = position.get('position_id') or position.get('id')
                    
                    # Update in risk manager
                    self.order_manager.risk_manager.update_position_mtm(position, current_ltp)
                    
                    # Update in database
                    if self.order_manager.position_service:
                        self.order_manager.position_service.update_position_price(
                            position_id, current_ltp
                        )
                    
                    # Update Greeks if available
                    if option_data:
                        await self.order_manager.update_position_greeks(position_id, option_data)
                    
                    updated_count += 1
                    logger.debug(f"Updated {symbol} {strike} {option_type}: ₹{current_ltp}")
                else:
                    logger.warning(f"No LTP found for {symbol} {strike} {option_type}")
                    
            except Exception as e:
                logger.error(f"Error updating position: {e}")
        
        return updated_count
    
    def get_status(self) -> Dict:
        """Get updater status"""
        return {
            'update_interval_seconds': self.update_interval_seconds,
            'last_update_time': self.last_update_time.isoformat() if self.last_update_time else None,
            'update_count': self.update_count,
            'error_count': self.error_count,
            'is_running': True
        }

# Integration with main trading system
def create_position_price_updater(trading_system) -> PositionPriceUpdater:
    """Create and integrate position price updater"""
    
    updater = PositionPriceUpdater(
        upstox_client=trading_system.upstox_client,
        order_manager=trading_system.order_manager,
        market_data_manager=trading_system.market_data
    )
    
    return updater
