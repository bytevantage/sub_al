"""
Quick Strategy Performance Analysis
Direct Python execution without Jupyter
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

print("="*100)
print("COMPREHENSIVE STRATEGY PERFORMANCE AUTOPSY - 2024-2025")
print("="*100)

# Load data
print("\nLoading trades data...")
df = pd.read_csv('/tmp/trades_analysis.csv', names=[
    'trade_id', 'symbol', 'strategy', 'strike', 'instrument_type',
    'entry_time', 'exit_time', 'entry_price', 'exit_price', 'quantity',
    'net_pnl', 'pnl_pct', 'status', 'hold_minutes', 'entry_hour', 'day_of_week', 'trade_date'
])

df['entry_time'] = pd.to_datetime(df['entry_time'])
df['exit_time'] = pd.to_datetime(df['exit_time'])

print(f"✓ Loaded {len(df)} trades")
print(f"  Period: {df['entry_time'].min()} to {df['exit_time'].max()}")
print(f"  Total P&L: ₹{df['net_pnl'].sum():,.2f}")

# ==================================================================================
# 1. OVERALL METRICS
# ==================================================================================
print("\n" + "="*100)
print("1. OVERALL PERFORMANCE")
print("="*100)

total_pnl = df['net_pnl'].sum()
total_trades = len(df)
winning_trades = len(df[df['net_pnl'] > 0])
losing_trades = len(df[df['net_pnl'] < 0])
win_rate = winning_trades / total_trades * 100

avg_win = df[df['net_pnl'] > 0]['net_pnl'].mean()
avg_loss = df[df['net_pnl'] < 0]['net_pnl'].mean()
profit_factor = abs(df[df['net_pnl'] > 0]['net_pnl'].sum() / df[df['net_pnl'] < 0]['net_pnl'].sum())

print(f"Total Trades: {total_trades}")
print(f"Winning Trades: {winning_trades} ({win_rate:.1f}%)")
print(f"Losing Trades: {losing_trades}")
print(f"Total P&L: ₹{total_pnl:,.2f}")
print(f"Average Win: ₹{avg_win:.2f}")
print(f"Average Loss: ₹{avg_loss:.2f}")
print(f"Profit Factor: {profit_factor:.2f}")
print(f"Avg Hold Time: {df['hold_minutes'].mean():.1f} minutes")

# ==================================================================================
# 2. PERFORMANCE BY STRATEGY
# ==================================================================================
print("\n" + "="*100)
print("2. PERFORMANCE BY STRATEGY")
print("="*100)

def calculate_strategy_metrics(group):
    total_pnl = group['net_pnl'].sum()
    num_trades = len(group)
    wins = len(group[group['net_pnl'] > 0])
    losses = len(group[group['net_pnl'] < 0])
    win_rate = wins / num_trades * 100 if num_trades > 0 else 0
    
    avg_win = group[group['net_pnl'] > 0]['net_pnl'].mean() if wins > 0 else 0
    avg_loss = group[group['net_pnl'] < 0]['net_pnl'].mean() if losses > 0 else 0
    
    total_wins = group[group['net_pnl'] > 0]['net_pnl'].sum()
    total_losses = abs(group[group['net_pnl'] < 0]['net_pnl'].sum())
    profit_factor = total_wins / total_losses if total_losses > 0 else np.inf
    
    avg_hold = group['hold_minutes'].mean()
    
    # Consecutive wins/losses
    pnl_signs = (group['net_pnl'] > 0).astype(int).values
    max_consec_wins = 0
    max_consec_losses = 0
    current_wins = 0
    current_losses = 0
    
    for is_win in pnl_signs:
        if is_win:
            current_wins += 1
            current_losses = 0
            max_consec_wins = max(max_consec_wins, current_wins)
        else:
            current_losses += 1
            current_wins = 0
            max_consec_losses = max(max_consec_losses, current_losses)
    
    # Sortino ratio
    returns = group['net_pnl'] / 10000
    downside_returns = returns[returns < 0]
    downside_std = downside_returns.std() if len(downside_returns) > 0 else 1
    sortino = returns.mean() / downside_std * np.sqrt(252) if downside_std > 0 else 0
    
    return pd.Series({
        'Total_PnL': total_pnl,
        'Num_Trades': num_trades,
        'Wins': wins,
        'Losses': losses,
        'Win_Rate_%': win_rate,
        'Avg_Win': avg_win,
        'Avg_Loss': avg_loss,
        'Profit_Factor': profit_factor,
        'Avg_Hold_Min': avg_hold,
        'Max_Consec_Wins': max_consec_wins,
        'Max_Consec_Losses': max_consec_losses,
        'Sortino_Ratio': sortino
    })

strategy_metrics = df.groupby('strategy').apply(calculate_strategy_metrics).reset_index()
strategy_metrics = strategy_metrics.sort_values('Sortino_Ratio', ascending=False)

pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.float_format', '{:.2f}'.format)

print(strategy_metrics.to_string(index=False))

# ==================================================================================
# 3. P&L BY TIME OF DAY
# ==================================================================================
print("\n" + "="*100)
print("3. P&L BY TIME OF DAY")
print("="*100)

def time_bucket(hour):
    if 9 <= hour < 10:
        return '09:15-10:00'
    elif 10 <= hour < 12:
        return '10:00-12:00'
    elif 12 <= hour < 14:
        return '12:00-14:00'
    elif 14 <= hour < 16:
        return '14:00-15:30'
    else:
        return 'Other'

df['time_bucket'] = df['entry_hour'].apply(time_bucket)

for strategy in sorted(df['strategy'].unique()):
    print(f"\n{strategy}:")
    time_pnl = df[df['strategy'] == strategy].groupby('time_bucket')['net_pnl'].agg([
        ('Total_PnL', 'sum'),
        ('Num_Trades', 'count'),
        ('Avg_PnL', 'mean')
    ]).reset_index()
    print(time_pnl.to_string(index=False))

# ==================================================================================
# 4. P&L BY DAY OF WEEK
# ==================================================================================
print("\n" + "="*100)
print("4. P&L BY DAY OF WEEK")
print("="*100)

day_names = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
df['day_name'] = df['day_of_week'].map(day_names)

for strategy in sorted(df['strategy'].unique()):
    print(f"\n{strategy}:")
    day_pnl = df[df['strategy'] == strategy].groupby('day_name')['net_pnl'].agg([
        ('Total_PnL', 'sum'),
        ('Num_Trades', 'count'),
        ('Avg_PnL', 'mean')
    ]).reset_index()
    print(day_pnl.to_string(index=False))

# ==================================================================================
# 5. EXPIRY vs NON-EXPIRY
# ==================================================================================
print("\n" + "="*100)
print("5. EXPIRY vs NON-EXPIRY DAYS")
print("="*100)

df['is_expiry'] = df['day_of_week'] == 3  # Thursday

for strategy in sorted(df['strategy'].unique()):
    print(f"\n{strategy}:")
    expiry_pnl = df[df['strategy'] == strategy].groupby('is_expiry')['net_pnl'].agg([
        ('Total_PnL', 'sum'),
        ('Num_Trades', 'count'),
        ('Avg_PnL', 'mean')
    ]).reset_index()
    expiry_pnl['is_expiry'] = expiry_pnl['is_expiry'].map({True: 'Expiry', False: 'Non-Expiry'})
    print(expiry_pnl.to_string(index=False))

# ==================================================================================
# 6. FINAL RANKINGS & RECOMMENDATIONS
# ==================================================================================
print("\n" + "="*100)
print("6. STRATEGY RANKINGS & RECOMMENDATIONS FOR 2025")
print("="*100)

def recommend(row):
    if row['Sortino_Ratio'] > 1.0 and row['Total_PnL'] > 0 and row['Num_Trades'] >= 10:
        return '✅ KEEP & SCALE'
    elif row['Sortino_Ratio'] > 0 and row['Total_PnL'] > -500:
        return '⚠️  MONITOR'
    elif row['Total_PnL'] < -1000 or row['Win_Rate_%'] < 30:
        return '❌ KILL'
    else:
        return '🔻 REDUCE'

rankings = strategy_metrics[['strategy', 'Total_PnL', 'Win_Rate_%', 'Profit_Factor', 
                             'Sortino_Ratio', 'Num_Trades']].copy()
rankings['Recommendation'] = rankings.apply(recommend, axis=1)

print(rankings.to_string(index=False))

# Summary counts
keep_scale = len(rankings[rankings['Recommendation'] == '✅ KEEP & SCALE'])
monitor = len(rankings[rankings['Recommendation'] == '⚠️  MONITOR'])
reduce = len(rankings[rankings['Recommendation'] == '🔻 REDUCE'])
kill = len(rankings[rankings['Recommendation'] == '❌ KILL'])

print("\n" + "="*100)
print("RECOMMENDATION SUMMARY")
print("="*100)
print(f"✅ Keep & Scale:  {keep_scale} strategies")
print(f"⚠️  Monitor:       {monitor} strategies")
print(f"🔻 Reduce:        {reduce} strategies")
print(f"❌ Kill:          {kill} strategies")

# ==================================================================================
# 7. KEY INSIGHTS
# ==================================================================================
print("\n" + "="*100)
print("7. KEY INSIGHTS & ACTION ITEMS")
print("="*100)

print("\n🔍 CRITICAL FINDINGS:")
print(f"  • Overall P&L is {total_pnl:,.2f} - NEEDS IMMEDIATE ATTENTION")
print(f"  • Win rate at {win_rate:.1f}% - Below 40% threshold")
print(f"  • Profit factor {profit_factor:.2f} - {'Acceptable' if profit_factor > 1.5 else 'Weak'}")

best_strategy = strategy_metrics.iloc[0]['strategy']
best_sortino = strategy_metrics.iloc[0]['Sortino_Ratio']
worst_strategy = strategy_metrics.iloc[-1]['strategy']
worst_pnl = strategy_metrics.iloc[-1]['Total_PnL']

print(f"\n⭐ BEST PERFORMER: {best_strategy} (Sortino: {best_sortino:.2f})")
print(f"💀 WORST PERFORMER: {worst_strategy} (P&L: ₹{worst_pnl:,.2f})")

print("\n📋 IMMEDIATE ACTIONS FOR 2025:")
print("  1. Kill strategies with Sortino < -0.5 and heavy losses")
print("  2. Double allocation to top-performing strategies")
print("  3. Implement stricter entry filters for underperformers")
print("  4. Add time-of-day filters to avoid worst-performing hours")
print("  5. Review expiry day strategies - may need adjustment")

print("\n" + "="*100)
print("✓ ANALYSIS COMPLETE")
print("="*100)
print(f"\n📊 Full report available in: reports/strategy_autopsy_2025.ipynb")
print(f"📄 Run 'python3 generate_strategy_report.py' to generate HTML/PDF")
