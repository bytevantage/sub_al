#!/bin/bash

# Docker Status Check Script

echo "════════════════════════════════════════════"
echo "🐳 Trading System Docker Status"
echo "════════════════════════════════════════════"
echo ""

# Check Docker daemon
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running"
    exit 1
fi
echo "✓ Docker daemon is running"
echo ""

# Check containers
echo "📦 Container Status:"
docker-compose ps

echo ""
echo "📊 Resource Usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" $(docker-compose ps -q) 2>/dev/null || echo "No containers running"

echo ""
echo "🔗 Access URLs:"
echo "  • Dashboard:     http://localhost:8000/dashboard/"
echo "  • API Docs:      http://localhost:8000/docs"
echo "  • Health:        http://localhost:8000/api/health"
echo "  • Grafana:       http://localhost:3000 (admin/admin)"
echo "  • Prometheus:    http://localhost:9090"
echo ""

echo "📝 Quick Commands:"
echo "  • View logs:     docker-compose logs -f trading-engine"
echo "  • Restart:       docker-compose restart trading-engine"
echo "  • Stop all:      docker-compose down"
echo "  • Start all:     docker-compose up -d"
echo ""
