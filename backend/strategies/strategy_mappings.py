"""
Strategy Mappings
Provides strategy name normalization and allocation mappings
"""

from typing import Dict
import re

# Default strategy allocations based on config.yaml
DEFAULT_STRATEGY_ALLOCATIONS = {
    "Quantum Edge V2": 25.0,
    "Quantum Edge": 20.0,
    "Default ORB": 10.0,
    "Gamma Scalping": 15.0,
    "VWAP Deviation": 10.0,
    "IV Rank Trading": 10.0,
    # Fallback for unknown strategies
    "default": 10.0
}

def normalize_strategy_name(strategy_name: str) -> str:
    """
    Normalize strategy name to match the standard naming convention
    
    Args:
        strategy_name: Raw strategy name
        
    Returns:
        Normalized strategy name
    """
    if not strategy_name:
        return "default"
    
    # Convert to string and strip whitespace
    name = str(strategy_name).strip()
    
    # Common normalization patterns
    normalized_mappings = {
        # Quantum Edge variations
        "quantum_edge": "Quantum Edge",
        "quantumedge": "Quantum Edge",
        "quantum-edge": "Quantum Edge",
        "quantum edge": "Quantum Edge",
        "quantum_edge_v2": "Quantum Edge V2",
        "quantumedgev2": "Quantum Edge V2",
        "quantum-edge-v2": "Quantum Edge V2",
        "quantum edge v2": "Quantum Edge V2",
        
        # Default ORB variations
        "default_orb": "Default ORB",
        "defaultorb": "Default ORB",
        "default-orb": "Default ORB",
        "default orb": "Default ORB",
        "default": "Default ORB",
        
        # Gamma Scalping variations
        "gamma_scalping": "Gamma Scalping",
        "gammascalping": "Gamma Scalping",
        "gamma-scalping": "Gamma Scalping",
        "gamma scalping": "Gamma Scalping",
        
        # VWAP Deviation variations
        "vwap_deviation": "VWAP Deviation",
        "vwapdeviation": "VWAP Deviation",
        "vwap-deviation": "VWAP Deviation",
        "vwap deviation": "VWAP Deviation",
        
        # IV Rank Trading variations
        "iv_rank_trading": "IV Rank Trading",
        "ivranktrading": "IV Rank Trading",
        "iv-rank-trading": "IV Rank Trading",
        "iv rank trading": "IV Rank Trading",
    }
    
    # Convert to lowercase for matching
    key = re.sub(r'[^a-z0-9]', '_', name.lower())
    
    # Return mapped name or original if not found
    return normalized_mappings.get(key, name)

def get_strategy_allocation(strategy_name: str) -> float:
    """
    Get allocation percentage for a strategy
    
    Args:
        strategy_name: Strategy name (will be normalized)
        
    Returns:
        Allocation percentage
    """
    normalized_name = normalize_strategy_name(strategy_name)
    
    # Return allocation from defaults or fallback to 10%
    return DEFAULT_STRATEGY_ALLOCATIONS.get(normalized_name, DEFAULT_STRATEGY_ALLOCATIONS["default"])

def update_strategy_allocation(strategy_name: str, allocation: float):
    """
    Update allocation for a strategy
    
    Args:
        strategy_name: Strategy name (will be normalized)
        allocation: New allocation percentage
    """
    normalized_name = normalize_strategy_name(strategy_name)
    DEFAULT_STRATEGY_ALLOCATIONS[normalized_name] = allocation

def get_all_strategy_allocations() -> Dict[str, float]:
    """
    Get all strategy allocations
    
    Returns:
        Dictionary mapping strategy names to allocations
    """
    return DEFAULT_STRATEGY_ALLOCATIONS.copy()

def load_strategy_config_from_yaml(config_path: str = "config/config.yaml"):
    """
    Load strategy allocations from YAML config file
    
    Args:
        config_path: Path to config file
    """
    try:
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        if 'strategies' in config:
            for strategy in config['strategies']:
                name = strategy.get('name', '').strip()
                allocation = strategy.get('allocation_base', 10.0)
                if name:
                    normalized_name = normalize_strategy_name(name)
                    DEFAULT_STRATEGY_ALLOCATIONS[normalized_name] = allocation
                    
    except Exception as e:
        # Fallback to defaults if config loading fails
        print(f"Warning: Could not load strategy config from {config_path}: {e}")

# Load config on module import
try:
    load_strategy_config_from_yaml()
except:
    pass  # Use defaults if config loading fails
