"""
Position Manager
Tracks positions, margin utilization, and capital allocation
"""

from typing import Dict, List, Optional
from datetime import datetime

from backend.core.logger import get_logger

logger = get_logger(__name__)


class PositionManager:
    """
    Advanced position management system
    
    Features:
    - Real-time margin tracking
    - Per-strategy capital allocation
    - Concentration limits
    - Exposure monitoring
    """
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Capital parameters
        self.total_capital = config.get('total_capital', 100000)
        self.max_capital_utilization = config.get('max_capital_utilization', 0.8)  # 80%
        self.max_strategy_allocation = config.get('max_strategy_allocation', 0.4)  # 40% per strategy
        self.max_position_allocation = config.get('max_position_allocation', 0.2)  # 20% per position
        
        # Positions tracking
        self.positions: Dict[str, Dict] = {}
        self.strategy_allocations: Dict[str, float] = {}
        
        # Margin tracking
        self.used_margin = 0.0
        self.available_margin = self.total_capital
        
    def _extract(self, position: Dict, key: str, default=None):
        """Safely extract attribute or dict value."""
        if isinstance(position, dict):
            return position.get(key, default)
        return getattr(position, key, default)

    def add_position(self, position: Dict) -> bool:
        """
        Add new position with capital allocation checks
        
        Args:
            position: Position dict
            
        Returns:
            True if position added successfully
        """
        
        position_id = self._extract(position, 'id')
        if not position_id:
            logger.error("Position missing identifier")
            return False

        strategy = self._extract(position, 'strategy', 'unknown') or self._extract(position, 'strategy_name', 'unknown')
        
        # Calculate position value
        quantity = self._extract(position, 'quantity', 0) or 0
        entry_price = self._extract(position, 'entry_price', 0.0) or 0.0
        position_value = quantity * entry_price
        
        # Check capital allocation limits
        checks_passed, error_msg = self._check_allocation_limits(
            strategy, position_value
        )
        
        if not checks_passed:
            logger.error(f"❌ Position rejected: {error_msg}")
            return False
            
        # Add position
        self.positions[position_id] = position
        
        # Update strategy allocation
        if strategy not in self.strategy_allocations:
            self.strategy_allocations[strategy] = 0
        self.strategy_allocations[strategy] += position_value

        # Update margin
        self.used_margin += position_value
        self.available_margin = self.total_capital - self.used_margin
        
        logger.info(
            f"✅ Position added: {strategy} ₹{position_value:,.0f}\n"
            f"Used margin: ₹{self.used_margin:,.0f} / ₹{self.total_capital:,.0f} "
            f"({self.used_margin/self.total_capital*100:.1f}%)"
        )
        
        return True
        
    def _check_allocation_limits(
        self,
        strategy: str,
        position_value: float
    ) -> tuple[bool, Optional[str]]:
        """Check if position fits within allocation limits"""
        
        # Check overall capital utilization
        new_used_margin = self.used_margin + position_value
        utilization = new_used_margin / self.total_capital
        
        if utilization > self.max_capital_utilization:
            return False, (
                f"Total capital utilization {utilization*100:.1f}% "
                f"exceeds limit {self.max_capital_utilization*100:.0f}%"
            )
            
        # Check per-strategy allocation
        current_strategy_allocation = self.strategy_allocations.get(strategy, 0)
        new_strategy_allocation = current_strategy_allocation + position_value
        strategy_percent = new_strategy_allocation / self.total_capital
        
        if strategy_percent > self.max_strategy_allocation:
            return False, (
                f"Strategy '{strategy}' allocation {strategy_percent*100:.1f}% "
                f"exceeds limit {self.max_strategy_allocation*100:.0f}%"
            )
            
        # Check per-position allocation
        position_percent = position_value / self.total_capital
        
        if position_percent > self.max_position_allocation:
            return False, (
                f"Single position allocation {position_percent*100:.1f}% "
                f"exceeds limit {self.max_position_allocation*100:.0f}%"
            )
            
        return True, None
        
    def remove_position(self, position_id: str):
        """Remove position and free up capital"""
        
        if position_id not in self.positions:
            logger.warning(f"Position {position_id} not found")
            return
            
        position = self.positions[position_id]
        strategy = self._extract(position, 'strategy', 'unknown') or self._extract(position, 'strategy_name', 'unknown')
        quantity = self._extract(position, 'quantity', 0) or 0
        entry_price = self._extract(position, 'entry_price', 0.0) or 0.0
        position_value = quantity * entry_price

        # Update allocations
        del self.positions[position_id]
        
        if strategy in self.strategy_allocations:
            self.strategy_allocations[strategy] -= position_value
            if self.strategy_allocations[strategy] <= 0:
                del self.strategy_allocations[strategy]
                
        # Update margin
        self.used_margin -= position_value
        self.available_margin = self.total_capital - self.used_margin
        
        logger.info(
            f"Position removed: {strategy} ₹{position_value:,.0f}\n"
            f"Available margin: ₹{self.available_margin:,.0f}"
        )
        
    def update_position_price(self, position_id: str, current_price: float):
        """Update position's current price (doesn't affect margin)"""
        
        if position_id in self.positions:
            self.positions[position_id]['current_price'] = current_price
            
            # Calculate unrealized P&L
            position = self.positions[position_id]
            entry_price = self._extract(position, 'entry_price', 0.0) or 0.0
            quantity = self._extract(position, 'quantity', 0) or 0
            
            pnl = (current_price - entry_price) * quantity
            self.positions[position_id]['unrealized_pnl'] = pnl
            
    def get_exposure_report(self) -> Dict:
        """Get detailed exposure and allocation report"""
        
        total_unrealized_pnl = sum(
            p.get('unrealized_pnl', 0) for p in self.positions.values()
        )
        
        strategy_breakdown = {}
        for strategy, allocation in self.strategy_allocations.items():
            strategy_positions = [
                p for p in self.positions.values()
                if self._extract(p, 'strategy', 'unknown') or self._extract(p, 'strategy_name', 'unknown') == strategy
            ]
            
            strategy_pnl = sum(
                p.get('unrealized_pnl', 0) for p in strategy_positions
            )
            
            strategy_breakdown[strategy] = {
                'allocation': allocation,
                'allocation_percent': allocation / self.total_capital * 100,
                'num_positions': len(strategy_positions),
                'unrealized_pnl': strategy_pnl
            }
            
        return {
            'timestamp': datetime.now().isoformat(),
            'total_capital': self.total_capital,
            'used_margin': self.used_margin,
            'available_margin': self.available_margin,
            'utilization_percent': self.used_margin / self.total_capital * 100,
            'total_positions': len(self.positions),
            'total_unrealized_pnl': total_unrealized_pnl,
            'strategy_breakdown': strategy_breakdown,
            'limits': {
                'max_capital_utilization': self.max_capital_utilization * 100,
                'max_strategy_allocation': self.max_strategy_allocation * 100,
                'max_position_allocation': self.max_position_allocation * 100
            }
        }
        
    def is_over_concentrated(self) -> tuple[bool, Optional[str]]:
        """Check if portfolio is over-concentrated"""
        
        # Check overall utilization
        utilization = self.used_margin / self.total_capital
        if utilization > self.max_capital_utilization:
            return True, f"Over-utilized: {utilization*100:.1f}%"
            
        # Check strategy concentration
        for strategy, allocation in self.strategy_allocations.items():
            strategy_percent = allocation / self.total_capital
            if strategy_percent > self.max_strategy_allocation:
                return True, (
                    f"Strategy '{strategy}' over-allocated: {strategy_percent*100:.1f}%"
                )
                
        return False, None
        
    def can_add_position(self, position_value: float, strategy: str) -> bool:
        """Check if new position can be added"""
        checks_passed, _ = self._check_allocation_limits(strategy, position_value)
        return checks_passed
        
    def get_available_capital(self, strategy: str) -> float:
        """Get available capital for a specific strategy"""
        
        # Check overall availability
        overall_available = self.total_capital * self.max_capital_utilization - self.used_margin

        # Check strategy-specific availability
        current_strategy_allocation = self.strategy_allocations.get(strategy, 0)
        strategy_available = (
            self.total_capital * self.max_strategy_allocation - current_strategy_allocation
        )
        
        # Return the smaller of the two
        return max(0, min(overall_available, strategy_available))

    def get_all_positions(self) -> List:
        """Return list of tracked positions."""
        return list(self.positions.values())

    def get_used_margin(self) -> float:
        """Return currently used margin."""
        return self.used_margin

    def get_capital_utilization(self) -> float:
        """Return utilization percentage of capital."""
        if self.total_capital <= 0:
            return 0.0
        return (self.used_margin / self.total_capital) * 100
