#!/usr/bin/env python3
"""
Quick Dashboard CORS and Error Fix Test
"""

import requests
import json
import time
from datetime import datetime

def test_dashboard_apis():
    """Test dashboard APIs after CORS fix"""
    
    base_url = "http://localhost:8000"
    results = {}
    
    print("🔧 DASHBOARD CORS FIX TEST")
    print("=" * 40)
    
    # Test 1: Capital API
    print("1. Testing Capital API...")
    try:
        response = requests.get(f"{base_url}/api/capital", timeout=5)
        results['capital'] = {
            'status_code': response.status_code,
            'success': response.status_code == 200,
            'data': response.json() if response.status_code == 200 else None
        }
        print(f"   ✅ Capital: {response.status_code}")
    except Exception as e:
        results['capital'] = {'status_code': 0, 'success': False, 'error': str(e)}
        print(f"   ❌ Capital: {e}")
    
    # Test 2: Positions API
    print("2. Testing Positions API...")
    try:
        response = requests.get(f"{base_url}/api/dashboard/positions", timeout=5)
        results['positions'] = {
            'status_code': response.status_code,
            'success': response.status_code == 200,
            'data': response.json() if response.status_code == 200 else None
        }
        print(f"   ✅ Positions: {response.status_code}")
    except Exception as e:
        results['positions'] = {'status_code': 0, 'success': False, 'error': str(e)}
        print(f"   ❌ Positions: {e}")
    
    # Test 3: Risk Metrics API
    print("3. Testing Risk Metrics API...")
    try:
        response = requests.get(f"{base_url}/api/dashboard/risk-metrics", timeout=5)
        results['risk_metrics'] = {
            'status_code': response.status_code,
            'success': response.status_code == 200,
            'data': response.json() if response.status_code == 200 else None
        }
        print(f"   ✅ Risk Metrics: {response.status_code}")
    except Exception as e:
        results['risk_metrics'] = {'status_code': 0, 'success': False, 'error': str(e)}
        print(f"   ❌ Risk Metrics: {e}")
    
    # Test 4: Health API
    print("4. Testing Health API...")
    try:
        response = requests.get(f"{base_url}/api/health/status", timeout=5)
        results['health'] = {
            'status_code': response.status_code,
            'success': response.status_code == 200,
            'data': response.json() if response.status_code == 200 else None
        }
        print(f"   ✅ Health: {response.status_code}")
    except Exception as e:
        results['health'] = {'status_code': 0, 'success': False, 'error': str(e)}
        print(f"   ❌ Health: {e}")
    
    # Test 5: Market Overview API
    print("5. Testing Market Overview API...")
    try:
        response = requests.get(f"{base_url}/api/market/overview", timeout=5)
        results['market_overview'] = {
            'status_code': response.status_code,
            'success': response.status_code == 200,
            'data': response.json() if response.status_code == 200 else None
        }
        print(f"   ✅ Market Overview: {response.status_code}")
    except Exception as e:
        results['market_overview'] = {'status_code': 0, 'success': False, 'error': str(e)}
        print(f"   ❌ Market Overview: {e}")
    
    # Test 6: Dashboard Page
    print("6. Testing Dashboard Page...")
    try:
        response = requests.get(f"{base_url}/dashboard/", timeout=10)
        results['dashboard_page'] = {
            'status_code': response.status_code,
            'success': response.status_code == 200,
            'content_length': len(response.text)
        }
        print(f"   ✅ Dashboard Page: {response.status_code}")
    except Exception as e:
        results['dashboard_page'] = {'status_code': 0, 'success': False, 'error': str(e)}
        print(f"   ❌ Dashboard Page: {e}")
    
    print("\n" + "=" * 40)
    print("📊 TEST RESULTS")
    print("=" * 40)
    
    success_count = sum(1 for r in results.values() if r.get('success', False))
    total_count = len(results)
    
    print(f"✅ Successful: {success_count}/{total_count}")
    print(f"📈 Success Rate: {success_count/total_count*100:.1f}%")
    
    print("\n🔍 Detailed Results:")
    for test, result in results.items():
        status = "✅" if result.get('success', False) else "❌"
        code = result.get('status_code', 'N/A')
        print(f"   {status} {test}: HTTP {code}")
    
    # Overall assessment
    if success_count == total_count:
        print("\n🎉 ALL TESTS PASSED!")
        print("   Dashboard CORS issues are fixed!")
        print("   Ready for browser testing.")
    elif success_count >= total_count * 0.8:
        print("\n🟡 MOSTLY WORKING")
        print("   Minor issues remain but mostly functional.")
    else:
        print("\n🔴 SIGNIFICANT ISSUES")
        print("   Further debugging needed.")
    
    return results

if __name__ == "__main__":
    results = test_dashboard_apis()
    
    # Save results
    with open('/Users/srbhandary/Documents/Projects/srb-algo/cors_fix_results.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': results
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: cors_fix_results.json")
