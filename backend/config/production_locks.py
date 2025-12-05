"""
Production Hard Locks - Never change without written justification
These settings are locked for production stability and risk management
"""

from datetime import time
from typing import Dict, Any

# ==============================================
# PRODUCTION HARD LOCKS - DO NOT MODIFY
# ==============================================

PRODUCTION_LOCKS = {
    # Risk Management Locks
    "max_concurrent_strategies": 3,  # SAC can pick max 3 strategies
    "max_daily_loss_percent": -5.0,  # Full shutdown at -5% daily loss (spec)
    "max_position_size_per_strike": 4,  # Max 4 lots per strike (prevents over-exposure)
    "force_eod_exit_time": time(15, 25),  # Force exit at 15:25 IST (not 15:29)
    
    # Position Limits
    "max_total_positions": 10,  # Maximum total open positions
    "max_positions_per_symbol": 6,  # Max positions per NIFTY/SENSEX
    "max_risk_per_trade_percent": 1.5,  # Absolute max risk per trade
    
    # Trading Session Locks
    "market_open_time": time(9, 15),  # 9:15 AM IST
    "market_close_time": time(15, 25),  # 3:25 PM IST (trading stops)
    "no_new_orders_after": time(16, 20),  # No new orders after 16:20 (temporarily extended for debugging)
    
    # Order Execution Locks
    "max_order_size_lots": 10,  # Max order size in lots
    "min_order_interval_seconds": 5,  # Minimum time between orders
    "max_orders_per_minute": 12,  # Rate limit
    
    # Capital Management
    "max_capital_usage_percent": 95,  # Keep 5% cash buffer
    "min_capital_for_trade": 50000,  # Minimum capital required
    
    # Strategy Weights (normalized)
    "max_strategy_weight_percent": 45,  # Max weight for any single strategy
    "min_strategy_weight_percent": 5,  # Min weight for active strategies
    
    # Technical Indicator Locks
    "min_rsi_for_long": 55,  # Minimum RSI for long entries
    "max_rsi_for_short": 45,  # Maximum RSI for short entries
    "min_vix_for_volatility_strategies": 18,  # Minimum VIX for vol strategies
    "max_vix_for_normal_trading": 35,  # Max VIX for normal strategies
    
    # Option Chain Filters
    "min_open_interest": 50000,  # Minimum OI for liquidity
    "min_volume_lots": 100,  # Minimum volume
    "max_strike_distance_pct": 10,  # Max distance from ATM in %
    
    # ML Model Locks
    "min_ml_confidence": 0.65,  # Minimum ML confidence for trades
    "max_ml_signals_per_minute": 5,  # Rate limit ML signals
    
    # Monitoring Locks
    "max_drawdown_percent": -5.0,  # Max system drawdown
    "max_consecutive_losses": 5,  # Stop after 5 consecutive losses
    "position_reconciliation_interval_seconds": 60,  # Check every 60 seconds
}

# ==============================================
# VALIDATION FUNCTIONS
# ==============================================

def validate_production_config(config: Dict[str, Any]) -> Dict[str, str]:
    """
    Validate config against production locks
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        Dict of validation errors (empty if valid)
    """
    errors = {}
    
    # Check risk limits
    if config.get("max_concurrent_strategies", 0) > PRODUCTION_LOCKS["max_concurrent_strategies"]:
        errors["max_concurrent_strategies"] = f"Exceeds production limit: {PRODUCTION_LOCKS['max_concurrent_strategies']}"
    
    if config.get("max_daily_loss_percent", 0) < PRODUCTION_LOCKS["max_daily_loss_percent"]:
        errors["max_daily_loss_percent"] = f"Below production limit: {PRODUCTION_LOCKS['max_daily_loss_percent']}"
    
    if config.get("max_position_size_per_strike", 0) > PRODUCTION_LOCKS["max_position_size_per_strike"]:
        errors["max_position_size_per_strike"] = f"Exceeds production limit: {PRODUCTION_LOCKS['max_position_size_per_strike']}"
    
    # Check timing
    eod_exit = config.get("force_eod_exit_time")
    if eod_exit and eod_exit > PRODUCTION_LOCKS["force_eod_exit_time"]:
        errors["force_eod_exit_time"] = f"Must be <= {PRODUCTION_LOCKS['force_eod_exit_time']}"
    
    # Check strategy weights
    for strategy, weight in config.get("strategy_weights", {}).items():
        if weight > PRODUCTION_LOCKS["max_strategy_weight_percent"]:
            errors[f"strategy_weight_{strategy}"] = f"Exceeds production limit: {PRODUCTION_LOCKS['max_strategy_weight_percent']}"
    
    return errors

def apply_production_locks(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply production locks to configuration
    
    Args:
        config: Original configuration
        
    Returns:
        Configuration with production locks applied
    """
    locked_config = config.copy()
    
    # Apply hard locks
    for key, value in PRODUCTION_LOCKS.items():
        if key in ["max_concurrent_strategies", "max_daily_loss_percent", 
                  "max_position_size_per_strike", "force_eod_exit_time"]:
            locked_config[key] = value
    
    # Cap values at production limits
    locked_config["max_concurrent_strategies"] = min(
        locked_config.get("max_concurrent_strategies", 3), 
        PRODUCTION_LOCKS["max_concurrent_strategies"]
    )
    
    locked_config["max_position_size_per_strike"] = min(
        locked_config.get("max_position_size_per_strike", 4), 
        PRODUCTION_LOCKS["max_position_size_per_strike"]
    )
    
    # Ensure EOD exit is not later than production limit
    current_eod = locked_config.get("force_eod_exit_time", time(15, 25))
    if current_eod > PRODUCTION_LOCKS["force_eod_exit_time"]:
        locked_config["force_eod_exit_time"] = PRODUCTION_LOCKS["force_eod_exit_time"]
    
    return locked_config

# ==============================================
# PRODUCTION MODE CHECK
# ==============================================

def is_production_mode() -> bool:
    """Check if system is running in production mode"""
    import os
    return os.getenv("ENVIRONMENT", "development").lower() == "production"

def get_production_status() -> Dict[str, Any]:
    """Get current production lock status"""
    return {
        "production_mode": is_production_mode(),
        "locks_active": PRODUCTION_LOCKS,
        "validation_required": True,
        "last_updated": "2025-11-21T16:00:00",
        "version": "v1.0.0-production"
    }
