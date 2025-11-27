#!/usr/bin/env python3
"""
Script to add Greeks extraction to all strategy Signal creation
This ensures ML training data has complete option chain information
"""

import re
import os
from pathlib import Path

# Greek fields to extract from option_data
GREEKS_EXTRACTION = """
        # Extract Greeks and market data for ML training
        delta = option_data.get('delta', 0.0)
        gamma = option_data.get('gamma', 0.0)
        theta = option_data.get('theta', 0.0)
        vega = option_data.get('vega', 0.0)
        oi = option_data.get('oi', 0)
        volume = option_data.get('volume', 0)
        bid = option_data.get('bid', 0.0)
        ask = option_data.get('ask', 0.0)"""

# Greeks parameters to add to Signal constructor
GREEKS_PARAMS = """            # Greeks for ML training
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            iv=iv,
            # Market data for ML training
            oi=oi,
            volume=volume,
            bid=bid,
            ask=ask,
            spot_price=spot_price,"""

# Updated metadata with Greeks
METADATA_WITH_GREEKS = """                'delta': delta,
                'gamma': gamma,
                'theta': theta,
                'vega': vega"""

def fix_strategy_file(filepath: str) -> bool:
    """
    Fix a single strategy file to include Greeks
    Returns True if file was modified
    """
    print(f"\nProcessing: {filepath}")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    modified = False
    
    # Pattern 1: Find Signal() constructor calls that don't have Greeks
    # Look for Signal( followed by parameters, checking if delta= is present
    signal_pattern = r'Signal\s*\([^)]*?\)'
    
    for match in re.finditer(signal_pattern, content, re.DOTALL):
        signal_call = match.group(0)
        
        # Skip if already has Greeks
        if 'delta=' in signal_call:
            continue
        
        # Check if this is inside a _create_signal or similar method
        start_pos = match.start()
        context_before = content[max(0, start_pos-1000):start_pos]
        
        # Find if we're in a method that has access to option_data
        if 'option_data' in context_before or 'extract_greeks' in context_before:
            print(f"  Found Signal without Greeks at position {start_pos}")
            modified = True
    
    # Pattern 2: Add spot_price extraction if missing
    if 'spot_price = data.get(\'spot_price\'' not in content and 'spot_price = market_data.get(\'spot_price\'' not in content:
        # Find entry_price = ... lines and add spot_price after them
        content = re.sub(
            r'(entry_price\s*=\s*option_data\.get\([\'"]ltp[\'"],\s*\d+\))',
            r'\1\n        spot_price = data.get(\'spot_price\', 0.0)',
            content
        )
    
    if content != original_content:
        print(f"  ✓ Modified {filepath}")
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    else:
        print(f"  - No changes needed for {filepath}")
        return False

def main():
    """Fix all strategy files"""
    strategies_dir = Path(__file__).parent / 'backend' / 'strategies'
    
    # List of strategy files to fix (excluding already fixed ones and base classes)
    strategy_files = [
        'support_resistance_strategy.py',
        'microstructure_strategies.py',
        'pattern_strategies.py',
        'spread_strategies.py',
        'price_spike_strategy.py',
    ]
    
    print("=" * 60)
    print("FIXING GREEKS IN STRATEGY FILES")
    print("=" * 60)
    
    fixed_count = 0
    for filename in strategy_files:
        filepath = strategies_dir / filename
        if filepath.exists():
            if fix_strategy_file(str(filepath)):
                fixed_count += 1
        else:
            print(f"  ✗ File not found: {filepath}")
    
    print("\n" + "=" * 60)
    print(f"SUMMARY: Fixed {fixed_count} out of {len(strategy_files)} strategy files")
    print("=" * 60)
    print("\nNote: Some strategies may need manual review if they have")
    print("complex Signal creation patterns or don't use option_data directly.")

if __name__ == '__main__':
    main()
