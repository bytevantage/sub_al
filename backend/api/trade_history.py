"""
Trade History API Routes
Comprehensive trade history and analytics endpoints
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from typing import List, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from backend.database import Trade, DailyPerformance, StrategyPerformance, get_db
from backend.core.logger import logger

# IST timezone
IST = ZoneInfo("Asia/Kolkata")

router = APIRouter(prefix="/api/trades", tags=["Trade History"])


@router.get("/today")
async def get_today_trades(
    db: Session = Depends(get_db)
):
    """
    Get all trades from today (both open and closed)
    Dashboard endpoint to show today's trading activity
    """
    
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Get today's start in IST
        today_start = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Query all trades from today
        trades = db.query(Trade)\
            .filter(Trade.entry_time >= today_start)\
            .order_by(desc(Trade.entry_time))\
            .all()
        
        # Separate open and closed
        open_trades = [t for t in trades if t.status == 'OPEN']
        closed_trades = [t for t in trades if t.status == 'CLOSED']
        
        # Calculate today's P&L
        today_pnl = sum(t.net_pnl or 0 for t in closed_trades)
        today_gross_pnl = sum(t.gross_pnl or 0 for t in closed_trades)
        
        return {
            "date": today_start.strftime("%Y-%m-%d"),
            "total": len(trades),
            "open": len(open_trades),
            "closed": len(closed_trades),
            "today_pnl": round(today_pnl, 2),
            "today_gross_pnl": round(today_gross_pnl, 2),
            "trades": [trade.to_dict() for trade in trades],
            "open_trades": [trade.to_dict() for trade in open_trades],
            "closed_trades": [trade.to_dict() for trade in closed_trades]
        }
        
    except Exception as e:
        logger.error(f"Error fetching today's trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/today")
async def get_today_trades(
    db: Session = Depends(get_db)
):
    """
    Get all trades from today (both open and closed)
    Dashboard endpoint to show today's trading activity
    """
    
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Get today's start in IST
        today_start = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Query all trades from today
        trades = db.query(Trade)\
            .filter(Trade.entry_time >= today_start)\
            .order_by(desc(Trade.entry_time))\
            .all()
        
        # Separate open and closed
        open_trades = [t for t in trades if t.status == 'OPEN']
        closed_trades = [t for t in trades if t.status == 'CLOSED']
        
        # Calculate today's P&L
        today_pnl = sum(t.net_pnl or 0 for t in closed_trades)
        today_gross_pnl = sum(t.gross_pnl or 0 for t in closed_trades)
        
        return {
            "date": today_start.strftime("%Y-%m-%d"),
            "total": len(trades),
            "open": len(open_trades),
            "closed": len(closed_trades),
            "today_pnl": round(today_pnl, 2),
            "today_gross_pnl": round(today_gross_pnl, 2),
            "trades": [trade.to_dict() for trade in trades],
            "open_trades": [trade.to_dict() for trade in open_trades],
            "closed_trades": [trade.to_dict() for trade in closed_trades]
        }
        
    except Exception as e:
        logger.error(f"Error fetching today's trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_trade_history(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    strategy: Optional[str] = Query(None, description="Filter by strategy name"),
    status: Optional[str] = Query(None, description="OPEN, CLOSED, CANCELLED"),
    symbol: Optional[str] = Query(None, description="NIFTY, BANKNIFTY"),
    min_pnl: Optional[float] = Query(None, description="Minimum P&L"),
    max_pnl: Optional[float] = Query(None, description="Maximum P&L"),
    winning_only: Optional[bool] = Query(False, description="Show only winning trades"),
    losing_only: Optional[bool] = Query(False, description="Show only losing trades"),
    limit: int = Query(100, le=1000, description="Maximum results"),
    offset: int = Query(0, description="Pagination offset"),
    db: Session = Depends(get_db)
):
    """
    Get trade history with comprehensive filtering
    
    Returns detailed trade records with all execution data
    """
    
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Build query
        query = db.query(Trade)
        
        # Date filters
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Trade.entry_time >= start)
        
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Trade.entry_time < end)
        
        # Strategy filter
        if strategy:
            query = query.filter(Trade.strategy_name.ilike(f"%{strategy}%"))
        
        # Status filter
        if status:
            query = query.filter(Trade.status == status.upper())
        
        # Symbol filter
        if symbol:
            query = query.filter(Trade.symbol == symbol.upper())
        
        # P&L filters
        if min_pnl is not None:
            query = query.filter(Trade.net_pnl >= min_pnl)
        
        if max_pnl is not None:
            query = query.filter(Trade.net_pnl <= max_pnl)
        
        # Winning/Losing filters
        if winning_only:
            query = query.filter(Trade.is_winning_trade == True)
        
        if losing_only:
            query = query.filter(Trade.is_winning_trade == False)
        
        # Order by most recent first
        query = query.order_by(desc(Trade.entry_time))
        
        # Pagination
        total_count = query.count()
        trades = query.offset(offset).limit(limit).all()
        
        return {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "trades": [trade.to_dict() for trade in trades]
        }
        
    except Exception as e:
        logger.error(f"Error fetching trade history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_trade_statistics(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    strategy: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get aggregated trading statistics
    
    Returns:
    - Total trades, win rate, P&L
    - Best/worst trades
    - Average hold time
    - Strategy breakdown
    """
    
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Build base query
        query = db.query(Trade).filter(Trade.status == "CLOSED")
        
        # Apply filters
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Trade.entry_time >= start)
        
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Trade.entry_time < end)
        
        if strategy:
            query = query.filter(Trade.strategy_name.ilike(f"%{strategy}%"))
        
        trades = query.all()
        
        if not trades:
            return {
                "message": "No trades found for the specified criteria",
                "total_trades": 0
            }
        
        # Calculate statistics
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.is_winning_trade)
        losing_trades = total_trades - winning_trades
        
        total_pnl = sum(t.net_pnl or 0 for t in trades)
        total_profit = sum(t.net_pnl for t in trades if t.net_pnl and t.net_pnl > 0)
        total_loss = abs(sum(t.net_pnl for t in trades if t.net_pnl and t.net_pnl < 0))
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else 0
        
        avg_profit = (total_profit / winning_trades) if winning_trades > 0 else 0
        avg_loss = (total_loss / losing_trades) if losing_trades > 0 else 0
        
        # Find best and worst trades
        best_trade = max(trades, key=lambda t: t.net_pnl or 0)
        worst_trade = min(trades, key=lambda t: t.net_pnl or 0)
        
        # Average hold duration
        hold_durations = [t.hold_duration_minutes for t in trades if t.hold_duration_minutes]
        avg_hold_minutes = sum(hold_durations) / len(hold_durations) if hold_durations else 0
        
        # Strategy breakdown
        strategy_stats = {}
        for trade in trades:
            sname = trade.strategy_name
            if sname not in strategy_stats:
                strategy_stats[sname] = {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "total_pnl": 0
                }
            strategy_stats[sname]["total_trades"] += 1
            if trade.is_winning_trade:
                strategy_stats[sname]["winning_trades"] += 1
            strategy_stats[sname]["total_pnl"] += trade.net_pnl or 0
        
        # Calculate win rate for each strategy
        for sname in strategy_stats:
            total = strategy_stats[sname]["total_trades"]
            wins = strategy_stats[sname]["winning_trades"]
            strategy_stats[sname]["win_rate"] = (wins / total * 100) if total > 0 else 0
        
        return {
            "overview": {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": round(win_rate, 2),
                "total_pnl": round(total_pnl, 2),
                "profit_factor": round(profit_factor, 2),
                "average_profit": round(avg_profit, 2),
                "average_loss": round(avg_loss, 2),
                "average_hold_minutes": round(avg_hold_minutes, 1),
            },
            "best_trade": {
                "trade_id": best_trade.trade_id,
                "strategy": best_trade.strategy_name,
                "pnl": best_trade.net_pnl,
                "entry_time": best_trade.entry_time.isoformat(),
            },
            "worst_trade": {
                "trade_id": worst_trade.trade_id,
                "strategy": worst_trade.strategy_name,
                "pnl": worst_trade.net_pnl,
                "entry_time": worst_trade.entry_time.isoformat(),
            },
            "strategy_breakdown": strategy_stats
        }
        
    except Exception as e:
        logger.error(f"Error calculating statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily-performance")
async def get_daily_performance(
    days: int = Query(30, le=365, description="Number of days to retrieve"),
    db: Session = Depends(get_db)
):
    """Get daily performance summary for the last N days"""
    
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        start_date = datetime.now(IST) - timedelta(days=days)
        
        daily_records = db.query(DailyPerformance)\
            .filter(DailyPerformance.date >= start_date)\
            .order_by(desc(DailyPerformance.date))\
            .all()
        
        return {
            "days": days,
            "records": [record.to_dict() for record in daily_records]
        }
        
    except Exception as e:
        logger.error(f"Error fetching daily performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy-performance")
async def get_strategy_performance(
    strategy_name: Optional[str] = Query(None),
    days: int = Query(30, le=365),
    db: Session = Depends(get_db)
):
    """Get strategy-wise performance metrics"""
    
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        start_date = datetime.now(IST) - timedelta(days=days)
        
        query = db.query(StrategyPerformance)\
            .filter(StrategyPerformance.date >= start_date)
        
        if strategy_name:
            query = query.filter(StrategyPerformance.strategy_name == strategy_name)
        
        records = query.order_by(
            desc(StrategyPerformance.date),
            desc(StrategyPerformance.total_pnl)
        ).all()
        
        return {
            "strategy": strategy_name or "All",
            "days": days,
            "records": [record.to_dict() for record in records]
        }
        
    except Exception as e:
        logger.error(f"Error fetching strategy performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{trade_id}")
async def get_trade_details(
    trade_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific trade"""
    
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        trade = db.query(Trade).filter(Trade.trade_id == trade_id).first()
        
        if not trade:
            raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
        
        # Return full trade details
        details = trade.to_dict()
        
        # Add additional detailed fields
        details.update({
            "spot_price_entry": trade.spot_price_entry,
            "spot_price_exit": trade.spot_price_exit,
            "iv_entry": trade.iv_entry,
            "iv_exit": trade.iv_exit,
            "delta_entry": trade.delta_entry,
            "gamma_entry": trade.gamma_entry,
            "theta_entry": trade.theta_entry,
            "vega_entry": trade.vega_entry,
            "target_price": trade.target_price,
            "stop_loss_price": trade.stop_loss_price,
            "max_profit_reached": trade.max_profit_reached,
            "max_loss_reached": trade.max_loss_reached,
            "brokerage": trade.brokerage,
            "taxes": trade.taxes,
            "risk_amount": trade.risk_amount,
            "risk_reward_ratio": trade.risk_reward_ratio,
            "notes": trade.notes,
            "tags": trade.tags,
        })
        
        return details
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching trade details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/csv")
async def export_trades_csv(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    strategy: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Export trade history to CSV format
    
    Returns CSV data as text with all trade fields for Excel analysis
    """
    
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Build query
        query = db.query(Trade).filter(Trade.status == "CLOSED")
        
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Trade.entry_time >= start)
        
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Trade.entry_time < end)
        
        if strategy:
            query = query.filter(Trade.strategy_name.ilike(f"%{strategy}%"))
        
        trades = query.order_by(Trade.entry_time).all()
        
        # Build CSV
        csv_lines = []
        
        # Header
        headers = [
            "Trade ID", "Entry Date", "Entry Time", "Exit Date", "Exit Time",
            "Symbol", "Type", "Strike", "Entry Price", "Exit Price", "Quantity",
            "Gross P&L", "Brokerage", "Taxes", "Net P&L", "P&L %",
            "Strategy", "Signal Strength", "Exit Type", "Hold Minutes",
            "Spot Entry", "Spot Exit", "IV Entry", "IV Exit",
            "Signal Reason", "Exit Reason"
        ]
        csv_lines.append(",".join(headers))
        
        # Data rows
        for trade in trades:
            entry_date = trade.entry_time.strftime("%Y-%m-%d") if trade.entry_time else ""
            entry_time = trade.entry_time.strftime("%H:%M:%S") if trade.entry_time else ""
            exit_date = trade.exit_time.strftime("%Y-%m-%d") if trade.exit_time else ""
            exit_time = trade.exit_time.strftime("%H:%M:%S") if trade.exit_time else ""
            
            row = [
                trade.trade_id,
                entry_date,
                entry_time,
                exit_date,
                exit_time,
                trade.symbol,
                trade.instrument_type,
                str(trade.strike_price or ""),
                str(trade.entry_price),
                str(trade.exit_price or ""),
                str(trade.quantity),
                str(trade.gross_pnl or ""),
                str(trade.brokerage),
                str(trade.taxes),
                str(trade.net_pnl or ""),
                str(trade.pnl_percentage or ""),
                trade.strategy_name,
                str(trade.signal_strength or ""),
                trade.exit_type or "",
                str(trade.hold_duration_minutes or ""),
                str(trade.spot_price_entry or ""),
                str(trade.spot_price_exit or ""),
                str(trade.iv_entry or ""),
                str(trade.iv_exit or ""),
                (trade.signal_reason or "").replace(",", ";"),  # Escape commas
                (trade.exit_reason or "").replace(",", ";"),
            ]
            csv_lines.append(",".join(row))
        
        csv_content = "\n".join(csv_lines)
        
        from fastapi.responses import Response
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=trades_{datetime.now(IST).strftime('%Y%m%d')}.csv"
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))
