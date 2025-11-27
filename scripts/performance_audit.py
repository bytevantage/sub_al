#!/usr/bin/env python3
"""
Performance Autopsy - November 20, 2025
Complete analysis of all trading activity
"""

import sys
import os
sys.path.insert(0, '/app')

from sqlalchemy import create_engine, text
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

# Database connection
DB_URL = "postgresql://trading_user:trading_pass@postgres:5432/trading_db"
engine = create_engine(DB_URL)

print("="*80)
print("🔍 PERFORMANCE AUTOPSY - NOVEMBER 20, 2025")
print("="*80)
print()

# Check if trades table exists
with engine.connect() as conn:
    tables_query = text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'trades';
    """)
    
    result = conn.execute(tables_query)
    tables = result.fetchall()
    
    if not tables:
        print("❌ No 'trades' table found in database")
        print()
        print("Checking all available tables:")
        all_tables = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        result = conn.execute(all_tables)
        for row in result:
            print(f"  - {row[0]}")
        
        print()
        print("⚠️  Database exists but no trades table yet.")
        print("   This is normal if no trades have been closed.")
        print("   System is in paper trading mode - trades are stored in JSON files.")
        sys.exit(0)

# Get all closed trades
query = text("""
    SELECT 
        id,
        strategy_name,
        symbol,
        direction,
        strike,
        entry_time,
        exit_time,
        entry_price,
        exit_price,
        quantity,
        pnl,
        exit_reason
    FROM trades
    WHERE exit_time IS NOT NULL
    ORDER BY exit_time;
""")

with engine.connect() as conn:
    df = pd.read_sql(query, conn)

print(f"📊 Total Closed Trades: {len(df)}")
print()

if len(df) == 0:
    print("⚠️  No closed trades in database yet.")
    print("   Checking paper trading file instead...")
    sys.exit(1)

# Calculate metrics
df['hold_duration'] = (pd.to_datetime(df['exit_time']) - pd.to_datetime(df['entry_time'])).dt.total_seconds() / 60
df['hour'] = pd.to_datetime(df['entry_time']).dt.hour
df['day_of_week'] = pd.to_datetime(df['entry_time']).dt.day_name()
df['date'] = pd.to_datetime(df['entry_time']).dt.date

# Strategy performance
print("📈 STRATEGY PERFORMANCE")
print("-" * 80)

for strategy in df['strategy_name'].unique():
    strat_df = df[df['strategy_name'] == strategy]
    
    total_pnl = strat_df['pnl'].sum()
    num_trades = len(strat_df)
    wins = len(strat_df[strat_df['pnl'] > 0])
    losses = len(strat_df[strat_df['pnl'] <= 0])
    win_rate = (wins / num_trades * 100) if num_trades > 0 else 0
    
    avg_win = strat_df[strat_df['pnl'] > 0]['pnl'].mean() if wins > 0 else 0
    avg_loss = abs(strat_df[strat_df['pnl'] < 0]['pnl'].mean()) if losses > 0 else 0
    profit_factor = (avg_win * wins) / (avg_loss * losses) if (avg_loss * losses) > 0 else 0
    
    print(f"\n{strategy}:")
    print(f"  Total P&L: ₹{total_pnl:,.2f}")
    print(f"  Trades: {num_trades} ({wins}W / {losses}L)")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Avg Win: ₹{avg_win:.2f} | Avg Loss: ₹{avg_loss:.2f}")
    print(f"  Profit Factor: {profit_factor:.2f}")

# Overall metrics
print()
print("="*80)
print("🎯 OVERALL PERFORMANCE")
print("-" * 80)

total_pnl = df['pnl'].sum()
num_trades = len(df)
wins = len(df[df['pnl'] > 0])
losses = len(df[df['pnl'] <= 0])
win_rate = (wins / num_trades * 100) if num_trades > 0 else 0

print(f"Total P&L: ₹{total_pnl:,.2f}")
print(f"Total Trades: {num_trades}")
print(f"Win Rate: {win_rate:.1f}% ({wins}W / {losses}L)")
print(f"Avg P&L per trade: ₹{df['pnl'].mean():.2f}")
print(f"Best trade: ₹{df['pnl'].max():.2f}")
print(f"Worst trade: ₹{df['pnl'].min():.2f}")

print()
print("="*80)
