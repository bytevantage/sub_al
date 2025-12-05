#!/usr/bin/env python3
"""
Complete CORS and API Test
Tests all dashboard endpoints to verify CORS fixes and error handling
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

# List of all dashboard API endpoints
ENDPOINTS = [
    "http://localhost:8000/api/capital",
    "http://localhost:8000/api/dashboard/positions", 
    "http://localhost:8000/api/dashboard/risk-metrics",
    "http://localhost:8000/api/dashboard/trades/recent?limit=100&today_only=true",
    "http://localhost:8000/api/market/overview",
    "http://localhost:8000/api/health",
    "http://localhost:8000/api/health/db",
    "http://localhost:8000/paper_trading_status.json",
    "http://localhost:8000/api/watchlist/recommended-strikes?symbol=NIFTY&min_ml_score=0.0&min_strategy_strength=50&min_strategies_agree=1",
    "http://localhost:8000/api/watchlist/recommended-strikes?symbol=SENSEX&min_ml_score=0.0&min_strategy_strength=50&min_strategies_agree=1",
    "http://localhost:8000/api/market/option-chain/NIFTY",
    "http://localhost:8000/api/market/option-chain/SENSEX",
]

async def test_endpoint(session, url, method="GET"):
    """Test a single endpoint with proper CORS headers"""
    start_time = time.time()
    try:
        # Simulate browser request with CORS headers
        headers = {
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "Content-Type",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        async with session.request(method, url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
            response_time = time.time() - start_time
            
            # Check CORS headers
            cors_headers = {
                "Access-Control-Allow-Origin": response.headers.get("Access-Control-Allow-Origin"),
                "Access-Control-Allow-Methods": response.headers.get("Access-Control-Allow-Methods"),
                "Access-Control-Allow-Headers": response.headers.get("Access-Control-Allow-Headers"),
                "Access-Control-Allow-Credentials": response.headers.get("Access-Control-Allow-Credentials"),
            }
            
            # Try to parse JSON response
            try:
                data = await response.json()
                content_type = "json"
                content_preview = json.dumps(data)[:100] + "..." if len(json.dumps(data)) > 100 else json.dumps(data)
            except:
                content_type = "text"
                content_preview = await response.text()
                content_preview = content_preview[:100] + "..." if len(content_preview) > 100 else content_preview
            
            return {
                "url": url,
                "status": response.status,
                "response_time": f"{response_time:.2f}s",
                "cors_headers": cors_headers,
                "content_type": content_type,
                "content_preview": content_preview,
                "success": response.status < 400
            }
            
    except asyncio.TimeoutError:
        return {
            "url": url,
            "status": "TIMEOUT",
            "response_time": f"{time.time() - start_time:.2f}s",
            "cors_headers": {},
            "content_type": "error",
            "content_preview": "Request timed out",
            "success": False
        }
    except Exception as e:
        return {
            "url": url,
            "status": "ERROR",
            "response_time": f"{time.time() - start_time:.2f}s",
            "cors_headers": {},
            "content_type": "error",
            "content_preview": str(e)[:100],
            "success": False
        }

async def main():
    """Run comprehensive CORS and API test"""
    print(f"🧪 Starting Comprehensive CORS & API Test at {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    # Create HTTP session
    connector = aiohttp.TCPConnector(limit=100, force_close=True)
    timeout = aiohttp.ClientTimeout(total=15)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # Test all endpoints concurrently
        tasks = [test_endpoint(session, url) for url in ENDPOINTS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Sort results by success status
        successful = [r for r in results if isinstance(r, dict) and r.get("success", False)]
        failed = [r for r in results if isinstance(r, dict) and not r.get("success", False)]
        
        # Print summary
        print(f"\n📊 SUMMARY: {len(successful)} successful, {len(failed)} failed")
        print("=" * 80)
        
        # Print successful endpoints
        if successful:
            print("\n✅ SUCCESSFUL ENDPOINTS:")
            for result in successful:
                print(f"  ✅ {result['url']}")
                print(f"     Status: {result['status']} | Time: {result['response_time']}")
                print(f"     CORS: {result['cors_headers']['Access-Control-Allow-Origin']}")
                print(f"     Content: {result['content_preview']}")
                print()
        
        # Print failed endpoints
        if failed:
            print("\n❌ FAILED ENDPOINTS:")
            for result in failed:
                print(f"  ❌ {result['url']}")
                print(f"     Status: {result['status']} | Time: {result['response_time']}")
                print(f"     Error: {result['content_preview']}")
                print()
        
        # CORS Analysis
        print("\n🔍 CORS ANALYSIS:")
        cors_ok = 0
        cors_missing = 0
        
        for result in results:
            if isinstance(result, dict):
                if result['cors_headers'].get('Access-Control-Allow-Origin'):
                    cors_ok += 1
                else:
                    cors_missing += 1
        
        print(f"  ✅ CORS headers present: {cors_ok}")
        print(f"  ❌ CORS headers missing: {cors_missing}")
        
        # Overall assessment
        print(f"\n🎯 OVERALL ASSESSMENT:")
        success_rate = len(successful) / len(ENDPOINTS) * 100
        print(f"  Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("  ✅ EXCELLENT - Dashboard should work well!")
        elif success_rate >= 60:
            print("  ⚠️  GOOD - Dashboard mostly functional")
        else:
            print("  ❌ NEEDS WORK - Dashboard will have issues")
        
        print(f"\n🚀 Dashboard URL: http://localhost:8000/dashboard/")
        print(f"📋 Test completed at {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    asyncio.run(main())
