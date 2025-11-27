"""
Production Lock API
One-click production lock with git tagging and config freeze
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from datetime import datetime
import subprocess
import os
from backend.core.logger import logger
from backend.config.production_locks import PRODUCTION_LOCKS, get_production_status
router = APIRouter(prefix="/api/production", tags=["production"])

@router.post("/lock")
async def activate_production_lock():
    """
    Activate production lock - tag v1.0.0-production and freeze config
    
    Returns:
        Dict with lock status and git tag info
    """
    try:
        # Check if already in production mode
        if os.getenv("ENVIRONMENT", "development").lower() == "production":
            return {
                "status": "already_locked",
                "message": "System is already in production mode",
                "git_tag": "v1.0.0-production",
                "timestamp": datetime.now().isoformat()
            }
        
        # Create git tag
        try:
            # Check if we're in a git repository
            subprocess.run(['git', 'status'], check=True, capture_output=True)
            
            # Create and push tag
            tag_name = "v1.0.0-production"
            tag_message = "Production lock - Final configuration freeze"
            
            # Create tag
            subprocess.run(['git', 'tag', '-a', tag_name, '-m', tag_message], check=True, capture_output=True)
            
            # Push tag to remote
            subprocess.run(['git', 'push', 'origin', tag_name], check=True, capture_output=True)
            
            logger.info(f"✅ Created and pushed git tag: {tag_name}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create git tag: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create git tag: {e}")
        except FileNotFoundError:
            logger.error("Git not found")
            raise HTTPException(status_code=500, detail="Git not available")
        
        # Set environment variable for production mode
        os.environ["ENVIRONMENT"] = "production"
        
        # Create production lock file
        lock_file = "/Users/srbhandary/Documents/Projects/srb-algo/.production_lock"
        lock_data = {
            "locked": True,
            "git_tag": "v1.0.0-production",
            "locked_at": datetime.now().isoformat(),
            "locks": PRODUCTION_LOCKS,
            "version": "v1.0.0-production"
        }
        
        import json
        with open(lock_file, 'w') as f:
            json.dump(lock_data, f, indent=2)
        
        logger.warning("🔒 PRODUCTION LOCK ACTIVATED - Configuration frozen")
        
        return {
            "status": "locked",
            "message": "Production lock activated successfully",
            "git_tag": "v1.0.0-production",
            "locked_at": lock_data["locked_at"],
            "locks_active": list(PRODUCTION_LOCKS.keys()),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error activating production lock: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_production_lock_status():
    """Get current production lock status"""
    try:
        status = get_production_status()
        
        # Check if lock file exists
        lock_file = "/Users/srbhandary/Documents/Projects/srb-algo/.production_lock"
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
        lock_file = "/Users/srbhandary/Documents/Projects/srb-algo/.production_lock"
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
                "locks": PRODUCTION_LOCKS,
                "total_locks": len(PRODUCTION_LOCKS),
                "categories": {
                    "risk_management": ["max_concurrent_strategies", "max_daily_loss_percent", "max_position_size_per_strike"],
                    "timing": ["force_eod_exit_time", "market_open_time", "market_close_time"],
                    "execution": ["max_order_size_lots", "min_order_interval_seconds", "max_orders_per_minute"],
                    "capital": ["max_capital_usage_percent", "min_capital_for_trade"]
                },
                "timestamp": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting active locks: {e}")
        raise HTTPException(status_code=500, detail=str(e))
