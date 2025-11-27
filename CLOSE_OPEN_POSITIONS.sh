#!/bin/bash
# Emergency script to close all open positions
# Use this if positions didn't close at EOD due to system being down

echo "========================================"
echo "Emergency: Closing All Open Positions"
echo "========================================"
echo ""

# Check if positions exist
echo "Checking open positions..."
POSITIONS=$(curl -s http://localhost:8000/api/dashboard/open-positions | jq -r '.data.positions | length')

if [ "$POSITIONS" = "0" ]; then
    echo "✓ No open positions found. All clear!"
    exit 0
fi

echo "Found $POSITIONS open position(s)"
echo ""

# Show positions
echo "Current open positions:"
curl -s http://localhost:8000/api/dashboard/open-positions | jq '.data.positions[] | {symbol, strike_price, instrument_type, entry_price, unrealized_pnl}'
echo ""

# Confirm before closing
read -p "Do you want to close ALL open positions? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted. No positions closed."
    exit 0
fi

echo ""
echo "Closing all positions via emergency API..."

# Use emergency API to close all positions
# Note: Requires API key authentication
curl -X POST http://localhost:8000/emergency/positions/close \
  -H "Content-Type: application/json" \
  -H "x-api-key: EMERGENCY_KEY_123" \
  -d '{
    "close_all": true,
    "reason": "Manual EOD closure - system was down at 3:29 PM"
  }'

echo ""
echo ""
echo "========================================"
echo "Position closure request sent!"
echo "Check dashboard to verify all closed."
echo "========================================"
