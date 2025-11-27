#!/bin/bash
# Trading Engine Startup Script
# This script starts both the trading engine and its monitor

set -e

PROJECT_DIR="/Users/srbhandary/Documents/Projects/srb-algo"
LOG_DIR="$PROJECT_DIR/data/logs"
MONITOR_LOG="$LOG_DIR/monitor_startup.log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$MONITOR_LOG"
}

# Function to check if process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# Stop existing processes
log "Stopping existing trading processes..."
pkill -f "backend.main" || true
pkill -f "monitor_trading_engine" || true
sleep 2

# Start the monitor (which will start the trading engine)
log "Starting trading engine monitor..."
cd "$PROJECT_DIR"

# Check if virtual environment exists
if [ -d "venv" ]; then
    source venv/bin/activate
    log "Activated virtual environment"
fi

# Start monitor in background
nohup python3 monitor_trading_engine.py >> "$LOG_DIR/monitor_service.log" 2>&1 &
MONITOR_PID=$!

log "Monitor started with PID: $MONITOR_PID"

# Wait a bit and check if it started
sleep 5
if is_running "monitor_trading_engine"; then
    log "✅ Monitor is running successfully"
    
    # Check if trading engine started
    sleep 10
    if is_running "backend.main"; then
        log "✅ Trading engine is running successfully"
    else
        log "⚠️ Trading engine may still be starting..."
    fi
    
    # Show status
    log ""
    log "=== Status ==="
    log "Monitor PID: $MONITOR_PID"
    log "Monitor running: $(is_running 'monitor_trading_engine' && echo 'Yes' || echo 'No')"
    log "Trading Engine running: $(is_running 'backend.main' && echo 'Yes' || echo 'No')"
    log ""
    log "Logs:"
    log "  Monitor: $LOG_DIR/monitor.log"
    log "  Trading: $LOG_DIR/trading_$(date +%Y%m%d).log"
    log "  Service: $LOG_DIR/monitor_service.log"
    log ""
    log "To stop: pkill -f monitor_trading_engine"
    
else
    log "❌ Monitor failed to start"
    exit 1
fi
