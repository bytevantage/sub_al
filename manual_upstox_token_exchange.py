#!/usr/bin/env python3
"""
Manual Upstox Token Exchange
Exchange authorization code for access token and save to ~/Algo/upstoxtoken.json
"""
import requests
import json
import pathlib
import time

# Fill these with your values
CLIENT_ID = input("Enter your Upstox Client ID: ").strip()
CLIENT_SECRET = input("Enter your Upstox Client Secret: ").strip()
REDIRECT_URI = input("Enter your Redirect URI: ").strip()
AUTH_CODE = input("Paste the authorization code from the callback URL: ").strip()

token_url = 'https://api.upstox.com/v2/login/authorization/token'
headers = {
    'accept': 'application/json',
    'Content-Type': 'application/x-www-form-urlencoded',
}
data = {
    'code': AUTH_CODE,
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'redirect_uri': REDIRECT_URI,
    'grant_type': 'authorization_code',
}

print("Exchanging code for access token...")
response = requests.post(token_url, headers=headers, data=data)
if response.status_code == 200:
    token_data = response.json()
    token_data['created_at'] = int(time.time())
    config_dir = pathlib.Path.home() / "Algo"
    config_dir.mkdir(parents=True, exist_ok=True)
    file_path = config_dir / 'upstoxtoken.json'
    with open(file_path, 'w') as f:
        json.dump(token_data, f, indent=2)
    print(f"✅ Access token saved to {file_path}")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)
