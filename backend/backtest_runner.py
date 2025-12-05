"""
Backtest Runner
Runs backtesting simulations for trading strategies
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

class BacktestRunner:
    """
    Runs backtesting simulations for trading strategies
    """
    
    def __init__(self):
        self.results = {}
        
    def run_full_backtest(self, strategies: List[str], start_date: datetime, end_date: datetime, 
                         initial_capital: float = 100000) -> Dict:
        """
        Run a full backtest simulation
        
        Args:
            strategies: List of strategy names to test
            start_date: Start date for backtest
            end_date: End date for backtest
            initial_capital: Initial capital for simulation
            
        Returns:
            Dictionary with backtest results
        """
        results = {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'initial_capital': initial_capital,
            'strategies': {}
        }
        
        for strategy in strategies:
            strategy_result = self._run_strategy_backtest(strategy, start_date, end_date, initial_capital)
            results['strategies'][strategy] = strategy_result
        
        # Calculate overall portfolio performance
        results['portfolio'] = self._calculate_portfolio_performance(results['strategies'])
        
        return results
    
    def _run_strategy_backtest(self, strategy: str, start_date: datetime, end_date: datetime, 
                              initial_capital: float) -> Dict:
        """
        Run backtest for a single strategy
        
        Args:
            strategy: Strategy name
            start_date: Start date
            end_date: End date
            initial_capital: Initial capital
            
        Returns:
            Strategy backtest results
        """
        # Mock implementation - in real system this would fetch historical data and run the strategy
        trades = self._generate_mock_trades(strategy, start_date, end_date)
        
        if not trades:
            return {
                'strategy': strategy,
                'total_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'final_capital': initial_capital,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0
            }
        
        # Calculate performance metrics
        total_pnl = sum(trade['pnl'] for trade in trades)
        winning_trades = [trade for trade in trades if trade['pnl'] > 0]
        win_rate = len(winning_trades) / len(trades) if trades else 0.0
        final_capital = initial_capital + total_pnl
        
        # Calculate running capital for drawdown
        running_capital = initial_capital
        capital_curve = [initial_capital]
        for trade in trades:
            running_capital += trade['pnl']
            capital_curve.append(running_capital)
        
        # Calculate max drawdown
        peak = capital_curve[0]
        max_drawdown = 0.0
        for capital in capital_curve:
            if capital > peak:
                peak = capital
            drawdown = (peak - capital) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # Calculate Sharpe ratio (simplified)
        returns = [trade['pnl'] / initial_capital for trade in trades]
        if len(returns) > 1:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe_ratio = avg_return / std_return if std_return > 0 else 0.0
        else:
            sharpe_ratio = 0.0
        
        return {
            'strategy': strategy,
            'total_trades': len(trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'final_capital': final_capital,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'trades': trades[:10]  # Return first 10 trades for sample
        }
    
    def _generate_mock_trades(self, strategy: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Generate mock trades for testing purposes
        
        Args:
            strategy: Strategy name
            start_date: Start date
            end_date: End date
            
        Returns:
            List of mock trades
        """
        trades = []
        current_date = start_date
        
        # Generate different trade patterns based on strategy
        strategy_configs = {
            'Quantum Edge V2': {'win_rate': 0.65, 'avg_trade': 150, 'trade_frequency': 2},
            'Quantum Edge': {'win_rate': 0.60, 'avg_trade': 120, 'trade_frequency': 3},
            'Default ORB': {'win_rate': 0.55, 'avg_trade': 80, 'trade_frequency': 4},
            'Gamma Scalping': {'win_rate': 0.70, 'avg_trade': 60, 'trade_frequency': 5},
            'VWAP Deviation': {'win_rate': 0.58, 'avg_trade': 100, 'trade_frequency': 3},
            'IV Rank Trading': {'win_rate': 0.62, 'avg_trade': 110, 'trade_frequency': 2}
        }
        
        config = strategy_configs.get(strategy, {
            'win_rate': 0.55, 'avg_trade': 100, 'trade_frequency': 3
        })
        
        # Calculate number of trading days
        trading_days = (end_date - start_date).days
        expected_trades = trading_days * config['trade_frequency'] // 7  # Approximate trades per day
        
        for i in range(expected_trades):
            # Random trade generation
            is_win = np.random.random() < config['win_rate']
            
            # Generate P&L with some randomness
            if is_win:
                pnl = abs(np.random.normal(config['avg_trade'], config['avg_trade'] * 0.5))
            else:
                pnl = -abs(np.random.normal(config['avg_trade'] * 0.8, config['avg_trade'] * 0.4))
            
            # Generate trade date
            trade_date = current_date + timedelta(days=np.random.randint(0, trading_days))
            
            trades.append({
                'date': trade_date.isoformat(),
                'pnl': pnl,
                'strategy': strategy,
                'entry_price': np.random.uniform(19000, 20000),  # Mock NIFTY range
                'exit_price': np.random.uniform(19000, 20000),
                'quantity': np.random.randint(50, 200)
            })
        
        # Sort trades by date
        trades.sort(key=lambda x: x['date'])
        
        return trades
    
    def _calculate_portfolio_performance(self, strategy_results: Dict) -> Dict:
        """
        Calculate overall portfolio performance across all strategies
        
        Args:
            strategy_results: Results from individual strategies
            
        Returns:
            Portfolio performance metrics
        """
        if not strategy_results:
            return {
                'total_capital': 0,
                'total_pnl': 0,
                'weighted_win_rate': 0,
                'best_strategy': None,
                'worst_strategy': None
            }
        
        total_pnl = sum(result['total_pnl'] for result in strategy_results.values())
        total_trades = sum(result['total_trades'] for result in strategy_results.values())
        
        # Calculate weighted win rate
        if total_trades > 0:
            weighted_win_rate = sum(
                result['win_rate'] * result['total_trades'] 
                for result in strategy_results.values()
            ) / total_trades
        else:
            weighted_win_rate = 0.0
        
        # Find best and worst performing strategies
        best_strategy = None
        worst_strategy = None
        best_pnl = float('-inf')
        worst_pnl = float('inf')
        
        for strategy_name, result in strategy_results.items():
            if result['total_pnl'] > best_pnl:
                best_pnl = result['total_pnl']
                best_strategy = strategy_name
            if result['total_pnl'] < worst_pnl:
                worst_pnl = result['total_pnl']
                worst_strategy = strategy_name
        
        return {
            'total_capital': sum(result['final_capital'] for result in strategy_results.values()),
            'total_pnl': total_pnl,
            'weighted_win_rate': weighted_win_rate,
            'best_strategy': best_strategy,
            'worst_strategy': worst_strategy,
            'strategy_count': len(strategy_results)
        }

# Global instance for easy access
backtest_runner = BacktestRunner()

# Convenience function for quick backtesting
def run_quick_backtest(strategy: str, days: int = 30) -> Dict:
    """
    Run a quick backtest for a single strategy
    
    Args:
        strategy: Strategy name
        days: Number of days to backtest
        
    Returns:
        Backtest results
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    return backtest_runner.run_full_backtest([strategy], start_date, end_date)

# Main backtest function (for import in main.py)
def run_full_backtest(strategies: List[str] = None, start_date: datetime = None, 
                      end_date: datetime = None, initial_capital: float = 100000) -> Dict:
    """
    Run full backtest - wrapper for backtest_runner.run_full_backtest
    
    Args:
        strategies: List of strategy names (defaults to all strategies)
        start_date: Start date (defaults to 30 days ago)
        end_date: End date (defaults to now)
        initial_capital: Initial capital
        
    Returns:
        Backtest results
    """
    if strategies is None:
        strategies = ['Quantum Edge V2', 'Quantum Edge', 'Default ORB', 
                     'Gamma Scalping', 'VWAP Deviation', 'IV Rank Trading']
    
    if end_date is None:
        end_date = datetime.now()
    
    if start_date is None:
        start_date = end_date - timedelta(days=30)
    
    return backtest_runner.run_full_backtest(strategies, start_date, end_date, initial_capital)
