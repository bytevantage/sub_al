#!/usr/bin/env python3
"""
Force close all positions by directly calling the trading system
"""

import asyncio
import sys
sys.path.insert(0, '/Users/srbhandary/Documents/Projects/srb-algo')

async def force_close():
    """Force close all positions"""
    try:
        from backend.main import trading_system
        
        print("Forcing closure of all positions...")
        
        # Get positions from risk manager
        positions = trading_system.risk_manager.get_open_positions()
        
        if not positions:
            print("✅ No positions found")
            return
        
        print(f"Found {len(positions)} positions:")
        for pos in positions:
            print(f"  - {pos.get('symbol')} {pos.get('strike_price')} {pos.get('instrument_type')}")
        
        # Close all positions
        closed_count = 0
        for pos in positions:
            try:
                await trading_system.order_manager.close_position(pos, exit_type="MANUAL_FORCE_CLOSE")
                closed_count += 1
                print(f"✓ Closed {pos.get('symbol')} {pos.get('strike_price')}")
            except Exception as e:
                print(f"✗ Error closing position: {e}")
        
        print(f"\n✅ Closed {closed_count}/{len(positions)} positions")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(force_close())
