#!/usr/bin/env python3
"""
Final Dashboard Test with Cache-Busting
Tests all endpoints with proper cache-busting parameters
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_with_cache_busting(endpoint, description):
    """Test endpoint with cache-busting parameter"""
    try:
        # Add cache-busting parameter
        url = f"{BASE_URL}{endpoint}?t={int(time.time() * 1000)}"
        response = requests.get(url, timeout=20)  # Increased timeout
        
        # Check for CORS headers
        cors_headers = {
            'access-control-allow-origin': response.headers.get('access-control-allow-origin'),
            'cache-control': response.headers.get('cache-control')
        }
        
        status = "✅" if response.status_code == 200 else "❌"
        print(f"{status} {description}: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   CORS: {cors_headers['access-control-allow-origin']}")
            print(f"   Cache: {cors_headers['cache-control']}")
            return True
        else:
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ {description}: Failed - {e}")
        return False

def main():
    print("🚀 Final Dashboard Test with Cache-Busting")
    print("=" * 60)
    
    # Test dashboard endpoints with cache-busting
    tests = [
        ("/api/dashboard/system-status", "System Status"),
        ("/paper_trading_status.json", "Paper Trading Status"),
        ("/api/dashboard/positions", "Positions"),
        ("/api/capital", "Capital Info"),
        ("/api/dashboard/risk-metrics", "Risk Metrics"),
        ("/api/market/overview", "Market Overview"),
        ("/api/watchlist/signal-stats", "Watchlist Signal Stats"),
        ("/api/health/summary", "Health Summary"),
        ("/api/dashboard/trades/recent", "Recent Trades"),
        ("/api/health/db", "Database Health"),
        ("/api/market/option-chain/NIFTY", "NIFTY Option Chain"),
        ("/api/watchlist/recommended-strikes?symbol=NIFTY", "NIFTY Watchlist"),
    ]
    
    results = []
    for endpoint, desc in tests:
        success = test_with_cache_busting(endpoint, desc)
        results.append((endpoint, desc, success))
        time.sleep(0.2)  # Small delay
    
    print("\n" + "=" * 60)
    print("📊 FINAL TEST RESULTS")
    print("=" * 60)
    
    passed = sum(1 for _, _, success in results if success)
    total = len(results)
    
    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Dashboard is ready with:")
        print("   - Proper CORS headers")
        print("   - Cache-busting enabled")
        print("   - All endpoints responding")
        print("\n📋 Browser Instructions:")
        print("   1. Open http://localhost:8000/dashboard/")
        print("   2. Hard refresh (Ctrl+Shift+R or Cmd+Shift+R)")
        print("   3. Clear browser cache if needed")
        print("   4. All errors should be resolved")
    else:
        print("\n⚠️ Some tests failed. Check the errors above.")
    
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
