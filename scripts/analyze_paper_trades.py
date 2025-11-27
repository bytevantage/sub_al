#!/usr/bin/env python3
"""
Performance Autopsy from Paper Trading Data
November 20, 2025
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# Load paper trading data
paper_file = Path(__file__).parent.parent / "frontend/dashboard/paper_trading_status.json"

print("="*80)
print("🔍 PERFORMANCE AUTOPSY - PAPER TRADING DATA")
print("="*80)
print()

try:
    with open(paper_file, 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"❌ Paper trading file not found: {paper_file}")
    print("   No trading data available yet.")
    exit(0)
except json.JSONDecodeError:
    print(f"❌ Invalid JSON in paper trading file")
    exit(1)

# Extract data
open_positions = data.get('open_positions', [])
closed_trades = data.get('closed_trades', [])
capital = data.get('capital', 5000000)
available_cash = data.get('available_cash', capital)
total_pnl = data.get('total_pnl', 0)

print(f"📊 CURRENT STATUS")
print(f"  Capital: ₹{capital:,.2f}")
print(f"  Available Cash: ₹{available_cash:,.2f}")
print(f"  Total P&L: ₹{total_pnl:,.2f}")
print(f"  Open Positions: {len(open_positions)}")
print(f"  Closed Trades: {len(closed_trades)}")
print()

if len(closed_trades) == 0:
    print("⚠️  No closed trades yet. System is actively trading.")
    print()
    
    if len(open_positions) > 0:
        print("📈 CURRENT OPEN POSITIONS")
        print("-" * 80)
        
        # Convert to DataFrame for analysis
        positions_df = pd.DataFrame(open_positions)
        
        # Strategy breakdown
        if 'strategy_name' in positions_df.columns:
            print()
            print("Positions by Strategy:")
            strategy_counts = positions_df['strategy_name'].value_counts()
            for strategy, count in strategy_counts.items():
                strategy_positions = positions_df[positions_df['strategy_name'] == strategy]
                total_unrealized = strategy_positions['unrealized_pnl'].sum() if 'unrealized_pnl' in strategy_positions else 0
                print(f"  {strategy}: {count} positions, Unrealized P&L: ₹{total_unrealized:,.2f}")
        
        print()
        print("Top 5 Positions by Unrealized P&L:")
        if 'unrealized_pnl' in positions_df.columns:
            top_positions = positions_df.nlargest(5, 'unrealized_pnl')[['symbol', 'strike_price', 'instrument_type', 'strategy_name', 'unrealized_pnl']]
            print(top_positions.to_string(index=False))
        
    exit(0)

# Analyze closed trades
print("="*80)
print("📊 CLOSED TRADES ANALYSIS")
print("="*80)
print()

# Convert to DataFrame
trades_df = pd.DataFrame(closed_trades)

# Calculate metrics
if 'pnl' not in trades_df.columns:
    print("❌ No P&L data in closed trades")
    exit(1)

# Parse timestamps
if 'entry_time' in trades_df.columns:
    trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
    trades_df['hour'] = trades_df['entry_time'].dt.hour
    trades_df['day_of_week'] = trades_df['entry_time'].dt.day_name()
    trades_df['date'] = trades_df['entry_time'].dt.date

if 'exit_time' in trades_df.columns:
    trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])
    if 'entry_time' in trades_df.columns:
        trades_df['hold_duration_min'] = (trades_df['exit_time'] - trades_df['entry_time']).dt.total_seconds() / 60

# Overall Performance
total_pnl = trades_df['pnl'].sum()
num_trades = len(trades_df)
wins = len(trades_df[trades_df['pnl'] > 0])
losses = len(trades_df[trades_df['pnl'] <= 0])
win_rate = (wins / num_trades * 100) if num_trades > 0 else 0

print("🎯 OVERALL PERFORMANCE")
print("-" * 80)
print(f"Total P&L: ₹{total_pnl:,.2f}")
print(f"Total Trades: {num_trades}")
print(f"Win Rate: {win_rate:.1f}% ({wins}W / {losses}L)")
print(f"Avg P&L per trade: ₹{trades_df['pnl'].mean():.2f}")
print(f"Best trade: ₹{trades_df['pnl'].max():.2f}")
print(f"Worst trade: ₹{trades_df['pnl'].min():.2f}")

if 'hold_duration_min' in trades_df.columns:
    print(f"Avg hold duration: {trades_df['hold_duration_min'].mean():.1f} minutes")

# Profit Factor
if wins > 0 and losses > 0:
    avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean()
    avg_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].mean())
    profit_factor = (avg_win * wins) / (avg_loss * losses) if (avg_loss * losses) > 0 else 0
    print(f"Avg Win: ₹{avg_win:.2f} | Avg Loss: ₹{avg_loss:.2f}")
    print(f"Profit Factor: {profit_factor:.2f}")

# Strategy Performance
if 'strategy_name' in trades_df.columns:
    print()
    print("="*80)
    print("📈 PERFORMANCE BY STRATEGY")
    print("="*80)
    
    for strategy in sorted(trades_df['strategy_name'].unique()):
        strat_df = trades_df[trades_df['strategy_name'] == strategy]
        
        strat_pnl = strat_df['pnl'].sum()
        strat_trades = len(strat_df)
        strat_wins = len(strat_df[strat_df['pnl'] > 0])
        strat_losses = len(strat_df[strat_df['pnl'] <= 0])
        strat_win_rate = (strat_wins / strat_trades * 100) if strat_trades > 0 else 0
        
        # Verdict
        if strat_pnl > 0:
            verdict = "✅ PROFITABLE"
        elif strat_pnl < -1000:
            verdict = "🔴 BLEEDING"
        else:
            verdict = "⚠️  MARGINAL"
        
        print(f"\n{strategy} {verdict}")
        print(f"  Total P&L: ₹{strat_pnl:,.2f}")
        print(f"  Trades: {strat_trades} ({strat_wins}W / {strat_losses}L)")
        print(f"  Win Rate: {strat_win_rate:.1f}%")
        
        if strat_wins > 0 and strat_losses > 0:
            strat_avg_win = strat_df[strat_df['pnl'] > 0]['pnl'].mean()
            strat_avg_loss = abs(strat_df[strat_df['pnl'] < 0]['pnl'].mean())
            strat_pf = (strat_avg_win * strat_wins) / (strat_avg_loss * strat_losses)
            print(f"  Avg Win: ₹{strat_avg_win:.2f} | Avg Loss: ₹{strat_avg_loss:.2f}")
            print(f"  Profit Factor: {strat_pf:.2f}")

# Time-based analysis
if 'hour' in trades_df.columns:
    print()
    print("="*80)
    print("⏰ PERFORMANCE BY TIME OF DAY")
    print("="*80)
    
    hourly_pnl = trades_df.groupby('hour')['pnl'].agg(['sum', 'count', 'mean'])
    hourly_pnl['win_rate'] = trades_df.groupby('hour').apply(
        lambda x: (len(x[x['pnl'] > 0]) / len(x) * 100) if len(x) > 0 else 0
    )
    
    for hour in sorted(hourly_pnl.index):
        row = hourly_pnl.loc[hour]
        print(f"{hour:02d}:00 - P&L: ₹{row['sum']:>8,.2f} | {int(row['count'])} trades | Win Rate: {row['win_rate']:.1f}% | Avg: ₹{row['mean']:.2f}")

print()
print("="*80)
print("✅ Analysis Complete")
print("="*80)
