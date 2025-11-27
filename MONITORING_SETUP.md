# Monitoring Setup Guide - Prometheus & Grafana

## Overview

This guide shows how to set up comprehensive monitoring for the trading system using Prometheus and Grafana.

## Components

### 1. Prometheus
- **Purpose**: Metrics collection and storage
- **Port**: 9090
- **Metrics Endpoint**: `http://localhost:8000/metrics`
- **Scrape Interval**: 5 seconds for trading metrics

### 2. Grafana
- **Purpose**: Visualization and dashboards
- **Port**: 3000
- **Default Credentials**: admin / admin123 (CHANGE IN PRODUCTION!)

### 3. Node Exporter (Optional)
- **Purpose**: System-level metrics (CPU, memory, disk)
- **Port**: 9100

## Quick Start

### 1. Install Dependencies

Add to `requirements.txt`:
```
prometheus-client>=0.17.0
```

Install:
```bash
pip install prometheus-client
```

### 2. Start Monitoring Stack

Using Docker Compose:
```bash
# Start Prometheus and Grafana
docker-compose -f docker-compose.monitoring.yml up -d

# Check status
docker-compose -f docker-compose.monitoring.yml ps

# View logs
docker-compose -f docker-compose.monitoring.yml logs -f
```

### 3. Update main.py

Add metrics exporter to your FastAPI app:

```python
from backend.monitoring.prometheus_exporter import metrics_router, metrics_exporter

# Include metrics router
app.include_router(metrics_router)

# Example: Update metrics in your code
@app.on_event("startup")
async def startup():
    # ... existing startup code ...
    
    # Set up periodic metrics updates
    asyncio.create_task(update_metrics_loop())

async def update_metrics_loop():
    """Periodically update Prometheus metrics"""
    while True:
        try:
            # Update position metrics
            positions = position_manager.get_all_positions()
            metrics_exporter.update_position_metrics(positions)
            
            # Update P&L metrics
            metrics_exporter.update_pnl_metrics(
                daily=circuit_breaker.daily_pnl,
                daily_pct=circuit_breaker.daily_pnl_percent,
                realized=circuit_breaker.realized_pnl
            )
            
            # Update capital metrics
            metrics_exporter.update_capital_metrics(
                total=position_manager.total_capital,
                used=position_manager.get_used_margin(),
                available=position_manager.available_margin,
                utilization=position_manager.get_capital_utilization()
            )
            
            # Update circuit breaker
            metrics_exporter.update_circuit_breaker_metrics(
                is_active=not circuit_breaker.is_trading_allowed()
            )
            
            # Update market metrics
            metrics_exporter.update_market_metrics(
                vix=market_monitor.current_vix,
                condition=market_monitor.market_condition.value
            )
            
            # Update WebSocket connections
            ws_manager = get_ws_manager()
            metrics_exporter.update_websocket_connections(
                ws_manager.get_connection_count()
            )
            
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
        
        await asyncio.sleep(5)  # Update every 5 seconds
```

### 4. Record Events

Instrument your code to record trading events:

```python
# When a trade is executed
metrics_exporter.record_trade(
    strategy="gamma_scalping",
    side="BUY",
    status="filled",
    pnl=125.50
)

# When an order is placed
metrics_exporter.record_order(
    strategy="gamma_scalping",
    side="BUY",
    order_type="LIMIT",
    status="submitted"
)

# When order is filled
metrics_exporter.record_order(
    strategy="gamma_scalping",
    side="BUY",
    order_type="LIMIT",
    status="filled",
    fill_time=0.75  # seconds
)

# When circuit breaker triggers
metrics_exporter.record_circuit_breaker_trigger(
    reason="max_daily_loss"
)

# When market data updates
metrics_exporter.record_market_data_update(
    symbol="NIFTY24600CE",
    age_seconds=0.5
)

# When system error occurs
metrics_exporter.record_system_error(
    component="order_manager",
    severity="error"
)

# When ML prediction is made
metrics_exporter.record_ml_prediction(
    model="xgboost",
    prediction="take_trade"
)
```

## Accessing the Dashboards

### Prometheus UI
1. Open: http://localhost:9090
2. Navigate to Status → Targets to verify scraping is working
3. Use the Graph tab to query metrics:
   - `trading_daily_pnl`
   - `trading_positions_open`
   - `trading_circuit_breaker_active`

### Grafana Dashboards
1. Open: http://localhost:3000
2. Login with: admin / admin123
3. Navigate to Dashboards → Trading System - Main Dashboard

## Available Metrics

### Trading Metrics
- `trading_daily_pnl` - Daily profit/loss
- `trading_unrealized_pnl` - Unrealized P&L from open positions
- `trading_realized_pnl` - Realized P&L from closed positions
- `trading_positions_open{strategy}` - Open positions by strategy
- `trading_trades_total{strategy,side,status}` - Total trades counter
- `trading_trades_pnl{strategy}` - P&L distribution histogram

### Risk Metrics
- `trading_circuit_breaker_active` - CB status (0=trading, 1=stopped)
- `trading_circuit_breaker_triggers_total{reason}` - CB trigger counter
- `trading_max_drawdown` - Maximum drawdown percentage
- `trading_risk_limit_breaches_total{limit_type}` - Risk breaches

### Capital Metrics
- `trading_capital_total` - Total capital
- `trading_capital_used` - Capital in use
- `trading_capital_available` - Available capital
- `trading_capital_utilization` - Utilization percentage
- `trading_margin_used` - Margin used
- `trading_margin_available` - Available margin

### Market Data Metrics
- `trading_market_vix` - Current VIX level
- `trading_market_condition{condition}` - Market condition
- `trading_market_data_updates_total{symbol}` - Update counter
- `trading_market_data_stale` - Stale data count
- `trading_market_data_age_seconds{symbol}` - Data age histogram

### Order Metrics
- `trading_orders_submitted_total{strategy,side,order_type}` - Orders submitted
- `trading_orders_filled_total{strategy,side}` - Orders filled
- `trading_orders_rejected_total{strategy,reason}` - Orders rejected
- `trading_orders_cancelled_total{strategy,reason}` - Orders cancelled
- `trading_order_fill_time_seconds{strategy}` - Fill time histogram

### Strategy Performance
- `trading_strategy_win_rate{strategy}` - Win rate per strategy
- `trading_strategy_avg_pnl{strategy}` - Average P&L per trade
- `trading_strategy_sharpe_ratio{strategy}` - Sharpe ratio
- `trading_strategy_trades_today{strategy}` - Trades today

### ML Model Metrics
- `trading_ml_model_accuracy{model}` - Model accuracy
- `trading_ml_predictions_total{model,prediction}` - Predictions counter
- `trading_ml_training_duration_seconds` - Training time histogram
- `trading_ml_last_training_timestamp` - Last training timestamp

### System Metrics
- `trading_system_uptime_seconds` - System uptime
- `trading_system_errors_total{component,severity}` - Error counter
- `trading_websocket_connections` - Active WebSocket connections
- `trading_api_requests_total{endpoint,method,status}` - API requests
- `trading_api_request_duration_seconds{endpoint,method}` - Request duration

## Example Queries

### PromQL Examples

```promql
# Current daily P&L
trading_daily_pnl

# P&L change rate (per minute)
rate(trading_daily_pnl[1m])

# Total open positions across all strategies
sum(trading_positions_open)

# Win rate by strategy (last hour)
avg_over_time(trading_strategy_win_rate[1h])

# Order fill rate (last 5 minutes)
rate(trading_orders_filled_total[5m])

# Order rejection rate by reason
sum by (reason) (rate(trading_orders_rejected_total[5m]))

# Circuit breaker triggers in last hour
increase(trading_circuit_breaker_triggers_total[1h])

# Average order fill time by strategy
avg by (strategy) (
  rate(trading_order_fill_time_seconds_sum[5m]) /
  rate(trading_order_fill_time_seconds_count[5m])
)

# Market data staleness
trading_market_data_stale > 0

# API error rate
sum(rate(trading_system_errors_total{severity="error"}[5m]))

# Top 5 strategies by trade count
topk(5, sum by (strategy) (trading_trades_total))
```

## Alerting (Optional)

Create `prometheus/alerts.yml`:

```yaml
groups:
  - name: trading_alerts
    interval: 30s
    rules:
      # Circuit Breaker Alert
      - alert: CircuitBreakerTriggered
        expr: trading_circuit_breaker_active == 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Trading has been stopped by circuit breaker"
          description: "Circuit breaker is active - trading halted"

      # Daily Loss Alert
      - alert: HighDailyLoss
        expr: trading_daily_pnl < -5000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High daily loss detected"
          description: "Daily P&L is {{ $value }} (threshold: -5000)"

      # Capital Utilization Alert
      - alert: HighCapitalUtilization
        expr: trading_capital_utilization > 90
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Capital utilization is very high"
          description: "{{ $value }}% of capital is in use (threshold: 90%)"

      # Stale Market Data Alert
      - alert: StaleMarketData
        expr: trading_market_data_stale > 5
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Multiple symbols have stale data"
          description: "{{ $value }} symbols have stale market data"

      # Order Rejection Rate Alert
      - alert: HighOrderRejectionRate
        expr: |
          sum(rate(trading_orders_rejected_total[5m])) /
          sum(rate(trading_orders_submitted_total[5m])) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High order rejection rate"
          description: "{{ $value | humanizePercentage }} of orders rejected"

      # System Error Rate Alert
      - alert: HighErrorRate
        expr: rate(trading_system_errors_total[5m]) > 1
        for: 5m
        labels:
          severity: error
        annotations:
          summary: "High system error rate"
          description: "{{ $value }} errors per second"

      # ML Model Accuracy Alert
      - alert: LowMLAccuracy
        expr: trading_ml_model_accuracy < 0.6
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "ML model accuracy is low"
          description: "Model accuracy is {{ $value | humanizePercentage }}"
```

Enable alerts in `prometheus.yml`:
```yaml
rule_files:
  - 'alerts.yml'
```

## Troubleshooting

### Prometheus Not Scraping
1. Check target status: http://localhost:9090/targets
2. Verify backend is running: `curl http://localhost:8000/metrics`
3. Check firewall rules
4. Verify network in docker-compose

### Grafana Not Showing Data
1. Check Prometheus datasource: Configuration → Data Sources
2. Test connection in datasource settings
3. Verify queries in dashboard panels
4. Check time range (default: last 1 hour)

### Metrics Not Updating
1. Verify metrics update loop is running in main.py
2. Check backend logs for errors
3. Verify metrics are being recorded: `curl http://localhost:8000/metrics | grep trading_`

## Best Practices

1. **Metric Naming**: Follow Prometheus naming conventions
   - Use `_total` suffix for counters
   - Use base units (seconds, bytes, not milliseconds or MB)
   - Use consistent label names

2. **Cardinality**: Avoid high-cardinality labels
   - Don't use user IDs, timestamps, or unique identifiers as labels
   - Use strategy names, status codes, etc.

3. **Recording Rules**: For expensive queries, use recording rules
   ```yaml
   groups:
     - name: trading_rules
       interval: 1m
       rules:
         - record: trading:daily_pnl:rate1m
           expr: rate(trading_daily_pnl[1m])
   ```

4. **Retention**: Adjust based on disk space
   - Default: 30 days in docker-compose
   - Increase for longer history: `--storage.tsdb.retention.time=90d`

5. **Backup**: Regularly backup Grafana dashboards and Prometheus data
   ```bash
   # Backup Grafana
   docker cp trading-grafana:/var/lib/grafana ./backups/grafana-$(date +%Y%m%d)
   
   # Backup Prometheus
   docker cp trading-prometheus:/prometheus ./backups/prometheus-$(date +%Y%m%d)
   ```

## Production Deployment

### Security
1. Change default Grafana password
2. Enable Prometheus authentication
3. Use HTTPS/TLS for external access
4. Restrict network access with firewall rules

### High Availability
1. Run multiple Prometheus instances with federation
2. Use remote storage (Thanos, Cortex, or cloud services)
3. Set up Grafana HA with shared database

### Scaling
1. Use remote write for high-volume metrics
2. Enable metric relabeling to drop unnecessary labels
3. Consider using VictoriaMetrics for better performance

## Next Steps

1. ✅ Set up Prometheus and Grafana using docker-compose
2. ✅ Add metrics exporter to main.py
3. ✅ Import trading dashboard to Grafana
4. ⏳ Configure alerting rules
5. ⏳ Set up notification channels (email, Slack, etc.)
6. ⏳ Create additional dashboards for specific strategies
7. ⏳ Set up long-term storage and backup

