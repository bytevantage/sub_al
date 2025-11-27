"""
Settings API - Manage trading configuration, risk parameters, strategy weights
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# ============================================================================
# OPTIMUM DEFAULT SETTINGS
# ============================================================================

DEFAULTS = {
    "trading": {
        "capital": 100000.0,  # ₹1,00,000 starting capital
        "max_trades_per_day": 999,  # Unlimited during paper trading
        "max_positions": 5,  # Maximum concurrent positions
        "trade_amount": 20000.0,  # ₹20,000 per trade
        "commission": 40.0  # ₹40 per trade (₹20 entry + ₹20 exit)
    },
    "risk": {
        "max_drawdown_pct": 10.0,  # 10% max drawdown
        "daily_loss_limit_pct": 5.0,  # 5% daily loss limit
        "per_trade_risk_pct": 2.0,  # 2% risk per trade
        "stop_loss_type": "fixed",  # fixed, trailing, or atr
        "position_sizing_method": "fixed"  # fixed or kelly
    },
    "strategies": {
        # OI Analysis Strategies
        "oi_buildup": 85,
        "oi_unwinding": 80,
        "max_pain": 75,
        "pcr_analysis": 70,
        
        # Sentiment Strategies
        "sentiment_flow": 85,
        "volume_surge": 80,
        "institutional_activity": 75,
        
        # Greeks Strategies
        "delta_hedging": 90,
        "gamma_scalping": 85,
        "vega_vanna": 80,
        
        # Institutional Flow
        "fii_dii": 85,
        "block_deals": 80,
        "bulk_deals": 75,
        
        # Spread Strategies
        "bull_spread": 70,
        "bear_spread": 70,
        "iron_condor": 65,
        
        # Intraday Strategies
        "vwap": 75,
        "pivot": 70,
        "momentum": 75,
        
        # Cross-Asset
        "vix_correlation": 80
    },
    "ml": {
        "min_ml_score": 0.65,  # 65% minimum ML confidence
        "min_strategy_strength": 70.0,  # 70% minimum strategy strength
        "min_strategies_agree": 3,  # At least 3 strategies must agree
        "retrain_frequency_days": 7  # Retrain ML model weekly
    },
    "system": {
        "refresh_rate_seconds": 2,  # Dashboard refresh every 2 seconds
        "log_level": "INFO",  # DEBUG, INFO, WARNING, ERROR
        "trading_mode": "paper"  # paper or live
    }
}

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class TradingConfig(BaseModel):
    capital: float = Field(ge=10000, description="Starting capital (min ₹10,000)")
    max_trades_per_day: int = Field(ge=1, le=9999, description="Max trades per day")
    max_positions: int = Field(ge=1, le=50, description="Max concurrent positions")
    trade_amount: float = Field(ge=1000, description="Amount per trade")
    commission: float = Field(ge=0, description="Commission per trade")

class RiskConfig(BaseModel):
    max_drawdown_pct: float = Field(ge=1, le=50, description="Max drawdown %")
    daily_loss_limit_pct: float = Field(ge=0.5, le=20, description="Daily loss limit %")
    per_trade_risk_pct: float = Field(ge=0.5, le=10, description="Per trade risk %")
    stop_loss_type: str = Field(pattern="^(fixed|trailing|atr)$", description="Stop loss type")
    position_sizing_method: str = Field(pattern="^(fixed|kelly)$", description="Position sizing")

class StrategyWeights(BaseModel):
    # OI Analysis
    oi_buildup: int = Field(ge=0, le=100)
    oi_unwinding: int = Field(ge=0, le=100)
    max_pain: int = Field(ge=0, le=100)
    pcr_analysis: int = Field(ge=0, le=100)
    
    # Sentiment
    sentiment_flow: int = Field(ge=0, le=100)
    volume_surge: int = Field(ge=0, le=100)
    institutional_activity: int = Field(ge=0, le=100)
    
    # Greeks
    delta_hedging: int = Field(ge=0, le=100)
    gamma_scalping: int = Field(ge=0, le=100)
    vega_vanna: int = Field(ge=0, le=100)
    
    # Institutional
    fii_dii: int = Field(ge=0, le=100)
    block_deals: int = Field(ge=0, le=100)
    bulk_deals: int = Field(ge=0, le=100)
    
    # Spreads
    bull_spread: int = Field(ge=0, le=100)
    bear_spread: int = Field(ge=0, le=100)
    iron_condor: int = Field(ge=0, le=100)
    
    # Intraday
    vwap: int = Field(ge=0, le=100)
    pivot: int = Field(ge=0, le=100)
    momentum: int = Field(ge=0, le=100)
    
    # Cross-Asset
    vix_correlation: int = Field(ge=0, le=100)

class MLConfig(BaseModel):
    min_ml_score: float = Field(ge=0, le=1, description="Min ML confidence (0-1)")
    min_strategy_strength: float = Field(ge=0, le=100, description="Min strategy strength %")
    min_strategies_agree: int = Field(ge=1, le=20, description="Min strategies agreeing")
    retrain_frequency_days: int = Field(ge=1, le=365, description="Retrain frequency (days)")

class SystemConfig(BaseModel):
    refresh_rate_seconds: int = Field(ge=1, le=60, description="Dashboard refresh rate")
    log_level: str = Field(pattern="^(DEBUG|INFO|WARNING|ERROR)$", description="Log level")
    trading_mode: str = Field(pattern="^(paper|live)$", description="Trading mode")

class Settings(BaseModel):
    trading: TradingConfig
    risk: RiskConfig
    strategies: StrategyWeights
    ml: MLConfig
    system: SystemConfig

# ============================================================================
# IN-MEMORY STORAGE (Replace with database later)
# ============================================================================

current_settings = Settings(**DEFAULTS)

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("")
async def get_settings():
    """
    Get current user settings
    
    Returns all trading, risk, strategy, ML, and system configuration
    """
    try:
        return current_settings.dict()
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
async def save_settings(settings: Settings):
    """
    Save user settings
    
    Validates and saves all configuration parameters
    """
    global current_settings
    
    try:
        # Validate settings
        settings_dict = settings.dict()
        
        # Additional business logic validation
        if settings.trading.trade_amount > settings.trading.capital:
            raise HTTPException(
                status_code=400,
                detail="Trade amount cannot exceed capital"
            )
        
        if settings.risk.per_trade_risk_pct > settings.risk.max_drawdown_pct:
            raise HTTPException(
                status_code=400,
                detail="Per trade risk cannot exceed max drawdown"
            )
        
        # Count enabled strategies
        enabled_strategies = sum(1 for w in settings.strategies.dict().values() if w > 0)
        if enabled_strategies < settings.ml.min_strategies_agree:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough enabled strategies. Need at least {settings.ml.min_strategies_agree}, got {enabled_strategies}"
            )
        
        # Save settings (in-memory for now)
        current_settings = settings
        
        logger.info("✓ Settings saved successfully")
        
        return {
            "status": "success",
            "message": "Settings saved successfully",
            "settings": settings_dict
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset")
async def reset_settings():
    """
    Reset all settings to optimum defaults
    
    Restores factory default configuration for all parameters
    """
    global current_settings
    
    try:
        current_settings = Settings(**DEFAULTS)
        
        logger.info("✓ Settings reset to defaults")
        
        return {
            "status": "success",
            "message": "Settings reset to optimum defaults",
            "settings": current_settings.dict()
        }
    except Exception as e:
        logger.error(f"Error resetting settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/defaults")
async def get_defaults():
    """
    Get factory default settings
    
    Returns the optimum default configuration without changing current settings
    """
    try:
        return DEFAULTS
    except Exception as e:
        logger.error(f"Error getting defaults: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export")
async def export_settings():
    """
    Export current settings as JSON
    
    Useful for backup or sharing configuration
    """
    try:
        return {
            "version": "1.0",
            "exported_at": __import__('datetime').now_ist().isoformat(),
            "settings": current_settings.dict()
        }
    except Exception as e:
        logger.error(f"Error exporting settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import")
async def import_settings(data: dict):
    """
    Import settings from JSON backup
    
    Validates and loads configuration from exported JSON
    """
    global current_settings
    
    try:
        if "settings" not in data:
            raise HTTPException(status_code=400, detail="Invalid import format")
        
        settings = Settings(**data["settings"])
        current_settings = settings
        
        logger.info("✓ Settings imported successfully")
        
        return {
            "status": "success",
            "message": "Settings imported successfully",
            "settings": settings.dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing settings: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid settings format: {str(e)}")

# ============================================================================
# HELPER FUNCTION TO GET CURRENT SETTINGS (for use by other modules)
# ============================================================================

def get_current_settings() -> Settings:
    """Get current settings for use in trading logic"""
    return current_settings
