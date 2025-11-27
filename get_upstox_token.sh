#!/bin/bash

# Quick Upstox Token Fetcher
# Sets credentials as environment variables and runs the Python script

echo "═══════════════════════════════════════════════════════════"
echo "🔐 Quick Upstox Token Fetcher"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Check if credentials are already set in environment
if [ -z "$UPSTOX_CLIENT_ID" ] || [ -z "$UPSTOX_CLIENT_SECRET" ] || [ -z "$UPSTOX_REDIRECT_URI" ]; then
    echo "Enter your Upstox credentials:"
    echo ""
    
    read -p "Client ID: " UPSTOX_CLIENT_ID
    read -p "Client Secret: " UPSTOX_CLIENT_SECRET
    read -p "Redirect URI [http://localhost:5001/callback]: " UPSTOX_REDIRECT_URI
    
    # Set default if empty
    UPSTOX_REDIRECT_URI=${UPSTOX_REDIRECT_URI:-http://localhost:5001/callback}
    
    echo ""
    echo "Credentials set:"
    echo "  Client ID: $UPSTOX_CLIENT_ID"
    echo "  Redirect URI: $UPSTOX_REDIRECT_URI"
    echo ""
fi

# Export for Python script to use
export UPSTOX_CLIENT_ID
export UPSTOX_CLIENT_SECRET  
export UPSTOX_REDIRECT_URI

# Run the Python script
python3 - <<'EOF'
import os
import requests
import webbrowser
from flask import Flask, request
import json
import time
import pathlib
from urllib.parse import quote

app = Flask(__name__)

CLIENT_ID = os.environ.get('UPSTOX_CLIENT_ID')
CLIENT_SECRET = os.environ.get('UPSTOX_CLIENT_SECRET')
REDIRECT_URI = os.environ.get('UPSTOX_REDIRECT_URI')

if not all([CLIENT_ID, CLIENT_SECRET, REDIRECT_URI]):
    print("❌ Missing credentials!")
    exit(1)

AUTH_URL = f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={CLIENT_ID}&redirect_uri={quote(REDIRECT_URI)}"

@app.route('/callback')
def callback():
    authorization_code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return f"<h1>❌ Authorization Failed</h1><p>{error}</p>"
    
    if authorization_code:
        print(f"✅ Authorization code received: {authorization_code}")
        
        # Exchange for access token
        token_url = 'https://api.upstox.com/v2/login/authorization/token'
        headers = {'accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'code': authorization_code,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code',
        }
        
        print("📡 Exchanging authorization code for access token...")
        response = requests.post(token_url, headers=headers, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            token_data['created_at'] = int(time.time())
            
            # Save to both locations
            paths = [
                pathlib.Path.home() / "Algo" / "upstoxtoken.json",
                pathlib.Path(__file__).parent / "config" / "upstox_token.json"
            ]
            
            for file_path in paths:
                try:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, 'w') as f:
                        json.dump(token_data, f, indent=2)
                    print(f"✅ Token saved to {file_path}")
                except Exception as e:
                    print(f"⚠️  Could not save to {file_path}: {e}")
            
            return f"""
            <html><body style="font-family: Arial; padding: 50px; text-align: center;">
                <h1 style="color: green;">✅ Success!</h1>
                <p>Token saved. You can close this tab and press Ctrl+C in the terminal.</p>
            </body></html>
            """
        else:
            return f"<h1>❌ Failed to get token</h1><p>{response.text}</p>"
    
    return "<h1>❌ No authorization code</h1>"

if __name__ == '__main__':
    import re
    port_match = re.search(r':(\d+)/', REDIRECT_URI)
    port = int(port_match.group(1)) if port_match else 5000
    
    print()
    print("═══════════════════════════════════════════════════════════")
    print(f"🚀 Server starting on http://localhost:{port}")
    print("═══════════════════════════════════════════════════════════")
    print()
    print("🌐 Opening browser for authorization...")
    print()
    
    try:
        webbrowser.open(AUTH_URL)
        time.sleep(2)
        print("✓ Browser opened")
    except Exception as e:
        print(f"⚠️  Could not open browser: {e}")
        print(f"Manually go to: {AUTH_URL}")
    
    print()
    print("⏳ Waiting for callback...")
    print("   Keep this window open!")
    print()
    
    try:
        app.run(host='0.0.0.0', port=port, debug=False)
    except KeyboardInterrupt:
        print("\n\n✅ Done! Now restart the trading system.")
EOF
