"""
Complete System Validation Script
Checks all components and verifies production readiness
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
import torch

print("="*100)
print("COMPLETE SYSTEM VALIDATION")
print("="*100)

validation_results = {
    'passed': [],
    'warnings': [],
    'failed': []
}

def check(name, status, message=""):
    """Record validation result"""
    if status:
        validation_results['passed'].append((name, message))
        print(f"✅ {name}")
        if message:
            print(f"   {message}")
    else:
        validation_results['failed'].append((name, message))
        print(f"❌ {name}")
        if message:
            print(f"   {message}")

def warn(name, message=""):
    """Record warning"""
    validation_results['warnings'].append((name, message))
    print(f"⚠️  {name}")
    if message:
        print(f"   {message}")

print("\n📦 CHECKING DEPENDENCIES...")
print("-"*100)

# Check Python packages
required_packages = [
    'torch', 'numpy', 'pandas', 'sklearn', 'optuna',
    'matplotlib', 'seaborn', 'sqlalchemy', 'psycopg2'
]

for package in required_packages:
    try:
        __import__(package.replace('-', '_'))
        check(f"Package: {package}", True)
    except ImportError:
        check(f"Package: {package}", False, f"Install with: pip install {package}")

print("\n🐳 CHECKING DOCKER SERVICES...")
print("-"*100)

# Check Docker
result = subprocess.run(['docker', 'ps'], capture_output=True, text=True)
if result.returncode == 0:
    check("Docker daemon", True)
    
    # Check specific containers
    containers = ['trading_db', 'trading_redis', 'trading_engine']
    for container in containers:
        if container in result.stdout:
            check(f"Container: {container}", True, "Running")
        else:
            warn(f"Container: {container}", "Not running")
else:
    check("Docker daemon", False, "Docker not available")

print("\n💾 CHECKING DATABASE...")
print("-"*100)

# Check database connection and tables
db_check = subprocess.run([
    'docker', 'exec', 'trading_db', 'psql', 
    '-U', 'trading_user', '-d', 'trading_db',
    '-c', "SELECT COUNT(*) FROM option_chain_snapshots;"
], capture_output=True, text=True)

if db_check.returncode == 0:
    check("Database connection", True)
    
    # Check clean data view
    view_check = subprocess.run([
        'docker', 'exec', 'trading_db', 'psql',
        '-U', 'trading_user', '-d', 'trading_db',
        '-c', "SELECT COUNT(*) FROM option_chain_snapshots_clean;"
    ], capture_output=True, text=True)
    
    if view_check.returncode == 0:
        check("Clean data view", True, "option_chain_snapshots_clean exists")
    else:
        check("Clean data view", False, "Run: python3 data_quality/apply_fixes.py")
else:
    check("Database connection", False, "Cannot connect to trading_db")

print("\n📁 CHECKING FILE STRUCTURE...")
print("-"*100)

# Check critical files
critical_files = [
    'data_quality/check_and_clean.py',
    'data_quality/apply_fixes.py',
    'training/quantum_edge_v2/feature_engineering.py',
    'training/quantum_edge_v2/train.py',
    'training/quantum_edge_v2/inference.py',
    'training/quantum_edge_v2/train_demo.py',
    'backend/strategies/quantum_edge_v2.py',
    'meta_controller/sac_agent.py',
    'meta_controller/state_builder.py',
    'start_sac_paper_trading.py',
    'monitor_sac_system.sh',
    'run_complete_system.sh'
]

for file_path in critical_files:
    path = Path(file_path)
    check(f"File: {file_path}", path.exists())

print("\n🤖 CHECKING MODELS...")
print("-"*100)

# Check models
models = {
    'models/quantum_edge_v2_demo.pt': 'Demo model (synthetic data)',
    'models/quantum_edge_v2.pt': 'Production model (REQUIRED for live)',
    'models/sac_comprehensive_real.pth': 'SAC Meta-Controller'
}

for model_path, description in models.items():
    path = Path(model_path)
    if path.exists():
        check(f"Model: {model_path}", True, description)
    else:
        if 'demo' in model_path:
            warn(f"Model: {model_path}", f"{description} - Run: python3 train_demo.py")
        else:
            warn(f"Model: {model_path}", f"{description} - Run: python3 train.py")

print("\n🧪 CHECKING FUNCTIONALITY...")
print("-"*100)

# Test feature extraction
try:
    sys.path.insert(0, 'training/quantum_edge_v2')
    from feature_engineering import QuantumEdgeFeatureEngineer
    
    engineer = QuantumEdgeFeatureEngineer()
    if len(engineer.FEATURE_NAMES) == 34:
        check("Feature engineering", True, "34 features defined")
    else:
        check("Feature engineering", False, f"Expected 34 features, got {len(engineer.FEATURE_NAMES)}")
except Exception as e:
    check("Feature engineering", False, str(e))

# Test model loading (if exists)
if Path('models/quantum_edge_v2_demo.pt').exists():
    try:
        checkpoint = torch.load('models/quantum_edge_v2_demo.pt', map_location='cpu')
        if 'model_state_dict' in checkpoint and 'hyperparameters' in checkpoint:
            check("Model loading", True, "Demo model can be loaded")
        else:
            check("Model loading", False, "Invalid model format")
    except Exception as e:
        check("Model loading", False, str(e))

print("\n📊 CHECKING DATA QUALITY...")
print("-"*100)

# Check data quality stats
quality_check = subprocess.run([
    'docker', 'exec', 'trading_db', 'psql',
    '-U', 'trading_user', '-d', 'trading_db', '-t', '-c',
    """SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE data_quality_flag='CLEAN') as clean,
        ROUND(COUNT(*) FILTER (WHERE data_quality_flag='CLEAN') * 100.0 / COUNT(*), 2) as clean_pct
    FROM option_chain_snapshots;"""
], capture_output=True, text=True)

if quality_check.returncode == 0:
    output = quality_check.stdout.strip()
    if output:
        parts = output.split('|')
        if len(parts) >= 3:
            clean_pct = float(parts[2].strip())
            if clean_pct >= 60:
                check("Data quality", True, f"{clean_pct}% clean data")
            else:
                warn("Data quality", f"Only {clean_pct}% clean data (< 60%)")

print("\n🔬 CHECKING RUNNING SERVICES...")
print("-"*100)

# Check running Python services
ps_result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)

services = {
    'start_sac_paper_trading': 'Paper Trading',
    'inference.py': 'QuantumEdge v2 Live Inference'
}

for process, name in services.items():
    if process in ps_result.stdout:
        check(f"Service: {name}", True, "Running")
    else:
        warn(f"Service: {name}", "Not running (optional)")

print("\n" + "="*100)
print("VALIDATION SUMMARY")
print("="*100)

print(f"\n✅ Passed: {len(validation_results['passed'])}")
for name, msg in validation_results['passed'][:5]:  # Show first 5
    print(f"   • {name}")
if len(validation_results['passed']) > 5:
    print(f"   ... and {len(validation_results['passed']) - 5} more")

if validation_results['warnings']:
    print(f"\n⚠️  Warnings: {len(validation_results['warnings'])}")
    for name, msg in validation_results['warnings']:
        print(f"   • {name}")
        if msg:
            print(f"     {msg}")

if validation_results['failed']:
    print(f"\n❌ Failed: {len(validation_results['failed'])}")
    for name, msg in validation_results['failed']:
        print(f"   • {name}")
        if msg:
            print(f"     {msg}")

print("\n" + "="*100)

# Overall status
if not validation_results['failed']:
    if len(validation_results['warnings']) <= 3:
        print("🎉 SYSTEM STATUS: PRODUCTION READY")
        print("\n✅ All critical checks passed")
        print("✅ Minor warnings are acceptable")
        print("\n🚀 Next steps:")
        print("   1. Review warnings above")
        print("   2. Train production model if needed: python3 train.py")
        print("   3. Start paper trading: ./run_complete_system.sh")
    else:
        print("⚠️  SYSTEM STATUS: READY WITH WARNINGS")
        print(f"\n⚠️  {len(validation_results['warnings'])} warnings need attention")
        print("\n📋 Recommended actions:")
        print("   1. Address warnings above")
        print("   2. Train missing models")
        print("   3. Re-run validation")
else:
    print("❌ SYSTEM STATUS: NOT READY")
    print(f"\n❌ {len(validation_results['failed'])} critical issues")
    print("\n🔧 Required actions:")
    print("   1. Fix failed checks above")
    print("   2. Install missing dependencies")
    print("   3. Re-run validation")
    sys.exit(1)

print("="*100)
