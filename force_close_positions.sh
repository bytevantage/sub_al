#!/bin/bash
# Force close all positions by directly accessing order manager

echo "========================================"
echo "Force Closing All Open Positions"
echo "========================================"
echo ""

# Get positions from dashboard
echo "Getting positions from dashboard..."
POSITIONS=$(curl -s http://localhost:8000/api/dashboard/positions)
COUNT=$(echo "$POSITIONS" | jq -r '.data.positions | length')

if [ "$COUNT" = "0" ] || [ "$COUNT" = "null" ]; then
    echo "✓ No positions to close"
    exit 0
fi

echo "Found $COUNT open positions:"
echo ""
echo "$POSITIONS" | jq -r '.data.positions[] | "- \(.symbol) \(.strike_price) \(.option_type) | Entry: ₹\(.entry_price) | Current: ₹\(.current_price) | P&L: ₹\(.unrealized_pnl)"'
echo ""

TOTAL_PNL=$(echo "$POSITIONS" | jq -r '.data.totals.total_unrealized_pnl')
echo "Total P&L: ₹$TOTAL_PNL"
echo ""

read -p "Close all positions? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Triggering position closure via backend..."

# Restart backend to force EOD close on positions
echo "Method: Restarting backend to trigger EOD closure"
echo ""

./stop.sh
sleep 2

# Set environment variable to force EOD close
export FORCE_CLOSE_POSITIONS=true

./start.sh

echo ""
echo "Backend restarted. Checking positions..."
sleep 5

NEW_COUNT=$(curl -s http://localhost:8000/api/dashboard/positions | jq -r '.data.positions | length')

if [ "$NEW_COUNT" = "0" ]; then
    echo "✅ All positions closed!"
else
    echo "⚠️ Still $NEW_COUNT positions open"
    echo ""
    echo "Manual intervention needed. Try:"
    echo "  python3 close_positions_direct_api.py"
fi
