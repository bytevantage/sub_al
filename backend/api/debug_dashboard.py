"""
Debug Dashboard API - Check trading system initialization
"""

from fastapi import APIRouter
from backend.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/debug", tags=["debug"])

# Global reference to check dashboard trading system
from backend.api.dashboard import _trading_system as dashboard_trading_system

@router.get("/trading-system-status")
async def debug_trading_system_status():
    """Debug endpoint to check trading system initialization"""
    # Try to get trading system from app.state if dashboard reference is None
    if dashboard_trading_system is None:
        try:
            from backend.main import app
            trading_system = getattr(app.state, 'trading_system', None)
            if trading_system:
                # Set the dashboard reference
                from backend.api.dashboard import set_trading_system
                set_trading_system(trading_system)
                return {
                    "dashboard_trading_system": True,
                    "dashboard_trading_system_type": type(trading_system).__name__,
                    "message": "Trading system reference set dynamically"
                }
        except Exception as e:
            return {
                "dashboard_trading_system": False,
                "dashboard_trading_system_type": None,
                "message": f"Failed to set trading system: {str(e)}"
            }
    
    return {
        "dashboard_trading_system": dashboard_trading_system is not None,
        "dashboard_trading_system_type": type(dashboard_trading_system).__name__ if dashboard_trading_system else None,
        "message": "Trading system reference check"
    }

@router.get("/app-state")
async def debug_app_state():
    """Check app.state.trading_system"""
    from backend.main import app
    trading_system = getattr(app.state, 'trading_system', None)
    return {
        "app_state_trading_system": trading_system is not None,
        "app_state_trading_system_type": type(trading_system).__name__ if trading_system else None,
        "message": "App state trading system check"
    }
