"""
WebSocket Manager for Real-time Dashboard Updates
Broadcasts position updates, P&L changes, alerts, and circuit breaker events
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Set, Dict, Any
import asyncio
import json
from backend.core.timezone_utils import now_ist
from datetime import datetime
from enum import Enum

from backend.core.logger import get_logger

logger = get_logger(__name__)


class MessageType(Enum):
    """WebSocket message types"""
    POSITION_UPDATE = "position_update"
    PNL_UPDATE = "pnl_update"
    CIRCUIT_BREAKER_EVENT = "circuit_breaker_event"
    ALERT = "alert"
    MARKET_CONDITION = "market_condition"
    DATA_QUALITY = "data_quality"
    SYSTEM_STATUS = "system_status"
    HEARTBEAT = "heartbeat"


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class WebSocketManager:
    """
    Manages WebSocket connections and broadcasts real-time updates
    """
    
    def __init__(self):
        # Active connections
        self.active_connections: Set[WebSocket] = set()
        
        # Connection metadata
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        
        # Heartbeat task
        self.heartbeat_task = None
        
        # Message queue for broadcasting
        self.message_queue: asyncio.Queue = asyncio.Queue()
        
        # Broadcast task
        self.broadcast_task = None
        
        logger.info("WebSocketManager initialized")
    
    async def connect(self, websocket: WebSocket, client_id: str = None):
        """
        Accept new WebSocket connection
        """
        await websocket.accept()
        self.active_connections.add(websocket)
        
        # Store metadata
        self.connection_metadata[websocket] = {
            "client_id": client_id or f"client_{id(websocket)}",
            "connected_at": now_ist(),
            "message_count": 0
        }
        
        logger.info(
            f"WebSocket connected: {self.connection_metadata[websocket]['client_id']} "
            f"(Total connections: {len(self.active_connections)})"
        )
        
        # Send initial connection success message
        await self.send_personal_message(websocket, {
            "type": "connection",
            "status": "connected",
            "client_id": self.connection_metadata[websocket]['client_id'],
            "timestamp": now_ist().isoformat()
        })
    
    def disconnect(self, websocket: WebSocket):
        """
        Remove WebSocket connection
        """
        client_id = self.connection_metadata.get(websocket, {}).get("client_id", "unknown")
        
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]
        
        logger.info(
            f"WebSocket disconnected: {client_id} "
            f"(Remaining connections: {len(self.active_connections)})"
        )
    
    async def send_personal_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """
        Send message to specific client
        """
        try:
            await websocket.send_json(message)
            
            if websocket in self.connection_metadata:
                self.connection_metadata[websocket]["message_count"] += 1
                
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
    
    def _convert_numpy_types(self, data):
        """Convert numpy types to native Python types for JSON serialization"""
        import numpy as np
        if isinstance(data, dict):
            return {k: self._convert_numpy_types(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_numpy_types(item) for item in data]
        elif isinstance(data, (np.float32, np.float64)):
            return float(data)
        elif isinstance(data, (np.int32, np.int64)):
            return int(data)
        elif isinstance(data, np.ndarray):
            return data.tolist()
        else:
            return data
    
    async def broadcast(self, message: Dict[str, Any]):
        """
        Broadcast message to all connected clients
        """
        if not self.active_connections:
            return
        
        # Convert numpy types before serialization
        message = self._convert_numpy_types(message)
        
        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = now_ist().isoformat()
        
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
                
                if connection in self.connection_metadata:
                    self.connection_metadata[connection]["message_count"] += 1
                    
            except WebSocketDisconnect:
                disconnected.add(connection)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)
        
        if disconnected:
            logger.debug(f"Cleaned up {len(disconnected)} disconnected clients")
    
    async def broadcast_position_update(self, position_data: Dict[str, Any]):
        """
        Broadcast position update
        """
        message = {
            "type": MessageType.POSITION_UPDATE.value,
            "data": position_data
        }
        await self.broadcast(message)
        logger.info(f"Broadcasted position update: {position_data.get('symbol', 'unknown')} @ ₹{position_data.get('current_price', 0)}")
    
    async def broadcast_pnl_update(self, pnl_data: Dict[str, Any]):
        """
        Broadcast P&L update
        """
        message = {
            "type": MessageType.PNL_UPDATE.value,
            "data": pnl_data
        }
        await self.broadcast(message)
        logger.debug(f"Broadcasted P&L update: {pnl_data.get('daily_pnl', 0)}")
    
    async def broadcast_circuit_breaker_event(self, event_data: Dict[str, Any]):
        """
        Broadcast circuit breaker event (triggered, reset, override)
        """
        message = {
            "type": MessageType.CIRCUIT_BREAKER_EVENT.value,
            "data": event_data
        }
        await self.broadcast(message)
        logger.warning(f"Broadcasted circuit breaker event: {event_data.get('event', 'unknown')}")
    
    async def broadcast_alert(self, alert_message: str, level: AlertLevel = AlertLevel.INFO, details: Dict[str, Any] = None):
        """
        Broadcast alert notification
        """
        message = {
            "type": MessageType.ALERT.value,
            "data": {
                "message": alert_message,
                "level": level.value,
                "details": details or {},
                "timestamp": now_ist().isoformat()
            }
        }
        await self.broadcast(message)
        
        log_method = {
            AlertLevel.INFO: logger.info,
            AlertLevel.WARNING: logger.warning,
            AlertLevel.ERROR: logger.error,
            AlertLevel.CRITICAL: logger.critical
        }.get(level, logger.info)
        
        log_method(f"Broadcasted alert [{level.value}]: {alert_message}")
    
    async def broadcast_market_condition(self, condition_data: Dict[str, Any]):
        """
        Broadcast market condition update
        """
        message = {
            "type": MessageType.MARKET_CONDITION.value,
            "data": condition_data
        }
        await self.broadcast(message)
        logger.debug(f"Broadcasted market condition: {condition_data.get('condition', 'unknown')}")
    
    async def broadcast_data_quality(self, quality_data: Dict[str, Any]):
        """
        Broadcast data quality update
        """
        message = {
            "type": MessageType.DATA_QUALITY.value,
            "data": quality_data
        }
        await self.broadcast(message)
        logger.debug(f"Broadcasted data quality: {quality_data.get('overall_quality', 'unknown')}")
    
    async def broadcast_system_status(self, status_data: Dict[str, Any]):
        """
        Broadcast system status update
        """
        message = {
            "type": MessageType.SYSTEM_STATUS.value,
            "data": status_data
        }
        await self.broadcast(message)
        logger.debug("Broadcasted system status update")
    
    async def start_heartbeat(self, interval: int = 30):
        """
        Start heartbeat task to keep connections alive
        """
        async def heartbeat_loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    
                    if self.active_connections:
                        message = {
                            "type": MessageType.HEARTBEAT.value,
                            "timestamp": now_ist().isoformat(),
                            "active_connections": len(self.active_connections)
                        }
                        await self.broadcast(message)
                        logger.debug(f"Heartbeat sent to {len(self.active_connections)} clients")
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in heartbeat loop: {e}")
        
        self.heartbeat_task = asyncio.create_task(heartbeat_loop())
        logger.info(f"Heartbeat started (interval: {interval}s)")
    
    async def stop_heartbeat(self):
        """
        Stop heartbeat task
        """
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
            logger.info("Heartbeat stopped")
    
    def get_connection_count(self) -> int:
        """
        Get number of active connections
        """
        return len(self.active_connections)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about connections
        """
        total_messages = sum(
            meta.get("message_count", 0) 
            for meta in self.connection_metadata.values()
        )
        
        return {
            "active_connections": len(self.active_connections),
            "total_messages_sent": total_messages,
            "connections": [
                {
                    "client_id": meta.get("client_id"),
                    "connected_at": meta.get("connected_at").isoformat() if meta.get("connected_at") else None,
                    "message_count": meta.get("message_count", 0)
                }
                for meta in self.connection_metadata.values()
            ]
        }


# Global WebSocket manager instance
ws_manager = WebSocketManager()


def get_ws_manager() -> WebSocketManager:
    """
    Get the global WebSocket manager instance
    """
    return ws_manager
