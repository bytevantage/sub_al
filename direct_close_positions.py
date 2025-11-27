#!/usr/bin/env python3
"""
Direct position closure by accessing the trading system directly
"""

import asyncio
import sys
sys.path.insert(0, '/Users/srbhandary/Documents/Projects/srb-algo')

async def direct_close():
    """Direct close all positions"""
    try:
        # Import the trading system
        from backend.main import TradingSystem
        
        print("Creating trading system instance...")
        
        # Create a new instance
        trading_system = TradingSystem()
        
        # Initialize it
        await trading_system.initialize()
        
        print("Getting positions from risk manager...")
        positions = trading_system.risk_manager.get_open_positions()
        
        if not positions:
            print("✅ No positions found")
            return
        
        print(f"Found {len(positions)} positions:")
        total_pnl = 0
        for pos in positions:
            pnl = pos.get('unrealized_pnl', 0)
            total_pnl += pnl
            print(f"  - {pos.get('symbol')} {pos.get('strike_price')} {pos.get('instrument_type')} | P&L: ₹{pnl:.2f}")
        
        print(f"\nTotal P&L: ₹{total_pnl:.2f}")
        
        # Close all positions
        closed_count = 0
        for pos in positions:
            try:
                pos['exit_reason'] = 'DIRECT_FORCE_CLOSE'
                await trading_system.order_manager.close_position(pos, exit_type="DIRECT_FORCE_CLOSE")
                closed_count += 1
                print(f"✓ Closed {pos.get('symbol')} {pos.get('strike_price')}")
            except Exception as e:
                print(f"✗ Error closing position: {e}")
        
        print(f"\n✅ Closed {closed_count}/{len(positions)} positions")
        
        # Shutdown
        await trading_system.shutdown()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(direct_close())
