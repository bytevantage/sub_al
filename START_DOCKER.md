# Start Trading System in Docker

## ✅ Completed Steps:

1. **Local PostgreSQL stopped** and disabled from auto-start
2. **Database migrated** - All 192 trades moved to Docker PostgreSQL  
3. **Config files updated** - Changed `localhost` → Docker service names (`postgres`, `redis`)
4. **Requirements fixed** - Removed incompatible `pandas-ta==0.3.14b0`

## 🚀 To Start the System:

### Option 1: Start Everything
```bash
cd /Users/srbhandary/Documents/Projects/srb-algo
docker-compose up -d
```

### Option 2: Start Individual Services
```bash
cd /Users/srbhandary/Documents/Projects/srb-algo

# Infrastructure first
docker-compose up -d postgres redis

# Then trading engine (will rebuild if needed)
docker-compose up -d trading-engine

# Optional: Frontend and monitoring
docker-compose up -d frontend grafana prometheus
```

## 📊 Check Status
```bash
./docker-status.sh
# OR
docker-compose ps
docker-compose logs -f trading-engine
```

## 🛑 Stop System
```bash
docker-compose down
# OR to also remove volumes:
docker-compose down -v
```

## 🔗 Access Points
- **Dashboard**: http://localhost:8000/dashboard/
- **API Docs**: http://localhost:8000/docs  
- **Health**: http://localhost:8000/api/health
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

## 📝 Notes

### ML Training Schedule
- Runs at **16:00 (4 PM) IST** daily
- System must be running at that time for training to execute
- Check logs: `docker-compose logs -f trading-engine | grep "ML training"`

### Data Location
- **Database**: Docker volume `postgres_data`
- **Redis**: Docker volume `redis_data`  
- **Logs**: `./logs/` (mounted from host)
- **Models**: `./models/` (mounted from host)
- **Config**: `./config/` (mounted from host)

### Troubleshooting

**If containers don't start:**
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

**If ports are in use:**
```bash
# Check what's using ports
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis
lsof -i :8000  # Trading engine

# Kill local services if needed
brew services stop postgresql@14
brew services stop redis
```

**View all logs:**
```bash
docker-compose logs -f
```

**Rebuild single container:**
```bash
docker-compose build trading-engine
docker-compose up -d trading-engine
```
