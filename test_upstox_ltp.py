#!/usr/bin/env python3
"""Test script to check Upstox LTP API response"""

import json
import sys
sys.path.append('/Users/srbhandary/Documents/Projects/srb-algo')

from backend.core.upstox_client import UpstoxClient

# Read token
with open('/Users/srbhandary/Algo/upstoxtoken.json') as f:
    token_data = json.load(f)

# Initialize client
client = UpstoxClient(access_token=token_data['access_token'])

# NIFTY 50 instrument key
nifty_key = "NSE_INDEX|Nifty 50"
sensex_key = "BSE_INDEX|SENSEX"

print(f"Testing Upstox LTP API...")
print(f"NIFTY instrument key: {nifty_key}")
print(f"SENSEX instrument key: {sensex_key}")
print("-" * 60)

# Test NIFTY
print(f"\n1. Testing NIFTY LTP:")
try:
    response = client.get_ltp([nifty_key])
    print(f"Response: {json.dumps(response, indent=2)}")
except Exception as e:
    print(f"Error: {e}")

# Test SENSEX
print(f"\n2. Testing SENSEX LTP:")
try:
    response = client.get_ltp([sensex_key])
    print(f"Response: {json.dumps(response, indent=2)}")
except Exception as e:
    print(f"Error: {e}")
