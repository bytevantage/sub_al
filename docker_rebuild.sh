#!/bin/bash

# Docker Rebuild Script for Trading Engine
# Rebuilds the Docker image with optimized PyTorch installation

set -e  # Exit on error

echo "════════════════════════════════════════════════════════════"
echo "🐳 Building Trading Engine Docker Image"
echo "════════════════════════════════════════════════════════════"
echo ""

# Build the image
echo "📦 Building image: srb-algo-trading-engine:latest"
echo "⏳ This may take 5-10 minutes for first build (PyTorch installation)"
echo ""

docker build \
    --file docker/Dockerfile.backend \
    --tag srb-algo-trading-engine:latest \
    --progress=plain \
    .

echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ Build completed successfully!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "📝 Build info:"
docker images srb-algo-trading-engine:latest
echo ""
echo "🚀 To start the system:"
echo "   docker-compose down && docker-compose up -d"
echo ""
echo "📊 To view logs:"
echo "   docker logs -f trading_engine"
echo ""
echo "🔍 To verify PyTorch:"
echo "   docker run --rm srb-algo-trading-engine:latest python -c 'import torch; print(f\"PyTorch {torch.__version__} installed\")'"
echo ""
