"""
Dynamic Position Sizer
Adjusts position sizes based on confidence levels
"""

import numpy as np
from typing import Dict, Optional
from datetime import datetime

from backend.core.config import config
from backend.core.logger import get_logger
from backend.optimization.enhanced_allocator import enhanced_allocator

logger = get_logger(__name__)


class DynamicPositionSizer:
    """
    Dynamically sizes positions based on:
    1. Signal confidence level
    2. Account value
    3. Market regime
    4. Strategy performance
    """
    
    def __init__(self):
        self.base_risk_pct = 0.02  # 2% base risk per trade
        self.max_risk_pct = 0.04   # 4% max risk per trade
        self.max_portfolio_risk = 0.10  # 10% max total portfolio risk
        
    def calculate_position_size(self, signal: Dict, account_value: float, 
                              current_positions: list) -> int:
        """
        Calculate dynamic position size based on signal confidence
        
        Args:
            signal: Trading signal with confidence score
            account_value: Total account value
            current_positions: List of current positions
            
        Returns:
            Optimal position size (quantity)
        """
        try:
            # Get base parameters
            confidence = signal.get('confidence', 0.75)
            strategy = signal.get('strategy_id', 'unknown')
            entry_price = signal.get('entry_price', 100)
            
            # Calculate confidence multiplier
            confidence_multiplier = self._get_confidence_multiplier(confidence)
            
            # Calculate strategy multiplier
            strategy_multiplier = self._get_strategy_multiplier(strategy)
            
            # Calculate portfolio risk adjustment
            portfolio_adjustment = self._calculate_portfolio_risk_adjustment(
                current_positions, account_value
            )
            
            # Calculate regime adjustment
            regime_adjustment = self._get_regime_adjustment()
            
            # Calculate final risk percentage
            risk_pct = (self.base_risk_pct * 
                       confidence_multiplier * 
                       strategy_multiplier * 
                       portfolio_adjustment * 
                       regime_adjustment)
            
            # Cap risk
            risk_pct = min(risk_pct, self.max_risk_pct)
            
            # Calculate position size
            risk_amount = account_value * risk_pct
            quantity = int(risk_amount / (entry_price * 50))  # 50 lot size
            
            # Apply minimum and maximum limits
            min_quantity = 25  # Minimum 1 lot
            max_quantity = 300  # Maximum 6 lots
            
            quantity = max(min_quantity, min(quantity, max_quantity))
            
            logger.info(f"Dynamic sizing: {strategy} confidence={confidence:.2f}, "
                       f"multiplier={confidence_multiplier:.2f}, "
                       f"risk_pct={risk_pct:.2%}, quantity={quantity}")
            
            return quantity
            
        except Exception as e:
            logger.error(f"Error calculating dynamic position size: {e}")
            return 75  # Default to 1 lot
    
    def _get_confidence_multiplier(self, confidence: float) -> float:
        """Get position size multiplier based on confidence level"""
        if confidence >= 0.95:
            return 2.0  # Double size for 95%+ confidence
        elif confidence >= 0.90:
            return 1.5  # 50% larger for 90-95% confidence
        elif confidence >= 0.85:
            return 1.2  # 20% larger for 85-90% confidence
        elif confidence >= 0.80:
            return 1.0  # Normal size for 80-85% confidence
        elif confidence >= 0.75:
            return 0.8  # 20% smaller for 75-80% confidence
        else:
            return 0.6  # 40% smaller for <75% confidence
    
    def _get_strategy_multiplier(self, strategy: str) -> float:
        """Get multiplier based on strategy performance"""
        # Top performers get larger allocations
        top_strategies = ['QuantumEdge', 'PCRReversal', 'InstitutionalFootprint']
        
        if strategy in top_strategies:
            return 1.15  # 15% boost for top strategies
        elif strategy == 'GammaScalping':
            return 1.10  # 10% boost
        elif strategy == 'VolatilityCapture':
            return 1.05  # 5% boost
        else:
            return 1.0  # Normal size
    
    def _calculate_portfolio_risk_adjustment(self, current_positions: list, 
                                           account_value: float) -> float:
        """Adjust size based on current portfolio risk"""
        if not current_positions:
            return 1.0
        
        # Calculate current portfolio risk
        total_risk = 0
        for pos in current_positions:
            pos_value = pos.get('quantity', 75) * pos.get('entry_price', 100) * 50
            total_risk += pos_value
        
        current_risk_pct = total_risk / account_value
        
        # Reduce size if portfolio is too risky
        if current_risk_pct > 0.08:  # 8% current risk
            return 0.5  # Halve new positions
        elif current_risk_pct > 0.06:  # 6% current risk
            return 0.7  # Reduce by 30%
        elif current_risk_pct > 0.04:  # 4% current risk
            return 0.85  # Reduce by 15%
        else:
            return 1.0  # Full size
    
    def _get_regime_adjustment(self) -> float:
        """Get adjustment based on current market regime"""
        regime = config.get('market.regime', 'NORMAL')
        
        if regime == 'HIGH_VOLATILITY':
            return 0.8  # Reduce size in high volatility
        elif regime == 'LOW_VOLATILITY':
            return 1.2  # Increase size in low volatility
        else:
            return 1.0  # Normal size
    
    def should_increase_size(self, recent_performance: list) -> bool:
        """
        Determine if position sizes should be increased based on recent performance
        
        Args:
            recent_performance: List of recent trade P&L
            
        Returns:
            True if sizes should be increased
        """
        if not recent_performance or len(recent_performance) < 5:
            return False
        
        # Check if recent performance is strong
        win_rate = sum(1 for pnl in recent_performance if pnl > 0) / len(recent_performance)
        avg_pnl = np.mean(recent_performance)
        
        # Increase if win rate > 70% and average P&L > ₹200
        if win_rate > 0.7 and avg_pnl > 200:
            logger.info(f"Increasing position sizes: win_rate={win_rate:.1%}, avg_pnl=₹{avg_pnl:.0f}")
            return True
        
        return False
    
    def should_decrease_size(self, recent_performance: list) -> bool:
        """
        Determine if position sizes should be decreased based on recent performance
        
        Args:
            recent_performance: List of recent trade P&L
            
        Returns:
            True if sizes should be decreased
        """
        if not recent_performance or len(recent_performance) < 5:
            return False
        
        # Check for poor performance
        win_rate = sum(1 for pnl in recent_performance if pnl > 0) / len(recent_performance)
        max_drawdown = abs(min(recent_performance))
        
        # Decrease if win rate < 40% or max loss > ₹2,000
        if win_rate < 0.4 or max_drawdown > 2000:
            logger.warning(f"Decreasing position sizes: win_rate={win_rate:.1%}, max_loss=₹{max_drawdown:.0f}")
            return True
        
        return False


# Global instance
dynamic_sizer = DynamicPositionSizer()


def calculate_optimal_size(signal: Dict, account_value: float, 
                          current_positions: list) -> int:
    """
    Calculate optimal position size for a signal
    
    Args:
        signal: Trading signal
        account_value: Account value
        current_positions: Current positions
        
    Returns:
        Optimal position size
    """
    return dynamic_sizer.calculate_position_size(
        signal, account_value, current_positions
    )
