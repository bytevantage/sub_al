"""
Health Monitoring API Endpoints
System health checks and ping alerts
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional
from datetime import datetime

from backend.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/health", tags=["health"])

@router.get("/status")
async def get_health_status():
    """Get current system health status"""
    try:
        from backend.monitoring.health_monitor import get_health_monitor
        health_monitor = get_health_monitor()
        
        # Run health checks
        import asyncio
        health_results = await asyncio.create_task(health_monitor.run_health_checks())
        
        # Get summary
        summary = health_monitor.get_system_health_summary()
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/summary")
async def get_health_summary():
    """Get health summary without running new checks"""
    try:
        from backend.monitoring.health_monitor import get_health_monitor
        health_monitor = get_health_monitor()
        
        summary = health_monitor.get_system_health_summary()
        return summary
        
    except Exception as e:
        logger.error(f"Error getting health summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/check")
async def run_health_check(check_name: Optional[str] = None):
    """Run specific health check or all checks"""
    try:
        from backend.monitoring.health_monitor import get_health_monitor
        health_monitor = get_health_monitor()
        
        import asyncio
        
        if check_name:
            # Run specific check
            check_functions = {
                'upstox_api': health_monitor.check_upstox_api_health,
                'database': health_monitor.check_database_health,
                'redis': health_monitor.check_redis_health,
                'market_data': health_monitor.check_market_data_freshness,
                'websocket': health_monitor.check_websocket_health,
            }
            
            if check_name not in check_functions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown check: {check_name}. Available: {list(check_functions.keys())}"
                )
            
            result = await asyncio.create_task(check_functions[check_name]())
            
            return {
                'check_name': check_name,
                'status': result.status.value,
                'message': result.message,
                'response_time': result.response_time,
                'timestamp': result.timestamp.isoformat(),
                'details': result.details
            }
        else:
            # Run all checks
            results = await asyncio.create_task(health_monitor.run_health_checks())
            
            return {
                'timestamp': datetime.now().isoformat(),
                'checks': {
                    name: {
                        'status': check.status.value,
                        'message': check.message,
                        'response_time': check.response_time,
                        'timestamp': check.timestamp.isoformat()
                    }
                    for name, check in results.items()
                }
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running health check: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts")
async def get_alert_history(limit: int = 50):
    """Get recent health alerts"""
    try:
        from backend.monitoring.health_monitor import get_health_monitor
        health_monitor = get_health_monitor()
        
        alerts = health_monitor.alert_history[-limit:] if health_monitor.alert_history else []
        
        return {
            'total_alerts': len(health_monitor.alert_history),
            'recent_alerts': alerts,
            'alert_count_24h': len([
                alert for alert in health_monitor.alert_history
                if datetime.fromisoformat(alert['timestamp']) > datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            ])
        }
        
    except Exception as e:
        logger.error(f"Error getting alert history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ping")
async def ping_check():
    """Simple ping check for basic connectivity"""
    try:
        start_time = datetime.now()
        
        # Basic system checks
        checks = {
            'system_time': datetime.now().isoformat(),
            'uptime': 'N/A',  # Would calculate actual uptime
            'memory_usage': 'N/A',  # Would get actual memory usage
            'disk_space': 'N/A'  # Would get actual disk space
        }
        
        response_time = (datetime.now() - start_time).total_seconds()
        
        return {
            'status': 'pong',
            'timestamp': start_time.isoformat(),
            'response_time_ms': round(response_time * 1000, 2),
            'checks': checks
        }
        
    except Exception as e:
        logger.error(f"Error in ping check: {e}")
        return {
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }

@router.post("/start-monitoring")
async def start_health_monitoring(background_tasks: BackgroundTasks, interval: int = 60):
    """Start continuous health monitoring"""
    try:
        from backend.monitoring.health_monitor import get_health_monitor
        health_monitor = get_health_monitor()
        
        # Start monitoring in background
        background_tasks.add_task(health_monitor.start_monitoring, interval)
        
        return {
            'status': 'started',
            'message': f'Health monitoring started with {interval}s interval',
            'interval': interval,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error starting health monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics")
async def get_health_metrics():
    """Get detailed health metrics for dashboard"""
    try:
        from backend.monitoring.health_monitor import get_health_monitor
        health_monitor = get_health_monitor()
        
        # Get current health status
        summary = health_monitor.get_system_health_summary()
        
        # Calculate metrics
        total_checks = len(summary['checks'])
        healthy_checks = sum(
            1 for check in summary['checks'].values()
            if check['status'] == 'healthy'
        )
        warning_checks = sum(
            1 for check in summary['checks'].values()
            if check['status'] == 'warning'
        )
        critical_checks = sum(
            1 for check in summary['checks'].values()
            if check['status'] == 'critical'
        )
        
        # Response time metrics
        response_times = [
            check['response_time'] for check in summary['checks'].values()
            if check['response_time'] > 0
        ]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        metrics = {
            'overall_status': summary['overall_status'],
            'total_checks': total_checks,
            'healthy_checks': healthy_checks,
            'warning_checks': warning_checks,
            'critical_checks': critical_checks,
            'health_score': (healthy_checks / total_checks * 100) if total_checks > 0 else 0,
            'avg_response_time_ms': round(avg_response_time * 1000, 2),
            'last_check': summary['last_check'],
            'recent_alerts': summary['alert_count'],
            'checks': summary['checks']
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting health metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
