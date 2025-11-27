"""
Lightweight Flask callback server for Upstox OAuth
Runs on port 5001 to handle redirects from Upstox
"""
from flask import Flask, request
import requests
import json
import time
from pathlib import Path

app = Flask(__name__)

# These will be loaded from config
CLIENT_ID = None
CLIENT_SECRET = None
REDIRECT_URI = None

@app.route('/callback')
def callback():
    """Handle OAuth callback from Upstox"""
    authorization_code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        error_description = request.args.get('error_description', 'Unknown error')
        return f"""
        <html>
        <head>
            <title>Authorization Failed</title>
            <script>setTimeout(function() {{ window.close(); }}, 3000);</script>
        </head>
        <body style="font-family: Arial; padding: 50px; text-align: center;">
            <h1 style="color: red;">❌ Authorization Failed</h1>
            <p><strong>Error:</strong> {error}</p>
            <p>{error_description}</p>
            <p style="color: #666; margin-top: 30px;">This window will close in 3 seconds...</p>
        </body>
        </html>
        """
    
    if not authorization_code:
        return """
        <html>
        <head>
            <title>Error</title>
            <script>setTimeout(function() { window.close(); }, 3000);</script>
        </head>
        <body style="font-family: Arial; padding: 50px; text-align: center;">
            <h1 style="color: red;">❌ No Authorization Code</h1>
            <p>The authorization code was not received.</p>
            <p style="color: #666; margin-top: 30px;">This window will close in 3 seconds...</p>
        </body>
        </html>
        """
    
    try:
        # Exchange authorization code for access token
        token_url = "https://api.upstox.com/v2/login/authorization/token"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "code": authorization_code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        
        print(f"📡 Exchanging authorization code for access token...")
        response = requests.post(token_url, headers=headers, data=data, timeout=10)
        
        if response.status_code != 200:
            error_data = response.json()
            error_msg = error_data.get('errors', [{}])[0].get('message', 'Unknown error')
            return f"""
            <html>
            <head>
                <title>Token Exchange Failed</title>
                <script>setTimeout(function() {{ window.close(); }}, 5000);</script>
            </head>
            <body style="font-family: Arial; padding: 50px; text-align: center;">
                <h1 style="color: red;">❌ Token Exchange Failed</h1>
                <p><strong>Error:</strong> {error_msg}</p>
                <p>Status Code: {response.status_code}</p>
                <p style="color: #666; margin-top: 30px;">This window will close in 5 seconds...</p>
            </body>
            </html>
            """
        
        token_data = response.json()
        token_data['created_at'] = int(time.time())
        
        # Save token to config directory
        token_file = Path(__file__).parent.parent.parent / "config" / "upstox_token.json"
        token_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(token_file, 'w') as f:
            json.dump(token_data, f, indent=2)
        
        print(f"✅ Token saved to {token_file}")
        
        # Also save backup to ~/Algo
        backup_file = Path.home() / "Algo" / "upstoxtoken.json"
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        with open(backup_file, 'w') as f:
            json.dump(token_data, f, indent=2)
        
        print(f"✅ Backup saved to {backup_file}")
        
        return """
        <html>
        <head>
            <title>Authorization Successful</title>
            <script>
                setTimeout(function() {
                    window.close();
                }, 2000);
            </script>
        </head>
        <body style="font-family: Arial; padding: 50px; text-align: center;">
            <h1 style="color: green;">✅ Authorization Successful!</h1>
            <p>Access token has been saved successfully.</p>
            <p style="color: #666; margin-top: 30px;">This window will close automatically in 2 seconds...</p>
            <p style="color: #999; font-size: 0.9em;">If it doesn't close, you can close it manually.</p>
        </body>
        </html>
        """
        
    except Exception as e:
        print(f"❌ Error in OAuth callback: {e}")
        return f"""
        <html>
        <head>
            <title>Error</title>
            <script>setTimeout(function() {{ window.close(); }}, 5000);</script>
        </head>
        <body style="font-family: Arial; padding: 50px; text-align: center;">
            <h1 style="color: red;">❌ Error Processing Authorization</h1>
            <p><strong>Error:</strong> {str(e)}</p>
            <p style="color: #666; margin-top: 30px;">This window will close in 5 seconds...</p>
        </body>
        </html>
        """

@app.route('/health')
def health():
    """Health check endpoint"""
    return {"status": "ok", "port": 5001}

def start_server(client_id, client_secret, redirect_uri):
    """Start the Flask server"""
    global CLIENT_ID, CLIENT_SECRET, REDIRECT_URI
    CLIENT_ID = client_id
    CLIENT_SECRET = client_secret
    REDIRECT_URI = redirect_uri
    
    print("=" * 60)
    print("🚀 Upstox OAuth Callback Server")
    print("=" * 60)
    print(f"Port: 5001")
    print(f"Redirect URI: {redirect_uri}")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5001, debug=False)

if __name__ == '__main__':
    # For standalone testing
    import sys
    if len(sys.argv) < 4:
        print("Usage: python upstox_callback_server.py <client_id> <client_secret> <redirect_uri>")
        sys.exit(1)
    
    start_server(sys.argv[1], sys.argv[2], sys.argv[3])
