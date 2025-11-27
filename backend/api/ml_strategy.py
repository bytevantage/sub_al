"""
ML and Strategy Management API
Endpoints for viewing strategy performance and triggering ML operations
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Optional
from backend.core.timezone_utils import now_ist
from datetime import datetime

from backend.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/ml-strategy", tags=["ML & Strategy"])

# Global state (set by main.py)
_app_state = {}


def set_ml_state(state: dict):
    """Set ML and strategy engine references"""
    global _app_state
    _app_state.update(state)


@router.get("/strategy-performance")
async def get_strategy_performance(lookback_days: int = 30):
    """
    Get performance metrics for all strategies
    
    Args:
        lookback_days: Number of days to analyze (default: 30)
        
    Returns:
        Dict mapping strategy_name to performance metrics
    """
    try:
        strategy_engine = _app_state.get('strategy_engine')
        
        if not strategy_engine:
            raise HTTPException(status_code=503, detail="Strategy engine not available")
        
        performance = await strategy_engine.analyze_strategy_performance(lookback_days)
        
        return {
            'status': 'success',
            'lookback_days': lookback_days,
            'analyzed_at': now_ist().isoformat(),
            'strategies': performance
        }
        
    except Exception as e:
        logger.error(f"Error getting strategy performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy-weights")
async def get_strategy_weights():
    """Get current weights for all strategies"""
    try:
        strategy_engine = _app_state.get('strategy_engine')
        
        if not strategy_engine:
            raise HTTPException(status_code=503, detail="Strategy engine not available")
        
        weights = strategy_engine.get_all_strategy_weights()
        
        return {
            'status': 'success',
            'weights': weights,
            'retrieved_at': now_ist().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting strategy weights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/adjust-weights")
async def adjust_strategy_weights(lookback_days: int = 30):
    """
    Manually trigger strategy weight adjustment based on performance
    
    Args:
        lookback_days: Number of days to analyze (default: 30)
        
    Returns:
        Dict with adjustment details for each strategy
    """
    try:
        strategy_engine = _app_state.get('strategy_engine')
        
        if not strategy_engine:
            raise HTTPException(status_code=503, detail="Strategy engine not available")
        
        logger.info(f"Manual weight adjustment triggered (lookback: {lookback_days} days)")
        
        adjustments = await strategy_engine.adjust_strategy_weights(lookback_days)
        
        # Count significant adjustments
        significant = sum(1 for a in adjustments.values() if abs(a.get('change', 0)) >= 5)
        
        return {
            'status': 'success',
            'adjusted_at': now_ist().isoformat(),
            'lookback_days': lookback_days,
            'total_strategies': len(adjustments),
            'significant_adjustments': significant,
            'adjustments': adjustments
        }
        
    except Exception as e:
        logger.error(f"Error adjusting strategy weights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train-model")
async def train_model_manually():
    """
    Manually trigger ML model training
    
    Returns:
        Training status and results
    """
    try:
        eod_training_job = _app_state.get('eod_training_job')
        
        if not eod_training_job:
            raise HTTPException(status_code=503, detail="Training job not available")
        
        logger.info("Manual ML training triggered")
        
        await eod_training_job.run_manual_training()
        
        return {
            'status': 'success',
            'message': 'ML model training completed',
            'trained_at': now_ist().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error training model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/eod-training-status")
async def get_eod_training_status():
    """Get status of EOD training job"""
    try:
        eod_training_job = _app_state.get('eod_training_job')
        
        if not eod_training_job:
            raise HTTPException(status_code=503, detail="Training job not available")
        
        status = eod_training_job.get_status()
        
        return {
            'status': 'success',
            'training_job': status
        }
        
    except Exception as e:
        logger.error(f"Error getting training status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-info")
async def get_model_info():
    """Get information about the current ML model"""
    try:
        model_manager = _app_state.get('model_manager')
        
        if not model_manager:
            raise HTTPException(status_code=503, detail="Model manager not available")
        
        info = model_manager.get_model_info()
        
        return {
            'status': 'success',
            'model': info,
            'retrieved_at': now_ist().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting model info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
