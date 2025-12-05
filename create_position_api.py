#!/usr/bin/env python3
"""
Create a temporary API endpoint to inject positions
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

# Positions to inject
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

def create_position_injection_file():
    """Create a position injection file that can be read by the system"""
    logger.info("🔄 Creating position injection file...")
    
    # Check current time
    now = datetime.now()
    target_time = now.replace(hour=15, minute=20, second=0, microsecond=0)
    
    if now >= target_time:
        logger.warning("⚠️ Market time past 3:20 PM - not creating injection file")
        return
    
    time_remaining = target_time - now
    logger.info(f"⏰ Time until 3:20 PM: {time_remaining}")
    
    try:
        import json
        
        # Create injection data
        injection_data = {
            'timestamp': datetime.now().isoformat(),
            'action': 'inject_positions',
            'positions': POSITIONS_TO_INJECT,
            'metadata': {
                'restore_reason': 'SYSTEM_RESTART_RECOVERY',
                'continuation': True,
                'target_close_time': target_time.isoformat()
            }
        }
        
        # Create injection file
        injection_file = "data/position_injection.json"
        
        with open(injection_file, 'w') as f:
            json.dump(injection_data, f, indent=2)
        
        logger.info(f"✅ Created injection file: {injection_file}")
        logger.info(f"📊 {len(POSITIONS_TO_INJECT)} positions ready for injection")
        
        # Log position details
        for i, pos in enumerate(POSITIONS_TO_INJECT, 1):
            logger.info(f"📋 {i}. {pos['symbol']} {pos['instrument_type']} {pos['strike_price']} @ ₹{pos['entry_price']}")
        
        logger.info("🎉 Injection file created successfully!")
        logger.info("📈 The trading system should detect and inject these positions")
        logger.info("⏰ Positions will run until 3:20 PM EOD exit")
        
    except Exception as e:
        logger.error(f"❌ Failed to create injection file: {e}")

if __name__ == "__main__":
    create_position_injection_file()
