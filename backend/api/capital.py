"""
Capital API - Track starting capital, current capital, and P&L
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.core.timezone_utils import now_ist
from datetime import datetime, date
from math import sqrt
from statistics import mean, stdev
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/capital", tags=["capital"])

# Cache for capital data to reduce database load
_capital_cache = {}
_capital_cache_timeout = 2  # 2 seconds cache - reduced for fresher data

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class CapitalUpdate(BaseModel):
    starting_capital: float = Field(ge=10000, description="Starting capital (min ₹10,000)")

class CapitalResponse(BaseModel):
    starting_capital: float
    current_capital: float
    today_pnl: float
    today_pnl_pct: float
    total_pnl: float
    total_pnl_pct: float
    last_updated: str

# ============================================================================
# IN-MEMORY STORAGE (Replace with database later)
# ============================================================================

capital_data = {
    "starting_capital": 100000.0,
    "last_updated": now_ist().isoformat()
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _ensure_trade_metrics(trade) -> float:
    """Ensure trade has net P&L calculated and return it"""
    if trade.net_pnl is None and trade.exit_price is not None:
        trade.calculate_pnl()
    return trade.net_pnl or 0.0


def _fetch_closed_trades(db: Session) -> List["Trade"]:
    """Retrieve all closed trades from database"""
    from backend.database import Trade  # Local import to avoid circular deps

    return (
        db.query(Trade)
        .filter(Trade.exit_time.isnot(None))
        .order_by(Trade.exit_time.asc())
        .all()
    )


def _aggregate_daily_pnl(trades: List["Trade"]) -> List[Tuple[date, float]]:
    """Aggregate net P&L per exit date"""
    daily_totals: Dict[date, float] = {}

    for trade in trades:
        if not trade.exit_time:
            continue
        trade_date = trade.exit_time.date()
        daily_totals.setdefault(trade_date, 0.0)
        daily_totals[trade_date] += _ensure_trade_metrics(trade)

    return sorted(daily_totals.items(), key=lambda item: item[0])


def _build_equity_curve(
    daily_pnl: List[Tuple[date, float]], starting_capital: float
) -> List[Dict[str, float]]:
    """Construct equity curve snapshots from daily pnl"""
    equity_curve: List[Dict[str, float]] = []
    equity = starting_capital

    for snapshot_date, pnl in daily_pnl:
        start_equity = equity
        equity += pnl
        daily_return = 0.0
        if start_equity > 0:
            daily_return = (equity / start_equity) - 1

        equity_curve.append(
            {
                "date": snapshot_date,
                "pnl": pnl,
                "equity": equity,
                "return": daily_return,
            }
        )

    return equity_curve


def _calculate_drawdown(equity_curve: List[Dict[str, float]]) -> Tuple[float, float]:
    """Return max drawdown absolute and percentage"""
    peak = float("-inf")
    max_drawdown = 0.0
    max_drawdown_pct = 0.0

    for point in equity_curve:
        equity = point["equity"]
        if equity > peak:
            peak = equity
        drawdown = peak - equity
        drawdown_pct = (drawdown / peak * 100) if peak > 0 else 0

        if drawdown > max_drawdown:
            max_drawdown = drawdown
        if drawdown_pct > max_drawdown_pct:
            max_drawdown_pct = drawdown_pct

    return max_drawdown, max_drawdown_pct


def _calculate_sharpe_ratio(returns: List[float]) -> float:
    """Compute annualised Sharpe ratio from daily returns"""
    # Use 252 trading days approximation
    if len(returns) < 2:
        return 0.0

    try:
        return_mean = mean(returns)
        return_std = stdev(returns)

        if return_std == 0:
            return 0.0

        return (return_mean / return_std) * sqrt(252)
    except Exception:
        return 0.0


def calculate_pnl_from_trades(db: Session = None):
    """
    Calculate P&L from trade history
    
    Returns:
        - today_pnl: Today's realized P&L
        - total_pnl: Total P&L since inception
        - current_capital: Starting capital + total P&L
    """
    try:
        # If database connection provided, query real trades
        if db:
            closed_trades = _fetch_closed_trades(db)

            today = date.today()
            today_pnl = sum(
                _ensure_trade_metrics(trade)
                for trade in closed_trades
                if trade.exit_time and trade.exit_time.date() == today
            )

            total_pnl = sum(_ensure_trade_metrics(trade) for trade in closed_trades)

            db.commit()
        else:
            # Mock data if no database
            today_pnl = 0.0
            total_pnl = 0.0
        
        starting_capital = capital_data["starting_capital"]
        current_capital = starting_capital + total_pnl
        
        # Calculate percentages
        today_pnl_pct = (today_pnl / starting_capital * 100) if starting_capital > 0 else 0
        total_pnl_pct = (total_pnl / starting_capital * 100) if starting_capital > 0 else 0
        
        return {
            "today_pnl": today_pnl,
            "total_pnl": total_pnl,
            "current_capital": current_capital,
            "today_pnl_pct": today_pnl_pct,
            "total_pnl_pct": total_pnl_pct
        }
    
    except Exception as e:
        logger.error(f"Error calculating P&L: {e}")
        return {
            "today_pnl": 0.0,
            "total_pnl": 0.0,
            "current_capital": capital_data["starting_capital"],
            "today_pnl_pct": 0.0,
            "total_pnl_pct": 0.0
        }

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("", response_model=CapitalResponse)
async def get_capital():
    """
    Get current capital and P&L
    
    Returns:
        - Starting capital
        - Current capital (starting + total P&L + unrealized P&L)
        - Today's P&L (₹ and %) - includes unrealized P&L from open positions
        - Total P&L (₹ and %)
    """
    try:
        # Check cache first
        cache_key = "capital_data"
        now = datetime.now()
        
        if cache_key in _capital_cache:
            cached_data, cached_time = _capital_cache[cache_key]
            if (now - cached_time).total_seconds() < _capital_cache_timeout:
                return cached_data
        
        # Get database session
        from backend.database import db as database
        session = database.get_session()
        
        try:
            # Calculate P&L from trades
            pnl_data = calculate_pnl_from_trades(session)
            
            # Add unrealized P&L from open positions
            from backend.main import app
            trading_system = getattr(app.state, 'trading_system', None)
            unrealized_pnl = 0.0
            
            if trading_system and trading_system.risk_manager:
                try:
                    positions = trading_system.risk_manager.get_open_positions()
                    unrealized_pnl = sum(pos.get('unrealized_pnl', 0) for pos in positions)
                except Exception as e:
                    logger.debug(f"Could not fetch unrealized P&L: {e}")
                    unrealized_pnl = 0.0
            
            # Include unrealized P&L in today's and current capital
            today_pnl_total = pnl_data["today_pnl"] + unrealized_pnl
            total_pnl = pnl_data["total_pnl"] + unrealized_pnl
            current_capital = pnl_data["current_capital"] + unrealized_pnl
            
            starting_capital = capital_data["starting_capital"]
            today_pnl_pct = (today_pnl_total / starting_capital * 100) if starting_capital > 0 else 0
            total_pnl_pct = (total_pnl / starting_capital * 100) if starting_capital > 0 else 0
            
            response = CapitalResponse(
                starting_capital=capital_data["starting_capital"],
                current_capital=current_capital,
                today_pnl=today_pnl_total,
                today_pnl_pct=today_pnl_pct,
                total_pnl=total_pnl,
                total_pnl_pct=total_pnl_pct,
                last_updated=capital_data["last_updated"]
            )
            
            # Store in cache
            _capital_cache[cache_key] = (response, now)
            
            return response
        finally:
            if session:
                session.close()
    
    except Exception as e:
        logger.error(f"Error getting capital: {e}")
        # Return fallback data instead of throwing error
        return CapitalResponse(
            starting_capital=100000.0,
            current_capital=100000.0,
            today_pnl=0.0,
            today_pnl_pct=0.0,
            total_pnl=0.0,
            total_pnl_pct=0.0,
            available_margin=100000.0,
            used_margin=0.0,
            margin_utilization=0.0,
            message=f"Database unavailable - using fallback: {str(e)[:100]}"
        )

@router.post("/starting")
async def update_starting_capital(capital_update: CapitalUpdate):
    """
    Update starting capital
    
    This will reset the baseline for P&L calculations
    """
    try:
        new_capital = capital_update.starting_capital
        
        if new_capital < 10000:
            raise HTTPException(
                status_code=400,
                detail="Starting capital must be at least ₹10,000"
            )
        
        # Update starting capital
        capital_data["starting_capital"] = new_capital
        capital_data["last_updated"] = now_ist().isoformat()
        
        logger.info(f"✓ Starting capital updated to ₹{new_capital:,.2f}")
        
        # Recalculate P&L with new baseline
        pnl_data = calculate_pnl_from_trades()
        
        return {
            "status": "success",
            "message": f"Starting capital updated to ₹{new_capital:,.2f}",
            "starting_capital": new_capital,
            "current_capital": pnl_data["current_capital"],
            "total_pnl": pnl_data["total_pnl"],
            "total_pnl_pct": pnl_data["total_pnl_pct"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating starting capital: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_capital_history():
    """
    Get capital history over time
    
    Returns daily snapshots of capital and P&L
    """
    try:
        from backend.database import db as database

        session = database.get_session()

        try:
            if not session:
                raise RuntimeError("Database session unavailable")

            closed_trades = _fetch_closed_trades(session)
            daily_pnl = _aggregate_daily_pnl(closed_trades)
            equity_curve = _build_equity_curve(daily_pnl, capital_data["starting_capital"])

            history = [
                {
                    "date": point["date"].isoformat(),
                    "starting_capital": capital_data["starting_capital"],
                    "ending_capital": round(point["equity"], 2),
                    "pnl": round(point["pnl"], 2),
                    "pnl_pct": round(point["return"] * 100, 2),
                }
                for point in equity_curve
            ]

            # Append today's unrealized P&L snapshot
            from backend.main import app

            trading_system = getattr(app.state, "trading_system", None)
            unrealized_pnl = 0.0

            if trading_system and getattr(trading_system, "risk_manager", None):
                open_positions = trading_system.risk_manager.get_open_positions()
                unrealized_pnl = sum(pos.get("unrealized_pnl", 0.0) for pos in open_positions)

            today_str = now_ist().date().isoformat()
            starting_capital = capital_data["starting_capital"]

            if history and history[-1]["date"] == today_str:
                today_snapshot = history[-1]
                today_snapshot["ending_capital"] = round(today_snapshot["ending_capital"] + unrealized_pnl, 2)
                today_snapshot["pnl"] = round(today_snapshot["pnl"] + unrealized_pnl, 2)
                today_snapshot["pnl_pct"] = round(
                    (today_snapshot["ending_capital"] - starting_capital) / starting_capital * 100,
                    2,
                )
            else:
                history.append(
                    {
                        "date": today_str,
                        "starting_capital": starting_capital,
                        "ending_capital": round(starting_capital + unrealized_pnl, 2),
                        "pnl": round(unrealized_pnl, 2),
                        "pnl_pct": round((unrealized_pnl / starting_capital * 100) if starting_capital else 0.0, 2),
                    }
                )

            return {"history": history[-60:]}  # Return up to last 60 trading days
        finally:
            if session:
                session.close()

    except Exception as e:
        logger.error(f"Error getting capital history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_capital_stats():
    """
    Get detailed capital statistics
    
    Returns:
        - Win rate
        - Average win/loss
        - Profit factor
        - Max drawdown
        - Sharpe ratio
    """
    try:
        from backend.database import db as database

        session = database.get_session()

        try:
            if not session:
                raise RuntimeError("Database session unavailable")

            closed_trades = _fetch_closed_trades(session)

            total_trades = len(closed_trades)
            if total_trades == 0:
                pnl_data = calculate_pnl_from_trades()
                return {
                    "starting_capital": capital_data["starting_capital"],
                    "current_capital": pnl_data["current_capital"],
                    "total_pnl": pnl_data["total_pnl"],
                    "total_return_pct": pnl_data["total_pnl_pct"],
                    "win_rate": 0.0,
                    "profit_factor": 0.0,
                    "max_drawdown_pct": 0.0,
                    "sharpe_ratio": 0.0,
                }

            pnl_values = []
            wins = 0
            losses = 0
            gross_profit = 0.0
            gross_loss = 0.0

            for trade in closed_trades:
                pnl = _ensure_trade_metrics(trade)
                pnl_values.append(pnl)
                if pnl > 0:
                    wins += 1
                    gross_profit += pnl
                elif pnl < 0:
                    losses += 1
                    gross_loss += abs(pnl)

            win_rate = (wins / total_trades * 100) if total_trades else 0.0
            profit_factor = (gross_profit / gross_loss) if gross_loss else float('inf')

            daily_pnl = _aggregate_daily_pnl(closed_trades)
            equity_curve = _build_equity_curve(daily_pnl, capital_data["starting_capital"])
            returns = [point["return"] for point in equity_curve if point["return"] != 0]
            _, max_drawdown_pct = _calculate_drawdown(equity_curve)
            sharpe_ratio = _calculate_sharpe_ratio(returns)

            pnl_data = calculate_pnl_from_trades(session)

            return {
                "starting_capital": capital_data["starting_capital"],
                "current_capital": pnl_data["current_capital"],
                "total_pnl": pnl_data["total_pnl"],
                "total_return_pct": pnl_data["total_pnl_pct"],
                "win_rate": round(win_rate, 2),
                "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else None,
                "max_drawdown_pct": round(max_drawdown_pct, 2),
                "sharpe_ratio": round(sharpe_ratio, 3),
            }
        finally:
            if session:
                session.close()

    except Exception as e:
        logger.error(f"Error getting capital stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset")
async def reset_capital():
    """
    Reset capital to default ₹1,00,000
    
    Warning: This will reset the baseline for P&L calculations
    """
    try:
        capital_data["starting_capital"] = 100000.0
        capital_data["last_updated"] = now_ist().isoformat()
        
        logger.info("✓ Capital reset to default ₹1,00,000")
        
        pnl_data = calculate_pnl_from_trades()
        
        return {
            "status": "success",
            "message": "Capital reset to default ₹1,00,000",
            "starting_capital": 100000.0,
            "current_capital": pnl_data["current_capital"],
            "total_pnl": pnl_data["total_pnl"]
        }
    
    except Exception as e:
        logger.error(f"Error resetting capital: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# HELPER FUNCTION (for use by other modules)
# ============================================================================

def get_current_capital() -> float:
    """Get current capital for position sizing calculations"""
    pnl_data = calculate_pnl_from_trades()
    return pnl_data["current_capital"]

def get_starting_capital() -> float:
    """Get starting capital"""
    return capital_data["starting_capital"]


# ============================================================================
# INTRADAY P&L TRACKING
# ============================================================================

# Store intraday P&L snapshots (time -> P&L value)
intraday_pnl_snapshots: List[Dict] = []

@router.get("/intraday-pnl")
async def get_intraday_pnl():
    """
    Get intraday P&L curve data from market open (9:15 AM IST) to now.
    Returns time-series data points for charting.
    """
    try:
        from zoneinfo import ZoneInfo
        IST = ZoneInfo("Asia/Kolkata")
        
        now = datetime.now(IST)
        today = now.date()
        market_open = datetime(today.year, today.month, today.day, 9, 15, tzinfo=IST)
        
        # Only return data if market is open or has been open today
        if now < market_open:
            return {
                "status": "pre_market",
                "data": [],
                "message": "Market has not opened yet"
            }
        
        # Get database session
        from backend.database import db as database
        session = database.get_session()
        
        try:
            # Get all trades closed today
            from backend.database import Trade
            from sqlalchemy import and_, func
            
            today_start = datetime(today.year, today.month, today.day, 0, 0, 0)
            today_end = datetime(today.year, today.month, today.day, 23, 59, 59)
            
            closed_trades = session.query(Trade).filter(
                and_(
                    Trade.exit_time >= today_start,
                    Trade.exit_time <= today_end,
                    func.lower(Trade.status) == 'closed'
                )
            ).order_by(Trade.exit_time).all()
            
            # Build intraday P&L curve from closed trades
            pnl_curve = []
            cumulative_pnl = 0.0
            
            # Add starting point at market open
            pnl_curve.append({
                "time": market_open.strftime("%H:%M"),
                "timestamp": market_open.isoformat(),
                "pnl": 0.0,
                "cumulative_pnl": 0.0
            })
            
            # Add points for each trade exit
            for trade in closed_trades:
                if trade.exit_time:
                    net_pnl = _ensure_trade_metrics(trade)
                    cumulative_pnl += net_pnl
                    # trade.exit_time is already in IST, just ensure it has timezone info
                    if trade.exit_time.tzinfo is None:
                        exit_time_ist = trade.exit_time.replace(tzinfo=IST)
                    else:
                        exit_time_ist = trade.exit_time.astimezone(IST)
                    
                    pnl_curve.append({
                        "time": exit_time_ist.strftime("%H:%M"),
                        "timestamp": exit_time_ist.isoformat(),
                        "pnl": round(net_pnl, 2),
                        "cumulative_pnl": round(cumulative_pnl, 2)
                    })
            
            # Add current snapshot with unrealized P&L
            from backend.main import app
            trading_system = getattr(app.state, 'trading_system', None)
            unrealized_pnl = 0.0
            
            if trading_system and trading_system.risk_manager:
                try:
                    positions = trading_system.risk_manager.get_open_positions()
                    unrealized_pnl = sum(pos.get('unrealized_pnl', 0) for pos in positions)
                except Exception as e:
                    logger.debug(f"Could not fetch unrealized P&L: {e}")
            
            # Add current time point with total P&L (realized + unrealized)
            total_pnl = cumulative_pnl + unrealized_pnl
            pnl_curve.append({
                "time": now.strftime("%H:%M"),
                "timestamp": now.isoformat(),
                "pnl": round(unrealized_pnl, 2),
                "cumulative_pnl": round(total_pnl, 2)
            })
            
            return {
                "status": "success",
                "data": pnl_curve,
                "market_open": market_open.isoformat(),
                "current_time": now.isoformat(),
                "realized_pnl": round(cumulative_pnl, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "total_pnl": round(total_pnl, 2)
            }
            
        finally:
            if session:
                session.close()
                
    except Exception as e:
        logger.error(f"Error getting intraday P&L: {e}")
        # Return fallback data when database is unavailable
        return {
            "status": "fallback",
            "data": [],
            "message": f"Database unavailable - using fallback: {str(e)}",
            "unrealized_pnl": 0.0,
            "total_pnl": 0.0
        }
