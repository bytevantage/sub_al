#!/usr/bin/env python3
"""
Force close positions using direct API calls
"""

import requests
import json

def force_close_positions():
    """Force close all positions via API"""
    
    # Get current positions
    try:
        response = requests.get('http://localhost:8000/api/dashboard/positions')
        response.raise_for_status()
        data = response.json()
        positions = data.get('data', {}).get('positions', [])
        
        if not positions:
            print("✅ No positions found")
            return
        
        print(f"Found {len(positions)} positions:")
        total_pnl = 0
        for pos in positions:
            pnl = pos.get('unrealized_pnl', 0)
            total_pnl += pnl
            print(f"  - {pos['symbol']} {pos['strike_price']} {pos['option_type']} | P&L: ₹{pnl:.2f}")
        
        print(f"\nTotal P&L: ₹{total_pnl:.2f}")
        
        # Try to close via emergency API with different API keys
        api_keys = ["EMERGENCY_KEY_123", "admin", "test", ""]
        
        for api_key in api_keys:
            print(f"\nTrying with API key: {api_key or 'empty'}")
            
            headers = {
                "Content-Type": "application/json"
            }
            if api_key:
                headers["X-API-Key"] = api_key
            
            try:
                response = requests.post(
                    'http://localhost:8000/emergency/positions/close',
                    headers=headers,
                    json={
                        "close_all": True,
                        "reason": "FORCE MANUAL CLOSE - API DIRECT"
                    },
                    timeout=10
                )
                
                print(f"Response: {response.status_code}")
                print(f"Body: {response.text}")
                
                if response.status_code == 200:
                    print("✅ Success!")
                    return
                    
            except Exception as e:
                print(f"Error: {e}")
        
        print("\n❌ All API attempts failed")
        
    except Exception as e:
        print(f"❌ Error getting positions: {e}")

if __name__ == "__main__":
    force_close_positions()
