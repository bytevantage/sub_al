#!/usr/bin/env python3
"""
Simple Backtest Using Available Data
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database.database import db
from backend.database.models import Trade
from backend.core.logger import get_logger

logger = get_logger(__name__)

def run_backtest_from_trades():
    """Run backtest analysis from actual trade data"""
    session = db.get_session()
    
    try:
        # Get trades from last 30 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        trades = session.query(Trade).filter(
            Trade.entry_time >= start_date,
            Trade.entry_time <= end_date,
            Trade.status == 'CLOSED'
        ).all()
        
        if not trades:
            print("No trades found in the last 30 days")
            return
        
        # Convert to DataFrame
        trade_data = []
        for trade in trades:
            trade_data.append({
                'trade_id': trade.trade_id,
                'symbol': trade.symbol,
                'strike': trade.strike_price,
                'option_type': trade.instrument_type,
                'entry_time': trade.entry_time,
                'exit_time': trade.exit_time,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'quantity': trade.quantity,
                'pnl': trade.net_pnl,
                'pnl_pct': trade.pnl_percentage,
                'strategy': trade.strategy_name,
                'hold_duration': trade.hold_duration_minutes
            })
        
        df = pd.DataFrame(trade_data)
        
        # Calculate metrics
        total_pnl = df['pnl'].sum()
        total_trades = len(df)
        winning_trades = len(df[df['pnl'] > 0])
        win_rate = (winning_trades / total_trades) * 100
        
        avg_win = df[df['pnl'] > 0]['pnl'].mean()
        avg_loss = df[df['pnl'] < 0]['pnl'].mean()
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        
        # Strategy breakdown
        strategy_summary = df.groupby('strategy').agg({
            'pnl': ['sum', 'mean', 'count'],
            'pnl_pct': 'mean'
        }).round(2)
        
        # Daily P&L
        df['date'] = pd.to_datetime(df['entry_time']).dt.date
        daily_pnl = df.groupby('date')['pnl'].sum()
        
        # Time analysis
        df['hour'] = pd.to_datetime(df['entry_time']).dt.hour
        hourly_performance = df.groupby('hour')['pnl'].agg(['sum', 'count'])
        
        # Option type analysis
        option_performance = df.groupby('option_type')['pnl'].agg(['sum', 'count'])
        
        print("=" * 80)
        print("BACKTEST RESULTS (Last 30 Days)")
        print("=" * 80)
        print(f"Total P&L:          ₹{total_pnl:,.2f}")
        print(f"Total Trades:       {total_trades}")
        print(f"Winning Trades:     {winning_trades}")
        print(f"Win Rate:           {win_rate:.2f}%")
        print(f"Average Win:        ₹{avg_win:,.2f}")
        print(f"Average Loss:       ₹{avg_loss:,.2f}")
        print(f"Profit Factor:      {profit_factor:.2f}")
        print(f"Average P&L/Trade:  ₹{total_pnl/total_trades:,.2f}")
        
        print("\nStrategy Performance:")
        print("-" * 80)
        for strategy in df['strategy'].unique():
            strat_df = df[df['strategy'] == strategy]
            strat_pnl = strat_df['pnl'].sum()
            strat_trades = len(strat_df)
            strat_win_rate = (strat_df['pnl'] > 0).mean() * 100
            print(f"{strategy:25} | Trades: {strat_trades:3} | P&L: ₹{strat_pnl:8,.2f} | Win Rate: {strat_win_rate:5.1f}%")
        
        print("\nTop 10 Most Profitable Trades:")
        print("-" * 80)
        top_trades = df.nlargest(10, 'pnl')[['symbol', 'strike', 'option_type', 'pnl', 'strategy', 'hold_duration']]
        for i, (_, trade) in enumerate(top_trades.iterrows(), 1):
            print(f"{i:2d}. {trade['symbol']} {trade['strike']} {trade['option_type']} | "
                  f"P&L: ₹{trade['pnl']:7,.2f} | Strategy: {trade['strategy']:15} | "
                  f"Hold: {trade['hold_duration']:3.0f} min")
        
        print("\nBottom 10 Trades (Losses):")
        print("-" * 80)
        bottom_trades = df.nsmallest(10, 'pnl')[['symbol', 'strike', 'option_type', 'pnl', 'strategy', 'hold_duration']]
        for i, (_, trade) in enumerate(bottom_trades.iterrows(), 1):
            print(f"{i:2d}. {trade['symbol']} {trade['strike']} {trade['option_type']} | "
                  f"P&L: ₹{trade['pnl']:7,.2f} | Strategy: {trade['strategy']:15} | "
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
        df['max_hold_pnl'] = df[df['hold_duration'] <= 120]['pnl'].sum()
        print(f"With 2hr Max Hold:   ₹{df['max_hold_pnl']:,.2f} (vs actual: ₹{total_pnl:,.2f})")
        
        # Save results
        results = {
            'summary': {
                'total_pnl': float(total_pnl),
                'total_trades': int(total_trades),
                'win_rate': float(win_rate),
                'avg_win': float(avg_win),
                'avg_loss': float(avg_loss),
                'profit_factor': float(profit_factor)
            },
            'strategy_performance': strategy_summary.to_dict(),
            'what_if': {
                'stop_loss_5pct': float(sl_total_pnl),
                'take_profit_10pct': float(tp_total_pnl),
                'max_hold_2hr': float(df['max_hold_pnl'])
            }
        }
        
        import json
        with open('backtest_analysis.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\nDetailed results saved to: backtest_analysis.json")
        
    except Exception as e:
        logger.error(f"Error running backtest: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    run_backtest_from_trades()
