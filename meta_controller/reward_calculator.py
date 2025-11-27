"""
Reward Function Calculator
Risk-adjusted PnL over next 30 minutes (6 bars @ 5min intervals)
"""

import numpy as np
from typing import List, Dict
from backend.core.logger import get_logger

logger = get_logger(__name__)


class RewardCalculator:
    """Calculate risk-adjusted rewards for SAC training"""
    
    def __init__(self):
        self.pnl_weight = 1.0
        self.dd_penalty = 3.0
        self.delta_penalty = 0.5
        
    def calculate_reward(
        self,
        realized_pnl: float,
        portfolio_value: float,
        max_drawdown: float,
        portfolio_delta: float,
        time_horizon_minutes: int = 30
    ) -> float:
        """
        Calculate reward: (PnL / portfolio_value) - 3.0 * max_DD - 0.5 * |delta|
        
        Args:
            realized_pnl: Total PnL over period
            portfolio_value: Total portfolio value
            max_drawdown: Maximum drawdown during period
            portfolio_delta: Absolute portfolio delta exposure
            time_horizon_minutes: Time horizon (default 30 min)
            
        Returns:
            Reward value
        """
        # Normalize PnL by portfolio value
        pnl_ratio = realized_pnl / portfolio_value if portfolio_value > 0 else 0
        
        # Drawdown penalty (already normalized)
        dd_penalty = self.dd_penalty * abs(max_drawdown)
        
        # Delta penalty (normalize by typical range)
        delta_penalty = self.delta_penalty * abs(portfolio_delta) / 10.0
        
        # Calculate total reward
        reward = (self.pnl_weight * pnl_ratio) - dd_penalty - delta_penalty
        
        # Scale by time horizon (annualize effect)
        scaling = np.sqrt(390 / time_horizon_minutes)  # 390 min trading day
        reward *= scaling
        
        return reward
    
    def calculate_trajectory_reward(
        self,
        pnl_series: List[float],
        portfolio_value: float
    ) -> Dict:
        """
        Calculate detailed reward metrics for a trajectory
        
        Args:
            pnl_series: List of cumulative PnL values over time
            portfolio_value: Portfolio value
            
        Returns:
            Dict with reward components
        """
        if not pnl_series:
            return {'reward': 0, 'pnl_ratio': 0, 'max_dd': 0, 'sharpe': 0}
        
        # Calculate returns
        returns = np.diff([0] + pnl_series)
        
        # Total PnL
        total_pnl = pnl_series[-1]
        pnl_ratio = total_pnl / portfolio_value
        
        # Maximum drawdown
        cumulative = np.array(pnl_series)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / portfolio_value
        max_dd = abs(drawdown.min()) if len(drawdown) > 0 else 0
        
        # Sharpe-like metric
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(len(returns))
        else:
            sharpe = 0
        
        # Calculate reward
        reward = pnl_ratio - self.dd_penalty * max_dd
        
        return {
            'reward': reward,
            'pnl_ratio': pnl_ratio,
            'max_dd': max_dd,
            'sharpe': sharpe,
            'total_pnl': total_pnl,
            'avg_return': np.mean(returns) if len(returns) > 0 else 0
        }
    
    def calculate_sortino_ratio(self, returns: np.ndarray, target: float = 0) -> float:
        """Calculate Sortino ratio"""
        if len(returns) == 0:
            return 0
        
        excess_returns = returns - target
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0:
            return float('inf')
        
        downside_std = np.sqrt(np.mean(downside_returns ** 2))
        
        if downside_std == 0:
            return 0
        
        return np.mean(excess_returns) / downside_std * np.sqrt(252)
    
    def calculate_max_drawdown_duration(self, equity_curve: List[float]) -> int:
        """Calculate maximum drawdown duration in periods"""
        if not equity_curve:
            return 0
        
        equity = np.array(equity_curve)
        running_max = np.maximum.accumulate(equity)
        drawdown = equity - running_max
        
        # Find drawdown periods
        in_drawdown = drawdown < 0
        durations = []
        current_duration = 0
        
        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
            else:
                if current_duration > 0:
                    durations.append(current_duration)
                current_duration = 0
        
        if current_duration > 0:
            durations.append(current_duration)
        
        return max(durations) if durations else 0
