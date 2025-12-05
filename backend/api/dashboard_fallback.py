"""
Fallback Dashboard API - Handles database failures gracefully
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from datetime import datetime
import pytz

router = APIRouter(prefix="/api/dashboard-fallback", tags=["dashboard-fallback"])

def ist_isoformat():
    """Get current IST time in ISO format"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist).isoformat()

@router.get("/positions")
async def get_positions_fallback() -> Dict[str, Any]:
    """Fallback positions endpoint when database fails"""
    return {
        "status": "success",
        "data": {
            "timestamp": ist_isoformat(),
            "positions": [],
            "totals": {
                "count": 0,
                "total_unrealized_pnl": 0.0,
                "used_margin": 0.0,
                "available_margin": 100000.0,
                "capital_utilization": 0.0
            },
            "message": "Database unavailable - using fallback data"
        }
    }

@router.get("/risk-metrics")
async def get_risk_metrics_fallback() -> Dict[str, Any]:
    """Fallback risk metrics endpoint when database fails"""
    return {
        "status": "success",
        "data": {
            "timestamp": ist_isoformat(),
            "daily_pnl": 0.0,
            "daily_pnl_percent": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "win_rate": 0.0,
            "total_trades": 0,
            "capital_utilization": 0.0,
            "largest_position_percent": 0.0,
            "total_unrealized_pnl": 0.0,
            "used_margin": 0.0,
            "available_margin": 100000.0,
            "exposure_by_strategy": {},
            "message": "Database unavailable - using fallback data"
        }
    }

@router.get("/capital")
async def get_capital_fallback() -> Dict[str, Any]:
    """Fallback capital endpoint when database fails"""
    return {
        "status": "success",
        "data": {
            "starting_capital": 100000.0,
            "current_capital": 100000.0,
            "today_pnl": 0.0,
            "today_pnl_pct": 0.0,
            "total_pnl": 0.0,
            "total_pnl_pct": 0.0,
            "available_margin": 100000.0,
            "used_margin": 0.0,
            "margin_utilization": 0.0,
            "message": "Database unavailable - using fallback data"
        }
    }

@router.get("/trades/recent")
async def get_recent_trades_fallback(limit: int = 100, today_only: bool = True) -> Dict[str, Any]:
    """Fallback trades endpoint when database fails"""
    return {
        "status": "success",
        "data": {
            "trades": [],
            "total_count": 0,
            "message": "Database unavailable - using fallback data"
        }
    }
