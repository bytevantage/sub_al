"""
Aggressive Mode API
Toggle aggressive trading mode with enhanced risk/reward parameters
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict
from backend.core.timezone_utils import now_ist
from datetime import datetime

from backend.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/aggressive-mode", tags=["Aggressive Mode"])

# Global state (set by main.py)
_app_state = {}

# Aggressive mode flag
aggressive_mode_enabled = False


def set_aggressive_state(state: dict):
    """Set aggressive mode state references"""
    global _app_state
    _app_state.update(state)


class AggressiveModeToggle(BaseModel):
    enabled: bool
    reason: str = ""


@router.post("/toggle")
async def toggle_aggressive_mode(request: AggressiveModeToggle):
    """
    Toggle aggressive trading mode
    
    When enabled:
    - Strategy weights boosted for high-conviction strategies
    - ML-driven position sizing increases risk per trade
    - Volatility harvesting strategies prioritized
    """
    global aggressive_mode_enabled
    
    try:
        aggressive_mode_enabled = request.enabled
        
        # Update strategy engine if available
        strategy_engine = _app_state.get('strategy_engine')
        if strategy_engine and hasattr(strategy_engine, 'aggressive_mode'):
            strategy_engine.aggressive_mode.enabled = request.enabled
            
            # Apply weight adjustments
            if request.enabled:
                strategy_engine._apply_aggressive_mode_if_enabled()
                logger.warning(f"⚡ AGGRESSIVE MODE ENABLED: {request.reason}")
            else:
                # Reset weights to default
                for strategy in strategy_engine.strategies:
                    strategy.weight = strategy.default_weight
                logger.info(f"Aggressive mode disabled: {request.reason}")
        
        # Update risk manager if available
        risk_manager = _app_state.get('risk_manager')
        if risk_manager:
            risk_manager.aggressive_mode_enabled = request.enabled
        
        return {
            "status": "success",
            "aggressive_mode": request.enabled,
            "timestamp": now_ist().isoformat(),
            "reason": request.reason
        }
        
    except Exception as e:
        logger.error(f"Error toggling aggressive mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_aggressive_mode_status():
    """Get current aggressive mode status"""
    try:
        strategy_engine = _app_state.get('strategy_engine')
        engine_enabled = False
        boost_map = {}
        
        if strategy_engine and hasattr(strategy_engine, 'aggressive_mode'):
            engine_enabled = strategy_engine.aggressive_mode.enabled
            boost_map = strategy_engine.aggressive_mode.boost_map
        
        return {
            "status": "success",
            "aggressive_mode_enabled": aggressive_mode_enabled,
            "strategy_engine_enabled": engine_enabled,
            "boost_map": boost_map,
            "timestamp": now_ist().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting aggressive mode status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
