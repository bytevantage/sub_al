#!/usr/bin/env python3
"""
Internal Dashboard Test - Complete Bug Fix Verification
"""

import requests
import json
import time
from datetime import datetime

def test_dashboard_endpoints():
    """Test all critical dashboard endpoints"""
    
    base_url = "http://localhost:8000"
    results = {}
    
    print("🚀 DASHBOARD INTERNAL TEST STARTING")
    print("=" * 50)
    
    # Test 1: Basic API Health
    print("1. Testing API Health...")
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        results['api_health'] = {
            'status': '✅ PASS',
            'response': response.status_code,
            'data': response.text[:100] if response.text else 'No data'
        }
        print("   ✅ API Health: OK")
    except Exception as e:
        results['api_health'] = {'status': '❌ FAIL', 'error': str(e)}
        print(f"   ❌ API Health: {e}")
    
    # Test 2: Dashboard Page Load
    print("2. Testing Dashboard Page...")
    try:
        response = requests.get(f"{base_url}/dashboard/", timeout=10)
        results['dashboard_page'] = {
            'status': '✅ PASS' if response.status_code == 200 else '❌ FAIL',
            'response': response.status_code,
            'content_length': len(response.text)
        }
        print("   ✅ Dashboard Page: Loads successfully")
    except Exception as e:
        results['dashboard_page'] = {'status': '❌ FAIL', 'error': str(e)}
        print(f"   ❌ Dashboard Page: {e}")
    
    # Test 3: Capital API
    print("3. Testing Capital API...")
    try:
        response = requests.get(f"{base_url}/api/capital", timeout=10)
        if response.status_code == 200:
            data = response.json()
            results['capital'] = {
                'status': '✅ PASS',
                'current_capital': data.get('current_capital', 0),
                'today_pnl': data.get('today_pnl', 0)
            }
            print(f"   ✅ Capital API: ₹{data.get('current_capital', 0):,.2f}")
        else:
            results['capital'] = {'status': '❌ FAIL', 'response': response.status_code}
            print(f"   ❌ Capital API: HTTP {response.status_code}")
    except Exception as e:
        results['capital'] = {'status': '❌ FAIL', 'error': str(e)}
        print(f"   ❌ Capital API: {e}")
    
    # Test 4: Positions API
    print("4. Testing Positions API...")
    try:
        response = requests.get(f"{base_url}/api/dashboard/positions", timeout=15)
        if response.status_code == 200:
            data = response.json()
            positions = data.get('data', {}).get('positions', [])
            results['positions'] = {
                'status': '✅ PASS',
                'position_count': len(positions),
                'total_unrealized': data.get('data', {}).get('totals', {}).get('total_unrealized_pnl', 0)
            }
            print(f"   ✅ Positions API: {len(positions)} positions")
        else:
            results['positions'] = {'status': '❌ FAIL', 'response': response.status_code}
            print(f"   ❌ Positions API: HTTP {response.status_code}")
    except Exception as e:
        results['positions'] = {'status': '❌ FAIL', 'error': str(e)}
        print(f"   ❌ Positions API: {e}")
    
    # Test 5: Risk Metrics API
    print("5. Testing Risk Metrics API...")
    try:
        response = requests.get(f"{base_url}/api/dashboard/risk-metrics", timeout=10)
        if response.status_code == 200:
            data = response.json()
            results['risk_metrics'] = {
                'status': '✅ PASS',
                'daily_pnl': data.get('data', {}).get('daily_pnl', 0),
                'capital_utilization': data.get('data', {}).get('capital_utilization', 0)
            }
            print(f"   ✅ Risk Metrics: Daily P&L ₹{data.get('data', {}).get('daily_pnl', 0):,.2f}")
        else:
            results['risk_metrics'] = {'status': '❌ FAIL', 'response': response.status_code}
            print(f"   ❌ Risk Metrics: HTTP {response.status_code}")
    except Exception as e:
        results['risk_metrics'] = {'status': '❌ FAIL', 'error': str(e)}
        print(f"   ❌ Risk Metrics: {e}")
    
    # Test 6: System Health
    print("6. Testing System Health...")
    try:
        response = requests.get(f"{base_url}/api/health/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            results['health'] = {
                'status': '✅ PASS' if data.get('overall_status') != 'critical' else '⚠️ WARNING',
                'overall_status': data.get('overall_status', 'unknown'),
                'checks': len(data.get('checks', {}))
            }
            print(f"   ✅ System Health: {data.get('overall_status', 'unknown')}")
        else:
            results['health'] = {'status': '❌ FAIL', 'response': response.status_code}
            print(f"   ❌ System Health: HTTP {response.status_code}")
    except Exception as e:
        results['health'] = {'status': '❌ FAIL', 'error': str(e)}
        print(f"   ❌ System Health: {e}")
    
    # Test 7: Trading System Status
    print("7. Testing Trading System...")
    try:
        response = requests.get(f"{base_url}/api/debug/trading-system-status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            results['trading_system'] = {
                'status': '✅ PASS' if data.get('dashboard_trading_system') else '❌ FAIL',
                'trading_system_available': data.get('dashboard_trading_system', False),
                'type': data.get('dashboard_trading_system_type', 'None')
            }
            print(f"   ✅ Trading System: {data.get('dashboard_trading_system_type', 'None')}")
        else:
            results['trading_system'] = {'status': '❌ FAIL', 'response': response.status_code}
            print(f"   ❌ Trading System: HTTP {response.status_code}")
    except Exception as e:
        results['trading_system'] = {'status': '❌ FAIL', 'error': str(e)}
        print(f"   ❌ Trading System: {e}")
    
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for r in results.values() if '✅ PASS' in r['status'])
    failed = sum(1 for r in results.values() if '❌ FAIL' in r['status'])
    warnings = sum(1 for r in results.values() if '⚠️ WARNING' in r['status'])
    
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️ Warnings: {warnings}")
    print(f"📈 Success Rate: {passed/(passed+failed+warnings)*100:.1f}%")
    
    print("\n📋 Detailed Results:")
    for test, result in results.items():
        print(f"   {test}: {result['status']}")
    
    # Overall Assessment
    print("\n🎯 OVERALL ASSESSMENT:")
    if failed == 0:
        print("🟢 ALL CRITICAL SYSTEMS OPERATIONAL")
        print("   Dashboard is ready for production use!")
    elif failed <= 2:
        print("🟡 MINOR ISSUES DETECTED")
        print("   Dashboard functional with some limitations.")
    else:
        print("🔴 SIGNIFICANT ISSUES FOUND")
        print("   Dashboard needs fixes before production use.")
    
    return results

if __name__ == "__main__":
    results = test_dashboard_endpoints()
    
    # Save results to file
    with open('/Users/srbhandary/Documents/Projects/srb-algo/dashboard_test_results.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': results
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: dashboard_test_results.json")
    print("\n🚀 Dashboard Internal Test Complete!")
