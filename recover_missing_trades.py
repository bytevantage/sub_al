#!/usr/bin/env python3
"""
Manually add missing trades from today that failed to save due to numpy error
"""

import sys
import os
sys.path.append('/Users/srbhandary/Documents/Projects/srb-algo')

from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

def add_missing_trades():
    """Add the 3 missing trades from 2025-12-02"""
    
    # Direct PostgreSQL connection using same defaults as backend
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="trading_db",
        user="trading_user",
        password="trading_pass"
    )
    cursor = conn.cursor()
    
    try:
        # Trade 1: SENSEX 85300 PUT - Small profit
        cursor.execute("""
            INSERT INTO trades (
                trade_id, symbol, instrument_type, strike_price, entry_price, exit_price,
                quantity, entry_mode, entry_time, exit_time, exit_type, signal_strength,
                strategy_name, signal_reason, exit_reason, gross_pnl, net_pnl, pnl_percentage,
                is_winning_trade, hold_duration_minutes
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            "manual_recover_1", "SENSEX", "PUT", 85300.0, 248.39, 248.40, 20, "PAPER",
            "2025-12-02 10:57:00", "2025-12-02 10:57:02", "TARGET", 80.0, "sac_0",
            "Manual recovery - numpy error", "TARGET", 1.00, 1.00, 0.02, True, 0
        ))
        
        # Trade 2: NIFTY 26100 PUT - Stop loss
        cursor.execute("""
            INSERT INTO trades (
                trade_id, symbol, instrument_type, strike_price, entry_price, exit_price,
                quantity, entry_mode, entry_time, exit_time, exit_type, signal_strength,
                strategy_name, signal_reason, exit_reason, gross_pnl, net_pnl, pnl_percentage,
                is_winning_trade, hold_duration_minutes
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            "manual_recover_2", "NIFTY", "PUT", 26100.0, 46.40, 37.90, 75, "PAPER",
            "2025-12-02 11:00:00", "2025-12-02 11:00:09", "STOP_LOSS_HIT", 80.0, "sac_0",
            "Manual recovery - numpy error", "STOP_LOSS_HIT", -750.00, -750.00, -21.77, False, 0
        ))
        
        # Trade 3: NIFTY 26100 CALL - Stop loss
        cursor.execute("""
            INSERT INTO trades (
                trade_id, symbol, instrument_type, strike_price, entry_price, exit_price,
                quantity, entry_mode, entry_time, exit_time, exit_type, signal_strength,
                strategy_name, signal_reason, exit_reason, gross_pnl, net_pnl, pnl_percentage,
                is_winning_trade, hold_duration_minutes
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            "manual_recover_3", "NIFTY", "CALL", 26100.0, 50.70, 35.70, 75, "PAPER",
            "2025-12-02 11:14:00", "2025-12-02 11:14:05", "STOP_LOSS_HIT", 80.0, "sac_0",
            "Manual recovery - numpy error", "STOP_LOSS_HIT", -1125.00, -1125.00, -29.60, False, 0
        ))
        
        conn.commit()
        print("✅ Successfully added 3 missing trades to database")
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM trades WHERE entry_time >= '2025-12-02'")
        trades_today = cursor.fetchone()[0]
        print(f"✅ Total trades today: {trades_today}")
        
    except Exception as e:
        print(f"❌ Error adding trades: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    add_missing_trades()
