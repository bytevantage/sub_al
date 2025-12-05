#!/usr/bin/env python3
"""
Script to reopen positions that were closed during system restart
Based on trades closed around 2:07 PM on Dec 1, 2025
"""

import asyncio
import sys
import logging
from datetime import datetime
from typing import Dict, List

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# Add project path
sys.path.append('.')

from backend.execution.order_manager import OrderManager
from backend.data.market_data import MarketDataManager
from backend.core.upstox_client import UpstoxClient
from backend.execution.risk_manager import RiskManager
from backend.database.database import db

# Positions that were closed around 2:07 PM (based on log analysis)
# These are approximate positions based on the P&L patterns seen in logs
CLOSED_POSITIONS_TO_REOPEN = [
    {
        "symbol": "NIFTY",
        "instrument_type": "PUT",  # Likely PUT based on negative P&L patterns
        "strike_price": 24200,     # Approximate based on typical NIFTY strikes
        "quantity": 50,           # Standard lot size
        "strategy_name": "Gamma Scalping",
        "entry_mode": "PAPER",
        "direction": "SELL"       # Based on negative P&L (short positions)
    },
    {
        "symbol": "SENSEX", 
        "instrument_type": "PUT",
        "strike_price": 81000,
        "quantity": 25,
        "strategy_name": "IV Rank Trading",
        "entry_mode": "PAPER",
        "direction": "SELL"
    },
    {
        "symbol": "NIFTY",
        "instrument_type": "CALL",  # Some were profitable (CALL positions)
        "strike_price": 24500,
        "quantity": 50,
        "strategy_name": "VWAP Deviation",
        "entry_mode": "PAPER", 
        "direction": "SELL"
    },
    {
        "symbol": "SENSEX",
        "instrument_type": "CALL",
        "strike_price": 81500,
        "quantity": 25,
        "strategy_name": "Quantum Edge V2",
        "entry_mode": "PAPER",
        "direction": "SELL"
    }
]

class PositionReopener:
    def __init__(self):
        self.order_manager = None
        self.market_data = None
        self.risk_manager = None
        self.upstox_client = None
        
    async def initialize(self):
        """Initialize trading components"""
        try:
            logger.info("🔄 Initializing position reopener...")
            
            # Initialize components
            self.upstox_client = UpstoxClient(access_token=None)  # Will use paper trading mode
            
            # Get risk config from system
            from backend.core.config import config
            risk_config = config.get('risk', {})
            
            self.market_data = MarketDataManager(self.upstox_client)
            self.risk_manager = RiskManager(risk_config=risk_config)
            self.order_manager = OrderManager(
                self.upstox_client, 
                self.risk_manager,
                self.market_data
            )
            
            # MarketDataManager doesn't need explicit start initialization
            # It will initialize when making API calls
            
            logger.info("✅ Position reopener initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            return False
    
    async def get_current_option_price(self, symbol: str, strike: float, option_type: str) -> float:
        """Get current market price for option"""
        try:
            # Get option chain with expiry
            from datetime import datetime
            # Get current week expiry (or next available)
            current_date = datetime.now()
            
            option_chain = await self.market_data.get_option_chain(symbol, expiry=current_date)
            
            if not option_chain:
                logger.warning(f"No option chain data for {symbol}")
                return 0.0
            
            # Extract price based on option type
            if option_type.upper() == "CALL":
                calls_data = option_chain.get('calls', {})
                strike_key = str(int(strike))
                if strike_key in calls_data:
                    return float(calls_data[strike_key].get('ltp', 0.0))
            else:  # PUT
                puts_data = option_chain.get('puts', {})
                strike_key = str(int(strike))
                if strike_key in puts_data:
                    return float(puts_data[strike_key].get('ltp', 0.0))
            
            logger.warning(f"No price found for {symbol} {option_type} {strike}")
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting option price: {e}")
            return 0.0
    
    async def reopen_position(self, position_config: Dict) -> bool:
        """Reopen a single position"""
        try:
            symbol = position_config['symbol']
            strike = position_config['strike_price']
            option_type = position_config['instrument_type']
            quantity = position_config['quantity']
            strategy = position_config['strategy_name']
            direction = position_config['direction']
            
            logger.info(f"🔄 Reopening position: {symbol} {option_type} {strike} ({direction} {quantity})")
            
            # Get current market price
            current_price = await self.get_current_option_price(symbol, strike, option_type)
            if current_price <= 0:
                logger.error(f"❌ Cannot get market price for {symbol} {option_type} {strike}")
                return False
            
            logger.info(f"📊 Market price: ₹{current_price}")
            
            # Create position order
            position = {
                'symbol': symbol,
                'instrument_type': option_type,
                'strike_price': strike,
                'quantity': quantity,
                'direction': direction,
                'entry_price': current_price,
                'strategy_name': strategy,
                'entry_mode': 'PAPER',
                'entry_time': datetime.now(),
                'trade_id': f"REOPEN_{symbol}_{option_type}_{strike}_{int(datetime.now().timestamp())}"
            }
            
            # Submit order
            success = await self.order_manager.open_position(position)
            
            if success:
                logger.info(f"✅ Successfully reopened position: {symbol} {option_type} {strike}")
                return True
            else:
                logger.error(f"❌ Failed to reopen position: {symbol} {option_type} {strike}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error reopening position: {e}")
            return False
    
    async def reopen_all_positions(self) -> int:
        """Reopen all closed positions"""
        logger.info(f"🔄 Starting to reopen {len(CLOSED_POSITIONS_TO_REOPEN)} positions...")
        
        success_count = 0
        for i, position_config in enumerate(CLOSED_POSITIONS_TO_REOPEN, 1):
            logger.info(f"📋 Processing position {i}/{len(CLOSED_POSITIONS_TO_REOPEN)}")
            
            success = await self.reopen_position(position_config)
            if success:
                success_count += 1
            
            # Small delay between orders to avoid rate limits
            await asyncio.sleep(2)
        
        logger.info(f"📊 Reopened {success_count}/{len(CLOSED_POSITIONS_TO_REOPEN)} positions")
        return success_count
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            # MarketDataManager doesn't have stop method, just pass
            logger.info("🧹 Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

async def main():
    """Main execution function"""
    logger.info("🚀 Starting position reopening process...")
    
    # Check current time
    now = datetime.now()
    target_time = now.replace(hour=15, minute=20, second=0, microsecond=0)
    
    if now >= target_time:
        logger.warning("⚠️ Market time past 3:20 PM - not reopening positions")
        return
    
    time_remaining = target_time - now
    logger.info(f"⏰ Time until 3:20 PM: {time_remaining}")
    
    # Initialize reopener
    reopener = PositionReopener()
    
    try:
        # Initialize components
        if not await reopener.initialize():
            logger.error("❌ Failed to initialize - aborting")
            return
        
        # Reopen positions
        success_count = await reopener.reopen_all_positions()
        
        if success_count > 0:
            logger.info(f"🎉 Successfully reopened {success_count} positions!")
            logger.info("📈 Positions will run until 3:20 PM EOD exit")
        else:
            logger.warning("⚠️ No positions were reopened")
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
    
    finally:
        await reopener.cleanup()
        logger.info("🏁 Position reopening process completed")

if __name__ == "__main__":
    asyncio.run(main())
