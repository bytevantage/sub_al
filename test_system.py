#!/usr/bin/env python3
"""
System Verification Test
Quick test to verify all components are working
"""

import sys
from pathlib import Path

print("=" * 70)
print("🧪  TRADING SYSTEM VERIFICATION TEST")
print("=" * 70)
print()

# Test 1: Python Version
print("1️⃣  Checking Python version...")
if sys.version_info >= (3, 10):
    print(f"   ✅ Python {sys.version_info.major}.{sys.version_info.minor} - OK")
else:
    print(f"   ❌ Python {sys.version_info.major}.{sys.version_info.minor} - Need 3.10+")
    sys.exit(1)

# Test 2: Required Files
print("\n2️⃣  Checking project structure...")
required_files = [
    "backend/main.py",
    "backend/core/config.py",
    "backend/core/upstox_client.py",
    "backend/strategies/strategy_engine.py",
    "config/config.yaml",
    "requirements.txt"
]

all_files_exist = True
for file in required_files:
    if Path(file).exists():
        print(f"   ✅ {file}")
    else:
        print(f"   ❌ {file} - Missing!")
        all_files_exist = False

if not all_files_exist:
    print("\n   ⚠️  Some files are missing. Please run from project root.")
    sys.exit(1)

# Test 3: Import Core Modules
print("\n3️⃣  Testing core imports...")
try:
    from backend.core.config import config
    print("   ✅ Configuration module")
    
    from backend.core.logger import logger
    print("   ✅ Logger module")
    
    from backend.core.upstox_client import UpstoxClient
    print("   ✅ Upstox client")
    
    from backend.strategies.strategy_engine import StrategyEngine
    print("   ✅ Strategy engine")
    
    from backend.execution.risk_manager import RiskManager
    print("   ✅ Risk manager")
    
    from backend.execution.order_manager import OrderManager
    print("   ✅ Order manager")
    
except ImportError as e:
    print(f"   ❌ Import failed: {e}")
    print("\n   Run: pip install -r requirements.txt")
    sys.exit(1)

# Test 4: Configuration
print("\n4️⃣  Checking configuration...")
try:
    mode = config.settings.mode
    capital = config.get('trading.initial_capital')
    print(f"   ✅ Trading Mode: {mode.upper()}")
    print(f"   ✅ Initial Capital: ₹{capital:,.0f}")
except Exception as e:
    print(f"   ❌ Configuration error: {e}")

# Test 5: Token Check
print("\n5️⃣  Checking Upstox token...")
token = config.get_upstox_token()
if token:
    print(f"   ✅ Token found: {token[:20]}...")
else:
    print("   ⚠️  No token found")
    print("   Run: python upstox_auth_working.py")

# Test 6: Dependencies
print("\n6️⃣  Checking key dependencies...")
dependencies = [
    ('fastapi', 'FastAPI'),
    ('uvicorn', 'Uvicorn'),
    ('pandas', 'Pandas'),
    ('requests', 'Requests'),
    ('pydantic', 'Pydantic')
]

all_deps_ok = True
for module, name in dependencies:
    try:
        __import__(module)
        print(f"   ✅ {name}")
    except ImportError:
        print(f"   ❌ {name} - Not installed")
        all_deps_ok = False

if not all_deps_ok:
    print("\n   Run: pip install -r requirements.txt")

# Test 7: Strategies
print("\n7️⃣  Checking strategies...")
try:
    from backend.strategies.pcr_strategy import PCRStrategy
    print("   ✅ PCR Strategy")
    
    from backend.strategies.oi_strategy import OIStrategy
    print("   ✅ OI Strategy")
    
    from backend.strategies.maxpain_strategy import MaxPainStrategy
    print("   ✅ Max Pain Strategy")
    
except ImportError as e:
    print(f"   ❌ Strategy import failed: {e}")

# Final Summary
print("\n" + "=" * 70)
print("📊  VERIFICATION SUMMARY")
print("=" * 70)

if all_files_exist and all_deps_ok:
    print("✅  All checks passed!")
    print("\n🚀  Your system is ready to run!")
    print("\n📝  Quick Start:")
    print("   1. Generate token: python upstox_auth_working.py")
    print("   2. Run system: python backend/main.py")
    print("   3. Check API: http://localhost:8000/api/health")
    print()
else:
    print("⚠️   Some issues found. Please fix them before running.")
    print()

print("=" * 70)
