#!/bin/bash
# Close positions via Emergency API
# This works regardless of database type

echo "========================================"
echo "Closing Positions via Emergency API"
echo "========================================"
echo ""

# Check if backend is running
if ! curl -s http://localhost:8000/api/dashboard/risk-metrics > /dev/null 2>&1; then
    echo "❌ Backend is not running!"
    echo ""
    echo "Start backend first:"
    echo "  cd /Users/srbhandary/Documents/Projects/srb-algo"
    echo "  ./start.sh"
    exit 1
fi

echo "✓ Backend is running"
echo ""

# Get current open positions
echo "Checking open positions..."
POSITIONS_JSON=$(curl -s http://localhost:8000/api/dashboard/open-positions)
POSITION_COUNT=$(echo "$POSITIONS_JSON" | jq -r '.data.positions | length')

if [ "$POSITION_COUNT" = "0" ] || [ "$POSITION_COUNT" = "null" ]; then
    echo "✓ No open positions found!"
    exit 0
fi

echo "Found $POSITION_COUNT open position(s):"
echo ""

# Show positions
echo "$POSITIONS_JSON" | jq -r '.data.positions[] | "- \(.symbol) \(.strike_price) \(.instrument_type) | Entry: ₹\(.entry_price) | Current: ₹\(.current_price) | P&L: ₹\(.unrealized_pnl)"'
echo ""

# Confirm
read -p "Close all positions? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Closing all positions..."

# Close via emergency API
RESPONSE=$(curl -s -X POST http://localhost:8000/emergency/positions/close \
  -H "Content-Type: application/json" \
  -H "x-api-key: EMERGENCY_KEY_123" \
  -d '{
    "close_all": true,
    "reason": "Manual EOD closure - market closed at 3:30 PM IST"
  }')

echo ""
echo "Response:"
echo "$RESPONSE" | jq '.'
echo ""

# Verify closure
echo "Verifying positions closed..."
sleep 2

NEW_COUNT=$(curl -s http://localhost:8000/api/dashboard/open-positions | jq -r '.data.positions | length')

if [ "$NEW_COUNT" = "0" ]; then
    echo "✅ SUCCESS: All positions closed!"
else
    echo "⚠️  Warning: Still $NEW_COUNT position(s) open"
    echo "Check logs: tail -100 backend/logs/trading.log"
fi

echo ""
echo "========================================"
echo "Next: Restart backend to apply timezone fixes"
echo "  ./stop.sh && sleep 3 && ./start.sh"
echo "========================================"
