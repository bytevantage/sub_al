"""
Token Status API
Provides real-time token health information using the token manager
"""
from fastapi import APIRouter, HTTPException
from backend.services.token_manager import get_token_manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/token", tags=["token"])


@router.get("/status")
async def get_token_status():
    """Get comprehensive token status from token manager"""
    try:
        token_manager = get_token_manager()
        token_manager.load_token()
        
        status = token_manager.get_status()
        
        # Add additional local validation (no API calls)
        if status.get('valid'):
            local_valid = token_manager.validate_token_locally()
            status['locally_validated'] = local_valid
            if not local_valid:
                status['valid'] = False
                status['message'] = 'Token failed local expiry validation'
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting token status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/force-refresh")
async def force_token_refresh():
    """Manually trigger token refresh"""
    try:
        token_manager = get_token_manager()
        
        success = await token_manager.refresh_token()
        
        if success:
            return {
                "status": "success",
                "message": "Token refresh initiated successfully"
            }
        else:
            return {
                "status": "failed",
                "message": "Token refresh failed, manual authentication required",
                "requires_manual_auth": True
            }
            
    except Exception as e:
        logger.error(f"Error forcing token refresh: {e}")
        raise HTTPException(status_code=500, detail=str(e))
