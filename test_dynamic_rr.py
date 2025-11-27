#!/usr/bin/env python3
"""
Test script to verify dynamic risk-reward system is working
"""
import sys
import os
sys.path.append('/Users/srbhandary/Documents/Projects/srb-algo')

from backend.execution.risk_reward_config import calculate_targets, RiskRewardCalculator

def test_dynamic_rr():
    print("Testing Dynamic Risk-Reward System")
    print("=" * 50)
    
    # Test different regimes
    test_cases = [
        {"entry": 100, "direction": "CALL", "confidence": 0.85, "vix": 22, "adx": 35, "name": "Monster Day"},
        {"entry": 100, "direction": "CALL", "confidence": 0.90, "vix": 15, "adx": 25, "name": "High Confidence"},
        {"entry": 100, "direction": "CALL", "confidence": 0.70, "vix": 12, "adx": 18, "name": "Choppy Regime"},
        {"entry": 100, "direction": "CALL", "confidence": 0.70, "vix": 16, "adx": 25, "name": "Default"},
    ]
    
    for test in test_cases:
        print(f"\n{test['name']}:")
        print(f"  Entry: ₹{test['entry']}, Confidence: {test['confidence']}, VIX: {test['vix']}, ADX: {test['adx']}")
        
        targets = calculate_targets(
            entry_price=test['entry'],
            signal_direction=test['direction'],
            confidence=test['confidence'],
            vix=test['vix'],
            adx=test['adx']
        )
        
        print(f"  Regime: {targets['regime']}")
        print(f"  Stop Loss: ₹{targets['stop_loss']}")
        print(f"  TP1 (40%): ₹{targets['tp1']} (+{((targets['tp1']-test['entry'])/test['entry']*100):.1f}%)")
        print(f"  TP2 (35%): ₹{targets['tp2']} (+{((targets['tp2']-test['entry'])/test['entry']*100):.1f}%)")
        print(f"  TP3 (25%): ₹{targets['tp3']} (+{((targets['tp3']-test['entry'])/test['entry']*100):.1f}%)")
        print(f"  RR Ratio: {targets['rr_final']}")
        print(f"  Risk %: {targets['risk_pct']:.1f}%")

if __name__ == "__main__":
    test_dynamic_rr()
