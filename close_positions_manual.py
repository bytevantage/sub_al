#!/usr/bin/env python3
"""
Emergency script to manually close all open positions
Run this when EOD exit fails and positions are stuck open
"""

import asyncio
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

# Add backend to path
sys.path.insert(0, '/Users/srbhandary/Documents/Projects/srb-algo')

from backend.database.database import db
from backend.database.models import Position, Trade
from sqlalchemy import func

IST = ZoneInfo("Asia/Kolkata")


def close_positions_in_db():
    """Manually close positions in database"""
    session = db.get_session()
    
    try:
        # Get all open positions (all records in positions table are open)
        positions = session.query(Position).all()
        
        if not positions:
            print("✅ No open positions found")
            return
        
        print(f"Found {len(positions)} open positions:")
        print("=" * 80)
        
        for pos in positions:
            print(f"Position: {pos.symbol} {pos.strike_price} {pos.instrument_type}")
            print(f"  Entry: ₹{pos.entry_price:.2f}")
            print(f"  Current: ₹{pos.current_price:.2f}")
            print(f"  Unrealized P&L: ₹{pos.unrealized_pnl:.2f}")
            print()
        
        # Confirm closure
        response = input("Close all these positions? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
        
        print("\nClosing positions...")
        now = datetime.now(IST)
        
        for pos in positions:
            # Calculate final P&L
            exit_price = pos.current_price or pos.entry_price
            quantity = pos.quantity
            
            # Calculate P&L based on direction
            if pos.direction == 'BUY':
                gross_pnl = (exit_price - pos.entry_price) * quantity
            else:  # SELL
                gross_pnl = (pos.entry_price - exit_price) * quantity
            
            # Estimate fees (2 legs: entry + exit)
            fees = (pos.entry_price + exit_price) * quantity * 0.0006  # ~0.06% total
            net_pnl = gross_pnl - fees
            
            # Create trade record
            trade = Trade(
                trade_id=pos.position_id,
                symbol=pos.symbol,
                instrument_type=pos.instrument_type,
                strike_price=pos.strike_price,
                expiry=pos.expiry,
                entry_time=pos.entry_time,
                exit_time=now,
                entry_price=pos.entry_price,
                exit_price=exit_price,
                quantity=quantity,
                direction=pos.direction,
                gross_pnl=gross_pnl,
                fees=fees,
                net_pnl=net_pnl,
                pnl_percentage=(net_pnl / (pos.entry_price * quantity)) * 100,
                status='CLOSED',
                exit_reason='MANUAL',
                strategy_name=pos.strategy_name or 'manual_close'
            )
            
            session.add(trade)
            session.delete(pos)
            
            print(f"✓ Closed {pos.symbol} {pos.strike_price} {pos.instrument_type} - P&L: ₹{net_pnl:.2f}")
        
        session.commit()
        print(f"\n✅ Successfully closed {len(positions)} positions")
        print(f"Timestamp: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    print("=" * 80)
    print("Emergency Position Closure Tool")
    print("=" * 80)
    print()
    
    close_positions_in_db()
