#!/usr/bin/env python3
"""
Close positions directly via risk_manager/order_manager
This works with the in-memory positions shown in dashboard
"""

import asyncio
import requests
import json

def get_positions():
    """Get positions from dashboard API"""
    try:
        response = requests.get('http://localhost:8000/api/dashboard/positions')
        response.raise_for_status()
        data = response.json()
        return data.get('data', {}).get('positions', [])
    except Exception as e:
        print(f"❌ Error getting positions: {e}")
        return []


async def close_via_backend():
    """Close positions by directly calling backend"""
    import sys
    sys.path.insert(0, '/Users/srbhandary/Documents/Projects/srb-algo')
    
    try:
        from backend.main import TradingSystem
        from backend.core.config import config
        
        # Get the running trading system instance
        # This is a bit hacky but works for manual intervention
        print("Connecting to backend...")
        
        # Alternative: use HTTP to trigger close
        positions = get_positions()
        
        if not positions:
            print("✅ No positions to close")
            return
        
        print(f"\nFound {len(positions)} positions:")
        print("=" * 80)
        
        total_pnl = 0
        for pos in positions:
            symbol = pos.get('symbol')
            strike = pos.get('strike_price')
            opt_type = pos.get('option_type')
            entry = pos.get('entry_price')
            current = pos.get('current_price')
            pnl = pos.get('unrealized_pnl', 0)
            strategy = pos.get('strategy')
            
            print(f"{symbol} {strike} {opt_type} | Entry: ₹{entry:.2f} | Current: ₹{current:.2f} | P&L: ₹{pnl:.2f} | {strategy}")
            total_pnl += pnl
        
        print("=" * 80)
        print(f"Total P&L: ₹{total_pnl:.2f}")
        print()
        
        response = input("Close all positions? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
        
        print("\nClosing positions via backend order manager...")
        
        # Import and get order manager
        from backend.api.emergency_controls import get_app_state
        state = get_app_state()
        
        order_manager = state.get('order_manager')
        risk_manager = state.get('risk_manager')
        
        if not order_manager:
            print("❌ Order manager not available in app state")
            print("\nTry restarting backend: ./stop.sh && ./start.sh")
            return
        
        if not risk_manager:
            print("❌ Risk manager not available")
            return
        
        # Get positions from risk manager (this is what dashboard shows)
        rm_positions = risk_manager.get_open_positions()
        
        print(f"Found {len(rm_positions)} positions in risk manager")
        
        closed_count = 0
        for pos in rm_positions:
            try:
                pos['exit_reason'] = 'MANUAL'
                await order_manager.close_position(pos)
                closed_count += 1
                print(f"✓ Closed {pos.get('symbol')} {pos.get('strike_price')} {pos.get('instrument_type')}")
            except Exception as e:
                print(f"✗ Error closing position: {e}")
        
        print(f"\n✅ Closed {closed_count}/{len(rm_positions)} positions")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("\nCannot access backend modules. Backend might not be running.")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("=" * 80)
    print("Direct Position Closure via Risk Manager")
    print("=" * 80)
    print()
    
    # Check if backend is running
    try:
        response = requests.get('http://localhost:8000/api/dashboard/positions', timeout=2)
        if response.status_code != 200:
            print("❌ Backend is not responding correctly")
            print("\nStart backend: ./start.sh")
            return
    except:
        print("❌ Backend is not running")
        print("\nStart backend: ./start.sh")
        return
    
    print("✓ Backend is running\n")
    
    # Run async close
    asyncio.run(close_via_backend())


if __name__ == "__main__":
    main()
