"""
Prometheus Metrics Exporter
Exposes trading system metrics in Prometheus format
"""

from prometheus_client import Counter, Gauge, Histogram, Info, generate_latest, REGISTRY
from fastapi import APIRouter, Response
from datetime import datetime
from typing import Dict, Any

from backend.core.logger import logger

# No need to call get_logger, use logger directly

# Initialize metrics router
metrics_router = APIRouter(prefix="/metrics", tags=["metrics"])


# ============================================
# Trading Metrics
# ============================================

# Trade Counters
trades_total = Counter(
    'trading_trades_total',
    'Total number of trades executed',
    ['strategy', 'side', 'status']
)

trades_pnl = Histogram(
    'trading_trades_pnl',
    'Trade P&L distribution',
    ['strategy'],
    buckets=[-5000, -1000, -500, -100, 0, 100, 500, 1000, 5000, 10000]
)

# Position Metrics
positions_open = Gauge(
    'trading_positions_open',
    'Number of currently open positions',
    ['strategy']
)

positions_value = Gauge(
    'trading_positions_value',
    'Total value of open positions',
    ['strategy']
)

# P&L Metrics
daily_pnl = Gauge(
    'trading_daily_pnl',
    'Daily profit and loss'
)

daily_pnl_percent = Gauge(
    'trading_daily_pnl_percent',
    'Daily P&L as percentage of capital'
)

unrealized_pnl = Gauge(
    'trading_unrealized_pnl',
    'Total unrealized P&L from open positions'
)

realized_pnl = Gauge(
    'trading_realized_pnl',
    'Total realized P&L from closed positions'
)

# Capital Metrics
capital_total = Gauge(
    'trading_capital_total',
    'Total trading capital'
)

capital_used = Gauge(
    'trading_capital_used',
    'Capital currently in use'
)

capital_available = Gauge(
    'trading_capital_available',
    'Available trading capital'
)

capital_utilization = Gauge(
    'trading_capital_utilization',
    'Capital utilization percentage'
)

# Margin Metrics
margin_used = Gauge(
    'trading_margin_used',
    'Margin currently in use'
)

margin_available = Gauge(
    'trading_margin_available',
    'Available margin'
)

# ============================================
# Risk Metrics
# ============================================

# Circuit Breaker
circuit_breaker_active = Gauge(
    'trading_circuit_breaker_active',
    'Whether circuit breaker is active (1=stopped, 0=trading)'
)

circuit_breaker_triggers = Counter(
    'trading_circuit_breaker_triggers_total',
    'Number of times circuit breaker was triggered',
    ['reason']
)

max_drawdown = Gauge(
    'trading_max_drawdown',
    'Maximum drawdown percentage'
)

# Stop Loss Metrics
stop_losses_triggered = Counter(
    'trading_stop_losses_triggered_total',
    'Number of stop losses triggered',
    ['strategy']
)

# Risk Limits
risk_limit_breaches = Counter(
    'trading_risk_limit_breaches_total',
    'Number of risk limit breaches',
    ['limit_type']
)

# ============================================
# Market Data Metrics
# ============================================

# Data Quality
market_data_updates = Counter(
    'trading_market_data_updates_total',
    'Number of market data updates received',
    ['symbol']
)

market_data_stale = Gauge(
    'trading_market_data_stale',
    'Number of symbols with stale data'
)

market_data_age_seconds = Histogram(
    'trading_market_data_age_seconds',
    'Age of market data in seconds',
    ['symbol'],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60]
)

# VIX and Market Condition
market_vix = Gauge(
    'trading_market_vix',
    'Current VIX level'
)

market_condition = Gauge(
    'trading_market_condition',
    'Market condition (0=normal, 1=elevated, 2=high_stress, 3=extreme)',
    ['condition']
)

# ============================================
# Order Metrics
# ============================================

orders_submitted = Counter(
    'trading_orders_submitted_total',
    'Total orders submitted',
    ['strategy', 'side', 'order_type']
)

orders_filled = Counter(
    'trading_orders_filled_total',
    'Total orders filled',
    ['strategy', 'side']
)

orders_rejected = Counter(
    'trading_orders_rejected_total',
    'Total orders rejected',
    ['strategy', 'reason']
)

orders_cancelled = Counter(
    'trading_orders_cancelled_total',
    'Total orders cancelled',
    ['strategy', 'reason']
)

order_fill_time = Histogram(
    'trading_order_fill_time_seconds',
    'Time to fill orders',
    ['strategy'],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30]
)

# ============================================
# Strategy Performance Metrics
# ============================================

strategy_win_rate = Gauge(
    'trading_strategy_win_rate',
    'Win rate per strategy',
    ['strategy']
)

strategy_avg_pnl = Gauge(
    'trading_strategy_avg_pnl',
    'Average P&L per trade',
    ['strategy']
)

strategy_sharpe_ratio = Gauge(
    'trading_strategy_sharpe_ratio',
    'Sharpe ratio per strategy',
    ['strategy']
)

strategy_trades_today = Gauge(
    'trading_strategy_trades_today',
    'Number of trades today per strategy',
    ['strategy']
)

# ============================================
# System Metrics
# ============================================

# System Info
system_info = Info(
    'trading_system',
    'Trading system information'
)

# Set system info
system_info.info({
    'version': '1.0.0',
    'environment': 'production',  # TODO: Get from config
    'start_time': datetime.now().isoformat()
})

# Uptime
system_uptime_seconds = Gauge(
    'trading_system_uptime_seconds',
    'System uptime in seconds'
)

# Errors
system_errors = Counter(
    'trading_system_errors_total',
    'Total system errors',
    ['component', 'severity']
)

# WebSocket connections
websocket_connections = Gauge(
    'trading_websocket_connections',
    'Number of active WebSocket connections'
)

# API requests
api_requests = Counter(
    'trading_api_requests_total',
    'Total API requests',
    ['endpoint', 'method', 'status']
)

api_request_duration = Histogram(
    'trading_api_request_duration_seconds',
    'API request duration',
    ['endpoint', 'method'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5]
)

# ML Model Metrics
ml_predictions_total = Counter(
    'trading_ml_predictions_total',
    'Total ML predictions made',
    ['model', 'prediction']
)

ml_model_accuracy = Gauge(
    'trading_ml_model_accuracy',
    'ML model accuracy',
    ['model']
)

ml_training_duration = Histogram(
    'trading_ml_training_duration_seconds',
    'ML model training duration',
    buckets=[10, 30, 60, 120, 300, 600]
)

ml_last_training = Gauge(
    'trading_ml_last_training_timestamp',
    'Timestamp of last ML training'
)


# ============================================
# Metrics Update Functions
# ============================================

class MetricsExporter:
    """
    Helper class to update metrics from trading system components
    """
    
    @staticmethod
    def update_position_metrics(positions: list, strategy_breakdown: Dict[str, int] = None):
        """Update position-related metrics"""
        # Total open positions
        total_positions = len(positions)
        
        # Strategy breakdown
        if strategy_breakdown:
            for strategy, count in strategy_breakdown.items():
                positions_open.labels(strategy=strategy).set(count)
        
        # Total unrealized P&L
        total_unrealized = sum(p.get('unrealized_pnl', 0) for p in positions)
        unrealized_pnl.set(total_unrealized)
    
    @staticmethod
    def update_pnl_metrics(daily: float, daily_pct: float, realized: float):
        """Update P&L metrics"""
        daily_pnl.set(daily)
        daily_pnl_percent.set(daily_pct)
        realized_pnl.set(realized)
    
    @staticmethod
    def update_capital_metrics(total: float, used: float, available: float, utilization: float):
        """Update capital metrics"""
        capital_total.set(total)
        capital_used.set(used)
        capital_available.set(available)
        capital_utilization.set(utilization)
    
    @staticmethod
    def update_circuit_breaker_metrics(is_active: bool, triggers_today: int = None):
        """Update circuit breaker metrics"""
        circuit_breaker_active.set(1 if is_active else 0)
    
    @staticmethod
    def update_market_metrics(vix: float, condition: str):
        """Update market metrics"""
        market_vix.set(vix)
        
        # Map condition to numeric value
        condition_map = {
            'normal': 0,
            'elevated': 1,
            'high_stress': 2,
            'extreme': 3
        }
        condition_value = condition_map.get(condition, 0)
        market_condition.labels(condition=condition).set(condition_value)
    
    @staticmethod
    def record_trade(strategy: str, side: str, status: str, pnl: float = None):
        """Record a trade"""
        trades_total.labels(strategy=strategy, side=side, status=status).inc()
        
        if pnl is not None:
            trades_pnl.labels(strategy=strategy).observe(pnl)
    
    @staticmethod
    def record_order(strategy: str, side: str, order_type: str, status: str, reason: str = None, fill_time: float = None):
        """Record an order"""
        if status == 'submitted':
            orders_submitted.labels(strategy=strategy, side=side, order_type=order_type).inc()
        elif status == 'filled':
            orders_filled.labels(strategy=strategy, side=side).inc()
            if fill_time is not None:
                order_fill_time.labels(strategy=strategy).observe(fill_time)
        elif status == 'rejected':
            orders_rejected.labels(strategy=strategy, reason=reason or 'unknown').inc()
        elif status == 'cancelled':
            orders_cancelled.labels(strategy=strategy, reason=reason or 'unknown').inc()
    
    @staticmethod
    def record_market_data_update(symbol: str, age_seconds: float):
        """Record market data update"""
        market_data_updates.labels(symbol=symbol).inc()
        market_data_age_seconds.labels(symbol=symbol).observe(age_seconds)
    
    @staticmethod
    def record_circuit_breaker_trigger(reason: str):
        """Record circuit breaker trigger"""
        circuit_breaker_triggers.labels(reason=reason).inc()
    
    @staticmethod
    def record_system_error(component: str, severity: str):
        """Record system error"""
        system_errors.labels(component=component, severity=severity).inc()
    
    @staticmethod
    def update_websocket_connections(count: int):
        """Update WebSocket connection count"""
        websocket_connections.set(count)
    
    @staticmethod
    def record_api_request(endpoint: str, method: str, status: int, duration: float):
        """Record API request"""
        api_requests.labels(endpoint=endpoint, method=method, status=str(status)).inc()
        api_request_duration.labels(endpoint=endpoint, method=method).observe(duration)
    
    @staticmethod
    def record_ml_prediction(model: str, prediction: str):
        """Record ML prediction"""
        ml_predictions_total.labels(model=model, prediction=prediction).inc()
    
    @staticmethod
    def update_ml_metrics(accuracy: float, last_training_timestamp: float):
        """Update ML model metrics"""
        ml_model_accuracy.labels(model='xgboost').set(accuracy)
        ml_last_training.set(last_training_timestamp)
    
    @staticmethod
    def record_ml_training(duration: float):
        """Record ML training duration"""
        ml_training_duration.observe(duration)


# ============================================
# Prometheus Endpoint
# ============================================

@metrics_router.get("")
async def metrics():
    """
    Prometheus metrics endpoint
    
    Exposes all trading system metrics in Prometheus format
    """
    return Response(
        content=generate_latest(REGISTRY),
        media_type="text/plain; charset=utf-8"
    )


@metrics_router.get("/health")
async def metrics_health():
    """Health check for metrics endpoint"""
    return {
        "status": "healthy",
        "service": "prometheus-exporter",
        "timestamp": datetime.now().isoformat()
    }


# Export the metrics exporter instance
metrics_exporter = MetricsExporter()
