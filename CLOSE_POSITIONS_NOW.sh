#!/bin/bash
# Emergency script to close positions immediately
# Run this NOW to close the 3 open NIFTY positions

echo "========================================"
echo "Closing Open NIFTY Positions"
echo "========================================"
echo ""

# Method 1: Try emergency API
echo "Attempting to close all positions via emergency API..."
echo ""

RESPONSE=$(curl -s -X POST http://localhost:8000/emergency/positions/close \
  -H "Content-Type: application/json" \
  -H "x-api-key: EMERGENCY_KEY_123" \
  -d '{
    "close_all": true,
    "reason": "Manual EOD closure - market closed at 3:30 PM"
  }')

echo "Response: $RESPONSE"
echo ""

# Check if successful
if echo "$RESPONSE" | grep -q "success"; then
    echo "✅ SUCCESS: Positions closed via emergency API"
    echo ""
    echo "Verifying positions are closed..."
    sleep 2
    curl -s http://localhost:8000/api/dashboard/open-positions | jq '.data.positions | length'
    echo ""
else
    echo "⚠️  Emergency API failed. Trying alternative method..."
    echo ""
    
    # Method 2: Try direct order manager
    echo "Attempting direct closure via order manager..."
    docker exec trading_engine python -c "
import asyncio
from backend.execution.order_manager import OrderManager
from backend.core.config import config

async def close_all():
    order_mgr = OrderManager(config.get('trading'), None, None)
    positions = await order_mgr.get_positions()
    print(f'Found {len(positions)} open positions')
    
    for pos in positions:
        print(f\"Closing {pos.get('symbol')} {pos.get('strike_price')} {pos.get('instrument_type')}\")
        await order_mgr.close_position(pos)
    
    print('All positions closed')

asyncio.run(close_all())
"
fi

echo ""
echo "========================================"
echo "Final Position Check"
echo "========================================"
echo ""
curl -s http://localhost:8000/api/dashboard/open-positions | jq '.'
echo ""
echo "========================================"
echo "NEXT STEP: Restart backend to apply timezone fixes"
echo "Run: docker-compose restart trading_engine"
echo "========================================"
