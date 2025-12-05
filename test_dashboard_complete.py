#!/usr/bin/env python3
"""
Complete Dashboard Test Suite
Tests all API endpoints that the dashboard uses
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_endpoint(endpoint, description):
    """Test a single endpoint"""
    try:
        response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)  # Increased timeout
        status = "✅" if response.status_code == 200 else "❌"
        print(f"{status} {description}: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                return True, data
            except:
                return True, response.text
        else:
            print(f"   Error: {response.text}")
            return False, None
    except Exception as e:
        print(f"❌ {description}: Failed - {e}")
        return False, None

def main():
    print("🚀 Testing Complete Dashboard API Suite")
    print("=" * 50)
    
    # Test all dashboard endpoints
    tests = [
        ("/api/dashboard/system-status", "System Status"),
        ("/paper_trading_status.json", "Paper Trading Status"),
        ("/api/dashboard/positions", "Positions"),
        ("/api/capital", "Capital Info"),
        ("/api/dashboard/risk-metrics", "Risk Metrics"),
        ("/api/market/overview", "Market Overview"),
        ("/api/watchlist/signal-stats", "Watchlist Signal Stats"),
        ("/api/health/summary", "Health Summary"),
        ("/api/dashboard/trades/recent?limit=10&today_only=true", "Recent Trades"),
        ("/api/health/db", "Database Health"),
    ]
    
    results = []
    for endpoint, desc in tests:
        success, data = test_endpoint(endpoint, desc)
        results.append((endpoint, desc, success))
        time.sleep(0.1)  # Small delay between requests
    
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, _, success in results if success)
    total = len(results)
    
    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Dashboard is ready!")
    else:
        print("\n⚠️ Some tests failed. Check the errors above.")
    
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
