"""
Structured Logging API Endpoints
Manage and monitor structured logging
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from backend.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/logging", tags=["logging"])

@router.get("/status")
async def get_logging_status():
    """Get structured logging status and configuration"""
    try:
        from backend.logging.structured_logger import get_structured_logger
        
        structured_logger = get_structured_logger('api')
        
        return {
            "status": "enabled",
            "format": "json",
            "timestamp": datetime.now().isoformat(),
            "logger_count": len(structured_logger.logger.handlers),
            "log_level": structured_logger.logger.level,
            "default_context": structured_logger.default_context
        }
        
    except Exception as e:
        logger.error(f"Error getting logging status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test")
async def test_structured_logging():
    """Test structured logging with sample events"""
    try:
        from backend.logging.structured_logger import get_structured_logger
        
        test_logger = get_structured_logger('test')
        
        # Test different log types
        test_logger.info("Test info message", test_type="info", user_id="test_user")
        test_logger.warning("Test warning message", test_type="warning", severity="medium")
        test_logger.error("Test error message", test_type="error", error_code="TEST_001")
        
        # Test specialized logging
        test_logger.log_api_request("GET", "/test", 200, 0.05, user_id="test_user")
        test_logger.log_database_query("SELECT", "trades", 0.02, rows_affected=10)
        test_logger.log_cache_operation("get", "redis", "test_key", hit=True, duration=0.001)
        test_logger.log_trading_event("entry", "NIFTY", "gamma_scalping", quantity=25, price=150.25)
        test_logger.log_market_data("spot_price", "NIFTY", "upstox", records_count=1)
        test_logger.log_health_check("test_check", "healthy", 0.01)
        test_logger.log_performance_metric("response_time", 0.05, "seconds", endpoint="/test")
        test_logger.log_business_event("user_login", user_id="test_user", ip="127.0.0.1")
        
        return {
            "status": "success",
            "message": "Structured logging test completed",
            "timestamp": datetime.now().isoformat(),
            "events_logged": 10
        }
        
    except Exception as e:
        logger.error(f"Error testing structured logging: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sample")
async def get_log_sample(event_type: Optional[str] = None, limit: int = Query(default=10, ge=1, le=100)):
    """Get sample structured log entries (simulated)"""
    try:
        # Simulate structured log entries for demo
        sample_logs = [
            {
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "service": "trading_engine",
                "event_type": "api_request",
                "method": "GET",
                "endpoint": "/api/positions",
                "status_code": 200,
                "response_time": 0.045,
                "user_id": "user_123"
            },
            {
                "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(),
                "level": "INFO",
                "service": "trading_engine",
                "event_type": "trading_event",
                "trading_event": "entry",
                "symbol": "NIFTY",
                "strategy": "gamma_scalping",
                "quantity": 25,
                "price": 150.25
            },
            {
                "timestamp": (datetime.now() - timedelta(minutes=10)).isoformat(),
                "level": "WARNING",
                "service": "trading_engine",
                "event_type": "cache_operation",
                "operation": "miss",
                "cache_type": "redis",
                "key": "spot:NIFTY",
                "duration": 0.002
            },
            {
                "timestamp": (datetime.now() - timedelta(minutes=15)).isoformat(),
                "level": "ERROR",
                "service": "trading_engine",
                "event_type": "database_query",
                "query_type": "SELECT",
                "table": "trades",
                "duration": 2.5,
                "error": "Connection timeout"
            },
            {
                "timestamp": (datetime.now() - timedelta(minutes=20)).isoformat(),
                "level": "INFO",
                "service": "trading_engine",
                "event_type": "health_check",
                "check_name": "upstox_api",
                "status": "healthy",
                "response_time": 0.12
            }
        ]
        
        # Filter by event type if specified
        if event_type:
            sample_logs = [log for log in sample_logs if log.get("event_type") == event_type]
        
        # Limit results
        sample_logs = sample_logs[:limit]
        
        return {
            "total_logs": len(sample_logs),
            "event_type_filter": event_type,
            "limit": limit,
            "logs": sample_logs
        }
        
    except Exception as e:
        logger.error(f"Error getting log sample: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics")
async def get_logging_metrics():
    """Get logging metrics and statistics"""
    try:
        # Simulate logging metrics
        metrics = {
            "total_logs_today": 15420,
            "logs_by_level": {
                "INFO": 12000,
                "WARNING": 2800,
                "ERROR": 580,
                "CRITICAL": 40
            },
            "logs_by_event_type": {
                "api_request": 8500,
                "trading_event": 3200,
                "database_query": 2100,
                "cache_operation": 1200,
                "health_check": 420
            },
            "average_log_size_bytes": 256,
            "logs_per_second": 2.5,
            "peak_logs_per_second": 15.2,
            "error_rate_percent": 4.0,
            "timestamp": datetime.now().isoformat()
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting logging metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/configure")
async def configure_logging(
    log_level: str = Query(default="INFO", regex="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"),
    enable_performance: bool = Query(default=True),
    enable_security: bool = Query(default=True)
):
    """Configure structured logging settings"""
    try:
        from backend.logging.structured_logger import get_structured_logger
        
        config_logger = get_structured_logger('config')
        
        # Apply configuration
        config_logger.logger.setLevel(getattr(logging, log_level))
        
        config_logger.info(
            f"Logging configuration updated",
            event_type="configuration_change",
            log_level=log_level,
            performance_enabled=enable_performance,
            security_enabled=enable_security
        )
        
        return {
            "status": "success",
            "message": "Logging configuration updated",
            "log_level": log_level,
            "performance_enabled": enable_performance,
            "security_enabled": enable_security,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error configuring logging: {e}")
        raise HTTPException(status_code=500, detail=str(e))
