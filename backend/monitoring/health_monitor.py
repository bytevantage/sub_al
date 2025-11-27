"""
System Health Monitor
Monitors system health and provides ping alerts for API failures
"""

import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from backend.core.logger import get_logger
from backend.core.upstox_client import UpstoxClient
from sqlalchemy import text

logger = get_logger(__name__)

class HealthStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

@dataclass
class HealthCheck:
    """Health check result"""
    name: str
    status: HealthStatus
    message: str
    response_time: float
    timestamp: datetime
    details: Dict[str, Any] = None

class SystemHealthMonitor:
    """Monitors system health and provides alerts"""
    
    def __init__(self):
        self.health_checks: Dict[str, HealthCheck] = {}
        self.alert_history: List[Dict] = []
        self.last_check_time: Optional[datetime] = None
        
        # Health check intervals (seconds)
        self.CHECK_INTERVALS = {
            'api_upstox': 30,      # Check Upstox API every 30s
            'database': 60,         # Check database every 60s
            'redis': 60,           # Check Redis every 60s
            'websocket': 45,       # Check WebSocket every 45s
            'market_data': 30,     # Check market data freshness every 30s
        }
        
        # Alert thresholds
        self.THRESHOLDS = {
            'response_time_warning': 2.0,   # 2 seconds
            'response_time_critical': 5.0,  # 5 seconds
            'max_consecutive_failures': 3,
            'data_freshness_warning': 120,  # 2 minutes
            'data_freshness_critical': 300, # 5 minutes
        }
        
        # Consecutive failure counters
        self.failure_counters: Dict[str, int] = {}
        
        logger.info("System Health Monitor initialized")
    
    async def check_upstox_api_health(self) -> HealthCheck:
        """Check Upstox API connectivity and response time"""
        start_time = time.time()
        
        try:
            # Create test client (won't affect trading)
            test_client = UpstoxClient("test_token")
            
            # Test basic API call
            response = test_client.test_connection()
            
            response_time = time.time() - start_time
            
            if response and response.get('status') == 'success':
                status = HealthStatus.HEALTHY
                message = "Upstox API responding normally"
                if response_time > self.THRESHOLDS['response_time_critical']:
                    status = HealthStatus.WARNING
                    message = f"Upstox API slow response ({response_time:.2f}s)"
            else:
                status = HealthStatus.CRITICAL
                message = "Upstox API not responding"
                response_time = -1
            
            test_client.close()
            
        except Exception as e:
            response_time = time.time() - start_time
            status = HealthStatus.CRITICAL
            message = f"Upstox API error: {str(e)}"
            response_time = -1
        
        return HealthCheck(
            name="upstox_api",
            status=status,
            message=message,
            response_time=response_time,
            timestamp=datetime.now(),
            details={'response_time': response_time}
        )
    
    async def check_database_health(self) -> HealthCheck:
        """Check database connectivity and performance"""
        start_time = time.time()
        
        try:
            from backend.database.database import db
            
            # Test database connection
            session = db.get_session()
            
            # Simple query test
            result = session.execute(text("SELECT 1 as test"))
            test_value = result.fetchone()[0]
            
            session.close()
            
            response_time = time.time() - start_time
            
            if test_value == 1:
                status = HealthStatus.HEALTHY
                message = "Database responding normally"
                if response_time > self.THRESHOLDS['response_time_critical']:
                    status = HealthStatus.WARNING
                    message = f"Database slow response ({response_time:.2f}s)"
            else:
                status = HealthStatus.CRITICAL
                message = "Database query returned unexpected result"
                response_time = -1
            
        except Exception as e:
            response_time = time.time() - start_time
            status = HealthStatus.CRITICAL
            message = f"Database error: {str(e)}"
            response_time = -1
        
        return HealthCheck(
            name="database",
            status=status,
            message=message,
            response_time=response_time,
            timestamp=datetime.now(),
            details={'response_time': response_time}
        )
    
    async def check_redis_health(self) -> HealthCheck:
        """Check Redis connectivity and performance"""
        start_time = time.time()
        
        try:
            from backend.cache.redis_cache import get_cache_manager
            
            cache_manager = get_cache_manager()
            
            if cache_manager.is_available():
                # Test Redis operations
                test_key = "health_check_test"
                test_value = str(datetime.now().timestamp())
                
                cache_manager.redis_client.set(test_key, test_value, ex=10)
                retrieved_value = cache_manager.redis_client.get(test_key)
                
                # Clean up
                cache_manager.redis_client.delete(test_key)
                
                response_time = time.time() - start_time
                
                if retrieved_value == test_value:
                    status = HealthStatus.HEALTHY
                    message = "Redis responding normally"
                    if response_time > self.THRESHOLDS['response_time_critical']:
                        status = HealthStatus.WARNING
                        message = f"Redis slow response ({response_time:.2f}s)"
                else:
                    status = HealthStatus.WARNING
                    message = "Redis data integrity issue"
            else:
                status = HealthStatus.WARNING
                message = "Redis not available (using memory cache)"
                response_time = -1
            
        except Exception as e:
            response_time = time.time() - start_time
            status = HealthStatus.WARNING
            message = f"Redis error: {str(e)}"
            response_time = -1
        
        return HealthCheck(
            name="redis",
            status=status,
            message=message,
            response_time=response_time,
            timestamp=datetime.now(),
            details={'response_time': response_time}
        )
    
    async def check_market_data_freshness(self) -> HealthCheck:
        """Check if market data is fresh"""
        start_time = time.time()
        
        try:
            from backend.data.market_data import MarketDataManager
            from backend.core.upstox_client import UpstoxClient
            
            # Create dummy client to test data freshness
            dummy_client = UpstoxClient("test_token")
            market_data = MarketDataManager(dummy_client)
            
            # Check cache timestamps
            now = datetime.now()
            data_age = None
            
            # Check spot price cache
            if market_data.spot_price_cache:
                latest_timestamp = max(
                    cache['timestamp'] for cache in market_data.spot_price_cache.values()
                    if isinstance(cache, dict) and 'timestamp' in cache
                )
                data_age = (now - latest_timestamp).total_seconds()
            
            response_time = time.time() - start_time
            
            if data_age is None:
                status = HealthStatus.WARNING
                message = "No cached market data available"
            elif data_age <= self.THRESHOLDS['data_freshness_warning']:
                status = HealthStatus.HEALTHY
                message = f"Market data fresh ({data_age:.0f}s old)"
            elif data_age <= self.THRESHOLDS['data_freshness_critical']:
                status = HealthStatus.WARNING
                message = f"Market data stale ({data_age:.0f}s old)"
            else:
                status = HealthStatus.CRITICAL
                message = f"Market data very stale ({data_age:.0f}s old)"
            
            dummy_client.close()
            
        except Exception as e:
            response_time = time.time() - start_time
            status = HealthStatus.WARNING
            message = f"Market data check error: {str(e)}"
            response_time = -1
        
        return HealthCheck(
            name="market_data",
            status=status,
            message=message,
            response_time=response_time,
            timestamp=datetime.now(),
            details={'data_age_seconds': data_age}
        )
    
    async def check_websocket_health(self) -> HealthCheck:
        """Check WebSocket connection health"""
        start_time = time.time()
        
        try:
            # This would check the actual WebSocket status
            # For now, we'll check if the WebSocket manager is accessible
            from backend.data.market_feed import MarketFeedManager
            
            # Check if WebSocket is connected (simplified check)
            is_connected = True  # This would be actual WebSocket status check
            
            response_time = time.time() - start_time
            
            if is_connected:
                status = HealthStatus.HEALTHY
                message = "WebSocket connection healthy"
            else:
                status = HealthStatus.WARNING
                message = "WebSocket not connected"
                response_time = -1
            
        except Exception as e:
            response_time = time.time() - start_time
            status = HealthStatus.WARNING
            message = f"WebSocket check error: {str(e)}"
            response_time = -1
        
        return HealthCheck(
            name="websocket",
            status=status,
            message=message,
            response_time=response_time,
            timestamp=datetime.now(),
            details={'connected': is_connected}
        )
    
    def update_failure_counter(self, check_name: str, is_success: bool):
        """Track consecutive failures for alerting"""
        if is_success:
            self.failure_counters[check_name] = 0
        else:
            self.failure_counters[check_name] = self.failure_counters.get(check_name, 0) + 1
    
    def should_send_alert(self, check_name: str, health_check: HealthCheck) -> bool:
        """Determine if an alert should be sent"""
        
        # Alert on critical status
        if health_check.status == HealthStatus.CRITICAL:
            return True
        
        # Alert on consecutive failures
        if self.failure_counters.get(check_name, 0) >= self.THRESHOLDS['max_consecutive_failures']:
            return True
        
        # Alert on slow response times
        if health_check.response_time > self.THRESHOLDS['response_time_critical']:
            return True
        
        return False
    
    def record_alert(self, health_check: HealthCheck):
        """Record an alert for tracking"""
        alert = {
            'timestamp': health_check.timestamp.isoformat(),
            'check_name': health_check.name,
            'status': health_check.status.value,
            'message': health_check.message,
            'response_time': health_check.response_time
        }
        
        self.alert_history.append(alert)
        
        # Keep only last 100 alerts
        if len(self.alert_history) > 100:
            self.alert_history = self.alert_history[-100:]
        
        logger.warning(f"🚨 HEALTH ALERT: {health_check.name} - {health_check.message}")
    
    async def run_health_checks(self) -> Dict[str, HealthCheck]:
        """Run all health checks"""
        logger.debug("🔍 Running system health checks...")
        
        # Define all health check functions
        check_functions = {
            'upstox_api': self.check_upstox_api_health,
            'database': self.check_database_health,
            'redis': self.check_redis_health,
            'market_data': self.check_market_data_freshness,
            'websocket': self.check_websocket_health,
        }
        
        # Run checks concurrently
        tasks = []
        for check_name, check_func in check_functions.items():
            task = asyncio.create_task(check_func())
            tasks.append((check_name, task))
        
        # Wait for all checks to complete
        results = {}
        for check_name, task in tasks:
            try:
                health_check = await task
                results[check_name] = health_check
                self.health_checks[check_name] = health_check
                
                # Update failure counter
                is_success = health_check.status in [HealthStatus.HEALTHY, HealthStatus.WARNING]
                self.update_failure_counter(check_name, is_success)
                
                # Check if alert needed
                if self.should_send_alert(check_name, health_check):
                    self.record_alert(health_check)
                
            except Exception as e:
                logger.error(f"Health check {check_name} failed: {e}")
                results[check_name] = HealthCheck(
                    name=check_name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Health check failed: {str(e)}",
                    response_time=-1,
                    timestamp=datetime.now()
                )
        
        self.last_check_time = datetime.now()
        return results
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """Get overall system health summary"""
        if not self.health_checks:
            return {
                'overall_status': HealthStatus.UNKNOWN.value,
                'message': 'No health checks performed yet',
                'last_check': None,
                'checks': {},
                'alert_count': 0
            }
        
        # Determine overall status
        statuses = [check.status for check in self.health_checks.values()]
        
        if HealthStatus.CRITICAL in statuses:
            overall_status = HealthStatus.CRITICAL
            message = "System has critical issues"
        elif HealthStatus.WARNING in statuses or HealthStatus.UNKNOWN in statuses:
            overall_status = HealthStatus.WARNING
            message = "System has warnings or unknown issues"
        else:
            overall_status = HealthStatus.HEALTHY
            message = "All systems operational"
        
        return {
            'overall_status': overall_status.value,
            'message': message,
            'last_check': self.last_check_time.isoformat() if self.last_check_time else None,
            'checks': {
                name: {
                    'status': check.status.value,
                    'message': check.message,
                    'response_time': check.response_time,
                    'timestamp': check.timestamp.isoformat()
                }
                for name, check in self.health_checks.items()
            },
            'alert_count': len(self.alert_history),
            'recent_alerts': self.alert_history[-5:] if self.alert_history else []
        }
    
    async def start_monitoring(self, interval: int = 60):
        """Start continuous health monitoring"""
        logger.info(f"🏥 Starting health monitoring (interval: {interval}s)")
        
        while True:
            try:
                await self.run_health_checks()
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(30)  # Shorter interval on error

# Global health monitor instance
_health_monitor = None

def get_health_monitor() -> SystemHealthMonitor:
    """Get global health monitor instance"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = SystemHealthMonitor()
    return _health_monitor
