"""
Analytics API Router

Provides endpoints for aggregated trading analytics and dashboards.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import func, and_
import logging

from backend.core.adaptive_config import adaptive_config
from backend.database import db, Trade

# IST timezone
IST = ZoneInfo("Asia/Kolkata")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/pnl")
async def get_pnl_analysis(
    period: str = Query("week", regex="^(day|week|month|all)$"),
    strategy: Optional[str] = None
):
    """
    Get P&L analysis for a time period.
    
    Args:
        period: Time period (day, week, month, all)
        strategy: Filter by strategy name (optional)
    
    Returns:
        P&L breakdown with daily/cumulative data
    """
    try:
        session = db.get_session()
        if not session:
            raise HTTPException(status_code=500, detail="Database unavailable")
        
        # Calculate date range
        now = datetime.now(IST)
        if period == "day":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start_date = now - timedelta(days=7)
        elif period == "month":
            start_date = now - timedelta(days=30)
        else:  # all
            start_date = datetime(2000, 1, 1)
        
        # Build query
        query = session.query(Trade).filter(Trade.exit_time >= start_date)
        if strategy:
            query = query.filter(Trade.strategy_name == strategy)
        
        trades = query.all()
        session.close()
        
        if not trades:
            return {
                'period': period,
                'strategy': strategy,
                'total_pnl': 0,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'daily_pnl': []
            }
        
        # Calculate metrics
        total_pnl = sum(t.net_pnl for t in trades)
        winning_trades = [t for t in trades if t.net_pnl > 0]
        losing_trades = [t for t in trades if t.net_pnl <= 0]
        
        # Daily P&L breakdown
        daily_pnl = {}
        for trade in trades:
            if trade.exit_time:
                date_key = trade.exit_time.date().isoformat()
                if date_key not in daily_pnl:
                    daily_pnl[date_key] = {'date': date_key, 'pnl': 0, 'trades': 0}
                daily_pnl[date_key]['pnl'] += trade.net_pnl
                daily_pnl[date_key]['trades'] += 1
        
        # Sort by date and calculate cumulative
        sorted_daily = sorted(daily_pnl.values(), key=lambda x: x['date'])
        cumulative = 0
        for day in sorted_daily:
            cumulative += day['pnl']
            day['cumulative_pnl'] = round(cumulative, 2)
            day['pnl'] = round(day['pnl'], 2)
        
        return {
            'period': period,
            'strategy': strategy,
            'total_pnl': round(total_pnl, 2),
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': round(len(winning_trades) / len(trades) * 100, 2),
            'avg_win': round(sum(t.net_pnl for t in winning_trades) / len(winning_trades), 2) if winning_trades else 0,
            'avg_loss': round(sum(t.net_pnl for t in losing_trades) / len(losing_trades), 2) if losing_trades else 0,
            'daily_pnl': sorted_daily
        }
        
    except Exception as e:
        logger.error(f"Error in get_pnl_analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drawdown")
async def get_drawdown_curve(
    period: str = Query("month", regex="^(week|month|all)$")
):
    """
    Get drawdown curve over time.
    
    Args:
        period: Time period (week, month, all)
    
    Returns:
        Drawdown data with peaks and troughs
    """
    try:
        session = db.get_session()
        if not session:
            raise HTTPException(status_code=500, detail="Database unavailable")
        
        # Calculate date range
        now = datetime.now(IST)
        if period == "week":
            start_date = now - timedelta(days=7)
        elif period == "month":
            start_date = now - timedelta(days=30)
        else:  # all
            start_date = datetime(2000, 1, 1)
        
        # Get all trades ordered by exit time
        trades = session.query(Trade).filter(
            Trade.exit_time >= start_date
        ).order_by(Trade.exit_time).all()
        
        session.close()
        
        if not trades:
            return {
                'period': period,
                'max_drawdown': 0,
                'max_drawdown_pct': 0,
                'current_drawdown': 0,
                'drawdown_curve': []
            }
        
        # Calculate equity curve and drawdown
        equity_curve = []
        cumulative_pnl = 0
        peak = 0
        max_drawdown = 0
        max_drawdown_pct = 0
        
        for trade in trades:
            cumulative_pnl += trade.net_pnl
            
            # Update peak
            if cumulative_pnl > peak:
                peak = cumulative_pnl
            
            # Calculate drawdown
            drawdown = peak - cumulative_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            
            # Calculate drawdown percentage
            drawdown_pct = (drawdown / peak * 100) if peak > 0 else 0
            if drawdown_pct > max_drawdown_pct:
                max_drawdown_pct = drawdown_pct
            
            equity_curve.append({
                'timestamp': trade.exit_time.isoformat() if trade.exit_time else None,
                'equity': round(cumulative_pnl, 2),
                'peak': round(peak, 2),
                'drawdown': round(drawdown, 2),
                'drawdown_pct': round(drawdown_pct, 2)
            })
        
        # Current drawdown
        current_drawdown = peak - cumulative_pnl
        current_drawdown_pct = (current_drawdown / peak * 100) if peak > 0 else 0
        
        return {
            'period': period,
            'max_drawdown': round(max_drawdown, 2),
            'max_drawdown_pct': round(max_drawdown_pct, 2),
            'current_drawdown': round(current_drawdown, 2),
            'current_drawdown_pct': round(current_drawdown_pct, 2),
            'peak_equity': round(peak, 2),
            'current_equity': round(cumulative_pnl, 2),
            'drawdown_curve': equity_curve[-100:]  # Last 100 points
        }
        
    except Exception as e:
        logger.error(f"Error in get_drawdown_curve: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy-heatmap")
async def get_strategy_heatmap():
    """
    Get strategy performance heatmap (strategy vs time).
    
    Returns:
        Heatmap data with strategy x hour/day performance
    """
    try:
        session = db.get_session()
        if not session:
            raise HTTPException(status_code=500, detail="Database unavailable")
        
        # Get all trades from last 30 days
        start_date = datetime.now(IST) - timedelta(days=30)
        trades = session.query(Trade).filter(Trade.exit_time >= start_date).all()
        session.close()
        
        if not trades:
            return {
                'strategies': [],
                'heatmap': []
            }
        
        # Build heatmap: strategy x hour
        heatmap_data = {}
        strategies = set()
        
        for trade in trades:
            if not trade.entry_time:
                continue
            
            strategy = trade.strategy_name or 'unknown'
            hour = trade.entry_time.hour
            strategies.add(strategy)
            
            key = (strategy, hour)
            if key not in heatmap_data:
                heatmap_data[key] = {'pnl': 0, 'count': 0}
            
            heatmap_data[key]['pnl'] += trade.net_pnl
            heatmap_data[key]['count'] += 1
        
        # Format heatmap
        heatmap = []
        for strategy in sorted(strategies):
            row = {'strategy': strategy, 'hours': []}
            for hour in range(9, 16):  # Market hours 9 AM to 3 PM
                key = (strategy, hour)
                if key in heatmap_data:
                    data = heatmap_data[key]
                    avg_pnl = data['pnl'] / data['count']
                    row['hours'].append({
                        'hour': hour,
                        'pnl': round(data['pnl'], 2),
                        'avg_pnl': round(avg_pnl, 2),
                        'count': data['count']
                    })
                else:
                    row['hours'].append({
                        'hour': hour,
                        'pnl': 0,
                        'avg_pnl': 0,
                        'count': 0
                    })
            heatmap.append(row)
        
        return {
            'strategies': sorted(strategies),
            'heatmap': heatmap,
            'period': 'last_30_days'
        }
        
    except Exception as e:
        logger.error(f"Error in get_strategy_heatmap: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance-summary")
async def get_performance_summary():
    """
    Get comprehensive performance summary.
    
    Returns:
        Overall trading performance metrics
    """
    try:
        session = db.get_session()
        if not session:
            raise HTTPException(status_code=500, detail="Database unavailable")
        
        # Get all closed trades
        all_trades = session.query(Trade).filter(Trade.status == 'CLOSED').all()
        
        # Get trades from different periods
        now = datetime.now(IST)
        # Convert now to naive datetime for comparison (DB stores naive UTC/IST)
        now_naive = now.replace(tzinfo=None)
        today_trades = [t for t in all_trades if t.exit_time and t.exit_time.date() == now_naive.date()]
        week_trades = [t for t in all_trades if t.exit_time and t.exit_time >= now_naive - timedelta(days=7)]
        month_trades = [t for t in all_trades if t.exit_time and t.exit_time >= now_naive - timedelta(days=30)]
        
        session.close()
        
        def calculate_metrics(trades):
            if not trades:
                return {
                    'total_pnl': 0,
                    'total_trades': 0,
                    'win_rate': 0,
                    'profit_factor': 0,
                    'avg_pnl': 0
                }
            
            total_pnl = sum(t.net_pnl for t in trades)
            winning = [t for t in trades if t.net_pnl > 0]
            losing = [t for t in trades if t.net_pnl <= 0]
            
            gross_profit = sum(t.net_pnl for t in winning)
            gross_loss = abs(sum(t.net_pnl for t in losing))
            
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
            
            return {
                'total_pnl': round(total_pnl, 2),
                'total_trades': len(trades),
                'win_rate': round(len(winning) / len(trades) * 100, 2),
                'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 999,
                'avg_pnl': round(total_pnl / len(trades), 2)
            }
        
        return {
            'overall': calculate_metrics(all_trades),
            'today': calculate_metrics(today_trades),
            'this_week': calculate_metrics(week_trades),
            'this_month': calculate_metrics(month_trades),
            'timestamp': now.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in get_performance_summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy-breakdown")
async def get_strategy_breakdown():
    """
    Get performance breakdown by strategy.
    
    Returns:
        Per-strategy metrics
    """
    try:
        session = db.get_session()
        if not session:
            raise HTTPException(status_code=500, detail="Database unavailable")
        
        # Get all trades grouped by strategy
        trades = session.query(Trade).filter(Trade.status == 'CLOSED').all()
        session.close()
        
        # Group by strategy
        strategy_stats = {}
        for trade in trades:
            strategy = trade.strategy_name or 'unknown'
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {
                    'trades': [],
                    'total_pnl': 0,
                    'winning': 0,
                    'losing': 0
                }
            
            strategy_stats[strategy]['trades'].append(trade)
            strategy_stats[strategy]['total_pnl'] += trade.net_pnl
            if trade.net_pnl > 0:
                strategy_stats[strategy]['winning'] += 1
            else:
                strategy_stats[strategy]['losing'] += 1
        
        # Format response
        breakdown = []
        for strategy, stats in strategy_stats.items():
            total_trades = len(stats['trades'])
            win_rate = (stats['winning'] / total_trades * 100) if total_trades > 0 else 0
            
            breakdown.append({
                'strategy': strategy,
                'total_pnl': round(stats['total_pnl'], 2),
                'total_trades': total_trades,
                'winning_trades': stats['winning'],
                'losing_trades': stats['losing'],
                'win_rate': round(win_rate, 2),
                'avg_pnl_per_trade': round(stats['total_pnl'] / total_trades, 2) if total_trades > 0 else 0
            })
        
        # Sort by total P&L
        breakdown.sort(key=lambda x: x['total_pnl'], reverse=True)
        
        return {
            'strategies': breakdown,
            'total_strategies': len(breakdown)
        }
        
    except Exception as e:
        logger.error(f"Error in get_strategy_breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/adaptive-config")
async def get_adaptive_config_status():
    """
    Get current adaptive configuration status and thresholds
    
    Returns:
        Current adaptive thresholds and market regime information
    """
    try:
        return adaptive_config.get_current_thresholds()
        
    except Exception as e:
        logger.error(f"Error getting adaptive config status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
