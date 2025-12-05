#!/usr/bin/env python3
"""
Simple Upstox Token Generator
"""
import requests
import webbrowser
import json
import time
from pathlib import Path

# Configuration
CLIENT_ID = '831e3836-d40e-411d-b659-63aaa41942b6'
CLIENT_SECRET = '1z9nq825ul'
REDIRECT_URI = 'http://localhost:8000/api/upstox/callback'  # Use the main API server

# Generate authorization URL
auth_url = f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"

print("🔗 Upstox Authentication URL:")
print(auth_url)
print()
print("📋 Steps:")
print("1. Open the above URL in your browser")
print("2. Login to Upstox and authorize the app")
print("3. After authorization, you'll be redirected to a callback URL")
print("4. Copy the 'code' parameter from the callback URL")
print("5. Run the token exchange script")
print()
print("🌐 Opening browser in 3 seconds...")
time.sleep(3)

try:
    webbrowser.open(auth_url)
    print("✅ Browser opened successfully")
except:
    print("❌ Could not open browser automatically")
    print(f"Please manually open: {auth_url}")

print()
print("⏳ Waiting for authorization...")
print("Once you get the callback URL with 'code' parameter,")
print("use the token exchange endpoint to get your access token.")
