#!/usr/bin/env python3
"""
Comprehensive Backtest with Option Chain, Greeks, and ML Data
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database.database import db
from backend.database.models import OptionSnapshot, Trade
from backend.core.logger import get_logger
from backend.strategies.quantum_edge import QuantumEdgeStrategy
from backend.strategies.gamma_scalping import GammaScalpingStrategy
from backend.strategies.volatility_harvesting import VolatilityHarvestingStrategy

logger = get_logger(__name__)

class ComprehensiveBacktest:
    def __init__(self, start_date: str, end_date: str, initial_capital: float = 100000):
        self.start_date = datetime.fromisoformat(start_date)
        self.end_date = datetime.fromisoformat(end_date)
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions = []
        self.trades = []
        self.daily_pnl = []
        
        # Initialize strategies
        self.strategies = {
            'QuantumEdge': QuantumEdgeStrategy(),
            'GammaScalping': GammaScalpingStrategy(),
            'VolatilityHarvesting': VolatilityHarvestingStrategy()
        }
        
    def load_option_data(self, date: datetime) -> pd.DataFrame:
        """Load option chain data for given date"""
        session = db.get_session()
        try:
            snapshots = session.query(OptionSnapshot).filter(
                OptionSnapshot.timestamp >= date,
                OptionSnapshot.timestamp < date + timedelta(days=1)
            ).all()
            
            data = []
            for snap in snapshots:
                data.append({
                    'timestamp': snap.timestamp,
                    'symbol': snap.symbol,
                    'strike': snap.strike_price,
                    'option_type': snap.option_type,
                    'spot': snap.spot_price,
                    'iv': snap.implied_volatility,
                    'delta': snap.delta,
                    'gamma': snap.gamma,
                    'theta': snap.theta,
                    'vega': snap.vega,
                    'volume': snap.volume,
                    'oi': snap.open_interest,
                    'bid': snap.bid_price,
                    'ask': snap.ask_price
                })
            
            return pd.DataFrame(data)
        finally:
            session.close()
    
    def generate_signals(self, option_data: pd.DataFrame) -> list:
        """Generate trading signals from all strategies"""
        all_signals = []
        
        for strategy_name, strategy in self.strategies.items():
            try:
                signals = strategy.analyze(option_data)
                for signal in signals:
                    signal['strategy'] = strategy_name
                    all_signals.append(signal)
            except Exception as e:
                logger.error(f"Error in {strategy_name}: {e}")
        
        return all_signals
    
    def execute_trade(self, signal: dict, option_data: pd.DataFrame) -> dict:
        """Execute trade based on signal"""
        # Find matching option
        matching_options = option_data[
            (option_data['symbol'] == signal['symbol']) &
            (option_data['strike'] == signal['strike']) &
            (option_data['option_type'] == signal['option_type'])
        ]
        
        if matching_options.empty:
            return None
        
        option = matching_options.iloc[0]
        
        # Calculate position size (1% risk per trade)
        risk_amount = self.current_capital * 0.01
        price = (option['bid'] + option['ask']) / 2
        quantity = int(risk_amount / (price * 50))  # 50 lot size for NIFTY
        
        position = {
            'position_id': f"{signal['strategy']}_{datetime.now().timestamp()}",
            'symbol': signal['symbol'],
            'strike': signal['strike'],
            'option_type': signal['option_type'],
            'quantity': quantity,
            'entry_price': price,
            'entry_time': signal.get('timestamp', datetime.now()),
            'strategy': signal['strategy'],
            'signal_strength': signal.get('strength', 0),
            'delta': option['delta'],
            'gamma': option['gamma'],
            'theta': option['theta'],
            'iv_entry': option['iv'],
            'ml_target_1': signal.get('target_price', price * 1.15),
            'ml_target_2': signal.get('target_price_2', price * 1.25),
            'stop_loss': signal.get('stop_loss', price * 0.9)
        }
        
        self.positions.append(position)
        return position
    
    def update_positions(self, option_data: pd.DataFrame, current_time: datetime):
        """Update position values and check exit conditions"""
        positions_to_close = []
        
        for pos in self.positions:
            # Find current option price
            current_option = option_data[
                (option_data['symbol'] == pos['symbol']) &
                (option_data['strike'] == pos['strike']) &
                (option_data['option_type'] == pos['option_type'])
            ]
            
            if current_option.empty:
                continue
            
            current = current_option.iloc[0]
            current_price = (current['bid'] + current['ask']) / 2
            
            # Update P&L
            pos['current_price'] = current_price
            pos['unrealized_pnl'] = (current_price - pos['entry_price']) * pos['quantity'] * 50
            pos['unrealized_pnl_pct'] = (current_price - pos['entry_price']) / pos['entry_price'] * 100
            
            # Check exit conditions
            hold_time = (current_time - pos['entry_time']).total_seconds() / 3600
            
            # Exit conditions
            if (current_price >= pos['ml_target_1'] or  # ML target hit
                current_price <= pos['stop_loss'] or    # Stop loss hit
                pos['unrealized_pnl_pct'] >= 15 or      # 15% profit
                (hold_time > 2 and pos['unrealized_pnl_pct'] > 5) or  # Quick profit
                current_time.hour >= 15 and current_time.minute >= 29):  # EOD exit
                
                positions_to_close.append(pos)
        
        # Close positions
        for pos in positions_to_close:
            self.close_position(pos, current_time)
    
    def close_position(self, position: dict, exit_time: datetime):
        """Close position and record trade"""
        pnl = position['unrealized_pnl']
        self.current_capital += pnl
        
        trade = {
            'trade_id': position['position_id'],
            'symbol': position['symbol'],
            'strike': position['strike'],
            'option_type': position['option_type'],
            'quantity': position['quantity'],
            'entry_price': position['entry_price'],
            'exit_price': position['current_price'],
            'entry_time': position['entry_time'],
            'exit_time': exit_time,
            'pnl': pnl,
            'pnl_pct': position['unrealized_pnl_pct'],
            'strategy': position['strategy'],
            'hold_duration_hours': (exit_time - position['entry_time']).total_seconds() / 3600
        }
        
        self.trades.append(trade)
        self.positions.remove(position)
    
    def run_backtest(self):
        """Execute the complete backtest"""
        current_date = self.start_date
        
        while current_date <= self.end_date:
            logger.info(f"Backtesting date: {current_date.date()}")
            
            # Load option data
            option_data = self.load_option_data(current_date)
            if option_data.empty:
                current_date += timedelta(days=1)
                continue
            
            # Process each 5-minute interval
            for hour in range(9, 16):
                for minute in range(0, 60, 5):
                    if hour == 15 and minute > 30:
                        break
                    
                    current_time = current_date.replace(hour=hour, minute=minute)
                    
                    # Filter data for current time
                    time_data = option_data[
                        (option_data['timestamp'] >= current_time) &
                        (option_data['timestamp'] < current_time + timedelta(minutes=5))
                    ]
                    
                    if time_data.empty:
                        continue
                    
                    # Generate signals
                    signals = self.generate_signals(time_data)
                    
                    # Execute new signals (max 3 positions)
                    if len(self.positions) < 3:
                        for signal in signals[:3]:
                            if signal.get('strength', 0) > 80:
                                self.execute_trade(signal, time_data)
                    
                    # Update existing positions
                    self.update_positions(time_data, current_time)
            
            # Close all positions at EOD
            for pos in self.positions.copy():
                self.close_position(pos, current_date.replace(hour=15, minute=30))
            
            # Record daily P&L
            daily_pnl = sum(t['pnl'] for t in self.trades 
                          if t['exit_time'].date() == current_date.date())
            self.daily_pnl.append({
                'date': current_date.date(),
                'pnl': daily_pnl,
                'capital': self.current_capital
            })
            
            current_date += timedelta(days=1)
    
    def generate_report(self) -> dict:
        """Generate comprehensive backtest report"""
        if not self.trades:
            return {"error": "No trades executed"}
        
        trades_df = pd.DataFrame(self.trades)
        
        # Calculate metrics
        total_pnl = trades_df['pnl'].sum()
        win_rate = (trades_df['pnl'] > 0).mean()
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean()
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean()
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        
        # Strategy breakdown
        strategy_performance = {}
        for strategy in trades_df['strategy'].unique():
            strat_trades = trades_df[trades_df['strategy'] == strategy]
            strategy_performance[strategy] = {
                'trades': len(strat_trades),
                'total_pnl': strat_trades['pnl'].sum(),
                'win_rate': (strat_trades['pnl'] > 0).mean(),
                'avg_pnl': strat_trades['pnl'].mean()
            }
        
        return {
            'summary': {
                'initial_capital': self.initial_capital,
                'final_capital': self.current_capital,
                'total_pnl': total_pnl,
                'return_pct': (total_pnl / self.initial_capital) * 100,
                'total_trades': len(self.trades),
                'win_rate': win_rate * 100,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'max_drawdown': self.calculate_max_drawdown()
            },
            'strategy_performance': strategy_performance,
            'daily_pnl': self.daily_pnl[-10:],  # Last 10 days
            'top_trades': trades_df.nlargest(5, 'pnl')[['symbol', 'strike', 'pnl', 'strategy']].to_dict('records')
        }
    
    def calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        capital_series = [d['capital'] for d in self.daily_pnl]
        peak = capital_series[0]
        max_dd = 0
        
        for capital in capital_series:
            if capital > peak:
                peak = capital
            dd = (peak - capital) / peak
            if dd > max_dd:
                max_dd = dd
        
        return max_dd * 100


def main():
    """Run comprehensive backtest"""
    # Test on last 30 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    print("=" * 80)
    print("COMPREHENSIVE BACKTEST WITH OPTION CHAIN & ML DATA")
    print("=" * 80)
    print(f"Period: {start_date.date()} to {end_date.date()}")
    print(f"Initial Capital: ₹100,000")
    print()
    
    # Initialize backtest
    backtest = ComprehensiveBacktest(
        start_date.isoformat(),
        end_date.isoformat(),
        100000
    )
    
    # Run backtest
    print("Running backtest...")
    backtest.run_backtest()
    
    # Generate report
    print("\nGenerating report...")
    report = backtest.generate_report()
    
    # Display results
    print("\n" + "=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)
    
    if 'error' in report:
        print(f"Error: {report['error']}")
        return
    
    summary = report['summary']
    print(f"Initial Capital:    ₹{summary['initial_capital']:,.2f}")
    print(f"Final Capital:      ₹{summary['final_capital']:,.2f}")
    print(f"Total P&L:          ₹{summary['total_pnl']:,.2f}")
    print(f"Return:             {summary['return_pct']:.2f}%")
    print(f"Total Trades:       {summary['total_trades']}")
    print(f"Win Rate:           {summary['win_rate']:.2f}%")
    print(f"Average Win:        ₹{summary['avg_win']:,.2f}")
    print(f"Average Loss:       ₹{summary['avg_loss']:,.2f}")
    print(f"Profit Factor:      {summary['profit_factor']:.2f}")
    print(f"Max Drawdown:       {summary['max_drawdown']:.2f}%")
    
    print("\nStrategy Performance:")
    for strategy, perf in report['strategy_performance'].items():
        print(f"  {strategy:20} | Trades: {perf['trades']:3} | P&L: ₹{perf['total_pnl']:7,.2f} | Win Rate: {perf['win_rate']*100:5.1f}%")
    
    print("\nTop 5 Trades:")
    for i, trade in enumerate(report['top_trades'], 1):
        print(f"  {i}. {trade['symbol']} {trade['strike']} {trade['option_type']} | P&L: ₹{trade['pnl']:,.2f} | Strategy: {trade['strategy']}")
    
    print("\nRecent Daily P&L:")
    for day in report['daily_pnl'][-5:]:
        print(f"  {day['date']}: ₹{day['pnl']:,.2f} (Capital: ₹{day['capital']:,.2f})")
    
    # Save detailed report
    import json
    with open('backtest_results.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\nDetailed report saved to: backtest_results.json")


if __name__ == "__main__":
    main()
