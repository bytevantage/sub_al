"""
Simple Production Lock API
One-click production lock with basic functionality
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/production", tags=["production"])

@router.post("/lock")
async def activate_production_lock():
    """
    Activate production lock - simple version
    
    Returns:
        Dict with lock status
    """
    try:
        # Check if already in production mode
        if os.getenv("ENVIRONMENT", "development").lower() == "production":
            return {
                "status": "already_locked",
                "message": "System is already in production mode",
                "timestamp": datetime.now().isoformat()
            }
        
        # Set environment variable for production mode
        os.environ["ENVIRONMENT"] = "production"
        
        # Create production lock file
        lock_file = "/app/.production_lock"
        lock_data = {
            "locked": True,
            "locked_at": datetime.now().isoformat(),
            "version": "v1.0.0-production"
        }
        
        import json
        with open(lock_file, 'w') as f:
            json.dump(lock_data, f, indent=2)
        
        logger.warning("🔒 PRODUCTION LOCK ACTIVATED - Configuration frozen")
        
        return {
            "status": "locked",
            "message": "Production lock activated successfully",
            "locked_at": lock_data["locked_at"],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error activating production lock: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_production_lock_status():
    """Get current production lock status"""
    try:
        is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
        
        status = {
            "production_mode": is_production,
            "environment": os.getenv("ENVIRONMENT", "development"),
            "timestamp": datetime.now().isoformat()
        }
        
        # Check if lock file exists
        lock_file = "/app/.production_lock"
        if os.path.exists(lock_file):
            import json
            with open(lock_file, 'r') as f:
                lock_data = json.load(f)
            status["lock_file_exists"] = True
            status["lock_data"] = lock_data
        else:
            status["lock_file_exists"] = False
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting production status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/unlock")
async def unlock_production():
    """
    Unlock production (emergency only)
    
    Returns:
        Dict with unlock status
    """
    try:
        # Remove production lock file
        lock_file = "/app/.production_lock"
        if os.path.exists(lock_file):
            os.remove(lock_file)
        
        # Reset environment
        os.environ["ENVIRONMENT"] = "development"
        
        logger.warning("⚠️ PRODUCTION LOCK REMOVED - System unlocked")
        
        return {
            "status": "unlocked",
            "message": "Production lock removed successfully",
            "timestamp": datetime.now().isoformat(),
            "warning": "System is now in development mode"
        }
        
    except Exception as e:
        logger.error(f"Error unlocking production: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/locks")
async def get_active_locks():
    """Get all active production locks"""
    try:
        return {
            "status": "success",
            "data": {
                "production_mode": os.getenv("ENVIRONMENT", "development").lower() == "production",
                "locks": {
                    "max_concurrent_strategies": 3,
                    "max_daily_loss_percent": -3.5,
                    "max_position_size_per_strike": 4,
                    "force_eod_exit_time": "15:25",
                    "market_open_time": "09:15",
                    "market_close_time": "15:25",
                    "max_order_size_lots": 10,
                    "min_order_interval_seconds": 5,
                    "max_orders_per_minute": 12,
                    "max_capital_usage_percent": 25.0,
                    "min_capital_for_trade": 10000
                },
                "total_locks": 10,
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting active locks: {e}")
        raise HTTPException(status_code=500, detail=str(e))
