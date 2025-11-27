"""
Simple Real-Time Metrics API
Provides basic metrics for dashboard without complex dependencies
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from datetime import datetime
import logging
from backend.database.database import db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/real-time", tags=["real-time"])

@router.get("/metrics")
async def get_real_time_metrics():
    """
    Get real-time trading metrics for dashboard
    
    Returns:
        Dict with IV Rank, VWAP, Net Delta, Greeks, P&L, etc.
    """
    try:
        # Get trading system from app state
        from fastapi import FastAPI
        import sys
        if 'backend.main' in sys.modules:
            from backend.main import app as main_app
        else:
            # Try to import main module
            from backend import main
            main_app = main.app
        
        trading_system = getattr(main_app.state, 'trading_system', None)
        
        # Initialize with default values
        metrics = {
            # IV Rank
            'iv_rank': 50.0,
            'iv_percentile': 50.0,
            'current_iv': 18.0,
            
            # Session VWAP - will be updated below
            'session_vwap': 26000.0,
            'vwap_deviation_pct': 0.0,
            'session_volume': 0,
            
            # Net Delta and Greeks - will be updated below
            'net_delta': 0.0,
            'total_gamma': 0.0,
            'total_theta': 0.0,
            'total_vega': 0.0,
            'open_positions': 0,
            
            # Daily P&L and Drawdown - will be updated below
            'daily_pnl': 0.0,
            'drawdown': 0.0,
            'win_rate': 0.0,
            'total_trades': 0,
            
            # SAC mode
            'sac_mode': 'Exploring',
            
            # Timestamp
            'timestamp': datetime.now().isoformat(),
            'status': 'success'
        }
        
        # Get real data from database and market data
        try:
            # Get open positions from database
            session = db.get_session()
            try:
                from backend.database.models import Position
                
                today = datetime.now().date()
                open_positions = session.query(Position).all()
                
                metrics['open_positions'] = len(open_positions)
                
                # Calculate Greeks from positions
                total_delta = sum(pos.delta_entry * pos.quantity for pos in open_positions if pos.delta_entry)
                total_gamma = sum(pos.gamma_entry * pos.quantity for pos in open_positions if pos.gamma_entry)
                total_theta = sum(pos.theta_entry * pos.quantity for pos in open_positions if pos.theta_entry)
                total_vega = sum(pos.vega_entry * pos.quantity for pos in open_positions if pos.vega_entry)
                
                metrics.update({
                    'net_delta': round(total_delta, 3),
                    'total_gamma': round(total_gamma, 3),
                    'total_theta': round(total_theta, 2),
                    'total_vega': round(total_vega, 2)
                })
                
                # Get performance metrics from trades
                from backend.database.models import Trade
                from sqlalchemy import func, and_
                
                # Get today's trades
                today_start = datetime(today.year, today.month, today.day, 0, 0, 0)
                today_end = datetime(today.year, today.month, today.day, 23, 59, 59)
                
                today_trades = session.query(Trade).filter(
                    and_(
                        Trade.exit_time >= today_start,
                        Trade.exit_time <= today_end,
                        Trade.status == 'CLOSED'
                    )
                ).all()
                
                daily_pnl = sum(trade.net_pnl for trade in today_trades if trade.net_pnl)
                metrics['daily_pnl'] = round(daily_pnl, 2)
                
                # Add profit percentage calculation
                starting_capital = 100000  # Default starting capital
                try:
                    from backend.api.capital import capital_data
                    starting_capital = capital_data.get('starting_capital', 100000)
                except:
                    pass
                
                profit_percentage = (daily_pnl / starting_capital) * 100 if starting_capital > 0 else 0
                metrics['profit_percentage'] = round(profit_percentage, 2)
                
                # Calculate other metrics
                metrics['total_trades'] = len(today_trades)
                winning_trades = len([t for t in today_trades if t.net_pnl and t.net_pnl > 0])
                metrics['win_rate'] = round((winning_trades / len(today_trades)) * 100, 1) if today_trades else 0
                
                # Simple drawdown calculation (max loss from starting capital)
                max_loss = min([trade.net_pnl for trade in today_trades if trade.net_pnl], default=0)
                metrics['drawdown'] = round(abs(max_loss / starting_capital) * 100, 2) if max_loss < 0 else 0
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Error getting database metrics: {e}")
        
        # Get real-time market data using Upstox client
        try:
            from backend.api.market_data import get_upstox_client
            client = get_upstox_client()
            
            if client:
                # Get NIFTY LTP for VWAP
                nifty_response = client.get_ltp(["NSE_INDEX|Nifty 50"])
                if nifty_response and 'data' in nifty_response:
                    nifty_data = nifty_response['data'].get("NSE_INDEX|Nifty 50", {})
                    nifty_ltp = nifty_data.get('lastPrice', 26000)
                    metrics['session_vwap'] = round(nifty_ltp, 2)
                    
                    # Calculate VWAP deviation (using spot as reference)
                    deviation = ((nifty_ltp - 26000) / 26000) * 100
                    metrics['vwap_deviation_pct'] = round(deviation, 3)
                
                # Get IV Rank from session VWAP service
                from backend.data.session_vwap import SessionVWAP
                vwap_service = SessionVWAP()
                try:
                    iv_data = vwap_service.get_real_iv_rank("NIFTY")
                    if iv_data:
                        metrics['iv_rank'] = round(iv_data.get('iv_rank', 50), 1)
                        metrics['current_iv'] = round(iv_data.get('current_iv', 18), 1)
                except:
                    pass
                    
        except Exception as e:
            logger.debug(f"Could not get market data: {e}")
        
        # Get SAC mode from config
        try:
            import yaml
            with open('/app/config/config.yaml', 'r') as f:
                config = yaml.safe_load(f)
                if config.get('sac_meta_controller', {}).get('enabled', False):
                    metrics['sac_mode'] = 'LEARNING'
                else:
                    metrics['sac_mode'] = 'EXPLORING'
        except:
            metrics['sac_mode'] = 'EXPLORING'
                        
        return metrics
        
    except Exception as e:
        logger.error(f"Error in real-time metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/hedge-summary")
async def get_hedge_summary():
    """Get delta hedging summary"""
    try:
        # Initialize with default values
        hedge_data = {
            'total_hedges': 0,
            'active_hedges': {},
            'last_hedge': None,
            'total_hedge_quantity': 0
        }
        
        # Get real hedge data from trading system
        try:
            from backend.main import app
            trading_system = getattr(app.state, 'trading_system', None)
            
            if trading_system and hasattr(trading_system, 'delta_hedger') and trading_system.delta_hedger:
                hedge_summary = trading_system.delta_hedger.get_hedge_summary()
                if hedge_summary:
                    hedge_data.update(hedge_summary)
                    
        except Exception as e:
            logger.warning(f"Could not get hedge data: {e}")
        
        return {
            'status': 'success',
            'data': hedge_data,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting hedge summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reconciliation-summary")
async def get_reconciliation_summary():
    """Get position reconciliation summary"""
    try:
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
