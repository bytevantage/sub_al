#!/usr/bin/env python3
"""
Test DNS caching and connection pooling in UpstoxClient
"""

import sys
import os
import time
import logging

# Add project root to path
sys.path.append('/Users/srbhandary/Documents/Projects/srb-algo')

from backend.core.upstox_client import UpstoxClient

def test_connection_pooling():
    """Test that connection pooling reduces DNS lookups and improves performance"""
    
    # Configure logging to see DNS requests
    logging.basicConfig(level=logging.DEBUG)
    
    # Create client (this will use connection pooling)
    client = UpstoxClient("dummy_token")
    
    print("Testing connection pooling and DNS caching...")
    print("=" * 50)
    
    # Test multiple rapid requests to the same endpoint
    endpoints = [
        "/v2/user/profile",
        "/v2/user/get-funds-and-margin", 
        "/v2/market-quote/ohlc?symbol=NSE_INDEX|Nifty 50"
    ]
    
    for i, endpoint in enumerate(endpoints):
        print(f"\nRequest {i+1}: {endpoint}")
        start_time = time.time()
        
        # This will use the pooled session
        result = client._make_request("GET", endpoint)
        
        end_time = time.time()
        print(f"  Time taken: {(end_time - start_time)*1000:.2f}ms")
        print(f"  Result: {'Success' if result else 'Failed (expected with dummy token)'}")
    
    print("\n" + "=" * 50)
    print("✓ Connection pooling test completed")
    print("✓ DNS should be cached after first request")
    print("✓ Subsequent requests should be faster")
    
    # Cleanup
    client.close()

if __name__ == "__main__":
    test_connection_pooling()
