"""
Emergency Controls API
FastAPI endpoints for emergency controls and monitoring dashboard
PRODUCTION VERSION - Wired to actual safety systems
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Request, WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from pydantic import BaseModel

from backend.core.logger import get_logger
from backend.safety.circuit_breaker import CircuitBreaker
from backend.safety.position_manager import PositionManager
from backend.safety.market_monitor import MarketMonitor
from backend.safety.data_monitor import MarketDataMonitor
from backend.safety.order_lifecycle import OrderLifecycleManager
from backend.safety.reconciliation import TradeReconciliation
from backend.execution.risk_manager import RiskManager
from backend.api.websocket_manager import get_ws_manager

# IST timezone for all timestamps
IST = ZoneInfo("Asia/Kolkata")

logger = get_logger("emergency_controls")

router = APIRouter(prefix="/emergency", tags=["emergency"])

# Global state (will be injected from main.py)
_app_state = None

def set_app_state(state):
    """Set the application state for emergency controls"""
    global _app_state
    _app_state = state

def get_app_state():
    """Get the application state"""
    return _app_state or {}

def is_market_open() -> bool:
    """Check if market is currently open (9:15 AM - 3:25 PM IST, Mon-Fri)"""
    try:
        from backend.core.timezone_utils import is_market_hours
        return is_market_hours()
    except Exception as e:
        logger.error(f"Error checking market hours: {e}")
        return False



# Request/Response Models
class EmergencyStopRequest(BaseModel):
    """Emergency stop request"""
    reason: str
    password: str


class CircuitBreakerResetRequest(BaseModel):
    """Circuit breaker reset request"""
    reason: str
    password: Optional[str] = None


class OverrideRequest(BaseModel):
    """Override enable request"""
    reason: str
    password: str


class ClosePositionRequest(BaseModel):
    """Close position request"""
    position_id: Optional[str] = None
    symbol: Optional[str] = None
    close_all: bool = False
    reason: str


class ManualOrderRequest(BaseModel):
    """Manual order placement"""
    symbol: str
    quantity: int
    price: float
    side: str
    order_type: str = "LIMIT"
    reason: str


# Dependency for API key authentication
async def verify_api_key(x_api_key: str = Header(None)):
    """Verify API key for protected endpoints"""
    # TODO: Implement proper API key verification
    if not x_api_key or x_api_key != "EMERGENCY_KEY_123":  # Replace with actual key
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


# Emergency Controls
@router.post("/stop")
async def emergency_stop(
    request: EmergencyStopRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Emergency stop - immediately halt all trading
    
    **Protected endpoint - requires API key**
    """
    try:
        state = get_app_state()
        circuit_breaker: CircuitBreaker = state.get('circuit_breaker')
        
        if not circuit_breaker:
            raise HTTPException(status_code=500, detail="Circuit breaker not available")
        
        # Verify password
        if request.password != "OVERRIDE123":  # TODO: Use env variable
            raise HTTPException(status_code=403, detail="Invalid password")
        
        logger.critical(
            f"🚨 EMERGENCY STOP TRIGGERED 🚨\n"
            f"Reason: {request.reason}\n"
            f"Time: {datetime.now(IST)}"
        )
        
        # Execute emergency stop
        circuit_breaker.emergency_stop(request.reason)
        
        return {
            "status": "success",
            "message": "Emergency stop activated - all trading halted",
            "timestamp": datetime.now(IST).isoformat(),
            "reason": request.reason
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in emergency stop: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(
    request: CircuitBreakerResetRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Reset circuit breaker to allow trading
    
    **Protected endpoint - requires API key**
    """
    try:
        state = get_app_state()
        circuit_breaker: CircuitBreaker = state.get('circuit_breaker')
        
        if not circuit_breaker:
            raise HTTPException(status_code=500, detail="Circuit breaker not available")
        
        # Verify password if provided
        if request.password and request.password != "OVERRIDE123":
            raise HTTPException(status_code=403, detail="Invalid password")
        
        logger.warning(
            f"Circuit breaker reset requested\n"
            f"Reason: {request.reason}"
        )
        
        # Reset circuit breaker with reason and password
        circuit_breaker.reset(reason=request.reason, override_password=request.password)
        
        return {
            "status": "success",
            "message": "Circuit breaker reset - trading resumed",
            "timestamp": datetime.now(IST).isoformat(),
            "reason": request.reason
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting circuit breaker: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/override/enable")
async def enable_override(
    request: OverrideRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Enable override mode to trade despite circuit breaker
    
    **WARNING: Use with extreme caution!**
    **Protected endpoint - requires API key**
    """
    try:
        state = get_app_state()
        circuit_breaker: CircuitBreaker = state.get('circuit_breaker')
        
        if not circuit_breaker:
            raise HTTPException(status_code=500, detail="Circuit breaker not available")
        
        # Verify password
        if request.password != "OVERRIDE123":
            raise HTTPException(status_code=403, detail="Invalid password")
        
        logger.critical(
            f"⚠️ OVERRIDE MODE REQUESTED ⚠️\n"
            f"Reason: {request.reason}"
        )
        
        # Enable override mode
        circuit_breaker.enable_override(request.reason)
        
        return {
            "status": "success",
            "message": "Override mode enabled - USE WITH CAUTION",
            "timestamp": datetime.now(IST).isoformat(),
            "reason": request.reason
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling override: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/override/disable")
async def disable_override(api_key: str = Depends(verify_api_key)):
    """
    Disable override mode
    
    **Protected endpoint - requires API key**
    """
    try:
        state = get_app_state()
        circuit_breaker: CircuitBreaker = state.get('circuit_breaker')
        
        if not circuit_breaker:
            raise HTTPException(status_code=500, detail="Circuit breaker not available")
        
        logger.warning("Override mode disabled")
        
        # Disable override mode
        circuit_breaker.disable_override()
        
        return {
            "status": "success",
            "message": "Override mode disabled - normal safety checks resumed",
            "timestamp": datetime.now(IST).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling override: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Position Management
@router.post("/positions/close")
async def close_positions(
    request: ClosePositionRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Close position(s) - specific position, by symbol, or all
    
    **Protected endpoint - requires API key**
    """
    try:
        state = get_app_state()
        risk_manager = state.get('risk_manager')
        order_manager = state.get('order_manager')
        
        if not risk_manager or not order_manager:
            raise HTTPException(status_code=500, detail="Position systems not available")
        
        if request.close_all:
            logger.warning(f"Closing ALL positions - Reason: {request.reason}")
            
            # Get all positions from risk manager and close them
            positions = risk_manager.get_open_positions()
            closed_count = 0
            
            for pos in positions:
                try:
                    pos['exit_reason'] = request.reason
                    await order_manager.close_position(pos, exit_type=request.reason)
                    closed_count += 1
                except Exception as e:
                    logger.error(f"Error closing position {pos.get('id')}: {e}")
            
            message = f"Closed {closed_count}/{len(positions)} positions"
            
        elif request.position_id:
            logger.info(f"Closing position {request.position_id}")
            # Get specific position from risk manager and close it
            positions = risk_manager.get_open_positions()
            target_pos = None
            for pos in positions:
                if pos.get('id') == request.position_id:
                    target_pos = pos
                    break
            
            if target_pos:
                target_pos['exit_reason'] = request.reason
                await order_manager.close_position(target_pos, exit_type=request.reason)
            message = f"Position {request.position_id} closed"
            
        elif request.symbol:
            logger.info(f"Closing all {request.symbol} positions")
            
            # Get positions for symbol from risk manager and close them
            positions = risk_manager.get_open_positions()
            symbol_positions = [p for p in positions if p.get('symbol') == request.symbol]
            closed_count = 0
            
            for pos in symbol_positions:
                try:
                    pos['exit_reason'] = request.reason
                    await order_manager.close_position(pos, exit_type=request.reason)
                    closed_count += 1
                except Exception as e:
                    logger.error(f"Error closing position {pos.get('id')}: {e}")
            
            message = f"Closed {closed_count} {request.symbol} positions"
            
        else:
            raise HTTPException(
                status_code=400,
                detail="Must specify position_id, symbol, or close_all=true"
            )
            
        return {
            "status": "success",
            "message": message,
            "timestamp": datetime.now(IST).isoformat(),
            "reason": request.reason
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions(api_key: str = Depends(verify_api_key)):
    """
    Get all open positions with P&L
    
    **Protected endpoint - requires API key**
    """
    try:
        state = get_app_state()
        position_manager: PositionManager = state.get('position_manager')
        
        if not position_manager:
            # Return empty positions if position manager not initialized
            return {
                "status": "success",
                "positions": [],
                "total_positions": 0,
                "total_unrealized_pnl": 0.0,
                "message": "Position manager not yet initialized"
            }
        
        # Get all positions
        positions = position_manager.get_all_positions()
        
        # Format positions for response
        positions_data = []
        total_unrealized_pnl = 0.0
        
        for pos in positions:
            pnl = pos.get_unrealized_pnl()
            pnl_percent = pos.get_pnl_percent()
            total_unrealized_pnl += pnl
            
            positions_data.append({
                "id": pos.id,
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "side": pos.side,
                "entry_price": pos.entry_price,
                "current_price": pos.current_price,
                "unrealized_pnl": pnl,
                "pnl_percent": pnl_percent,
                "strategy": pos.strategy_name,
                "entry_time": pos.entry_time.isoformat() if pos.entry_time else None
            })
        
        return {
            "status": "success",
            "positions": positions_data,
            "total_positions": len(positions_data),
            "total_unrealized_pnl": total_unrealized_pnl,
            "timestamp": datetime.now(IST).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Manual Trading
@router.post("/manual-order")
async def place_manual_order(
    request: ManualOrderRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Place manual order (bypasses strategies)
    
    **Protected endpoint - requires API key**
    **Still subject to order validator checks**
    """
    try:
        state = get_app_state()
        order_lifecycle: OrderLifecycleManager = state.get('order_lifecycle')
        circuit_breaker: CircuitBreaker = state.get('circuit_breaker')
        
        if not order_lifecycle:
            raise HTTPException(status_code=500, detail="Order lifecycle manager not available")
        
        # Check if trading is allowed
        if circuit_breaker and not circuit_breaker.is_trading_allowed():
            raise HTTPException(
                status_code=403,
                detail="Trading is not allowed - circuit breaker is active"
            )
        
        logger.warning(
            f"Manual order requested: {request.side} {request.quantity} "
            f"{request.symbol} @ {request.price}\n"
            f"Reason: {request.reason}"
        )
        
        # Create and place manual order
        from backend.models.order import Order, OrderType, OrderSide
        
        order = Order(
            symbol=request.symbol,
            quantity=request.quantity,
            price=request.price,
            side=OrderSide.BUY if request.side.upper() == "BUY" else OrderSide.SELL,
            order_type=OrderType.LIMIT if request.order_type == "LIMIT" else OrderType.MARKET,
            strategy_name="MANUAL",
            metadata={"reason": request.reason, "manual": True}
        )
        
        # Place order through lifecycle manager
        order_id = await order_lifecycle.place_order(order)
        
        return {
            "status": "success",
            "message": "Manual order placed",
            "order_id": order_id,
            "timestamp": datetime.now(IST).isoformat(),
            "reason": request.reason
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error placing manual order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Status and Monitoring
@router.get("/status")
async def get_emergency_status():
    """
    Get emergency controls status - REAL DATA
    
    **Public endpoint - no authentication required**
    """
    try:
        state = get_app_state()
        
        circuit_breaker: CircuitBreaker = state.get('circuit_breaker')
        market_monitor: MarketMonitor = state.get('market_monitor')
        position_manager: PositionManager = state.get('position_manager')
        risk_manager: RiskManager = state.get('risk_manager')

        daily_loss = risk_manager.get_daily_pnl() if risk_manager else 0.0
        daily_loss_percent = risk_manager.get_daily_pnl_percent() if risk_manager else 0.0
        
        # Check if market is open
        market_open = is_market_open()
        
        # Trading is allowed only if circuit breaker allows AND market is open
        cb_allowed = circuit_breaker.is_trading_allowed() if circuit_breaker else False
        trading_allowed = cb_allowed and market_open
        
        # Build status from real systems
        status = {
            "timestamp": datetime.now(IST).isoformat(),
            "circuit_breaker": {
                "status": circuit_breaker.get_status() if circuit_breaker else "unknown",
                "trading_allowed": trading_allowed,  # Now considers market hours
                "market_open": market_open,  # New field
                "circuit_breaker_allowed": cb_allowed,  # Original CB status
                "override_enabled": circuit_breaker.is_override_enabled() if circuit_breaker else False,
                "triggers": circuit_breaker.get_active_triggers() if circuit_breaker else [],
                "daily_loss": daily_loss,
                "daily_loss_percent": daily_loss_percent
            },
            "market_condition": {
                "condition": market_monitor.market_condition.value if market_monitor else "unknown",
                "current_vix": market_monitor.current_vix if market_monitor else 0.0,
                "is_market_halted": market_monitor.is_market_halted if market_monitor else False,
                "recent_shocks": market_monitor.get_recent_shocks() if market_monitor else []
            },
            "positions": {
                "total_positions": len(position_manager.positions) if position_manager else 0,
                "used_margin": position_manager.get_used_margin() if position_manager else 0.0,
                "available_margin": position_manager.available_margin if position_manager else 0.0,
                "capital_utilization": position_manager.get_capital_utilization() if position_manager else 0.0
            }
        }
        
        return {
            "status": "success",
            "data": status
        }
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        # Return graceful degradation
        return {
            "status": "error",
            "message": str(e),
            "data": {
                "timestamp": datetime.now(IST).isoformat(),
                "circuit_breaker": {"status": "unavailable"},
                "market_condition": {"condition": "unavailable"},
                "positions": {"total_positions": 0}
            }
        }


@router.get("/risk-metrics")
async def get_risk_metrics(api_key: str = Depends(verify_api_key)):
    """
    Get comprehensive risk metrics
    
    **Protected endpoint - requires API key**
    """
    try:
        state = get_app_state()
        circuit_breaker: CircuitBreaker = state.get('circuit_breaker')
        position_manager: PositionManager = state.get('position_manager')
        risk_manager: RiskManager = state.get('risk_manager')
        
        if not risk_manager or not position_manager:
            # Return empty metrics if systems not initialized
            return {
                "status": "success",
                "data": {
                    "timestamp": datetime.now(IST).isoformat(),
                    "daily_pnl": 0.0,
                    "daily_pnl_percent": 0.0,
                    "max_drawdown": 0.0,
                    "sharpe_ratio": 0.0,
                    "win_rate": 0.0,
                    "total_trades": 0,
                    "capital_utilization": 0.0,
                    "largest_position_percent": 0.0,
                    "exposure_by_strategy": {},
                    "message": "Risk systems not yet initialized"
                }
            }
        
        # Calculate risk metrics
        positions = position_manager.get_all_positions()
        def _safe_get(position: Dict, key: str, default=0.0):
            if isinstance(position, dict):
                return position.get(key, default)
            return getattr(position, key, default)

        total_pnl = sum(_safe_get(p, 'unrealized_pnl', 0.0) for p in positions)
        
        # Get strategy breakdown
        exposure_by_strategy = {}
        for pos in positions:
            strategy = _safe_get(pos, 'strategy_name') or _safe_get(pos, 'strategy') or 'unknown'
            if strategy not in exposure_by_strategy:
                exposure_by_strategy[strategy] = 0.0
            quantity = _safe_get(pos, 'quantity', 0)
            current_price = _safe_get(pos, 'current_price', 0.0)
            exposure_by_strategy[strategy] += abs(quantity * current_price)
        
        # Calculate largest position
        largest_position_value = 0.0
        for pos in positions:
            quantity = _safe_get(pos, 'quantity', 0)
            current_price = _safe_get(pos, 'current_price', 0.0)
            position_value = abs(quantity * current_price)
            if position_value > largest_position_value:
                largest_position_value = position_value

        total_capital = position_manager.total_capital if position_manager else 0.0
        largest_position_percent = (largest_position_value / total_capital * 100) if total_capital > 0 else 0.0
        
        metrics = {
            "timestamp": datetime.now(IST).isoformat(),
            "daily_pnl": risk_manager.get_daily_pnl(),
            "daily_pnl_percent": risk_manager.get_daily_pnl_percent(),
            "max_drawdown": risk_manager.get_max_drawdown_percent(),
            "sharpe_ratio": 0.0,  # TODO: Calculate from trade history
            "win_rate": risk_manager.get_win_rate() * 100,
            "total_trades": risk_manager.get_total_trades(),
            "capital_utilization": position_manager.get_capital_utilization(),
            "largest_position_percent": largest_position_percent,
            "var_95": 0.0,  # TODO: Calculate VaR from historical returns
            "exposure_by_strategy": exposure_by_strategy,
            "total_unrealized_pnl": total_pnl,
            "used_margin": position_manager.get_used_margin(),
            "available_margin": position_manager.available_margin
        }
        
        return {
            "status": "success",
            "data": metrics
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting risk metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data-quality")
async def get_data_quality():
    """
    Get market data quality report
    
    **Public endpoint - no authentication required**
    """
    try:
        state = get_app_state()
        data_monitor: MarketDataMonitor = state.get('data_monitor')
        
        if not data_monitor:
            # Return empty data quality report if monitor not initialized
            return {
                "status": "success",
                "report": {
                    "timestamp": datetime.now(IST).isoformat(),
                    "overall_quality": "good",
                    "symbols": {},
                    "streaming_health": True,
                    "total_symbols": 0,
                    "stale_count": 0,
                    "message": "Data monitor not yet initialized"
                }
            }
        
        # Get quality report from data monitor
        quality_report = data_monitor.get_quality_report()
        
        # Format for response
        report = {
            "timestamp": datetime.now(IST).isoformat(),
            "overall_quality": quality_report.get("overall_quality", "unknown"),
            "symbols": quality_report.get("symbol_quality", {}),
            "streaming_health": quality_report.get("streaming_healthy", False),
            "total_symbols": len(quality_report.get("symbol_quality", {})),
            "stale_count": sum(1 for s in quality_report.get("symbol_quality", {}).values() if s.get("is_stale", False))
        }
        
        return {
            "status": "success",
            "report": report
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting data quality: {e}")
        # Return graceful degradation
        return {
            "status": "error",
            "message": str(e),
            "report": {
                "timestamp": datetime.now(IST).isoformat(),
                "overall_quality": "unavailable",
                "symbols": {},
                "streaming_health": False
            }
        }


@router.get("/logs/recent")
async def get_recent_logs(
    lines: int = 50,
    level: str = "INFO",
    api_key: str = Depends(verify_api_key)
):
    """
    Get recent log entries
    
    **Protected endpoint - requires API key**
    """
    try:
        import os
        from pathlib import Path
        
        # Find log file
        log_dir = Path("logs")
        log_file = log_dir / "trading.log"
        
        if not log_file.exists():
            return {
                "status": "success",
                "logs": [],
                "count": 0,
                "message": "No log file found"
            }
        
        # Read last N lines from log file
        log_entries = []
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        # Parse log lines
        for line in recent_lines:
            # Simple parsing - assumes format: timestamp [LEVEL] message
            try:
                parts = line.split(' ', 2)
                if len(parts) >= 3:
                    timestamp_str = parts[0] + ' ' + parts[1]
                    level_match = parts[2].split(']', 1)
                    if len(level_match) >= 2:
                        log_level = level_match[0].replace('[', '').strip()
                        message = level_match[1].strip()
                        
                        # Filter by level if specified
                        if level.upper() == "ALL" or log_level == level.upper():
                            log_entries.append({
                                "timestamp": timestamp_str,
                                "level": log_level,
                                "message": message
                            })
            except Exception as e:
                logger.debug(f"Error parsing log line: {e}")
                continue
        
        return {
            "status": "success",
            "logs": log_entries,
            "count": len(log_entries),
            "level_filter": level
        }
        
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health Check
@router.get("/health")
async def health_check():
    """
    Health check endpoint
    
    **Public endpoint - no authentication required**
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(IST).isoformat(),
        "service": "emergency-controls",
        "version": "1.0.0"
    }


# WebSocket Endpoint
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates
    
    Broadcasts:
    - Position updates
    - P&L changes
    - Circuit breaker events
    - Alerts
    - Market condition changes
    - Data quality updates
    - System status
    
    **Public endpoint - no authentication required for now**
    TODO: Add WebSocket authentication in production
    """
    ws_manager = get_ws_manager()
    
    await ws_manager.connect(websocket)
    
    try:
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Receive messages from client (e.g., ping, subscription requests)
                data = await websocket.receive_text()
                
                # Echo back for now (can add subscription logic later)
                logger.debug(f"Received WebSocket message: {data}")
                
                # Could implement subscription filtering here:
                # - Subscribe to specific position updates
                # - Subscribe to specific alert levels
                # - etc.
                
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected normally")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}")
                break
                
    finally:
        ws_manager.disconnect(websocket)


# WebSocket Stats Endpoint
@router.get("/ws/stats")
async def websocket_stats(api_key: str = Depends(verify_api_key)):
    """
    Get WebSocket connection statistics
    
    **Protected endpoint - requires API key**
    """
    ws_manager = get_ws_manager()
    stats = ws_manager.get_connection_stats()
    
    return {
        "status": "success",
        "stats": stats,
        "timestamp": datetime.now(IST).isoformat()
    }
