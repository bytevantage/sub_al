#!/usr/bin/env python3
"""
Backtest Using API Data
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def get_trades_from_api():
    """Get trades from dashboard API"""
    url = "http://localhost:8000/api/dashboard/trades/recent"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            trades = data.get('data', {}).get('trades', [])
            return trades
        else:
            print(f"API Error: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching trades: {e}")
        return []

def analyze_trades(trades):
    """Analyze trade performance"""
    if not trades:
        print("No trades found")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(trades)
    
    # Convert timestamps
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['exit_time'] = pd.to_datetime(df['exit_time'])
    
    # Calculate metrics
    total_pnl = df['net_pnl'].sum()
    total_trades = len(df)
    winning_trades = len(df[df['net_pnl'] > 0])
    win_rate = (winning_trades / total_trades) * 100
    
    avg_win = df[df['net_pnl'] > 0]['net_pnl'].mean()
    avg_loss = df[df['net_pnl'] < 0]['net_pnl'].mean()
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
    
    # Strategy breakdown
    strategy_summary = df.groupby('strategy_name').agg({
        'net_pnl': ['sum', 'mean', 'count'],
        'pnl_percentage': 'mean'
    }).round(2)
    
    # Daily P&L
    df['date'] = df['entry_time'].dt.date
    daily_pnl = df.groupby('date')['net_pnl'].sum()
    
    # Time analysis
    df['hour'] = df['entry_time'].dt.hour
    hourly_performance = df.groupby('hour')['net_pnl'].agg(['sum', 'count'])
    
    # Option type analysis
    option_performance = df.groupby('instrument_type')['net_pnl'].agg(['sum', 'count'])
    
    # Hold time analysis
    df['hold_duration'] = (df['exit_time'] - df['entry_time']).dt.total_seconds() / 60
    avg_hold_time = df['hold_duration'].mean()
    
    print("=" * 80)
    print("BACKTEST RESULTS (From API Data)")
    print("=" * 80)
    print(f"Total P&L:          ₹{total_pnl:,.2f}")
    print(f"Total Trades:       {total_trades}")
    print(f"Winning Trades:     {winning_trades}")
    print(f"Win Rate:           {win_rate:.2f}%")
    print(f"Average Win:        ₹{avg_win:,.2f}")
    print(f"Average Loss:       ₹{avg_loss:,.2f}")
    print(f"Profit Factor:      {profit_factor:.2f}")
    print(f"Average P&L/Trade:  ₹{total_pnl/total_trades:,.2f}")
    print(f"Average Hold Time:  {avg_hold_time:.1f} minutes")
    
    print("\nStrategy Performance:")
    print("-" * 80)
    for strategy in df['strategy_name'].unique():
        strat_df = df[df['strategy_name'] == strategy]
        strat_pnl = strat_df['net_pnl'].sum()
        strat_trades = len(strat_df)
        strat_win_rate = (strat_df['net_pnl'] > 0).mean() * 100
        print(f"{strategy:25} | Trades: {strat_trades:3} | P&L: ₹{strat_pnl:8,.2f} | Win Rate: {strat_win_rate:5.1f}%")
    
    print("\nTop 10 Most Profitable Trades:")
    print("-" * 80)
    top_trades = df.nlargest(10, 'net_pnl')[['symbol', 'strike_price', 'instrument_type', 'net_pnl', 'strategy_name', 'hold_duration']]
    for i, (_, trade) in enumerate(top_trades.iterrows(), 1):
        print(f"{i:2d}. {trade['symbol']} {trade['strike_price']} {trade['instrument_type']} | "
              f"P&L: ₹{trade['net_pnl']:7,.2f} | Strategy: {trade['strategy_name']:15} | "
              f"Hold: {trade['hold_duration']:3.0f} min")
    
    print("\nBottom 10 Trades (Losses):")
    print("-" * 80)
    bottom_trades = df.nsmallest(10, 'net_pnl')[['symbol', 'strike_price', 'instrument_type', 'net_pnl', 'strategy_name', 'hold_duration']]
    for i, (_, trade) in enumerate(bottom_trades.iterrows(), 1):
        print(f"{i:2d}. {trade['symbol']} {trade['strike_price']} {trade['instrument_type']} | "
              f"P&L: ₹{trade['net_pnl']:7,.2f} | Strategy: {trade['strategy_name']:15} | "
              f"Hold: {trade['hold_duration']:3.0f} min")
    
    print("\nHourly Performance:")
    print("-" * 80)
    for hour in sorted(hourly_performance.index):
        hour_pnl = hourly_performance.loc[hour, 'sum']
        hour_trades = hourly_performance.loc[hour, 'count']
        print(f"{hour:2d}:00-{hour:2d}:59 | P&L: ₹{hour_pnl:7,.2f} | Trades: {hour_trades:3}")
    
    print("\nOption Type Performance:")
    print("-" * 80)
    for opt_type in option_performance.index:
        opt_pnl = option_performance.loc[opt_type, 'sum']
        opt_trades = option_performance.loc[opt_type, 'count']
        print(f"{opt_type:4} | P&L: ₹{opt_pnl:7,.2f} | Trades: {opt_trades:3}")
    
    print("\nDaily P&L (Last 10 days):")
    print("-" * 80)
    for date, pnl in daily_pnl.tail(10).items():
        print(f"{date}: ₹{pnl:,.2f}")
    
    # Calculate what-if scenarios
    print("\nWhat-If Analysis:")
    print("-" * 80)
    
    # If we had a 5% stop loss
    df['potential_sl'] = df['entry_price'] * 0.95
    df['sl_pnl'] = (df['potential_sl'] - df['entry_price']) * df['quantity'] * 50
    sl_total_pnl = df['sl_pnl'].sum()
    print(f"With 5% Stop Loss:   ₹{sl_total_pnl:,.2f} (vs actual: ₹{total_pnl:,.2f})")
    
    # If we took profit at 10%
    df['potential_tp'] = df['entry_price'] * 1.10
    df['tp_pnl'] = (df['potential_tp'] - df['entry_price']) * df['quantity'] * 50
    tp_total_pnl = df['tp_pnl'].sum()
    print(f"With 10% Take Profit: ₹{tp_total_pnl:,.2f} (vs actual: ₹{total_pnl:,.2f})")
    
    # If we held only 2 hours max
    df['max_hold_pnl'] = df[df['hold_duration'] <= 120]['net_pnl'].sum()
    print(f"With 2hr Max Hold:   ₹{df['max_hold_pnl']:,.2f} (vs actual: ₹{total_pnl:,.2f})")
    
    # Simulate ML-based exits
    print("\nML-Based Exit Simulation:")
    print("-" * 80)
    
    # Exit at 15% profit or after 2 hours
    df['ml_exit_pnl'] = df.apply(lambda row: 
        min(row['net_pnl'], row['entry_price'] * 0.15 * row['quantity'] * 50) 
        if row['hold_duration'] > 120 else row['net_pnl'], axis=1)
    ml_total_pnl = df['ml_exit_pnl'].sum()
    print(f"With ML Exits:       ₹{ml_total_pnl:,.2f} (vs actual: ₹{total_pnl:,.2f})")
    
    # Volatility harvesting simulation
    print("\nVolatility Harvesting Simulation:")
    print("-" * 80)
    
    # Sell options when IV > 25%
    high_iv_trades = df[df['entry_price'] > 150]  # Approximate high IV filter
    if not high_iv_trades.empty:
        harvest_pnl = high_iv_trades['net_pnl'].sum()
        print(f"High IV Trades P&L: ₹{harvest_pnl:,.2f} from {len(high_iv_trades)} trades")
    
    # Save results
    results = {
        'summary': {
            'total_pnl': float(total_pnl),
            'total_trades': int(total_trades),
            'win_rate': float(win_rate),
            'avg_win': float(avg_win),
            'avg_loss': float(avg_loss),
            'profit_factor': float(profit_factor),
            'avg_hold_time': float(avg_hold_time)
        },
        'strategy_performance': strategy_summary.to_dict(),
        'what_if': {
            'stop_loss_5pct': float(sl_total_pnl),
            'take_profit_10pct': float(tp_total_pnl),
            'max_hold_2hr': float(df['max_hold_pnl']),
            'ml_exits': float(ml_total_pnl)
        }
    }
    
    import json
    with open('api_backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: api_backtest_results.json")
    
    return results

def main():
    """Main execution"""
    print("Fetching trades from API...")
    trades = get_trades_from_api()
    
    if trades:
        print(f"Found {len(trades)} trades")
        analyze_trades(trades)
    else:
        print("No trades found or API not accessible")
        print("Make sure the backend is running: ./start.sh")

if __name__ == "__main__":
    main()
