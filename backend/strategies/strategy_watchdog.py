"""
Strategy Watchdog
Monitors strategy performance and can disable strategies that perform poorly
"""

from typing import Dict, Set
from datetime import datetime
from collections import defaultdict, deque
import json

class StrategyWatchdog:
    """
    Monitors strategy performance and can disable underperforming strategies
    """
    
    def __init__(self, min_trades_for_evaluation: int = 20, min_win_rate: float = 0.45, 
                 max_consecutive_losses: int = 5):
        """
        Initialize strategy watchdog
        
        Args:
            min_trades_for_evaluation: Minimum trades before evaluating strategy
            min_win_rate: Minimum win rate required (decimal, e.g., 0.45 for 45%)
            max_consecutive_losses: Maximum consecutive losses before disabling
        """
        self.min_trades_for_evaluation = min_trades_for_evaluation
        self.min_win_rate = min_win_rate
        self.max_consecutive_losses = max_consecutive_losses
        
        # Track performance metrics
        self.strategy_trades: Dict[str, int] = defaultdict(int)
        self.strategy_wins: Dict[str, int] = defaultdict(int)
        self.strategy_losses: Dict[str, int] = defaultdict(int)
        self.strategy_consecutive_losses: Dict[str, int] = defaultdict(int)
        self.strategy_total_pnl: Dict[str, float] = defaultdict(float)
        self.disabled_strategies: Set[str] = set()
        
        # Track recent trades for better evaluation
        self.recent_trades: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
    
    def is_strategy_enabled(self, strategy: str) -> bool:
        """
        Check if a strategy is enabled for trading
        
        Args:
            strategy: Strategy name
            
        Returns:
            True if strategy is enabled, False if disabled
        """
        return strategy not in self.disabled_strategies
    
    def record_trade(self, strategy: str, pnl: float, allocated_capital: float = 0):
        """
        Record a trade outcome for performance tracking
        
        Args:
            strategy: Strategy name
            pnl: Profit/loss from the trade (positive for profit, negative for loss)
            allocated_capital: Capital allocated to the trade
        """
        # Update trade counts
        self.strategy_trades[strategy] += 1
        self.strategy_total_pnl[strategy] += pnl
        
        # Track recent trade
        self.recent_trades[strategy].append({
            'pnl': pnl,
            'capital': allocated_capital,
            'timestamp': datetime.now(),
            'is_win': pnl > 0
        })
        
        # Update win/loss tracking
        if pnl > 0:
            self.strategy_wins[strategy] += 1
            self.strategy_consecutive_losses[strategy] = 0  # Reset consecutive losses
        else:
            self.strategy_losses[strategy] += 1
            self.strategy_consecutive_losses[strategy] += 1
        
        # Check if strategy should be disabled
        self._evaluate_strategy(strategy)
    
    def _evaluate_strategy(self, strategy: str):
        """
        Evaluate strategy performance and disable if necessary
        
        Args:
            strategy: Strategy name
        """
        # Don't evaluate if we don't have enough trades
        if self.strategy_trades[strategy] < self.min_trades_for_evaluation:
            return
        
        # Check consecutive losses
        if self.strategy_consecutive_losses[strategy] >= self.max_consecutive_losses:
            self.disabled_strategies.add(strategy)
            return
        
        # Check win rate
        total_trades = self.strategy_trades[strategy]
        win_rate = self.strategy_wins[strategy] / total_trades if total_trades > 0 else 0
        
        if win_rate < self.min_win_rate:
            self.disabled_strategies.add(strategy)
            return
        
        # Check overall profitability
        if self.strategy_total_pnl[strategy] < 0 and total_trades >= self.min_trades_for_evaluation * 2:
            # If strategy is consistently losing over many trades, disable it
            recent_win_rate = self._calculate_recent_win_rate(strategy)
            if recent_win_rate < self.min_win_rate:
                self.disabled_strategies.add(strategy)
    
    def _calculate_recent_win_rate(self, strategy: str, lookback: int = 20) -> float:
        """
        Calculate win rate for recent trades
        
        Args:
            strategy: Strategy name
            lookback: Number of recent trades to consider
            
        Returns:
            Recent win rate as decimal
        """
        recent_trades_list = list(self.recent_trades[strategy])[-lookback:]
        if not recent_trades_list:
            return 0.0
        
        wins = sum(1 for trade in recent_trades_list if trade['is_win'])
        return wins / len(recent_trades_list)
    
    def enable_strategy(self, strategy: str):
        """
        Manually enable a strategy
        
        Args:
            strategy: Strategy name
        """
        self.disabled_strategies.discard(strategy)
        # Optionally reset performance metrics
        # self.strategy_consecutive_losses[strategy] = 0
    
    def disable_strategy(self, strategy: str):
        """
        Manually disable a strategy
        
        Args:
            strategy: Strategy name
        """
        self.disabled_strategies.add(strategy)
    
    def get_strategy_stats(self, strategy: str) -> Dict:
        """
        Get performance statistics for a strategy
        
        Args:
            strategy: Strategy name
            
        Returns:
            Dictionary with performance metrics
        """
        total_trades = self.strategy_trades[strategy]
        win_rate = self.strategy_wins[strategy] / total_trades if total_trades > 0 else 0
        avg_trade = self.strategy_total_pnl[strategy] / total_trades if total_trades > 0 else 0
        
        return {
            'strategy': strategy,
            'total_trades': total_trades,
            'wins': self.strategy_wins[strategy],
            'losses': self.strategy_losses[strategy],
            'win_rate': win_rate,
            'total_pnl': self.strategy_total_pnl[strategy],
            'avg_trade_pnl': avg_trade,
            'consecutive_losses': self.strategy_consecutive_losses[strategy],
            'is_enabled': strategy not in self.disabled_strategies,
            'recent_win_rate': self._calculate_recent_win_rate(strategy)
        }
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """
        Get statistics for all strategies
        
        Returns:
            Dictionary mapping strategy names to their stats
        """
        all_strategies = set(self.strategy_trades.keys()) | set(self.disabled_strategies)
        return {strategy: self.get_strategy_stats(strategy) for strategy in all_strategies}
    
    def reset_strategy(self, strategy: str):
        """
        Reset all performance metrics for a strategy
        
        Args:
            strategy: Strategy name
        """
        # Remove from all tracking dictionaries
        self.strategy_trades.pop(strategy, None)
        self.strategy_wins.pop(strategy, None)
        self.strategy_losses.pop(strategy, None)
        self.strategy_consecutive_losses.pop(strategy, None)
        self.strategy_total_pnl.pop(strategy, None)
        self.recent_trades.pop(strategy, None)
        
        # Re-enable the strategy
        self.disabled_strategies.discard(strategy)
    
    def export_config(self) -> Dict:
        """
        Export current configuration and state
        
        Returns:
            Dictionary with current state
        """
        return {
            'config': {
                'min_trades_for_evaluation': self.min_trades_for_evaluation,
                'min_win_rate': self.min_win_rate,
                'max_consecutive_losses': self.max_consecutive_losses
            },
            'disabled_strategies': list(self.disabled_strategies),
            'stats': self.get_all_stats()
        }
    
    def import_config(self, config_data: Dict):
        """
        Import configuration and state
        
        Args:
            config_data: Dictionary with configuration and state
        """
        if 'config' in config_data:
            cfg = config_data['config']
            self.min_trades_for_evaluation = cfg.get('min_trades_for_evaluation', self.min_trades_for_evaluation)
            self.min_win_rate = cfg.get('min_win_rate', self.min_win_rate)
            self.max_consecutive_losses = cfg.get('max_consecutive_losses', self.max_consecutive_losses)
        
        if 'disabled_strategies' in config_data:
            self.disabled_strategies = set(config_data['disabled_strategies'])
