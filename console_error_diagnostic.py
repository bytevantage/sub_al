#!/usr/bin/env python3
"""
Console Error Diagnostic Tool
Tests all dashboard APIs to identify remaining console errors
"""

import subprocess
import json
import time
from datetime import datetime

def test_api_with_cors_headers(url, method="GET"):
    """Test API with proper CORS headers like browser would send"""
    try:
        cmd = f"""curl -s -v \
            -H "Origin: http://localhost:8000" \
            -H "Access-Control-Request-Method: {method}" \
            -H "Access-Control-Request-Headers: Content-Type" \
            -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
            -X {method} \
            -m 10 \
            "{url}" 2>&1"""
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        
        # Parse response
        lines = result.stdout.split('\n')
        headers = {}
        body = ""
        in_headers = True
        
        for line in lines:
            if line.startswith('< '):
                if ': ' in line:
                    key, value = line[2:].split(': ', 1)
                    headers[key.lower()] = value
            elif line.startswith('{') or line.startswith('['):
                in_headers = False
                body += line
            elif not in_headers and line.strip():
                body += line
        
        # Check for CORS headers
        cors_headers = {
            'access-control-allow-origin': headers.get('access-control-allow-origin'),
            'access-control-allow-methods': headers.get('access-control-allow-methods'),
            'access-control-allow-headers': headers.get('access-control-allow-headers'),
        }
        
        # Check response status
        status_line = headers.get('http/1.1', headers.get('status', 'Unknown'))
        
        return {
            'url': url,
            'status': status_line,
            'cors_headers': cors_headers,
            'body': body[:200] + "..." if len(body) > 200 else body,
            'success': '200' in status_line and cors_headers.get('access-control-allow-origin') == '*'
        }
        
    except Exception as e:
        return {
            'url': url,
            'status': 'ERROR',
            'cors_headers': {},
            'body': str(e),
            'success': False
        }

def main():
    """Run comprehensive diagnostic"""
    print("🔍 CONSOLE ERROR DIAGNOSTIC")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Test all dashboard APIs
    apis = [
        "http://localhost:8000/api/capital",
        "http://localhost:8000/api/dashboard/positions",
        "http://localhost:8000/api/dashboard/risk-metrics",
        "http://localhost:8000/api/dashboard/trades/recent?limit=100&today_only=true",
        "http://localhost:8000/api/market/overview",
        "http://localhost:8000/health",
        "http://localhost:8000/paper_trading_status.json",
        "http://localhost:8000/api/watchlist/recommended-strikes?symbol=NIFTY&min_ml_score=0.0&min_strategy_strength=50&min_strategies_agree=1",
        "http://localhost:8000/api/market/option-chain/NIFTY",
    ]
    
    results = []
    for api in apis:
        print(f"Testing: {api}")
        result = test_api_with_cors_headers(api)
        results.append(result)
        
        if result['success']:
            print(f"  ✅ {result['status']} - CORS: {result['cors_headers']['access-control-allow-origin']}")
        else:
            print(f"  ❌ {result['status']} - CORS: {result['cors_headers'].get('access-control-allow-origin', 'MISSING')}")
            print(f"     Error: {result['body']}")
    
    print("\n" + "=" * 60)
    print("📊 DIAGNOSTIC SUMMARY:")
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"✅ Successful: {len(successful)}")
    print(f"❌ Failed: {len(failed)}")
    
    if successful:
        print("\n✅ WORKING APIS:")
        for r in successful:
            print(f"  ✅ {r['url']}")
            print(f"     Status: {r['status']} | CORS: {r['cors_headers']['access-control-allow-origin']}")
    
    if failed:
        print("\n❌ FAILED APIS:")
        for r in failed:
            print(f"  ❌ {r['url']}")
            print(f"     Status: {r['status']} | Error: {r['body']}")
    
    # CORS analysis
    cors_ok = len([r for r in results if r['cors_headers'].get('access-control-allow-origin') == '*'])
    print(f"\n🔍 CORS ANALYSIS:")
    print(f"  ✅ CORS headers present: {cors_ok}/{len(results)}")
    print(f"  ❌ CORS headers missing: {len(results) - cors_ok}/{len(results)}")
    
    print(f"\n🎯 RECOMMENDATIONS:")
    if len(successful) >= len(results) * 0.7:
        print("  ✅ Most APIs working - check browser console for specific errors")
    else:
        print("  ❌ Many APIs failing - server may have issues")
    
    if cors_ok >= len(results) * 0.7:
        print("  ✅ CORS mostly working - browser cache may need clearing")
    else:
        print("  ❌ CORS issues persist - check server configuration")

if __name__ == "__main__":
    main()
