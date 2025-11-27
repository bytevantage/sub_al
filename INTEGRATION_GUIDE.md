# Integration Guide for main.py

This guide shows how to integrate all the new components into your existing `backend/main.py`.

## Required Imports

Add these imports at the top of your main.py:

```python
from backend.ml.training_data_collector import TrainingDataCollector
from backend.ml.model_manager import ModelManager
from backend.jobs.eod_training import EODTrainingJob
from backend.api import emergency_controls
```

## Initialization Code

Add this to your startup sequence (typically in a `startup_event` or `main()` function):

```python
async def startup_event():
    """Initialize all systems on startup"""
    
    # ... existing initialization code ...
    
    # ============================================
    # NEW: Initialize ML Training Components
    # ============================================
    
    logger.info("Initializing ML training pipeline...")
    
    # 1. Initialize Training Data Collector
    data_collector = TrainingDataCollector(db_manager)
    logger.info("✓ Training data collector initialized")
    
    # 2. Initialize Model Manager
    model_manager = ModelManager(model_dir="models")
    model_manager.load_models()  # Load existing models if available
    logger.info("✓ Model manager initialized")
    
    # 3. Initialize EOD Training Job
    eod_job = EODTrainingJob(
        model_manager=model_manager,
        data_collector=data_collector,
        eod_time="16:00"  # 4 PM
    )
    eod_job.start()
    logger.info("✓ EOD training job started (scheduled for 4:00 PM)")
    
    # ============================================
    # NEW: Set Emergency API State
    # ============================================
    
    logger.info("Configuring emergency controls API...")
    
    # Inject all system instances for emergency API
    emergency_controls.set_app_state({
        'circuit_breaker': circuit_breaker,
        'position_manager': position_manager,
        'market_monitor': market_monitor,
        'data_monitor': data_monitor,
        'order_lifecycle': order_lifecycle,
        'trade_reconciliation': trade_reconciliation
    })
    logger.info("✓ Emergency API state configured")
    
    # Include emergency controls router
    app.include_router(emergency_controls.router)
    logger.info("✓ Emergency controls API mounted")
    
    logger.info("🚀 All systems initialized and ready")
```

## Shutdown Code

Add this to your shutdown sequence:

```python
async def shutdown_event():
    """Clean shutdown of all systems"""
    
    # ... existing shutdown code ...
    
    # Stop EOD training scheduler
    logger.info("Stopping EOD training scheduler...")
    eod_job.stop()
    logger.info("✓ EOD training scheduler stopped")
    
    logger.info("👋 Shutdown complete")
```

## Complete Example

Here's a complete example of how it fits together:

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager

from backend.core.logger import get_logger
from backend.database.db_manager import DatabaseManager
from backend.safety.circuit_breaker import CircuitBreaker
from backend.safety.position_manager import PositionManager
from backend.safety.market_monitor import MarketMonitor
from backend.safety.data_monitor import MarketDataMonitor
from backend.safety.order_lifecycle import OrderLifecycleManager
from backend.safety.reconciliation import TradeReconciliation

# NEW IMPORTS
from backend.ml.training_data_collector import TrainingDataCollector
from backend.ml.model_manager import ModelManager
from backend.jobs.eod_training import EODTrainingJob
from backend.api import emergency_controls

logger = get_logger(__name__)

# Global instances
db_manager = None
circuit_breaker = None
position_manager = None
market_monitor = None
data_monitor = None
order_lifecycle = None
trade_reconciliation = None
eod_job = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    await startup_event()
    yield
    # Shutdown
    await shutdown_event()

app = FastAPI(
    title="Trading System",
    description="Professional Options Trading System",
    version="1.0.0",
    lifespan=lifespan
)

async def startup_event():
    """Initialize all systems"""
    global db_manager, circuit_breaker, position_manager
    global market_monitor, data_monitor, order_lifecycle
    global trade_reconciliation, eod_job
    
    logger.info("🚀 Starting Trading System...")
    
    # 1. Initialize Database
    logger.info("Initializing database...")
    db_manager = DatabaseManager()
    await db_manager.connect()
    logger.info("✓ Database connected")
    
    # 2. Initialize Safety Systems
    logger.info("Initializing safety systems...")
    circuit_breaker = CircuitBreaker(max_daily_loss=10000)
    position_manager = PositionManager(max_positions=10)
    market_monitor = MarketMonitor()
    data_monitor = MarketDataMonitor()
    order_lifecycle = OrderLifecycleManager()
    trade_reconciliation = TradeReconciliation()
    logger.info("✓ Safety systems initialized")
    
    # 3. Initialize ML Training Pipeline
    logger.info("Initializing ML training pipeline...")
    data_collector = TrainingDataCollector(db_manager)
    model_manager = ModelManager(model_dir="models")
    model_manager.load_models()
    logger.info("✓ ML pipeline initialized")
    
    # 4. Start EOD Training Job
    logger.info("Starting EOD training scheduler...")
    eod_job = EODTrainingJob(
        model_manager=model_manager,
        data_collector=data_collector,
        eod_time="16:00"
    )
    eod_job.start()
    logger.info("✓ EOD job scheduled for 4:00 PM")
    
    # 5. Configure Emergency API
    logger.info("Configuring emergency controls...")
    emergency_controls.set_app_state({
        'circuit_breaker': circuit_breaker,
        'position_manager': position_manager,
        'market_monitor': market_monitor,
        'data_monitor': data_monitor,
        'order_lifecycle': order_lifecycle,
        'trade_reconciliation': trade_reconciliation
    })
    app.include_router(emergency_controls.router)
    logger.info("✓ Emergency API mounted at /emergency")
    
    logger.info("✅ All systems ready - Trading system online")

async def shutdown_event():
    """Clean shutdown"""
    logger.info("🛑 Shutting down Trading System...")
    
    # Stop EOD scheduler
    if eod_job:
        logger.info("Stopping EOD training scheduler...")
        eod_job.stop()
    
    # Close database
    if db_manager:
        logger.info("Closing database connection...")
        await db_manager.disconnect()
    
    logger.info("✅ Shutdown complete")

# Health check endpoint
@app.get("/health")
async def health_check():
    """System health check"""
    return {
        "status": "healthy",
        "service": "trading-system",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Testing the Integration

After integrating, test each component:

### 1. Test ML Pipeline
```python
# Test training data collection
from backend.ml.training_data_collector import test_training_data_collector
await test_training_data_collector(db_manager)

# Test model training
from backend.ml.model_manager import ModelManager
manager = ModelManager()
# Create sample data and test
```

### 2. Test EOD Job
```python
# Check job status
status = eod_job.get_status()
print(f"EOD Job: {status}")

# Run manual training (for testing)
await eod_job.run_manual_training(datetime.now().date())
```

### 3. Test Emergency API
```bash
# Test health check
curl http://localhost:8000/emergency/health

# Test system status
curl http://localhost:8000/emergency/status

# Test with API key
curl -H "X-API-Key: EMERGENCY_KEY_123" \
     http://localhost:8000/emergency/positions
```

### 4. Test Dashboard
1. Start the backend: `python -m backend.main`
2. Open `frontend/dashboard/index.html` in browser
3. Verify all cards load data
4. Test emergency controls

## Environment Variables

Create a `.env` file for production:

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost/trading

# API Keys
EMERGENCY_API_KEY=your-secure-key-here

# Passwords (use strong passwords in production!)
EMERGENCY_PASSWORD=your-secure-password
OVERRIDE_PASSWORD=your-secure-override-password

# Training
EOD_TRAINING_TIME=16:00
MIN_TRAINING_SAMPLES=100

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/trading.log
```

Then update the code to use environment variables:

```python
import os
from dotenv import load_dotenv

load_dotenv()

EMERGENCY_API_KEY = os.getenv("EMERGENCY_API_KEY", "EMERGENCY_KEY_123")
EMERGENCY_PASSWORD = os.getenv("EMERGENCY_PASSWORD", "OVERRIDE123")
EOD_TIME = os.getenv("EOD_TRAINING_TIME", "16:00")
```

## Troubleshooting

### Issue: EOD job not running
**Solution**: Check scheduler status
```python
status = eod_job.get_status()
print(status)
```

### Issue: Emergency API returns 500
**Solution**: Check app state is set
```python
# In main.py, ensure set_app_state() is called before including router
emergency_controls.set_app_state({...})
app.include_router(emergency_controls.router)
```

### Issue: Dashboard not loading data
**Solution**: 
1. Check backend is running: `curl http://localhost:8000/emergency/health`
2. Check CORS settings in FastAPI
3. Check browser console for errors
4. Verify API_BASE in dashboard.js matches backend URL

### Issue: Greeks not calculated
**Solution**: Ensure market_data.calculate_greeks() is called in update loop
```python
# In your market data update loop
market_data.update_option_chain(data)
market_data.calculate_greeks()  # Add this line
```

## Next Steps

1. ✅ Integrate into main.py (using this guide)
2. ✅ Update requirements.txt (scipy, xgboost, apscheduler)
3. ✅ Test all components individually
4. ✅ Test end-to-end workflow
5. ✅ Deploy to production
6. ⏳ Implement WebSocket for real-time updates (Task 7)
7. ⏳ Set up Grafana/Prometheus (Task 8 - Optional)

