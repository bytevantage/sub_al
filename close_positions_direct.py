#!/usr/bin/env python3
"""
Direct database script to close open positions
Bypasses backend config issues
"""

import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
import json

IST = ZoneInfo("Asia/Kolkata")

# Database path
DB_PATH = "/Users/srbhandary/Documents/Projects/srb-algo/data/trading.db"

def close_positions():
    """Close all open positions directly in database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get all open positions
        cursor.execute("""
            SELECT position_id, symbol, instrument_type, strike_price, expiry,
                   entry_time, entry_price, current_price, quantity, direction,
                   strategy_name, unrealized_pnl
            FROM positions 
            WHERE status = 'OPEN'
        """)
        
        positions = cursor.fetchall()
        
        if not positions:
            print("✅ No open positions found")
            return
        
        print(f"Found {len(positions)} open positions:")
        print("=" * 80)
        
        for pos in positions:
            position_id, symbol, instrument_type, strike, expiry, entry_time, \
            entry_price, current_price, quantity, direction, strategy_name, unrealized_pnl = pos
            
            print(f"Position: {symbol} {strike} {instrument_type}")
            print(f"  Entry: ₹{entry_price:.2f}")
            print(f"  Current: ₹{current_price:.2f}")
            print(f"  Unrealized P&L: ₹{unrealized_pnl:.2f}")
            print()
        
        # Confirm closure
        response = input("Close all these positions? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
        
        print("\nClosing positions...")
        now = datetime.now(IST)
        now_naive = now.replace(tzinfo=None)
        
        for pos in positions:
            position_id, symbol, instrument_type, strike, expiry, entry_time, \
            entry_price, current_price, quantity, direction, strategy_name, unrealized_pnl = pos
            
            # Use current price as exit price
            exit_price = current_price if current_price and current_price > 0 else entry_price
            
            # Calculate P&L
            if direction == 'BUY':
                gross_pnl = (exit_price - entry_price) * quantity
            else:
                gross_pnl = (entry_price - exit_price) * quantity
            
            # Estimate fees
            fees = (entry_price + exit_price) * quantity * 0.0006
            net_pnl = gross_pnl - fees
            pnl_pct = (net_pnl / (entry_price * quantity)) * 100 if entry_price * quantity > 0 else 0
            
            # Calculate hold duration
            try:
                entry_dt = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                hold_duration = (now_naive - entry_dt).total_seconds() / 60
            except:
                hold_duration = 0
            
            # Insert trade record
            cursor.execute("""
                INSERT INTO trades (
                    trade_id, symbol, instrument_type, strike_price, expiry,
                    entry_time, exit_time, entry_price, exit_price, quantity, direction,
                    gross_pnl, fees, net_pnl, pnl_percentage,
                    status, exit_reason, strategy_name, hold_duration_minutes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position_id, symbol, instrument_type, strike, expiry,
                entry_time, now_naive, entry_price, exit_price, quantity, direction,
                gross_pnl, fees, net_pnl, pnl_pct,
                'CLOSED', 'MANUAL', strategy_name or 'manual_close', hold_duration
            ))
            
            # Delete position
            cursor.execute("DELETE FROM positions WHERE position_id = ?", (position_id,))
            
            print(f"✓ Closed {symbol} {strike} {instrument_type} - P&L: ₹{net_pnl:.2f}")
        
        conn.commit()
        print(f"\n✅ Successfully closed {len(positions)} positions")
        print(f"Timestamp: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 80)
    print("Direct Database Position Closure Tool")
    print("=" * 80)
    print()
    
    close_positions()
