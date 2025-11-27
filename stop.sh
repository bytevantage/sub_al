#!/bin/bash
# Trading System Stop Script

set -e

echo "🛑 Stopping Trading System..."

# Stop all containers
docker-compose down --remove-orphans

echo "✅ Trading System Stopped"
