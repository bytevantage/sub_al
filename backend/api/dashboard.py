"""
Dashboard API endpoints for the trading system
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List
import pytz
from datetime import datetime, date
import asyncio
import logging

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Global trading system reference
_trading_system = None

def set_trading_system(system: Any) -> None:
    """Inject trading system reference once initialized."""
    global _trading_system
    _trading_system = system

def _require_trading_system() -> Any:
    if _trading_system is None:
        raise HTTPException(status_code=503, detail="Trading system not initialized yet")
    return _trading_system

def _round(value: float, decimals: int = 2) -> float:
    """Round a float to specified decimals."""
    if value is None:
        return 0.0
    return round(float(value), decimals)

def ist_isoformat():
    """Get current IST time in ISO format"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist).isoformat()

def today_ist():
    """Get today's date in IST"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist).date()

def start_of_day_ist():
    """Get start of today in IST"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist).replace(hour=0, minute=0, second=0, microsecond=0)

logger = logging.getLogger(__name__)

@router.get("/positions")
async def get_positions() -> Dict[str, Any]:
    """Get current positions with real-time P&L."""
    try:
        system = _require_trading_system()
        risk_manager = getattr(system, "risk_manager", None)
        
        if not risk_manager:
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
                        "capital_utilization": 0.0,
                    },
                    "message": "Risk manager not initialized",
                },
            }

        positions = risk_manager.get_open_positions_summary()
        
        # Calculate totals
        total_unrealized_pnl = sum(p.get("unrealized_pnl", 0.0) or 0.0 for p in positions)
        position_manager = getattr(system, "position_manager", None)
        
        response = {
            "status": "success",
            "data": {
                "timestamp": ist_isoformat(),
                "positions": positions,
                "totals": {
                    "count": len(positions),
                    "total_unrealized_pnl": _round(total_unrealized_pnl),
                    "used_margin": position_manager.get_used_margin() if position_manager else 0.0,
                    "available_margin": getattr(position_manager, "available_margin", 0.0) if position_manager else 100000.0,
                    "capital_utilization": position_manager.get_capital_utilization() if position_manager else 0.0,
                },
            },
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        # Return fallback data
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
                    "capital_utilization": 0.0,
                },
                "message": f"Database unavailable - using fallback: {str(e)[:100]}"
            },
        }

@router.get("/risk-metrics")
async def get_risk_metrics_snapshot() -> Dict[str, Any]:
    """Return risk metrics without requiring emergency credentials."""
    try:
        system = _require_trading_system()
        risk_manager = getattr(system, "risk_manager", None)
        position_manager = getattr(system, "position_manager", None)

        if not risk_manager:
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
                    "capital_utilization": position_manager.get_capital_utilization() if position_manager else 0.0,
                    "largest_position_percent": 0.0,
                    "total_unrealized_pnl": 0.0,
                    "used_margin": position_manager.get_used_margin() if position_manager else 0.0,
                    "available_margin": getattr(position_manager, "available_margin", 0.0) if position_manager else 0.0,
                    "message": "Risk manager not initialized",
                },
            }

        positions = risk_manager.get_open_positions_summary()
        capital_total = position_manager.total_capital if position_manager else risk_manager.initial_capital

        # Strategy exposure and largest position calculations
        exposure_by_strategy: Dict[str, float] = {}
        largest_position_value = 0.0

        for pos in positions:
            strategy = pos.get("strategy") or "unknown"
            quantity = pos.get("quantity", 0)
            current_price = _round(pos.get("current_price"))
            position_value = abs(quantity * current_price)
            exposure_by_strategy[strategy] = exposure_by_strategy.get(strategy, 0.0) + position_value
            largest_position_value = max(largest_position_value, position_value)

        largest_position_percent = (
            (largest_position_value / capital_total * 100) if capital_total else 0.0
        )

        # Get realized P&L from trades today (with timeout)
        today_realized_pnl = 0.0
        total_trades_today = 0
        winning_trades = 0
        losing_trades = 0
        
        try:
            from backend.database import db as database
            from backend.database import Trade
            from sqlalchemy import case
            import asyncio
            session = database.get_session()
            
            # Add timeout to database query
            async def get_trade_stats():
                return (
                    session.query(Trade)
                    .filter(Trade.trade_date >= today_ist().date())
                    .with_entities(
                        database.func.sum(Trade.net_pnl).label("realized_pnl"),
                        database.func.count(Trade.id).label("total_trades"),
                        database.func.sum(case((Trade.net_pnl > 0, 1), (Trade.net_pnl <= 0, 0))).label("winning_trades"),
                        database.func.sum(case((Trade.net_pnl < 0, 1), (Trade.net_pnl >= 0, 0))).label("losing_trades"),
                    )
                    .all()
                )
            
            # Run with timeout
            result = await asyncio.wait_for(get_trade_stats(), timeout=5.0)
            if result and result[0]:
                today_realized_pnl = float(result[0].realized_pnl or 0.0)
                total_trades_today = int(result[0].total_trades or 0)
                winning_trades = int(result[0].winning_trades or 0)
                losing_trades = int(result[0].losing_trades or 0)
                
        except asyncio.TimeoutError:
            logger.warning("Database query timeout in risk metrics - using fallback values")
            today_realized_pnl = 0.0
            total_trades_today = 0
            winning_trades = 0
            losing_trades = 0
        except Exception as e:
            logger.warning(f"Database error in risk metrics: {e} - using fallback values")
            today_realized_pnl = 0.0
            total_trades_today = 0
            winning_trades = 0
            losing_trades = 0
        finally:
            try:
                session.close()
            except:
                pass

        # Add unrealized P&L from open positions
        total_unrealized_pnl = sum(p.get("unrealized_pnl", 0.0) or 0.0 for p in positions)
        today_total_pnl = today_realized_pnl + total_unrealized_pnl
        
        # Calculate win rate
        win_rate = (winning_trades / total_trades_today * 100) if total_trades_today > 0 else 0.0
        
        # Calculate daily P&L percentage based on initial capital
        initial_capital = getattr(risk_manager, 'initial_capital', 100000.0)
        daily_pnl_percent = (today_total_pnl / initial_capital * 100) if initial_capital > 0 else 0.0

        # Get market data for IV Rank and VWAP
        market_data_manager = getattr(system, "market_data_manager", None)
        iv_rank = 50.0  # Default fallback
        vwap_deviation = 0.0
        sac_status = "EXPLORING"  # Default status
        
        try:
            if market_data_manager:
                # Get IV Rank for primary symbol (SENSEX)
                primary_symbol = "SENSEX"
                iv_rank_calculator = getattr(market_data_manager, "iv_rank_calculator", None)
                if iv_rank_calculator:
                    import asyncio
                    try:
                        iv_rank_data = asyncio.run(iv_rank_calculator.get_real_iv_rank(primary_symbol))
                        if iv_rank_data and 'iv_rank' in iv_rank_data:
                            iv_rank = float(iv_rank_data['iv_rank'])
                    except Exception as e:
                        logger.warning(f"Error getting IV Rank: {e}")
                
                # Get VWAP deviation for primary symbol
                vwap_calculator = getattr(market_data_manager, "session_vwap", None)
                if vwap_calculator:
                    try:
                        vwap_data = asyncio.run(vwap_calculator.get_session_vwap(primary_symbol))
                        if vwap_data and vwap_data.get('spot_price') and vwap_data.get('vwap'):
                            spot_price = vwap_data['spot_price']
                            vwap = vwap_data['vwap']
                            vwap_deviation = ((spot_price - vwap) / vwap * 100) if vwap > 0 else 0.0
                    except Exception as e:
                        logger.warning(f"Error getting VWAP: {e}")
                
                # Get SAC status
                sac_agent = getattr(system, "sac_agent", None)
                if sac_agent:
                    sac_status = "EXPLORING" if getattr(sac_agent, "exploration", True) else "PRODUCTION"
        except Exception as e:
            logger.warning(f"Error getting market data: {e}")

        # Calculate portfolio delta and gamma from open positions
        net_delta = 0.0
        total_gamma = 0.0
        
        try:
            if positions:
                for pos in positions:
                    quantity = pos.get('quantity', 0)
                    current_price = pos.get('current_price', 0)
                    instrument_type = pos.get('instrument_type', '').upper()
                    direction = pos.get('direction', 'BUY').upper()
                    
                    # Get Greeks from position metadata or calculate
                    delta = pos.get('delta', 0.0)
                    gamma = pos.get('gamma', 0.0)
                    
                    # If Greeks not stored, estimate based on option type
                    if delta == 0.0:
                        if instrument_type == 'CALL':
                            # Rough delta estimation for calls (0-1 range)
                            moneyness = current_price / pos.get('strike_price', current_price)
                            if moneyness > 1.05:  # ITM
                                delta = 0.7 + 0.3 * min(1, (moneyness - 1.05) / 0.1)
                            elif moneyness < 0.95:  # OTM
                                delta = 0.3 * max(0, moneyness / 0.95)
                            else:  # ATM
                                delta = 0.5
                        elif instrument_type == 'PUT':
                            # Rough delta estimation for puts (-1 to 0 range)
                            moneyness = current_price / pos.get('strike_price', current_price)
                            if moneyness < 0.95:  # ITM
                                delta = -0.7 - 0.3 * min(1, (0.95 - moneyness) / 0.1)
                            elif moneyness > 1.05:  # OTM
                                delta = -0.3 * max(0, 1.05 / moneyness)
                            else:  # ATM
                                delta = -0.5
                    
                    if gamma == 0.0:
                        # Rough gamma estimation (higher for ATM options)
                        moneyness = current_price / pos.get('strike_price', current_price)
                        if 0.95 <= moneyness <= 1.05:  # Near ATM
                            gamma = 0.05  # Higher gamma for ATM
                        else:
                            gamma = 0.02  # Lower gamma for ITM/OTM
                    
                    # Calculate position contribution
                    position_delta = delta * quantity
                    position_gamma = gamma * quantity
                    
                    # Apply direction multiplier
                    if direction == 'SELL':
                        position_delta *= -1
                        position_gamma *= -1
                    
                    net_delta += position_delta
                    total_gamma += position_gamma
                    
        except Exception as e:
            logger.warning(f"Error calculating Greeks: {e}")

        # Calculate current capital
        current_capital = initial_capital + today_realized_pnl
        available_margin = current_capital - (position_manager.get_used_margin() if position_manager else 0.0)
        
        metrics: Dict[str, Any] = {
            "timestamp": ist_isoformat(),
            "daily_pnl": _round(today_total_pnl),
            "daily_pnl_percent": _round(daily_pnl_percent),
            "max_drawdown": _round(risk_manager.get_max_drawdown_percent()),
            "sharpe_ratio": 0.0,  # TODO: calculate when return series available
            "win_rate": _round(win_rate),
            "total_trades": total_trades_today,
            "capital_utilization": position_manager.get_capital_utilization() if position_manager else 0.0,
            "largest_position_percent": _round(largest_position_percent),
            "total_unrealized_pnl": _round(total_unrealized_pnl),
            "used_margin": position_manager.get_used_margin() if position_manager else 0.0,
            "available_margin": _round(available_margin),
            "current_capital": _round(current_capital),
            "initial_capital": _round(initial_capital),
            "exposure_by_strategy": exposure_by_strategy,
            # Market metrics
            "iv_rank": _round(iv_rank),
            "vwap_deviation": _round(vwap_deviation),
            "sac_status": sac_status,
            "net_delta": _round(net_delta, 2),
            "total_gamma": _round(total_gamma, 3),
        }

        return {"status": "success", "data": metrics}
        
    except Exception as e:
        # Fallback when database or other errors occur
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
                "current_capital": 100000.0,
                "initial_capital": 100000.0,
                "exposure_by_strategy": {},
                # Market metrics fallback
                "iv_rank": 50.0,  # Default IV Rank
                "vwap_deviation": 0.0,
                "sac_status": "EXPLORING",
                "net_delta": 0.0,  # No positions = 0 delta
                "total_gamma": 0.0,  # No positions = 0 gamma
                "message": f"Database unavailable - using fallback: {str(e)[:100]}"
            }
        }

@router.get("/trades/recent")
async def get_recent_trades(
    limit: int = Query(25, ge=1, le=200),
    today_only: bool = Query(True, description="Limit to trades from today"),
) -> Dict[str, Any]:
    """Return the most recent trades for dashboard display."""
    try:
        from backend.database import db as database
        from backend.database import Trade
        session = database.get_session()
        if not session:
            raise HTTPException(status_code=503, detail="Database not available")

        query = session.query(Trade).order_by(Trade.entry_time.desc())

        if today_only:
            # Use IST timezone for accurate "today" filtering
            start_of_today = start_of_day_ist()
            # Convert to naive datetime for database comparison (DB stores as naive)
            start_of_day_naive = start_of_today.replace(tzinfo=None)
            query = query.filter(Trade.entry_time >= start_of_day_naive)

        trades: List[Trade] = query.limit(limit).all()

        trade_rows: List[Dict[str, Any]] = []
        for trade in trades:
            trade_dict = trade.to_dict()
            trade_rows.append(
                {
                    "trade_id": trade_dict.get("trade_id"),
                    "entry_time": trade_dict.get("entry_time"),
                    "exit_time": trade_dict.get("exit_time"),
                    "symbol": trade_dict.get("symbol"),
                    "direction": trade_dict.get("instrument_type"),
                    "instrument_type": trade_dict.get("instrument_type"),
                    "strike_price": trade_dict.get("strike_price"),
                    "entry_price": trade_dict.get("entry_price"),
                    "exit_price": trade_dict.get("exit_price"),
                    "quantity": trade_dict.get("quantity"),
                    "net_pnl": trade_dict.get("net_pnl"),
                    "pnl_percentage": trade_dict.get("pnl_percentage"),
                    "strategy_name": trade_dict.get("strategy_name"),
                    "status": trade_dict.get("status"),
                    "hold_duration_minutes": trade_dict.get("hold_duration_minutes"),
                }
            )

        return {
            "status": "success",
            "data": {
                "timestamp": ist_isoformat(),
                "count": len(trade_rows),
                "trades": trade_rows,
            },
        }
    except Exception as exc:
        logger.error(f"Error fetching recent trades: {exc}")
        # Return fallback data instead of throwing error
        return {
            "status": "success",
            "data": {
                "timestamp": ist_isoformat(),
                "count": 0,
                "trades": [],
                "message": f"Database unavailable - using fallback: {str(exc)[:100]}"
            },
        }
    finally:
        try:
            session.close()
        except:
            pass
