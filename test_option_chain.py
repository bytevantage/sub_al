#!/usr/bin/env python3
"""Test Upstox option chain API to see actual response structure"""

import json
import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from core.upstox_client import UpstoxClient

def main():
    print("Testing Upstox Option Chain API...")
    
    # Load token
    token_path = os.path.expanduser("~/Algo/upstoxtoken.json")
    with open(token_path, 'r') as f:
        token_data = json.load(f)
        access_token = token_data.get('access_token')
    
    # Initialize client
    client = UpstoxClient(access_token=access_token)
    
    # Get available option contracts first
    print("\n1. Getting available NIFTY option contracts...")
    print("-" * 60)
    contracts = client.get_option_contracts("NIFTY", "NSE_INDEX|Nifty 50")
    
    if contracts and 'data' in contracts:
        # Extract unique expiries
        expiries = sorted(set(contract.get('expiry') for contract in contracts['data'] if contract.get('expiry')))
        print(f"✓ Available expiries (showing first 10):")
        for exp in expiries[:10]:
            # Parse to see which are weekly
            exp_date = datetime.strptime(exp, '%Y-%m-%d')
            is_tuesday = exp_date.weekday() == 1
            marker = " <- WEEKLY (Tuesday)" if is_tuesday else ""
            print(f"  - {exp}{marker}")
        
        # Use first Tuesday expiry (NIFTY weekly)
        tuesday_expiries = [exp for exp in expiries if datetime.strptime(exp, '%Y-%m-%d').weekday() == 1]
        
        if len(tuesday_expiries) > 0:
            first_tuesday = tuesday_expiries[0]
            print(f"\n2. Testing option chain for expiry: {first_tuesday} (NIFTY weekly)")
            print("-" * 60)
            
            response = client.get_option_chain("NSE_INDEX|Nifty 50", first_tuesday)
            
            if response and 'data' in response:
                data = response['data']
                print(f"\n✓ Got response with {len(data)} strikes\n")
                
                # Show first 2 strikes to see structure
                for i, item in enumerate(data[:2]):
                    print(f"Strike {i+1}:")
                    print(json.dumps(item, indent=2))
                    print()
            else:
                print(f"✗ API Error: {response}")
    else:
        print(f"✗ Failed to get contracts: {contracts}")

if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
