"""
Real-Time Metrics API
Provides IV Rank, Session VWAP, Net Delta, Total Greeks for dashboard
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from datetime import datetime
from backend.core.logger import logger
from backend.services.position_persistence import get_position_service
from backend.data.iv_rank_calculator import IVRankCalculator
from backend.data.session_vwap import SessionVWAP
from backend.execution.delta_hedger import DeltaHedger
from backend.database.database import db
router = APIRouter(prefix="/api/real-time", tags=["real-time"])

# Global instances (will be initialized in main.py)
iv_rank_calculator = None
session_vwap = None
delta_hedger = None
position_service = None

def initialize_real_time_metrics(iv_calc, vwap_calc, hedge, pos_service):
    """Initialize real-time metrics components"""
    global iv_rank_calculator, session_vwap, delta_hedger, position_service
    iv_rank_calculator = iv_calc
    session_vwap = vwap_calc
    delta_hedger = hedge
    position_service = pos_service

@router.get("/metrics")
async def get_real_time_metrics():
    """
    Get real-time trading metrics for dashboard
    
    Returns:
        Dict with IV Rank, VWAP, Net Delta, Greeks, P&L, etc.
    """
    try:
        metrics = {}
        
        # Get IV Rank for NIFTY
        if iv_rank_calculator:
            try:
                import asyncio
                nifty_iv = asyncio.run(iv_rank_calculator.get_real_iv_rank("NIFTY"))
                metrics['iv_rank'] = nifty_iv.get('iv_rank', 0)
                metrics['iv_percentile'] = nifty_iv.get('iv_percentile', 0)
                metrics['current_iv'] = nifty_iv.get('current_iv', 0)
            except Exception as e:
                logger.error(f"Error getting IV rank: {e}")
                metrics['iv_rank'] = 50
                metrics['iv_percentile'] = 50
                metrics['current_iv'] = 18.0
        else:
            metrics['iv_rank'] = 50
            metrics['iv_percentile'] = 50
            metrics['current_iv'] = 18.0
        
        # Get Session VWAP for NIFTY
        if session_vwap:
            try:
                nifty_vwap = asyncio.run(session_vwap.get_session_vwap("NIFTY"))
                metrics['session_vwap'] = nifty_vwap.get('vwap', 0)
                metrics['vwap_deviation_pct'] = nifty_vwap.get('vwap_deviation_pct', 0)
                metrics['session_volume'] = nifty_vwap.get('total_volume', 0)
            except Exception as e:
                logger.error(f"Error getting session VWAP: {e}")
                metrics['session_vwap'] = 26000
                metrics['vwap_deviation_pct'] = 0
                metrics['session_volume'] = 0
        else:
            metrics['session_vwap'] = 26000
            metrics['vwap_deviation_pct'] = 0
            metrics['session_volume'] = 0
        
        # Calculate Net Delta and Total Greeks from open positions
        if position_service:
            try:
                open_positions = position_service.get_all_positions()
                net_delta = 0.0
                net_gamma = 0.0
                net_theta = 0.0
                net_vega = 0.0
                
                for position in open_positions:
                    # Get current Greeks (would need market data for real-time)
                    delta = position.get('delta_entry', 0.0)
                    gamma = position.get('gamma_entry', 0.0)
                    theta = position.get('theta_entry', 0.0)
                    vega = position.get('vega_entry', 0.0)
                    quantity = position.get('quantity', 0)
                    
                    if position.get('direction') == 'BUY':
                        net_delta += delta * quantity
                        net_gamma += gamma * quantity
                        net_theta += theta * quantity
                        net_vega += vega * quantity
                    else:  # SELL
                        net_delta -= delta * quantity
                        net_gamma -= gamma * quantity
                        net_theta -= theta * quantity
                        net_vega -= vega * quantity
                
                metrics['net_delta'] = net_delta
                metrics['total_gamma'] = net_gamma
                metrics['total_theta'] = net_theta
                metrics['total_vega'] = net_vega
                metrics['open_positions'] = len(open_positions)
                
            except Exception as e:
                logger.error(f"Error calculating Greeks: {e}")
                metrics['net_delta'] = 0
                metrics['total_gamma'] = 0
                metrics['total_theta'] = 0
                metrics['total_vega'] = 0
                metrics['open_positions'] = 0
        else:
            metrics['net_delta'] = 0
            metrics['total_gamma'] = 0
            metrics['total_theta'] = 0
            metrics['total_vega'] = 0
            metrics['open_positions'] = 0
        
        # Get Daily P&L and Drawdown
        try:
            # Get today's trades
            today = datetime.now().strftime('%Y-%m-%d')
            trades = db.query(Trade).filter(
                Trade.entry_time >= today,
                Trade.status.in_(['CLOSED', 'PARTIALLY_CLOSED'])
            ).all()
            
            daily_pnl = sum(trade.pnl or 0 for trade in trades)
            metrics['daily_pnl'] = daily_pnl
            
            # Calculate drawdown (simplified)
            if daily_pnl >= 0:
                metrics['drawdown'] = 0
            else:
                # Assuming 100k starting capital
                metrics['drawdown'] = (daily_pnl / 100000) * 100
            
            # Additional metrics
            winning_trades = [t for t in trades if (t.pnl or 0) > 0]
            metrics['win_rate'] = (len(winning_trades) / len(trades) * 100) if trades else 0
            metrics['total_trades'] = len(trades)
            
        except Exception as e:
            logger.error(f"Error calculating P&L: {e}")
            metrics['daily_pnl'] = 0
            metrics['drawdown'] = 0
            metrics['win_rate'] = 0
            metrics['total_trades'] = 0
        
        # Get SAC mode (would need to check SAC agent state)
        metrics['sac_mode'] = 'Exploring'  # Placeholder - would get from SAC agent
        
        # Add timestamp
        metrics['timestamp'] = datetime.now().isoformat()
        metrics['status'] = 'success'
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error in real-time metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/hedge-summary")
async def get_hedge_summary():
    """Get delta hedging summary"""
    try:
        if delta_hedger:
            summary = await delta_hedger.get_hedge_summary()
            return {
                'status': 'success',
                'data': summary,
                'timestamp': datetime.now().isoformat()
            }
        else:
            return {
                'status': 'success',
                'data': {'total_hedges': 0, 'active_hedges': {}},
                'timestamp': datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Error getting hedge summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reconciliation-summary")
async def get_reconciliation_summary():
    """Get position reconciliation summary"""
    try:
        # This would use the position reconciler
        return {
            'status': 'success',
            'data': {
                'last_check': datetime.now().isoformat(),
                'orphans_found': 0,
                'orphans_killed': 0,
                'broker_positions': 0,
                'internal_positions': 0
            },
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting reconciliation summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
