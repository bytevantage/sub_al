"""
Dashboard API Endpoints
Authoritative endpoints for dashboard widgets (positions, risk metrics, trade history)
"""

from datetime import datetime, time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.core.logger import get_logger
from backend.database.database import db
from backend.database.models import Trade
from backend.core.timezone_utils import now_ist, today_ist, start_of_day_ist, ist_isoformat, is_market_hours
import logging

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Cache for positions data to reduce API load
_positions_cache = {}
_positions_cache_timeout = 15  # 15 seconds cache for positions (increased from 5)

logger = get_logger(__name__)

_trading_system: Optional[Any] = None


def set_trading_system(system: Any) -> None:
    """Inject trading system reference once initialized."""
    global _trading_system
    _trading_system = system


def _require_trading_system() -> Any:
    if _trading_system is None:
        raise HTTPException(status_code=503, detail="Trading system not initialized yet")
    return _trading_system


def _round(value: Optional[float], digits: int = 2) -> float:
    if value is None:
        return 0.0
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return 0.0


@router.get("/system-status")
async def get_system_status() -> Dict[str, Any]:
    """Get system status including strategy count and ML integration status"""
    return {
        "status": "active",
        "strategy_count": 6,
        "strategies": [
            "Quantum Edge V2",
            "Quantum Edge", 
            "Default ORB",
            "Gamma Scalping",
            "VWAP Deviation",
            "IV Rank Trading"
        ],
        "ml_integration_status": "pending",
        "banner": "ML integration pending – Quantum Edge V2 is rule-based",
        "deployment_date": "2025-11-21",
        "mode": "production_ready"
    }


@router.get("/positions")
async def get_positions_snapshot() -> Dict[str, Any]:
    """Return open positions tailored for dashboard consumption."""
    # Check cache first
    cache_key = "positions_data"
    now = datetime.now()
    market_open = is_market_hours()
    cache_ttl = 0 if market_open else _positions_cache_timeout
    
    if cache_key in _positions_cache and cache_ttl > 0:
        cached_data, cached_time = _positions_cache[cache_key]
        if (now - cached_time).total_seconds() < cache_ttl:
            return cached_data
    
    system = _require_trading_system()
    risk_manager = getattr(system, "risk_manager", None)
    position_manager = getattr(system, "position_manager", None)

    if not risk_manager:
        return {
            "status": "success",
            "data": {
                "timestamp": ist_isoformat(),
                "positions": [],
                "totals": {
                    "count": 0,
                    "total_unrealized_pnl": 0.0,
                    "used_margin": position_manager.get_used_margin() if position_manager else 0.0,
                    "available_margin": getattr(position_manager, "available_margin", 0.0) if position_manager else 0.0,
                    "capital_utilization": position_manager.get_capital_utilization() if position_manager else 0.0,
                },
            },
        }

    summaries = risk_manager.get_open_positions_summary()
    positions: List[Dict[str, Any]] = []
    total_unrealized = 0.0

    for pos in summaries:
        entry_price = _round(pos.get("entry_price"))
        current_price = _round(pos.get("current_price"))
        pnl = _round(pos.get("unrealized_pnl"))
        pnl_percent = _round(pos.get("pnl_percent"))
        total_unrealized += pnl
        
        # Get stop loss and targets
        stop_loss = _round(pos.get("stop_loss", 0))
        trailing_sl = _round(pos.get("trailing_sl", stop_loss))
        target_price = _round(pos.get("target_price", 0))
        
        # Calculate target levels if not stored (backward compatibility)
        if entry_price > 0 and target_price > 0:
            target_pct = ((target_price - entry_price) / entry_price) * 100
            target_1 = _round(entry_price * (1 + target_pct * 0.005))  # 50% of target
            target_2 = target_price  # Main target
            target_3 = _round(entry_price * (1 + target_pct * 0.015))  # 150% of target
        else:
            target_1 = target_2 = target_3 = 0

        # Get option details
        strike_price = pos.get("strike_price", 0)
        option_type = pos.get("instrument_type", "")  # CALL or PUT
        option_type_short = "CE" if option_type == "CALL" else "PE" if option_type == "PUT" else ""
        
        positions.append(
            {
                "id": pos.get("id"),
                "symbol": pos.get("symbol"),
                "strike_price": strike_price,
                "option_type": option_type_short,  # CE or PE
                "side": pos.get("direction") or pos.get("side"),
                "quantity": pos.get("quantity", 0),
                "entry_price": entry_price,
                "current_price": current_price,
                "unrealized_pnl": pnl,
                "pnl_percent": pnl_percent,
                "strategy": pos.get("strategy"),
                "entry_time": pos.get("entry_time"),
                "status": pos.get("status", "open"),
                # Risk management levels
                "stop_loss": stop_loss,
                "trailing_sl": trailing_sl,
                "target_1": target_1,
                "target_2": target_2,
                "target_3": target_3,
                "highest_price": _round(pos.get("highest_price", entry_price)),
            }
        )

    totals: Dict[str, Any] = {
        "count": len(positions),
        "total_unrealized_pnl": _round(total_unrealized),
        "used_margin": position_manager.get_used_margin() if position_manager else 0.0,
        "available_margin": getattr(position_manager, "available_margin", 0.0) if position_manager else 0.0,
        "capital_utilization": position_manager.get_capital_utilization() if position_manager else 0.0,
    }

    response = {
        "status": "success",
        "data": {
            "timestamp": now_ist().isoformat(),
            "positions": positions,
            "totals": totals,
        },
    }
    
    # Store in cache
    _positions_cache[cache_key] = (response, now)
    
    return response


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
            import asyncio
            session = db.get_session()
            
            # Add timeout to database query
            async def get_trade_stats():
                return (
                    session.query(Trade)
                    .filter(Trade.trade_date >= today_ist().date())
                    .with_entities(
                        db.func.sum(Trade.pnl).label("realized_pnl"),
                        db.func.count(Trade.id).label("total_trades"),
                    )
                    .all()
                )
        
        # Run with timeout
            result = await asyncio.wait_for(get_trade_stats(), timeout=5.0)
            if result and result[0]:
                today_realized_pnl = float(result[0].realized_pnl or 0.0)
                total_trades_today = int(result[0].total_trades or 0)
                
        except asyncio.TimeoutError:
            logger.warning("Database query timeout in risk metrics - using fallback values")
            today_realized_pnl = 0.0
            total_trades_today = 0
        except Exception as e:
            logger.warning(f"Database error in risk metrics: {e} - using fallback values")
            today_realized_pnl = 0.0
            total_trades_today = 0
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
        
        # Calculate daily P&L percentage
        daily_pnl_percent = (today_total_pnl / capital_total * 100) if capital_total > 0 else 0.0

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
            "available_margin": getattr(position_manager, "available_margin", 0.0) if position_manager else 0.0,
            "exposure_by_strategy": exposure_by_strategy,
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
                "exposure_by_strategy": {},
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
        session = db.get_session()
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
