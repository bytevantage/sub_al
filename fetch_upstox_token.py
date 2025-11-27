#!/usr/bin/env python3
"""
Interactive Upstox Token Fetcher
Helps you configure and fetch a fresh Upstox access token
"""

import requests
import webbrowser
from flask import Flask, request
import json
import time
import pathlib
from urllib.parse import quote

app = Flask(__name__)

# These will be set interactively
CLIENT_ID = None
CLIENT_SECRET = None
REDIRECT_URI = None
AUTH_URL = None

# Global variable to store the access token
access_token = None

def get_credentials():
    """Interactively get Upstox credentials from user"""
    global CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, AUTH_URL
    
    print("═══════════════════════════════════════════════════════════")
    print("🔐 Upstox Token Fetcher - Interactive Setup")
    print("═══════════════════════════════════════════════════════════")
    print()
    print("First, get your credentials from Upstox Developer Portal:")
    print("👉 https://api.upstox.com/")
    print()
    print("Go to: My Apps → [Your App Name]")
    print()
    
    # Get Client ID
    print("─────────────────────────────────────────────────────────────")
    CLIENT_ID = input("Enter your Client ID (App ID): ").strip()
    if not CLIENT_ID:
        print("❌ Client ID is required!")
        exit(1)
    
    # Get Client Secret
    print("─────────────────────────────────────────────────────────────")
    CLIENT_SECRET = input("Enter your Client Secret (App Secret): ").strip()
    if not CLIENT_SECRET:
        print("❌ Client Secret is required!")
        exit(1)
    
    # Get Redirect URI
    print("─────────────────────────────────────────────────────────────")
    print()
    print("📋 Common Redirect URIs:")
    print("  1. http://localhost:5000/callback")
    print("  2. http://127.0.0.1:5000/callback")
    print("  3. Custom (enter your own)")
    print()
    
    choice = input("Select option (1/2/3) or press Enter for option 1: ").strip()
    
    if choice == '2':
        REDIRECT_URI = 'http://127.0.0.1:5000/callback'
    elif choice == '3':
        REDIRECT_URI = input("Enter your custom Redirect URI: ").strip()
    else:
        REDIRECT_URI = 'http://localhost:5000/callback'
    
    if not REDIRECT_URI:
        print("❌ Redirect URI is required!")
        exit(1)
    
    # Build auth URL
    AUTH_URL = f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={CLIENT_ID}&redirect_uri={quote(REDIRECT_URI)}"
    
    print()
    print("═══════════════════════════════════════════════════════════")
    print("✅ Configuration Summary:")
    print("═══════════════════════════════════════════════════════════")
    print(f"Client ID:     {CLIENT_ID}")
    print(f"Client Secret: {CLIENT_SECRET[:4]}...{CLIENT_SECRET[-4:]}")
    print(f"Redirect URI:  {REDIRECT_URI}")
    print()
    print("⚠️  IMPORTANT: Verify that your Redirect URI in Upstox portal")
    print(f"   EXACTLY matches: {REDIRECT_URI}")
    print()
    
    confirm = input("Continue with these settings? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Exiting...")
        exit(0)
    
    # Save credentials for future use
    save_credentials()

def save_credentials():
    """Save credentials to config file for future use"""
    try:
        config_dir = pathlib.Path.home() / "Algo"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "upstox_credentials.json"
        
        credentials = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI
        }
        
        with open(config_file, 'w') as f:
            json.dump(credentials, f, indent=2)
        
        print(f"✅ Credentials saved to {config_file}")
    except Exception as e:
        print(f"⚠️  Could not save credentials: {e}")

def load_saved_credentials():
    """Try to load previously saved credentials"""
    global CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, AUTH_URL
    
    try:
        config_file = pathlib.Path.home() / "Algo" / "upstox_credentials.json"
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                credentials = json.load(f)
            
            CLIENT_ID = credentials['client_id']
            CLIENT_SECRET = credentials['client_secret']
            REDIRECT_URI = credentials['redirect_uri']
            
            AUTH_URL = f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={CLIENT_ID}&redirect_uri={quote(REDIRECT_URI)}"
            
            print("═══════════════════════════════════════════════════════════")
            print("✅ Found saved credentials!")
            print("═══════════════════════════════════════════════════════════")
            print(f"Client ID:     {CLIENT_ID}")
            print(f"Redirect URI:  {REDIRECT_URI}")
            print()
            
            use_saved = input("Use these credentials? (y/n): ").strip().lower()
            if use_saved == 'y':
                return True
    except Exception as e:
        pass
    
    return False

# Open the authorization URL in the browser
def open_authorization_url():
    print()
    print("═══════════════════════════════════════════════════════════")
    print("🌐 Opening browser for authorization...")
    print("═══════════════════════════════════════════════════════════")
    print()
    print("Steps:")
    print("1. Browser will open to Upstox login page")
    print("2. Login with your Upstox credentials (mobile + OTP)")
    print("3. Click 'Authorize' to grant access")
    print("4. You'll be redirected back automatically")
    print("5. Token will be saved to ~/Algo/upstoxtoken.json")
    print()
    print("If browser doesn't open, manually go to:")
    print(AUTH_URL)
    print()
    
    try:
        webbrowser.open(AUTH_URL)
    except Exception as e:
        print(f"⚠️  Error opening browser: {e}")
        print("Please manually open the URL above")

# Set up Flask route to handle the callback and extract the code
@app.route('/callback')
def callback():
    global access_token
    authorization_code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        error_description = request.args.get('error_description', 'Unknown error')
        print(f"❌ Authorization error: {error} - {error_description}")
        return f"<h1>Authorization Failed</h1><p>{error}: {error_description}</p><p>Check your Client ID and Redirect URI in Upstox portal.</p>"
    
    if authorization_code:
        print(f"✅ Authorization code received: {authorization_code}")
        
        # Exchange authorization code for access token
        token_data = get_access_token(authorization_code)
        
        # Save the access token to a file
        if token_data:
            save_access_token_to_file(token_data)
            return f"""
            <html>
            <head><title>Authorization Successful</title></head>
            <body style="font-family: Arial; padding: 50px; text-align: center;">
                <h1 style="color: green;">✅ Authorization Successful!</h1>
                <p>Access token has been saved to:<br><code>~/Algo/upstoxtoken.json</code></p>
                <p><strong>Token:</strong><br><code>{token_data.get('access_token')[:20]}...</code></p>
                <hr>
                <p style="color: green;">✅ You can close this tab now.</p>
                <p>The trading system can now use this token.</p>
            </body>
            </html>
            """
        else:
            return "<h1>Failed to obtain access token</h1><p>Check the console for errors.</p>"
    else:
        return "<h1>Authorization code not found</h1><p>Something went wrong during authorization.</p>"

# Function to exchange authorization code for access token
def get_access_token(authorization_code):
    token_url = 'https://api.upstox.com/v2/login/authorization/token'
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
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
        print(f"✅ Access token obtained: {token_data.get('access_token')[:20]}...")
        return token_data
    else:
        print(f"❌ Error getting access token: {response.status_code}")
        print(f"Response: {response.text}")
        return None

# Function to save the access token to a JSON file
def save_access_token_to_file(token_data):
    try:
        current_dir = pathlib.Path.home() / "Algo"
        file_path = current_dir / 'upstoxtoken.json'
        backup_path = current_dir / 'upstoxtoken_backup.json'

        # Ensure the directory exists
        current_dir.mkdir(parents=True, exist_ok=True)

        # Add timestamp to token data
        token_data['created_at'] = int(time.time())

        # Save as JSON
        with open(file_path, 'w') as file:
            json.dump(token_data, file, indent=2)
        print(f"✅ Access token saved to {file_path}")
        
        # Save backup
        with open(backup_path, 'w') as file:
            json.dump(token_data, file, indent=2)
        print(f"✅ Backup saved to {backup_path}")
        
        print()
        print("═══════════════════════════════════════════════════════════")
        print("✅ SUCCESS! Token is ready to use")
        print("═══════════════════════════════════════════════════════════")
        print()
        print("Next steps:")
        print("1. Close the browser tab")
        print("2. Press Ctrl+C here to stop the server")
        print("3. Run: ./launch_system.sh")
        print()
        
    except Exception as e:
        print(f"❌ Error saving token to file: {e}")

if __name__ == '__main__':
    print()
    
    # Try to load saved credentials first
    if not load_saved_credentials():
        # If no saved credentials, get them interactively
        get_credentials()
    
    # Extract port from redirect URI
    import re
    port_match = re.search(r':(\d+)/', REDIRECT_URI)
    port = int(port_match.group(1)) if port_match else 5000
    
    print()
    print("═══════════════════════════════════════════════════════════")
    print(f"🚀 Starting Flask server on http://localhost:{port}")
    print("═══════════════════════════════════════════════════════════")
    print()
    print("⚠️  IMPORTANT: Keep this terminal window open!")
    print()
    print(f"📌 Your Redirect URI is: {REDIRECT_URI}")
    print(f"📌 Server will listen on port: {port}")
    print()
    
    # Open the authorization URL in the browser
    open_authorization_url()
    
    print()
    print("Waiting for authorization callback...")
    print()
    print("After you authorize in the browser, you'll be redirected back here.")
    print("Press Ctrl+C to stop the server after getting the token")
    print()
    
    # Start the Flask server to listen for the callback
    try:
        app.run(host='0.0.0.0', port=port, debug=False)
    except KeyboardInterrupt:
        print("\n\n✅ Server stopped. Token should be saved if authorization was successful.")
        print("Now run: ./launch_system.sh")
