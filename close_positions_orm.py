#!/usr/bin/env python3
"""
Close positions using backend ORM
Works with any database (PostgreSQL, SQLite, etc.)
"""

import sys
import os

# Add backend to path
sys.path.insert(0, '/Users/srbhandary/Documents/Projects/srb-algo')

# Suppress config validation error
os.environ['SUPPRESS_CONFIG_VALIDATION'] = 'true'

def close_positions():
    """Close all open positions using backend ORM"""
    try:
        from datetime import datetime
        from backend.core.timezone_utils import now_ist, to_naive_ist
        from backend.database.database import db
        from backend.database.models import Position, Trade
        
        print("=" * 80)
        print("Closing Open Positions (ORM Method)")
        print("=" * 80)
        print()
        
        # Get database session
        session = db.get_session()
        if not session:
            print("❌ Could not connect to database")
            print()
            print("Try alternative method:")
            print("  1. Ensure backend is running: ./start.sh")
            print("  2. Use API method: bash close_via_api.sh")
            return
        
        try:
            # Get all open positions
            positions = session.query(Position).all()
            
            if not positions:
                print("✅ No open positions found")
                return
            
            print(f"Found {len(positions)} open position(s):")
            print("=" * 80)
            
            total_pnl = 0
            for pos in positions:
                print(f"Position: {pos.symbol} {pos.strike_price} {pos.instrument_type}")
                print(f"  Entry: ₹{pos.entry_price:.2f}")
                print(f"  Current: ₹{pos.current_price:.2f}")
                print(f"  Unrealized P&L: ₹{pos.unrealized_pnl:.2f}")
                print(f"  Strategy: {pos.strategy_name}")
                total_pnl += pos.unrealized_pnl or 0
                print()
            
            print(f"Total Unrealized P&L: ₹{total_pnl:.2f}")
            print()
            
            # Confirm closure
            response = input("Close all these positions? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted.")
                return
            
            print("\nClosing positions...")
            now = now_ist()
            now_naive = to_naive_ist(now)
            
            closed_count = 0
            
            for pos in positions:
                # Use current price as exit price, fallback to entry price
                exit_price = pos.current_price if pos.current_price and pos.current_price > 0 else pos.entry_price
                
                # Calculate P&L
                if pos.direction == 'BUY':
                    gross_pnl = (exit_price - pos.entry_price) * pos.quantity
                else:
                    gross_pnl = (pos.entry_price - exit_price) * pos.quantity
                
                # Estimate fees (0.06% of total value)
                fees = (pos.entry_price + exit_price) * pos.quantity * 0.0006
                net_pnl = gross_pnl - fees
                pnl_pct = (net_pnl / (pos.entry_price * pos.quantity)) * 100 if pos.entry_price * pos.quantity > 0 else 0
                
                # Calculate hold duration in minutes
                hold_duration = 0
                if pos.entry_time:
                    try:
                        entry_naive = pos.entry_time.replace(tzinfo=None) if pos.entry_time.tzinfo else pos.entry_time
                        hold_duration = (now_naive - entry_naive).total_seconds() / 60
                    except:
                        hold_duration = 0
                
                # Create trade record
                trade = Trade(
                    trade_id=pos.position_id,
                    symbol=pos.symbol,
                    instrument_type=pos.instrument_type,
                    strike_price=pos.strike_price,
                    expiry_date=pos.expiry,
                    entry_time=pos.entry_time,
                    exit_time=now_naive,
                    entry_price=pos.entry_price,
                    exit_price=exit_price,
                    quantity=pos.quantity,
                    entry_mode='PAPER',  # Assuming paper mode
                    exit_type='MANUAL',
                    gross_pnl=gross_pnl,
                    brokerage=0.0,
                    taxes=fees,
                    net_pnl=net_pnl,
                    pnl_percentage=pnl_pct,
                    strategy_name=pos.strategy_name or 'manual_close',
                    signal_strength=pos.signal_strength,
                    ml_score=pos.ml_score,
                    delta_entry=pos.delta_entry,
                    gamma_entry=pos.gamma_entry,
                    theta_entry=pos.theta_entry,
                    vega_entry=pos.vega_entry,
                    hold_duration=int(hold_duration)
                )
                
                session.add(trade)
                session.delete(pos)
                closed_count += 1
                
                print(f"✓ Closed {pos.symbol} {pos.strike_price} {pos.instrument_type} - P&L: ₹{net_pnl:.2f}")
            
            session.commit()
            print(f"\n✅ Successfully closed {closed_count} position(s)")
            print(f"Timestamp: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            session.rollback()
        finally:
            session.close()
            
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print()
        print("Alternative methods:")
        print("  1. Ensure backend is running: ./start.sh")
        print("  2. Use API method: bash close_via_api.sh")
        return
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    close_positions()
