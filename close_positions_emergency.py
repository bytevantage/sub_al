#!/usr/bin/env python3
"""
Emergency position closure using app state
"""

import asyncio
import sys
sys.path.insert(0, '/Users/srbhandary/Documents/Projects/srb-algo')

async def emergency_close():
    """Emergency close all positions"""
    try:
        from backend.api.emergency_controls import get_app_state
        
        print("Getting app state...")
        state = get_app_state()
        
        order_manager = state.get('order_manager')
        risk_manager = state.get('risk_manager')
        
        if not order_manager:
            print("❌ Order manager not found")
            return
        
        if not risk_manager:
            print("❌ Risk manager not found")
            return
        
        print("Getting positions from risk manager...")
        positions = risk_manager.get_open_positions()
        
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
                await order_manager.close_position(pos, exit_type="EMERGENCY_MANUAL_CLOSE")
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
    asyncio.run(emergency_close())
