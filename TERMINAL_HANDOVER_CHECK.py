#!/usr/bin/env python3
"""
Terminal Handover Check
Verifies dashboard status for final handover
"""

import subprocess
import json
import time
from datetime import datetime

def run_command(cmd, timeout=10):
    """Run command and return result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", 1
    except Exception as e:
        return "", str(e), 1

def check_docker_status():
    """Check Docker container status"""
    print("🐳 DOCKER CONTAINER STATUS:")
    stdout, stderr, code = run_command("docker ps | grep trading_engine")
    if code == 0 and stdout:
        print(f"  ✅ Trading Engine Container: RUNNING")
        print(f"  📋 Container Info: {stdout}")
    else:
        print(f"  ❌ Trading Engine Container: ISSUE")
        print(f"  📋 Error: {stderr}")
    
def check_server_health():
    """Check server health endpoints"""
    print("\n🏥 SERVER HEALTH CHECK:")
    
    endpoints = [
        ("Basic Health", "curl -s -m 3 http://localhost:8000/health"),
        ("Capital API", "curl -s -m 5 http://localhost:8000/api/capital"),
        ("Market Overview", "curl -s -m 5 http://localhost:8000/api/market/overview"),
        ("Dashboard Positions", "curl -s -m 5 http://localhost:8000/api/dashboard/positions"),
    ]
    
    for name, cmd in endpoints:
        stdout, stderr, code = run_command(cmd)
        if code == 0 and stdout:
            try:
                # Try to parse as JSON
                data = json.loads(stdout)
                print(f"  ✅ {name}: OK (JSON response)")
                if "starting_capital" in str(data):
                    print(f"     💰 Capital: {data.get('starting_capital', 'N/A')}")
            except:
                print(f"  ✅ {name}: OK (text response)")
                print(f"     📄 Preview: {stdout[:50]}...")
        else:
            print(f"  ❌ {name}: FAILED")
            print(f"     📋 Error: {stderr[:50]}...")

def check_trading_activity():
    """Check recent trading activity"""
    print("\n📈 TRADING ACTIVITY CHECK:")
    
    stdout, stderr, code = run_command("docker logs trading_engine --tail 10 | grep -E '(INFO|ERROR)'")
    if code == 0 and stdout:
        lines = stdout.strip().split('\n')
        info_lines = [line for line in lines if 'INFO' in line]
        error_lines = [line for line in lines if 'ERROR' in line]
        
        print(f"  📊 Recent Activity: {len(lines)} log entries")
        print(f"  ✅ Info Messages: {len(info_lines)}")
        print(f"  ⚠️  Error Messages: {len(error_lines)}")
        
        if info_lines:
            latest_info = info_lines[-1]
            print(f"  📋 Latest: {latest_info[:80]}...")
            
        if error_lines:
            latest_error = error_lines[-1]
            print(f"  🚨 Latest Error: {latest_error[:80]}...")
    else:
        print(f"  ❌ Could not fetch logs")

def check_network_status():
    """Check network connectivity"""
    print("\n🌐 NETWORK STATUS:")
    
    stdout, stderr, code = run_command("netstat -an | grep 8000 | grep LISTEN")
    if code == 0 and stdout:
        print(f"  ✅ Port 8000: LISTENING")
        connections = stdout.strip().split('\n')
        print(f"  📊 Active Connections: {len(connections)}")
    else:
        print(f"  ❌ Port 8000: NOT LISTENING")

def check_dashboard_files():
    """Check dashboard files exist"""
    print("\n📁 DASHBOARD FILES CHECK:")
    
    import os
    dashboard_path = "/Users/srbhandary/Documents/Projects/srb-algo/frontend/dashboard"
    
    if os.path.exists(dashboard_path):
        print(f"  ✅ Dashboard Directory: EXISTS")
        
        files = ["index.html", "dashboard.js", "paper_trading_status.js"]
        for file in files:
            file_path = os.path.join(dashboard_path, file)
            if os.path.exists(file_path):
                print(f"  ✅ {file}: EXISTS")
            else:
                print(f"  ❌ {file}: MISSING")
    else:
        print(f"  ❌ Dashboard Directory: MISSING")

def main():
    """Run comprehensive handover check"""
    print(f"🔍 DASHBOARD HANDOVER CHECK")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    check_docker_status()
    check_server_health()
    check_trading_activity()
    check_network_status()
    check_dashboard_files()
    
    print("\n" + "=" * 60)
    print("🎯 HANDOVER SUMMARY:")
    print("🚀 Dashboard URL: http://localhost:8000/dashboard/")
    print("📊 Server should be running and responding")
    print("✅ All core APIs should be functional")
    print("🔧 Console should be clean of CORS errors")

if __name__ == "__main__":
    main()
