#!/usr/bin/env python3
"""
Verify All Optimizations Are Applied
"""

import yaml
import json
import requests
from pathlib import Path


def verify_quantum_edge_boost():
    """Verify QuantumEdge allocation is 45%"""
    print("🔍 Verifying QuantumEdge boost...")
    
    config_path = Path('config/config.yaml')
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        quantum_weight = config.get('strategy_weights', {}).get('QuantumEdge', 0)
        if quantum_weight == 0.45:
            print(f"✅ QuantumEdge allocation: {quantum_weight * 100:.0f}%")
            return True
        else:
            print(f"❌ QuantumEdge allocation: {quantum_weight * 100:.0f}% (expected 45%)")
            return False
    else:
        print("❌ Config file not found")
        return False


def verify_pcr_reversal_boost():
    """Verify PCRReversal allocation is 15%"""
    print("🔍 Verifying PCRReversal boost...")
    
    config_path = Path('config/config.yaml')
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        pcr_weight = config.get('strategy_weights', {}).get('PCRReversal', 0)
        if pcr_weight == 0.15:
            print(f"✅ PCRReversal allocation: {pcr_weight * 100:.0f}%")
            return True
        else:
            print(f"❌ PCRReversal allocation: {pcr_weight * 100:.0f}% (expected 15%)")
            return False
    else:
        print("❌ Config file not found")
        return False


def verify_dynamic_sizing():
    """Verify dynamic sizing is configured"""
    print("🔍 Verifying dynamic sizing...")
    
    config_path = Path('config/dynamic_sizing.yaml')
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        if config.get('dynamic_sizing', {}).get('enabled', False):
            print("✅ Dynamic sizing is enabled")
            
            # Check confidence thresholds
            thresholds = config['dynamic_sizing'].get('confidence_thresholds', {})
            if '95-100%' in thresholds and thresholds['95-100%']['multiplier'] == 2.0:
                print("✅ High confidence multiplier (2x) configured")
                return True
            else:
                print("❌ High confidence multiplier not configured")
                return False
        else:
            print("❌ Dynamic sizing is not enabled")
            return False
    else:
        print("❌ Dynamic sizing config not found")
        return False


def verify_volatility_capture():
    """Verify volatility capture is configured"""
    print("🔍 Verifying volatility capture...")
    
    config_path = Path('config/volatility_capture.yaml')
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        if config.get('volatility_capture', {}).get('enabled', False):
            print("✅ Volatility capture is enabled")
            
            # Check IV threshold
            iv_threshold = config['volatility_capture'].get('iv_threshold', 0)
            if iv_threshold == 25.0:
                print(f"✅ IV threshold: {iv_threshold}%")
                return True
            else:
                print(f"❌ IV threshold: {iv_threshold}% (expected 25%)")
                return False
        else:
            print("❌ Volatility capture is not enabled")
            return False
    else:
        print("❌ Volatility capture config not found")
        return False


def verify_backend_running():
    """Verify backend is running"""
    print("🔍 Verifying backend status...")
    
    try:
        response = requests.get('http://localhost:8000/health', timeout=5)
        if response.status_code == 200:
            print("✅ Backend is running")
            return True
        else:
            print(f"❌ Backend returned status: {response.status_code}")
            return False
    except:
        print("❌ Backend is not accessible")
        return False


def verify_optimization_summary():
    """Verify optimization summary exists"""
    print("🔍 Verifying optimization summary...")
    
    summary_path = Path('optimization_summary.json')
    if summary_path.exists():
        with open(summary_path, 'r') as f:
            summary = json.load(f)
        
        expected_improvement = summary.get('total_expected_improvement', '')
        if '+40-55%' in expected_improvement:
            print(f"✅ Expected improvement: {expected_improvement}")
            return True
        else:
            print(f"❌ Expected improvement: {expected_improvement}")
            return False
    else:
        print("❌ Optimization summary not found")
        return False


def main():
    """Run all verifications"""
    print("="*80)
    print("VERIFYING ALL OPTIMIZATIONS")
    print("="*80)
    print()
    
    verifications = [
        ("QuantumEdge Boost", verify_quantum_edge_boost),
        ("PCRReversal Boost", verify_pcr_reversal_boost),
        ("Dynamic Sizing", verify_dynamic_sizing),
        ("Volatility Capture", verify_volatility_capture),
        ("Backend Running", verify_backend_running),
        ("Optimization Summary", verify_optimization_summary)
    ]
    
    results = []
    for name, verify_func in verifications:
        result = verify_func()
        results.append((name, result))
        print()
    
    # Summary
    print("="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:8} {name}")
    
    print()
    print(f"Overall: {passed}/{total} verifications passed")
    
    if passed == total:
        print("\n🎉 ALL OPTIMIZATIONS SUCCESSFULLY APPLIED!")
        print("\nExpected improvements:")
        print("- Monthly returns: ₹43,000 → ₹60,000-₹67,000")
        print("- Win rate: 69% → 75%+")
        print("- Total improvement: +40-55%")
        print("\nNext steps:")
        print("1. Monitor performance at: http://localhost:8000/dashboard")
        print("2. Review results in 7 days")
        print("3. Adjust allocations based on performance")
    else:
        print(f"\n⚠️  {total - passed} verification(s) failed")
        print("Please check the failed items above")


if __name__ == "__main__":
    main()
