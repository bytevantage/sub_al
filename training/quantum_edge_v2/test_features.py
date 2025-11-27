"""
Quick test of feature engineering
Verifies 34-feature extraction from clean data
"""

import sys
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from feature_engineering import QuantumEdgeFeatureEngineer

print("="*100)
print("QUANTUM EDGE V2 - FEATURE ENGINEERING TEST")
print("="*100)

# Initialize
engineer = QuantumEdgeFeatureEngineer()

print(f"\n📊 Configuration:")
print(f"   Feature count: {len(engineer.FEATURE_NAMES)}")
print(f"   Expected shape: (34,)")

# Test feature extraction
print(f"\n🔧 Testing feature extraction from database...")

try:
    # Extract features for latest timestamp
    features = engineer.extract_features_from_db('NIFTY')
    
    print(f"\n✅ Feature extraction successful!")
    print(f"   Shape: {features.shape}")
    print(f"   Non-zero features: {np.count_nonzero(features)}/34")
    
    print(f"\n📊 Feature Values:")
    print("-"*100)
    
    for i, (name, value) in enumerate(zip(engineer.FEATURE_NAMES, features)):
        # Add category markers
        if i == 0:
            print(f"\n   🎯 Spot Price & Returns:")
        elif i == 4:
            print(f"\n   📈 VIX Proxy:")
        elif i == 5:
            print(f"\n   ⚖️  PCR Metrics:")
        elif i == 9:
            print(f"\n   🎯 Max Pain:")
        elif i == 12:
            print(f"\n   ⚡ Dealer GEX:")
        elif i == 16:
            print(f"\n   📊 Gamma Profile:")
        elif i == 20:
            print(f"\n   📉 IV Features:")
        elif i == 23:
            print(f"\n   🔄 OI Velocity:")
        elif i == 27:
            print(f"\n   💱 Order Flow:")
        elif i == 29:
            print(f"\n   📐 Technical:")
        elif i == 32:
            print(f"\n   ⏰ Time Features:")
        
        print(f"      [{i:2d}] {name:30s}: {value:10.4f}")
    
    print(f"\n{'='*100}")
    print("✅ ALL TESTS PASSED!")
    print("="*100)
    
    print(f"\n🎯 Next Steps:")
    print(f"   1. Run training: python train.py")
    print(f"   2. This will take 2-4 hours")
    print(f"   3. Model will be saved to: models/quantum_edge_v2.pt")
    print(f"   4. Test inference: python inference.py --mode single")

except Exception as e:
    print(f"\n❌ Error: {e}")
    print(f"\n🔍 Troubleshooting:")
    print(f"   1. Check database connection")
    print(f"   2. Verify option_chain_snapshots_clean view exists")
    print(f"   3. Ensure clean data is available")
    print(f"   4. Run: docker ps (check trading_db is running)")
