import requests
import webbrowser
from flask import Flask, request
from urllib.parse import quote
import os
import json
import time
import pathlib  # Added pathlib for path compatibility

app = Flask(__name__)

# Upstox app credentials
CLIENT_ID = '831e3836-d40e-411d-b659-63aaa41942b6'
CLIENT_SECRET = '1z9nq825ul'
REDIRECT_URI = 'http://localhost:5001/callback'

# URL to request authorization code
AUTH_URL = f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"

# Global variable to store the access token
access_token = None

# Open the authorization URL in the browser
def open_authorization_url():
    print("Opening browser for authorization...")
    try:
        webbrowser.open(AUTH_URL)
    except Exception as e:
        print(f"Error opening browser: {e}")
        print("Please manually open the following URL in your browser:")
        print(AUTH_URL)

# Set up Flask route to handle the callback and extract the code
@app.route('/callback')
def callback():
    global access_token
    authorization_code = request.args.get('code')
    if authorization_code:
        print(f"Authorization code received: {authorization_code}")
        
        # Exchange authorization code for access token
        token_data = get_access_token(authorization_code)
        
        # Save the access token to a file in a compatible directory
        if token_data:
            save_access_token_to_file(token_data)
            return f"Access token: {token_data.get('access_token')}<br>This tab can be closed."
        else:
            return "Failed to obtain access token."
    else:
        return "Authorization code not found in the request."

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
    
    response = requests.post(token_url, headers=headers, data=data)

    if response.status_code == 200:
        # Return the full token response (not just access_token)
        token_data = response.json()
        print("Access token:", token_data.get('access_token'))
        return token_data
    else:
        print("Error getting access token:", response.status_code)
        print(response.json())
        return None

# Function to save the access token to a JSON file in the correct format
def save_access_token_to_file(token_data):
    try:
        # Save to project config directory (works both locally and in Docker)
        project_root = pathlib.Path(__file__).parent.absolute()
        config_dir = project_root / 'config'
        file_path = config_dir / 'upstox_token.json'
        backup_path = config_dir / 'upstox_token_backup.json'

        # Ensure the directory exists
        config_dir.mkdir(parents=True, exist_ok=True)

        # Add timestamp to token data
        token_data['created_at'] = int(time.time())

        # Save as JSON (format expected by dashboard)
        with open(file_path, 'w') as file:
            json.dump(token_data, file, indent=2)
        print(f"Access token saved to {file_path}")
        
        # Save backup
        with open(backup_path, 'w') as file:
            json.dump(token_data, file, indent=2)
        print(f"Backup saved to {backup_path}")
    except Exception as e:
        print(f"Error saving token to file: {e}")

if __name__ == '__main__':
    # Open the authorization URL in the browser
    open_authorization_url()
    
    # Start the Flask server to listen for the callback
    app.run(port=5001)
