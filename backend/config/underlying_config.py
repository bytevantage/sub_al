"""
Final Underlying Lock Configuration
NIFTY & SENSEX ONLY (21 NOV 2025)
"""

import random
from typing import Dict, List

# FINAL UNDERLYING LOCK – NIFTY & SENSEX ONLY
ALLOWED_UNDERLYINGS = ["NIFTY", "SENSEX"]

# Symbol mapping for broker compatibility
SYMBOL_MAPPING = {
    "NIFTY": "NSE:NIFTY50",      # or "NIFTY" depending on broker
    "SENSEX": "BSE:SENSEX",       # or "SENSEX"
    "INDEX": ["NIFTY", "SENSEX"]  # for option chains
}

# PCR source lock - use NIFTY PCR for both (99% of pros do this)
PCR_SOURCE = "NIFTY"

# Data sources configuration
DATA_SOURCES = {
    "pcr_oi": "NIFTY",
    "pcr_volume": "NIFTY",
    "india_vix": "INDIAVIX",
    "max_pain": "NIFTY",
    "iv_rank": "NIFTY"
}

# Stop loss percentages tuned for each underlying
STOP_LOSS_PCT = {
    "NIFTY": 0.18,   # 18% for NIFTY
    "SENSEX": 0.16   # 16% for SENSEX (moves slower)
}

# Strike rounding increments
STRIKE_ROUNDING = {
    "NIFTY": 50,     # NIFTY strikes in 50 increments
    "SENSEX": 100    # SENSEX strikes in 100 increments
}

# Strategy allocation weights
BASE_ALLOCATIONS = {
    "quantum_edge_v2": 0.25,
    "quantum_edge": 0.20,
    "default": 0.10,
    "gamma_scalping": 0.15,
    "vwap_deviation": 0.10,
    "iv_rank_trading": 0.10,
    "sac_ml_strategy": 0.10
}


class UnderlyingManager:
    """
    Manages underlying selection and configuration
    Ensures only NIFTY and SENSEX are traded
    """
    
    def __init__(self):
        self.current_underlying = None
        self.underlying_cycle = ["NIFTY", "SENSEX"]
        self.cycle_index = 0
    
    def get_allowed_underlyings(self) -> List[str]:
        """Get list of allowed underlyings"""
        return ALLOWED_UNDERLYINGS.copy()
    
    def is_allowed(self, symbol: str) -> bool:
        """Check if symbol is allowed for trading"""
        return symbol in ALLOWED_UNDERLYINGS
    
    def get_broker_symbol(self, symbol: str) -> str:
        """Get broker-specific symbol mapping"""
        return SYMBOL_MAPPING.get(symbol, symbol)
    
    def get_pcr_source(self) -> str:
        """Get PCR source (always NIFTY)"""
        return PCR_SOURCE
    
    def get_stop_loss_pct(self, underlying: str) -> float:
        """Get stop loss percentage for underlying"""
        return STOP_LOSS_PCT.get(underlying, 0.18)  # Default to NIFTY's 18%
    
    def get_strike_rounding(self, underlying: str) -> int:
        """Get strike rounding increment for underlying"""
        return STRIKE_ROUNDING.get(underlying, 50)  # Default to NIFTY's 50
    
    def round_strike(self, underlying: str, price: float) -> float:
        """Round strike price according to underlying's increment"""
        increment = self.get_strike_rounding(underlying)
        return round(price / increment) * increment
    
    def get_data_source(self, data_type: str) -> str:
        """Get data source for a given data type"""
        return DATA_SOURCES.get(data_type, "NIFTY")
    
    def cycle_underlying(self) -> str:
        """Cycle through allowed underlyings"""
        self.current_underlying = self.underlying_cycle[self.cycle_index]
        self.cycle_index = (self.cycle_index + 1) % len(self.underlying_cycle)
        return self.current_underlying
    
    def get_random_underlying(self) -> str:
        """Get a random allowed underlying"""
        return random.choice(ALLOWED_UNDERLYINGS)
    
    def set_underlying(self, underlying: str) -> bool:
        """Set specific underlying if allowed"""
        if self.is_allowed(underlying):
            self.current_underlying = underlying
            return True
        return False
    
    def get_current_underlying(self) -> str:
        """Get current underlying"""
        return self.current_underlying or self.get_random_underlying()
    
    def validate_strategy_config(self, strategy_config: Dict) -> Dict:
        """
        Validate and update strategy configuration to use only allowed underlyings
        """
        if "underlying" in strategy_config:
            underlying = strategy_config["underlying"]
            if not self.is_allowed(underlying):
                # Replace with allowed underlying
                strategy_config["underlying"] = self.get_random_underlying()
        
        # Ensure stop loss is appropriate for underlying
        underlying = strategy_config.get("underlying", "NIFTY")
        if "stop_loss_pct" in strategy_config:
            strategy_config["stop_loss_pct"] = self.get_stop_loss_pct(underlying)
        
        return strategy_config


# Global instance
underlying_manager = UnderlyingManager()
