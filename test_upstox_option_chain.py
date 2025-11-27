#!/usr/bin/env python3
"""
Test script to see what strikes Upstox actually returns in the option chain
"""
import sys
import json
from datetime import datetime, timedelta
sys.path.append('/Users/srbhandary/Documents/Projects/srb-algo')

from backend.core.upstox_client import UpstoxClient

# Load token
with open('config/upstox_token.json', 'r') as f:
    token_data = json.load(f)

client = UpstoxClient(token_data['access_token'])

# Get NIFTY spot price
print("Fetching NIFTY spot price...")
spot_response = client.get_ltp(["NSE_INDEX|Nifty 50"])
if spot_response and 'data' in spot_response:
    spot_key = "NSE_INDEX:Nifty 50"
    spot_price = spot_response['data'][spot_key]['last_price']
    print(f"NIFTY spot: {spot_price}")
else:
    print("Could not get spot price")
    sys.exit(1)

# Calculate next Tuesday (NIFTY weekly expiry)
today = datetime.now()
days_ahead = (1 - today.weekday()) % 7  # Tuesday is 1
if days_ahead == 0 and (today.hour >= 15 and today.minute >= 30):
    days_ahead = 7
elif days_ahead < 0:
    days_ahead += 7
expiry = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
print(f"Using expiry: {expiry}")

# Get option chain
print(f"\nFetching NIFTY option chain for {expiry}...")
response = client.get_option_chain("NSE_INDEX|Nifty 50", expiry)

if not response or 'data' not in response:
    print("Failed to get option chain")
    print(f"Response: {response}")
    sys.exit(1)

# Analyze strikes
call_strikes = []
put_strikes = []

for item in response['data']:
    strike = item.get('strike_price')
    if not strike:
        continue
    
    if 'call_options' in item:
        call_data = item['call_options'].get('market_data', {})
        if call_data.get('ltp', 0) > 0:
            call_strikes.append(strike)
    
    if 'put_options' in item:
        put_data = item['put_options'].get('market_data', {})
        if put_data.get('ltp', 0) > 0:
            put_strikes.append(strike)

call_strikes.sort()
put_strikes.sort()

print(f"\n=== UPSTOX OPTION CHAIN ANALYSIS ===")
print(f"Spot Price: {spot_price}")
print(f"Total strikes returned: {len(response['data'])}")
print(f"\nCALL strikes with LTP > 0: {len(call_strikes)}")
if call_strikes:
    print(f"  Range: {call_strikes[0]} to {call_strikes[-1]}")
    print(f"  Nearest to ATM: {min(call_strikes, key=lambda x: abs(x-spot_price))}")
    
print(f"\nPUT strikes with LTP > 0: {len(put_strikes)}")
if put_strikes:
    print(f"  Range: {put_strikes[0]} to {put_strikes[-1]}")
    print(f"  Nearest to ATM: {min(put_strikes, key=lambda x: abs(x-spot_price))}")

# Check for specific strike
target_strike = 25850
print(f"\n=== CHECKING FOR {target_strike} STRIKE ===")
found = False
for item in response['data']:
    if item.get('strike_price') == target_strike:
        found = True
        print(f"✅ Found {target_strike} strike!")
        if 'put_options' in item:
            put_data = item['put_options'].get('market_data', {})
            print(f"  PUT LTP: {put_data.get('ltp', 0)}")
            print(f"  PUT OI: {put_data.get('oi', 0)}")
            print(f"  PUT Volume: {put_data.get('volume', 0)}")
        break

if not found:
    print(f"❌ {target_strike} strike NOT in Upstox response")
    print(f"\nStrikes near {target_strike}:")
    nearby = [s for s in put_strikes if abs(s - target_strike) < 200]
    print(f"  {nearby if nearby else 'None within 200 points'}")
