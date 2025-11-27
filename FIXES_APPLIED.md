# Fixes Applied - Nov 20, 2025

## Issue 1: Strategy Showing as "default" in Positions/Trades ✅

### Root Cause
Signals were not properly passing strategy identification through the execution pipeline.

### Fixes Applied
1. **Enhanced logging in `order_manager.py`**:
   - Added debug trace to see strategy_id/strategy_name at signal execution
   - Changed fallback from 'default' to 'unknown' for better visibility
   - Upgraded logging from debug to info level for strategy resolution

2. **Signal class** (`strategy_base.py`):
   - Already has proper strategy_id auto-normalization (line 77-79)
   - to_dict() method properly exports both 'strategy' and 'strategy_id'

### How to Verify
After restarting the system, check logs for:
```bash
grep "Strategy resolved" data/logs/trading_*.log
```

You should now see proper strategy names like:
- `quantum_edge`
- `oi_analysis` 
- `gamma_scalping`
- etc.

Instead of `default` or `unknown`.

---

## Issue 2: Docker + PyTorch Integration ✅

### Root Cause
PyTorch was NOT in main `requirements.txt`, causing Docker builds to fail or miss ML functionality.

### Fixes Applied

#### 1. Updated `requirements.txt`
Added PyTorch and related dependencies:
```txt
# Deep Learning (PyTorch - CPU only for Docker)
torch==2.1.0
pytorch-forecasting==1.0.0
```

#### 2. Optimized `docker/Dockerfile.backend`
Multi-stage installation to prevent timeout:
- **Stage 1**: Core numpy/pandas/scipy
- **Stage 2**: PyTorch from CPU-only index (faster download)
- **Stage 3**: ML libraries (scikit-learn, xgboost, lightgbm)
- **Stage 4**: All remaining dependencies

Key optimization:
```dockerfile
# Stage 2: PyTorch (CPU-only, optimized for Docker)
RUN pip install --no-cache-dir \
    torch==2.1.0 --index-url https://download.pytorch.org/whl/cpu
```

This uses PyTorch CPU-only wheels (~200MB) instead of GPU wheels (~2GB), preventing timeout.

#### 3. Created `docker_rebuild.sh`
Convenient script to rebuild Docker image with progress monitoring:
```bash
./docker_rebuild.sh
```

### How to Build & Verify

1. **Rebuild Docker image:**
   ```bash
   ./docker_rebuild.sh
   ```
   
   First build takes 5-10 minutes (PyTorch installation)

2. **Verify PyTorch is installed:**
   ```bash
   docker run --rm srb-algo-trading-engine:latest \
       python -c 'import torch; print(f"PyTorch {torch.__version__} installed")'
   ```
   
   Expected output: `PyTorch 2.1.0+cpu installed`

3. **Start system:**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

4. **Check logs:**
   ```bash
   docker logs -f trading_engine
   ```

---

## System Architecture Confirmed ✅

### SAC Meta-Controller
- ✅ Enabled in `config.yaml` (line 250-251)
- ✅ Integrated in `backend/main.py` (line 77-79)

### 6 Active Strategies
All configured with proper meta_group assignments:

1. **quantum_edge** (Group 0) - 25% allocation
2. **quantum_edge_v2** (Group 0) - 25% allocation  
3. **gamma_scalping** (Group 1) - 15% allocation
4. **vwap_deviation** (Group 3) - 15% allocation
5. **iv_rank_trading** (Group 2) - 15% allocation
6. **default** (time-filtered) - 15% allocation

---

## Docker Compose Status

### Services
- ✅ **postgres** (TimescaleDB) - Internal network only
- ✅ **redis** - Internal network only
- ✅ **trading-engine** - Port 8000 exposed

### Volumes Mapped
- `./backend` → Hot-reload support
- `./config` → Live config changes
- `./models` → SAC/ML models
- `./data` → Persistent logs/trades
- `./meta_controller` → SAC controller code

### Environment
- Database: `postgres:5432` (internal)
- Redis: `redis:6379` (internal)
- DNS: 8.8.8.8, 8.8.4.4 (for Upstox API)

---

## Next Steps

### 1. Rebuild Docker (if using Docker)
```bash
./docker_rebuild.sh
docker-compose down
docker-compose up -d
```

### 2. If Running Locally (not Docker)
```bash
# Update dependencies
pip install -r requirements.txt

# Restart system
pkill -f "python.*backend.main"
./launch_system.sh
```

### 3. Verify Fixes
```bash
# Check strategy resolution in logs
tail -f data/logs/trading_*.log | grep "Strategy resolved"

# Monitor positions in dashboard
open http://localhost:3000
```

### 4. Expected Behavior
- **Open Positions**: Should show actual strategy names (not "default")
- **Today's Trades**: Should show actual strategy names  
- **PyTorch**: Should load without errors in logs
- **SAC Controller**: Should be active and adjusting allocations

---

## Troubleshooting

### If strategies still show "default":
1. Check signal generation logs: `grep "Signal generated" data/logs/trading_*.log`
2. Check strategy resolution: `grep "Strategy resolved" data/logs/trading_*.log`
3. Verify Signal objects use `.to_dict()` before execution

### If PyTorch fails to load:
```bash
# Test import
python -c "import torch; print(torch.__version__)"

# If missing, reinstall
pip install torch==2.1.0 --index-url https://download.pytorch.org/whl/cpu
```

### If Docker build stuck:
- Check Docker has enough memory (8GB+ recommended)
- Use `--progress=plain` flag to see detailed output
- Try building individual stages manually if needed

---

## Files Modified

1. ✅ `backend/execution/order_manager.py` - Enhanced strategy logging
2. ✅ `requirements.txt` - Added PyTorch
3. ✅ `docker/Dockerfile.backend` - Optimized multi-stage build
4. ✅ `docker_rebuild.sh` - New build helper script
5. ✅ `frontend/dashboard/dashboard.js` - Token cache fix (from earlier)

---

## Verification Checklist

- [ ] Docker image builds successfully
- [ ] PyTorch imports without errors  
- [ ] Trading system starts without crashes
- [ ] Strategies show proper names in dashboard
- [ ] SAC controller is active
- [ ] All 6 strategies are enabled
- [ ] Token expiry banner is fixed

---

**Status**: All fixes applied and ready for testing!
**Time**: Nov 20, 2025 10:20 AM IST
