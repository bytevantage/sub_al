"""
State Builder - Combines features and portfolio state
"""

import numpy as np
from datetime import datetime
from typing import Dict, Optional

from features.greeks_engine import GreeksEngine
from backend.core.logger import get_logger

logger = get_logger(__name__)


class StateBuilder:
    """Builds complete state vector for SAC agent"""
    
    def __init__(self):
        self.greeks_engine = GreeksEngine()
        self.state_dim = 35
        self.last_state = None
        
    def build_state(
        self,
        symbol: str = "NIFTY",
        timestamp: Optional[datetime] = None,
        portfolio_delta: float = 0.0,
        portfolio_gamma: float = 0.0,
        portfolio_vega: float = 0.0
    ) -> np.ndarray:
        """
        Build complete 35-dimensional state vector
        
        Args:
            symbol: Symbol to analyze
            timestamp: Current timestamp
            portfolio_delta: Current portfolio delta
            portfolio_gamma: Current portfolio gamma
            portfolio_vega: Current portfolio vega
            
        Returns:
            np.ndarray of shape (35,)
        """
        try:
            # Extract market features
            state = self.greeks_engine.extract_state_vector(symbol, timestamp)
            
            # Update portfolio Greeks (last 3 features)
            state[-3] = portfolio_delta / 1000  # Normalize
            state[-2] = portfolio_gamma / 100
            state[-1] = portfolio_vega / 1000
            
            # Store last state
            self.last_state = state
            
            return state
            
        except Exception as e:
            logger.error(f"Error building state: {e}")
            # Return last state or zeros
            return self.last_state if self.last_state is not None else np.zeros(self.state_dim)
    
    def get_market_regime(self, state: np.ndarray) -> str:
        """
        Determine current market regime from state
        
        Returns:
            'LOW_VOL', 'NORMAL', 'HIGH_VOL', 'CRISIS'
        """
        vix_percentile = state[4]  # Feature 4 is VIX percentile
        
        if vix_percentile > 0.9:
            return 'CRISIS'
        elif vix_percentile > 0.7:
            return 'HIGH_VOL'
        elif vix_percentile < 0.3:
            return 'LOW_VOL'
        else:
            return 'NORMAL'
    
    def should_pause_trading(self, state: np.ndarray) -> bool:
        """
        Check if trading should be paused based on state
        
        Pause conditions:
        - VIX > 28 (very high volatility)
        - |Net GEX| > threshold (extreme gamma exposure)
        - |Portfolio Delta| > threshold (too directional)
        """
        vix_percentile = state[4]
        gex_total = state[11]
        portfolio_delta = state[32]
        
        # Pause if VIX is extremely high
        if vix_percentile > 0.95:
            logger.warning("Trading paused: Extreme VIX levels")
            return True
        
        # Pause if GEX is extreme
        if abs(gex_total) > 5.0:  # Billions
            logger.warning(f"Trading paused: Extreme GEX = {gex_total:.2f}B")
            return True
        
        # Pause if portfolio is too directional
        if abs(portfolio_delta) > 5.0:  # Normalized
            logger.warning(f"Trading paused: Extreme portfolio delta = {portfolio_delta:.2f}")
            return True
        
        return False
    
    def get_risk_multiplier(self, state: np.ndarray) -> float:
        """
        Get risk multiplier based on market conditions
        
        Returns:
            Risk multiplier (0.5 to 1.5)
        """
        regime = self.get_market_regime(state)
        
        multipliers = {
            'LOW_VOL': 1.2,      # Increase size in low vol
            'NORMAL': 1.0,       # Normal size
            'HIGH_VOL': 0.7,     # Reduce size in high vol
            'CRISIS': 0.5        # Minimum size in crisis
        }
        
        return multipliers.get(regime, 1.0)
