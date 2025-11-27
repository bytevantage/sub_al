"""
Watchlist Performance Tracking API
Track win rate and performance of Smart Watchlist recommendations
"""

from fastapi import APIRouter, HTTPException, Depends
from backend.core.timezone_utils import now_ist
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from backend.core.logger import get_logger
from backend.database.database import get_db
from backend.database.models import WatchlistRecommendation

logger = get_logger(__name__)

router = APIRouter(tags=["watchlist"])


@router.get("/api/watchlist/performance")
async def get_watchlist_performance(
    days: int = 30,
    symbol: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get Smart Watchlist performance metrics
    
    Returns:
    - Overall win rate
    - Win rate by symbol
    - Win rate by direction (CALL/PUT)
    - Average P&L per signal
    - Best/worst signals
    - Daily performance breakdown
    """
    try:
        # Calculate date range
        end_date = now_ist()
        start_date = end_date - timedelta(days=days)
        
        # Base query
        query = db.query(WatchlistRecommendation).filter(
            WatchlistRecommendation.recommended_at >= start_date
        )
        
        # Filter by symbol if provided
        if symbol:
            query = query.filter(WatchlistRecommendation.symbol == symbol)
        
        # Get all recommendations
        all_recommendations = query.all()
        total_signals = len(all_recommendations)
        
        # Get closed recommendations (with outcomes)
        closed_recommendations = [r for r in all_recommendations if r.outcome in ['WIN', 'LOSS']]
        total_closed = len(closed_recommendations)
        
        if total_closed == 0:
            return {
                "status": "success",
                "data": {
                    "period_days": days,
                    "symbol": symbol,
                    "total_signals": total_signals,
                    "closed_signals": 0,
                    "pending_signals": total_signals,
                    "message": "No closed signals yet to calculate performance"
                }
            }
        
        # Calculate overall metrics
        wins = len([r for r in closed_recommendations if r.outcome == 'WIN'])
        losses = len([r for r in closed_recommendations if r.outcome == 'LOSS'])
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
        
        # Calculate P&L metrics
        total_pnl = sum(r.pnl for r in closed_recommendations if r.pnl is not None)
        avg_pnl = total_pnl / total_closed if total_closed > 0 else 0
        avg_win_pnl = sum(r.pnl for r in closed_recommendations if r.outcome == 'WIN' and r.pnl) / wins if wins > 0 else 0
        avg_loss_pnl = sum(r.pnl for r in closed_recommendations if r.outcome == 'LOSS' and r.pnl) / losses if losses > 0 else 0
        
        # Win rate by symbol
        symbols = {}
        for rec in closed_recommendations:
            if rec.symbol not in symbols:
                symbols[rec.symbol] = {'wins': 0, 'losses': 0, 'total_pnl': 0}
            
            if rec.outcome == 'WIN':
                symbols[rec.symbol]['wins'] += 1
            else:
                symbols[rec.symbol]['losses'] += 1
            
            if rec.pnl:
                symbols[rec.symbol]['total_pnl'] += rec.pnl
        
        # Calculate win rates per symbol
        symbol_performance = {}
        for sym, data in symbols.items():
            total = data['wins'] + data['losses']
            symbol_performance[sym] = {
                'win_rate': (data['wins'] / total * 100) if total > 0 else 0,
                'wins': data['wins'],
                'losses': data['losses'],
                'total_signals': total,
                'total_pnl': data['total_pnl'],
                'avg_pnl': data['total_pnl'] / total if total > 0 else 0
            }
        
        # Win rate by direction
        calls = [r for r in closed_recommendations if r.direction == 'CALL']
        puts = [r for r in closed_recommendations if r.direction == 'PUT']
        
        call_wins = len([r for r in calls if r.outcome == 'WIN'])
        put_wins = len([r for r in puts if r.outcome == 'WIN'])
        
        call_win_rate = (call_wins / len(calls) * 100) if calls else 0
        put_win_rate = (put_wins / len(puts) * 100) if puts else 0
        
        # Best and worst signals
        best_signals = sorted(closed_recommendations, key=lambda x: x.pnl or 0, reverse=True)[:5]
        worst_signals = sorted(closed_recommendations, key=lambda x: x.pnl or 0)[:5]
        
        # Daily breakdown
        daily_performance = {}
        for rec in closed_recommendations:
            day = rec.recommended_at.date().isoformat()
            if day not in daily_performance:
                daily_performance[day] = {'wins': 0, 'losses': 0, 'pnl': 0}
            
            if rec.outcome == 'WIN':
                daily_performance[day]['wins'] += 1
            else:
                daily_performance[day]['losses'] += 1
            
            if rec.pnl:
                daily_performance[day]['pnl'] += rec.pnl
        
        # Calculate daily win rates
        for day, data in daily_performance.items():
            total = data['wins'] + data['losses']
            data['win_rate'] = (data['wins'] / total * 100) if total > 0 else 0
            data['total_signals'] = total
        
        return {
            "status": "success",
            "data": {
                "period_days": days,
                "symbol": symbol,
                "summary": {
                    "total_signals": total_signals,
                    "closed_signals": total_closed,
                    "pending_signals": total_signals - total_closed,
                    "win_rate": round(win_rate, 2),
                    "wins": wins,
                    "losses": losses,
                    "total_pnl": round(total_pnl, 2),
                    "avg_pnl_per_signal": round(avg_pnl, 2),
                    "avg_win": round(avg_win_pnl, 2),
                    "avg_loss": round(avg_loss_pnl, 2),
                    "profit_factor": round(abs(avg_win_pnl / avg_loss_pnl), 2) if avg_loss_pnl != 0 else 0
                },
                "by_symbol": symbol_performance,
                "by_direction": {
                    "CALL": {
                        "win_rate": round(call_win_rate, 2),
                        "total_signals": len(calls),
                        "wins": call_wins,
                        "losses": len(calls) - call_wins
                    },
                    "PUT": {
                        "win_rate": round(put_win_rate, 2),
                        "total_signals": len(puts),
                        "wins": put_wins,
                        "losses": len(puts) - put_wins
                    }
                },
                "best_signals": [
                    {
                        "symbol": s.symbol,
                        "strike": s.strike_price,
                        "direction": s.direction,
                        "pnl": round(s.pnl, 2) if s.pnl else 0,
                        "pnl_pct": round(s.pnl_pct, 2) if s.pnl_pct else 0,
                        "date": s.recommended_at.date().isoformat()
                    }
                    for s in best_signals if s.pnl
                ],
                "worst_signals": [
                    {
                        "symbol": s.symbol,
                        "strike": s.strike_price,
                        "direction": s.direction,
                        "pnl": round(s.pnl, 2) if s.pnl else 0,
                        "pnl_pct": round(s.pnl_pct, 2) if s.pnl_pct else 0,
                        "date": s.recommended_at.date().isoformat()
                    }
                    for s in worst_signals if s.pnl
                ],
                "daily_breakdown": daily_performance
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching watchlist performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/watchlist/recommendations/pending")
async def get_pending_recommendations(db: Session = Depends(get_db)):
    """Get all pending watchlist recommendations (not yet resolved)"""
    try:
        
        pending = db.query(WatchlistRecommendation).filter(
            WatchlistRecommendation.outcome == 'PENDING'
        ).order_by(WatchlistRecommendation.recommended_at.desc()).all()
        
        return {
            "status": "success",
            "count": len(pending),
            "recommendations": [
                {
                    "id": r.id,
                    "symbol": r.symbol,
                    "strike": r.strike_price,
                    "direction": r.direction,
                    "composite_score": r.composite_score,
                    "recommended_entry": r.recommended_entry,
                    "recommended_target": r.recommended_target,
                    "recommended_sl": r.recommended_sl,
                    "recommended_at": r.recommended_at.isoformat(),
                    "reasons": r.reasons
                }
                for r in pending
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching pending recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))
