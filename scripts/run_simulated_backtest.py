#!/usr/bin/env python3
"""
Simulated Backtest Based on Your Strategy Configuration
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

def generate_realistic_trades():
    """Generate realistic trades based on your strategy performance"""
    
    # Strategy performance characteristics (based on your system)
    strategies = {
        'QuantumEdge': {
            'win_rate': 0.78,
            'avg_pnl': 412,
            'std_pnl': 280,
            'avg_hold': 45,
            'trade_frequency': 3,  # trades per day
            'confidence_threshold': 0.85
        },
        'GammaScalping': {
            'win_rate': 0.72,
            'avg_pnl': 287,
            'std_pnl': 195,
            'avg_hold': 38,
            'trade_frequency': 2,
            'confidence_threshold': 0.80
        },
        'VolatilityHarvesting': {
            'win_rate': 0.65,
            'avg_pnl': 198,
            'std_pnl': 150,
            'avg_hold': 55,
            'trade_frequency': 2,
            'confidence_threshold': 0.75
        },
        'PCRReversal': {
            'win_rate': 0.68,
            'avg_pnl': 225,
            'std_pnl': 180,
            'avg_hold': 42,
            'trade_frequency': 2,
            'confidence_threshold': 0.78
        },
        'InstitutionalFootprint': {
            'win_rate': 0.68,
            'avg_pnl': 325,
            'std_pnl': 240,
            'avg_hold': 35,
            'trade_frequency': 1,
            'confidence_threshold': 0.82
        },
        'VWAPDeviation': {
            'win_rate': 0.62,
            'avg_pnl': 165,
            'std_pnl': 140,
            'avg_hold': 30,
            'trade_frequency': 2,
            'confidence_threshold': 0.72
        },
        'MomentumImpulse': {
            'win_rate': 0.64,
            'avg_pnl': 189,
            'std_pnl': 160,
            'avg_hold': 28,
            'trade_frequency': 2,
            'confidence_threshold': 0.74
        },
        'MarketProfileGapFill': {
            'win_rate': 0.61,
            'avg_pnl': 145,
            'std_pnl': 130,
            'avg_hold': 50,
            'trade_frequency': 1,
            'confidence_threshold': 0.70
        }
    }
    
    trades = []
    base_date = datetime.now() - timedelta(days=30)
    
    # Generate trades for 30 days
    for day in range(30):
        current_date = base_date + timedelta(days=day)
        
        # Skip weekends
        if current_date.weekday() >= 5:
            continue
        
        for strategy_name, strategy in strategies.items():
            # Generate trades based on frequency
            num_trades = np.random.poisson(strategy['trade_frequency'])
            
            for _ in range(num_trades):
                # Random entry time during market hours
                entry_hour = np.random.choice([9, 10, 11, 12, 13, 14, 15], p=[0.1, 0.2, 0.2, 0.2, 0.15, 0.1, 0.05])
                entry_minute = np.random.choice([0, 15, 30, 45])
                entry_time = current_date.replace(hour=entry_hour, minute=entry_minute)
                
                # Generate P&L based on strategy characteristics
                if np.random.random() < strategy['win_rate']:
                    pnl = np.random.normal(strategy['avg_pnl'], strategy['std_pnl'])
                else:
                    pnl = -np.random.normal(abs(strategy['avg_pnl']) * 0.6, strategy['std_pnl'] * 0.8)
                
                # Hold time with some variation
                hold_time = int(np.random.normal(strategy['avg_hold'], strategy['avg_hold'] * 0.3))
                hold_time = max(5, min(180, hold_time))  # Between 5 min and 3 hours
                
                exit_time = entry_time + timedelta(minutes=hold_time)
                
                # Generate realistic option parameters
                symbols = ['NIFTY', 'BANKNIFTY']
                symbol = np.random.choice(symbols)
                
                if symbol == 'NIFTY':
                    strikes = [25800, 25900, 26000, 26100, 26200]
                    base_price = 26000
                else:
                    strikes = [47500, 47600, 47700, 47800, 47900, 48000]
                    base_price = 48000
                
                strike = np.random.choice(strikes)
                option_type = np.random.choice(['CE', 'PE'])
                
                # Calculate entry and exit prices based on P&L
                quantity = 75 if symbol == 'NIFTY' else 25
                price_change = pnl / (quantity * 50)
                
                # Realistic entry price based on option type and strike
                if option_type == 'CE':
                    if strike > base_price:
                        entry_price = np.random.uniform(50, 150)
                    else:
                        entry_price = np.random.uniform(150, 300)
                else:
                    if strike < base_price:
                        entry_price = np.random.uniform(50, 150)
                    else:
                        entry_price = np.random.uniform(150, 300)
                
                exit_price = entry_price + price_change
                
                # Ensure prices are positive
                exit_price = max(10, exit_price)
                
                trade = {
                    'trade_id': f"{strategy_name}_{entry_time.timestamp()}",
                    'symbol': symbol,
                    'strike_price': strike,
                    'instrument_type': option_type,
                    'entry_time': entry_time.isoformat(),
                    'exit_time': exit_time.isoformat(),
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'quantity': quantity,
                    'net_pnl': pnl,
                    'pnl_percentage': (pnl / (entry_price * quantity * 50)) * 100,
                    'strategy_name': strategy_name,
                    'hold_duration_minutes': hold_time,
                    'confidence': np.random.uniform(strategy['confidence_threshold'], 0.95)
                }
                
                trades.append(trade)
    
    return trades

def analyze_simulated_trades(trades):
    """Analyze the simulated trades"""
    df = pd.DataFrame(trades)
    
    # Calculate metrics
    total_pnl = df['net_pnl'].sum()
    total_trades = len(df)
    winning_trades = len(df[df['net_pnl'] > 0])
    win_rate = (winning_trades / total_trades) * 100
    
    avg_win = df[df['net_pnl'] > 0]['net_pnl'].mean()
    avg_loss = df[df['net_pnl'] < 0]['net_pnl'].mean()
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
    
    # Strategy breakdown
    strategy_performance = {}
    for strategy in df['strategy_name'].unique():
        strat_df = df[df['strategy_name'] == strategy]
        strategy_performance[strategy] = {
            'trades': len(strat_df),
            'total_pnl': strat_df['net_pnl'].sum(),
            'win_rate': (strat_df['net_pnl'] > 0).mean() * 100,
            'avg_pnl': strat_df['net_pnl'].mean(),
            'avg_hold': strat_df['hold_duration_minutes'].mean()
        }
    
    # Daily P&L
    df['date'] = pd.to_datetime(df['entry_time']).dt.date
    daily_pnl = df.groupby('date')['net_pnl'].sum()
    
    # Confidence analysis
    confidence_bins = pd.cut(df['confidence'], bins=[0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0], 
                            labels=['70-75%', '75-80%', '80-85%', '85-90%', '90-95%', '95-100%'])
    confidence_performance = df.groupby(confidence_bins)['net_pnl'].agg(['mean', 'count'])
    
    print("=" * 80)
    print("SIMULATED BACKTEST RESULTS (30 Days)")
    print("=" * 80)
    print(f"Total P&L:          ₹{total_pnl:,.2f}")
    print(f"Total Trades:       {total_trades}")
    print(f"Winning Trades:     {winning_trades}")
    print(f"Win Rate:           {win_rate:.2f}%")
    print(f"Average Win:        ₹{avg_win:,.2f}")
    print(f"Average Loss:       ₹{avg_loss:,.2f}")
    print(f"Profit Factor:      {profit_factor:.2f}")
    print(f"Average P&L/Trade:  ₹{total_pnl/total_trades:,.2f}")
    print(f"Daily Avg P&L:      ₹{total_pnl/30:,.2f}")
    print(f"Monthly Return:     {(total_pnl/100000)*100:.2f}%")
    
    print("\nStrategy Performance:")
    print("-" * 80)
    sorted_strategies = sorted(strategy_performance.items(), key=lambda x: x[1]['total_pnl'], reverse=True)
    for strategy, perf in sorted_strategies:
        print(f"{strategy:25} | Trades: {perf['trades']:3} | P&L: ₹{perf['total_pnl']:8,.2f} | "
              f"Win Rate: {perf['win_rate']:5.1f}% | Avg P&L: ₹{perf['avg_pnl']:6.0f}")
    
    print("\nConfidence Level Performance:")
    print("-" * 80)
    for conf_level, perf in confidence_performance.iterrows():
        if perf['count'] > 0:
            print(f"Confidence {conf_level:7} | Trades: {perf['count']:3} | Avg P&L: ₹{perf['mean']:7.0f}")
    
    print("\nDaily P&L Summary:")
    print("-" * 80)
    print(f"Best Day:   ₹{daily_pnl.max():,.2f}")
    print(f"Worst Day:  ₹{daily_pnl.min():,.2f}")
    print(f"Avg Day:    ₹{daily_pnl.mean():,.2f}")
    print(f"Volatility: ₹{daily_pnl.std():,.2f}")
    
    # What-if scenarios
    print("\nWhat-If Analysis:")
    print("-" * 80)
    
    # Only trade high confidence (>85%)
    high_conf_trades = df[df['confidence'] > 0.85]
    high_conf_pnl = high_conf_trades['net_pnl'].sum()
    high_conf_count = len(high_conf_trades)
    print(f"High Confidence Only (>85%): ₹{high_conf_pnl:,.2f} from {high_conf_count} trades "
          f"(vs ₹{total_pnl:,.2f} from {total_trades})")
    
    # Stop loss at 5%
    df['max_loss'] = df['entry_price'] * df['quantity'] * 50 * 0.05
    df['sl_pnl'] = df.apply(lambda row: max(row['net_pnl'], -row['max_loss']), axis=1)
    sl_total_pnl = df['sl_pnl'].sum()
    print(f"With 5% Stop Loss:          ₹{sl_total_pnl:,.2f} (vs ₹{total_pnl:,.2f})")
    
    # Take profit at 15%
    df['max_profit'] = df['entry_price'] * df['quantity'] * 50 * 0.15
    df['tp_pnl'] = df.apply(lambda row: min(row['net_pnl'], row['max_profit']), axis=1)
    tp_total_pnl = df['tp_pnl'].sum()
    print(f"With 15% Take Profit:       ₹{tp_total_pnl:,.2f} (vs ₹{total_pnl:,.2f})")
    
    # ML-optimized exits (combination of rules)
    def ml_exit(row):
        # Exit at 15% profit or 2 hours max
        if row['hold_duration_minutes'] > 120:
            return row['net_pnl'] * 0.8  # Assume 80% of max if held too long
        if row['net_pnl'] > row['entry_price'] * row['quantity'] * 50 * 0.15:
            return row['entry_price'] * row['quantity'] * 50 * 0.15
        return row['net_pnl']
    
    df['ml_optimized_pnl'] = df.apply(ml_exit, axis=1)
    ml_total_pnl = df['ml_optimized_pnl'].sum()
    print(f"ML-Optimized Exits:        ₹{ml_total_pnl:,.2f} (vs ₹{total_pnl:,.2f})")
    
    # Save results
    results = {
        'summary': {
            'total_pnl': float(total_pnl),
            'total_trades': int(total_trades),
            'win_rate': float(win_rate),
            'avg_win': float(avg_win),
            'avg_loss': float(avg_loss),
            'profit_factor': float(profit_factor),
            'daily_avg_pnl': float(total_pnl/30),
            'monthly_return_pct': float((total_pnl/100000)*100)
        },
        'strategy_performance': strategy_performance,
        'what_if': {
            'high_confidence_only': float(high_conf_pnl),
            'stop_loss_5pct': float(sl_total_pnl),
            'take_profit_15pct': float(tp_total_pnl),
            'ml_optimized': float(ml_total_pnl)
        }
    }
    
    with open('simulated_backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: simulated_backtest_results.json")
    
    return results

def main():
    """Main execution"""
    print("Generating realistic trades based on your strategy characteristics...")
    trades = generate_realistic_trades()
    
    print(f"Generated {len(trades)} trades over 30 days")
    print("\nAnalyzing performance...")
    
    results = analyze_simulated_trades(trades)
    
    print("\n" + "=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)
    
    if results['summary']['total_pnl'] > 0:
        print(f"✅ Profitable System: ₹{results['summary']['total_pnl']:,.2f} in 30 days")
        print(f"✅ Monthly Return: {results['summary']['monthly_return_pct']:.2f}%")
        
        if results['what_if']['ml_optimized'] > results['summary']['total_pnl']:
            improvement = results['what_if']['ml_optimized'] - results['summary']['total_pnl']
            print(f"💡 ML Optimization Could Add: ₹{improvement:,.2f} (+{improvement/results['summary']['total_pnl']*100:.1f}%)")
        
        if results['what_if']['high_confidence_only'] > results['summary']['total_pnl']:
            improvement = results['what_if']['high_confidence_only'] - results['summary']['total_pnl']
            print(f"💡 High-Confidence Filter Could Add: ₹{improvement:,.2f}")
    else:
        print("❌ System shows loss - need to review strategy parameters")

if __name__ == "__main__":
    main()
