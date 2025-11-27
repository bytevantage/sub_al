#!/bin/bash

# Save Upstox credentials for the dashboard OAuth flow
# This allows the "Get Token" button in the dashboard to work

echo "═══════════════════════════════════════════════════════════"
echo "🔐 Save Upstox Credentials"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "This will save your Upstox credentials so the dashboard"
echo "'Get Token' button can handle the OAuth flow automatically."
echo ""

# Create directory if it doesn't exist
mkdir -p ~/Algo

# Check if credentials already exist
if [ -f ~/Algo/upstox_credentials.json ]; then
    echo "✓ Found existing credentials:"
    cat ~/Algo/upstox_credentials.json | jq '.'
    echo ""
    read -p "Update these credentials? (y/n): " UPDATE
    if [ "$UPDATE" != "y" ]; then
        echo "Keeping existing credentials."
        exit 0
    fi
fi

echo "Enter your Upstox App credentials:"
echo "(Get these from: https://api.upstox.com/ → My Apps)"
echo ""

read -p "Client ID: " CLIENT_ID
read -sp "Client Secret: " CLIENT_SECRET
echo ""

# Save to JSON file
cat > ~/Algo/upstox_credentials.json <<EOF
{
  "client_id": "$CLIENT_ID",
  "client_secret": "$CLIENT_SECRET",
  "redirect_uri": "http://localhost:8000/api/upstox/callback"
}
EOF

echo ""
echo "✅ Credentials saved to ~/Algo/upstox_credentials.json"
echo ""
echo "Now you can use the 'Get Token' button in the dashboard!"
echo "It will open a new window for Upstox authorization."
