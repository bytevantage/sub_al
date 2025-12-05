#!/usr/bin/env python3
"""
Directly inject positions into the running trading system
This creates positions in the system's memory that will be managed until 3:20 PM
"""

import asyncio
import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# Add project path
sys.path.append('.')

# Exact positions to restore (continuations)
POSITIONS_TO_INJECT = [
    {
        "symbol": "NIFTY",
        "instrument_type": "PUT",
        "strike_price": 26200.0,
        "quantity": 50,
        "direction": "SELL",
        "entry_price": 55.65,
        "current_price": 55.65,
        "strategy_name": "RESTORED_POSITION",
        "position_id": "RESTORED_NIFTY_PUT_26200_18331696"
    },
    {
        "symbol": "SENSEX", 
        "instrument_type": "PUT",
        "strike_price": 85600.0,
        "quantity": 25,
        "direction": "SELL",
        "entry_price": 249.65,
        "current_price": 249.65,
        "strategy_name": "RESTORED_POSITION",
        "position_id": "RESTORED_SENSEX_PUT_85600_18331697"
    },
    {
        "symbol": "NIFTY",
        "instrument_type": "CALL", 
        "strike_price": 26200.0,
        "quantity": 50,
        "direction": "SELL",
        "entry_price": 77.40,
        "current_price": 77.40,
        "strategy_name": "RESTORED_POSITION",
        "position_id": "RESTORED_NIFTY_CALL_26200_18331698"
    },
    {
        "symbol": "NIFTY",
        "instrument_type": "PUT",
        "strike_price": 26200.0, 
        "quantity": 50,
        "direction": "SELL",
        "entry_price": 55.65,
        "current_price": 55.65,
        "strategy_name": "RESTORED_POSITION",
        "position_id": "RESTORED_NIFTY_PUT_26200_18331699"
    },
    {
        "symbol": "SENSEX",
        "instrument_type": "CALL",
        "strike_price": 85600.0,
        "quantity": 25,
        "direction": "SELL", 
        "entry_price": 489.85,
        "current_price": 489.85,
        "strategy_name": "RESTORED_POSITION",
        "position_id": "RESTORED_SENSEX_CALL_85600_18331700"
    },
    {
        "symbol": "SENSEX",
        "instrument_type": "PUT",
        "strike_price": 85600.0,
        "quantity": 25,
        "direction": "SELL",
        "entry_price": 248.35,
        "current_price": 248.35,
        "strategy_name": "RESTORED_POSITION",
        "position_id": "RESTORED_SENSEX_PUT_85600_18331701"
    }
]

async def inject_positions():
    """Inject positions directly into the trading system"""
    logger.info("🔄 Injecting positions into trading system...")
    
    # Check current time
    now = datetime.now()
    target_time = now.replace(hour=15, minute=20, second=0, microsecond=0)
    
    if now >= target_time:
        logger.warning("⚠️ Market time past 3:20 PM - not injecting positions")
        return
    
    time_remaining = target_time - now
    logger.info(f"⏰ Time until 3:20 PM: {time_remaining}")
    
    try:
        # Get the running trading system's position manager
        from backend.main import trading_system
        
        if not trading_system or not trading_system.order_manager:
            logger.error("❌ Trading system not available")
            return
        
        logger.info("✅ Connected to trading system")
        
        success_count = 0
        
        for i, position_data in enumerate(POSITIONS_TO_INJECT, 1):
            logger.info(f"📋 Injecting position {i}/{len(POSITIONS_TO_INJECT)}")
            
            try:
                # Create position dict
                position = {
                    'position_id': position_data['position_id'],
                    'symbol': position_data['symbol'],
                    'instrument_type': position_data['instrument_type'],
                    'strike_price': position_data['strike_price'],
                    'quantity': position_data['quantity'],
                    'direction': position_data['direction'],
                    'entry_price': position_data['entry_price'],
                    'current_price': position_data['current_price'],
                    'strategy_name': position_data['strategy_name'],
                    'entry_time': datetime.now(),
                    'position_metadata': {
                        'restored': True,
                        'continuation': True,
                        'restore_reason': 'SYSTEM_RESTART_RECOVERY',
                        'restore_time': datetime.now().isoformat()
                    }
                }
                
                # Add to order manager's positions
                trading_system.order_manager.positions.append(position)
                
                # Also add to risk manager's positions
                if hasattr(trading_system, 'risk_manager') and trading_system.risk_manager:
                    trading_system.risk_manager.positions.append(position)
                
                logger.info(f"✅ Injected: {position_data['symbol']} {position_data['instrument_type']} {position_data['strike_price']}")
                logger.info(f"📊 Entry price: ₹{position_data['entry_price']}")
                logger.info(f"📈 Direction: {position_data['direction']} {position_data['quantity']} lots")
                
                success_count += 1
                
                # Small delay between injections
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"❌ Failed to inject position: {e}")
        
        logger.info(f"📊 Injected {success_count}/{len(POSITIONS_TO_INJECT)} positions")
        
        if success_count > 0:
            logger.info("🎉 Positions injected successfully!")
            logger.info("📈 These are continuations of closed trades")
            logger.info("🔍 Check dashboard to see injected positions")
            logger.info("⏰ Positions will run until 3:20 PM EOD exit")
            logger.info("🔄 System will manage stop losses and targets automatically")
        else:
            logger.warning("⚠️ No positions were injected")
            
    except Exception as e:
        logger.error(f"❌ Failed to inject positions: {e}")

async def main():
    """Main execution"""
    await inject_positions()

if __name__ == "__main__":
    asyncio.run(main())
