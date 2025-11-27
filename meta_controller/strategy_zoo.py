"""
Strategy Zoo - Executes allocated strategies with position sizing
"""

import asyncio
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass

from meta_controller.strategy_clustering import META_GROUPS, get_meta_group
from backend.core.logger import get_logger
from backend.core.config import config

logger = get_logger(__name__)


@dataclass
class StrategySignal:
    """Signal from a strategy"""
    strategy_name: str
    meta_group: int
    symbol: str
    direction: str  # CALL or PUT
    strike: float
    entry_price: float
    strength: float
    confidence: float
    quantity: int
    stop_loss: float
    target_price: float


class StrategyZoo:
    """
    Manages and executes all 25 strategies with dynamic allocation
    """
    
    def __init__(self, portfolio_value: float = 1000000):
        self.portfolio_value = portfolio_value
        self.max_leverage = 4.0
        self.risk_per_decision = 0.005  # 0.5% risk cap per decision
        self.strategies = self._initialize_strategies()
        self.active_positions = []
        
        logger.info(f"Strategy Zoo initialized with {len(self.strategies)} strategies")
    
    def _initialize_strategies(self) -> Dict:
        """Initialize all strategy instances"""
        strategies = {}
        
        # Import all strategies
        try:
            from backend.strategies.quantum_edge import QuantumEdgeStrategy
            from backend.strategies.gamma_scalping import GammaScalpingStrategy
            from backend.strategies.volatility_harvesting import VolatilityHarvestingStrategy
            from backend.strategies.vwap_deviation import VWAPDeviationStrategy
            from backend.strategies.oi_accumulation import OIAccumulationStrategy
            from backend.strategies.pcr_reversal import PCRReversalStrategy
            
            # Add more strategy imports as needed
            
            strategies['QuantumEdge'] = QuantumEdgeStrategy(weight=90)
            strategies['GammaScalping'] = GammaScalpingStrategy(weight=80)
            strategies['VolatilityHarvesting'] = VolatilityHarvestingStrategy(weight=75)
            strategies['VWAPDeviation'] = VWAPDeviationStrategy(weight=70)
            strategies['OIAccumulation'] = OIAccumulationStrategy(weight=75)
            strategies['PCRReversal'] = PCRReversalStrategy(weight=70)
            
            # Add more strategies as they become available
            
        except Exception as e:
            logger.error(f"Error loading strategies: {e}")
        
        return strategies
    
    async def generate_signals(
        self,
        market_data: Dict,
        allocations: np.ndarray,
        timestamp: datetime
    ) -> List[StrategySignal]:
        """
        Generate signals from all strategies based on allocations
        
        Args:
            market_data: Current market state
            allocations: 9-dim allocation vector from SAC
            timestamp: Current timestamp
            
        Returns:
            List of StrategySignal objects
        """
        all_signals = []
        
        # Generate signals from each strategy
        for strategy_name, strategy_obj in self.strategies.items():
            try:
                # Get meta-group for this strategy
                meta_group = get_meta_group(strategy_name)
                
                # Get allocation for this meta-group
                group_allocation = allocations[meta_group]
                
                # Skip if allocation is too low
                if group_allocation < 0.01:
                    continue
                
                # Generate signals
                signals = await strategy_obj.analyze(market_data)
                
                # Convert to StrategySignal objects with position sizing
                for signal in signals:
                    strategy_signal = self._create_strategy_signal(
                        signal,
                        strategy_name,
                        meta_group,
                        group_allocation
                    )
                    
                    if strategy_signal:
                        all_signals.append(strategy_signal)
                        
            except Exception as e:
                logger.error(f"Error generating signals from {strategy_name}: {e}")
        
        # Rank and filter signals
        ranked_signals = self._rank_signals(all_signals, allocations)
        
        return ranked_signals
    
    def _create_strategy_signal(
        self,
        signal,
        strategy_name: str,
        meta_group: int,
        allocation: float
    ) -> StrategySignal:
        """Convert strategy signal to StrategySignal with position sizing"""
        try:
            # Calculate position size based on allocation and risk
            max_risk_amount = self.portfolio_value * self.risk_per_decision
            allocated_capital = self.portfolio_value * allocation
            
            # Calculate quantity based on risk
            risk_per_contract = abs(signal.entry_price - signal.stop_loss) * 50  # 50 lot size
            
            if risk_per_contract > 0:
                max_contracts = int(max_risk_amount / risk_per_contract)
                allocated_contracts = int(allocated_capital / (signal.entry_price * 50))
                
                quantity = min(max_contracts, allocated_contracts)
                quantity = max(25, min(quantity, 500))  # Min 25, max 500
            else:
                quantity = 75  # Default 1 lot
            
            return StrategySignal(
                strategy_name=strategy_name,
                meta_group=meta_group,
                symbol=signal.symbol,
                direction=signal.direction,
                strike=signal.strike,
                entry_price=signal.entry_price,
                strength=signal.strength,
                confidence=getattr(signal, 'ml_confidence', signal.strength / 100),
                quantity=quantity,
                stop_loss=signal.stop_loss,
                target_price=signal.target_price
            )
            
        except Exception as e:
            logger.error(f"Error creating strategy signal: {e}")
            return None
    
    def _rank_signals(
        self,
        signals: List[StrategySignal],
        allocations: np.ndarray
    ) -> List[StrategySignal]:
        """
        Rank and filter signals based on strength and allocations
        
        Returns top N signals ensuring:
        - No more than 5 total positions
        - Diversification across meta-groups
        - Highest strength signals prioritized
        """
        if not signals:
            return []
        
        # Score each signal
        scored_signals = []
        for signal in signals:
            # Composite score: strength * allocation * confidence
            score = (signal.strength / 100) * allocations[signal.meta_group] * signal.confidence
            scored_signals.append((score, signal))
        
        # Sort by score descending
        scored_signals.sort(key=lambda x: x[0], reverse=True)
        
        # Select top signals with diversification
        selected_signals = []
        group_counts = {i: 0 for i in range(9)}
        max_positions = 5
        max_per_group = 2
        
        for score, signal in scored_signals:
            # Check limits
            if len(selected_signals) >= max_positions:
                break
            
            if group_counts[signal.meta_group] >= max_per_group:
                continue
            
            selected_signals.append(signal)
            group_counts[signal.meta_group] += 1
        
        logger.info(f"Selected {len(selected_signals)} signals from {len(signals)} candidates")
        
        return selected_signals
    
    def calculate_portfolio_greeks(self) -> Tuple[float, float, float]:
        """
        Calculate total portfolio Greeks
        
        Returns:
            (delta, gamma, vega)
        """
        total_delta = 0.0
        total_gamma = 0.0
        total_vega = 0.0
        
        for position in self.active_positions:
            # Placeholder - should use actual option Greeks
            total_delta += position.get('delta', 0) * position.get('quantity', 0)
            total_gamma += position.get('gamma', 0) * position.get('quantity', 0)
            total_vega += position.get('vega', 0) * position.get('quantity', 0)
        
        return total_delta, total_gamma, total_vega
    
    def check_leverage(self) -> float:
        """Check current portfolio leverage"""
        total_exposure = sum(
            pos.get('entry_price', 0) * pos.get('quantity', 0) * 50
            for pos in self.active_positions
        )
        
        leverage = total_exposure / self.portfolio_value
        
        if leverage > self.max_leverage:
            logger.warning(f"Leverage {leverage:.2f}x exceeds max {self.max_leverage}x")
        
        return leverage
    
    def get_portfolio_allocation(self) -> np.ndarray:
        """Get current portfolio allocation across meta-groups"""
        allocation = np.zeros(9)
        
        total_value = sum(
            pos.get('current_value', 0)
            for pos in self.active_positions
        )
        
        if total_value == 0:
            return allocation
        
        for position in self.active_positions:
            group = position.get('meta_group', 0)
            value = position.get('current_value', 0)
            allocation[group] += value / total_value
        
        return allocation
