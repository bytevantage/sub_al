#!/usr/bin/env python3
"""
Apply Greeks fix to remaining strategy files
This script adds Greeks extraction to all Signal() creations that are missing it
"""

import re
from pathlib import Path

def fix_signal_creation(content: str, file_path: str) -> tuple[str, int]:
    """Fix Signal() creations to include Greeks. Returns (new_content, changes_count)"""
    
    changes = 0
    
    # Pattern 1: Fix calculate_targets() calls with wrong signature
    # Replace: targets = self.calculate_targets(entry=spot_price, direction="X", ...)
    # With: target, stop_loss = self.calculate_targets(entry_price, strength, iv, 3)
    
    wrong_targets_pattern = r'targets\s*=\s*self\.calculate_targets\s*\(\s*entry=([^,]+),\s*direction="([^"]+)",\s*strength=([^,]+),\s*volatility=([^,]+),\s*time_decay_factor=[^)]+\)'
    
    def replace_targets(match):
        return f'target, stop_loss = self.calculate_targets(entry_price, strength, {match.group(4)}, 3)'
    
    content = re.sub(wrong_targets_pattern, replace_targets, content)
    
    # Pattern 2: Find Signal() calls and check if they need Greeks
    signal_pattern = r'return Signal\(((?:[^()]+|\([^)]*\))*)\)'
    
    def add_greeks_to_signal(match):
        nonlocal changes
        signal_content = match.group(1)
        
        # Skip if already has Greeks
        if 'delta=' in signal_content:
            return match.group(0)
        
        # Check if we're using entry_price (means we have option_data)
        if 'entry_price=entry_price' not in signal_content and 'entry_price=spot_price' in signal_content:
            # Need to add option_data extraction before this Signal
            return match.group(0)  # Can't fix inline, needs context
        
        # Skip if entry_price=spot_price (no option_data yet)
        if 'entry_price=spot_price' in signal_content:
            return match.group(0)
        
        # Add Greeks to existing Signal
        changes += 1
        
        # Insert Greeks before metadata or at end
        if 'metadata=' in signal_content:
            signal_content = signal_content.replace(
                'metadata=',
                '''delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            iv=iv,
            oi=oi,
            volume=volume,
            bid=bid,
            ask=ask,
            spot_price=spot_price,
            metadata='''
            )
        else:
            # Add before last closing paren
            signal_content = signal_content.rstrip() + ''',
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            iv=iv,
            oi=oi,
            volume=volume,
            bid=bid,
            ask=ask,
            spot_price=spot_price'''
        
        return f'return Signal({signal_content})'
    
    content = re.sub(signal_pattern, add_greeks_to_signal, content, flags=re.DOTALL)
    
    return content, changes


def main():
    """Apply fixes to all remaining strategy files"""
    
    strategies_dir = Path('/Users/srbhandary/Documents/Projects/srb-algo/backend/strategies')
    
    files_to_fix = [
        'pattern_strategies.py',
        'spread_strategies.py'
    ]
    
    print("Applying Greeks fixes to remaining strategies...")
    print("=" * 60)
    
    total_changes = 0
    
    for filename in files_to_fix:
        filepath = strategies_dir / filename
        
        if not filepath.exists():
            print(f"✗ {filename}: File not found")
            continue
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        new_content, changes = fix_signal_creation(content, str(filepath))
        
        if changes > 0:
            with open(filepath, 'w') as f:
                f.write(new_content)
            print(f"✓ {filename}: {changes} fixes applied")
            total_changes += changes
        else:
            print(f"- {filename}: No changes needed")
    
    print("=" * 60)
    print(f"Total fixes applied: {total_changes}")
    print("\nNote: Some files may need manual review for:")
    print("- Adding option_data extraction before Signal creation")
    print("- Adding expiry and action parameters")
    print("- Converting entry_price from spot_price to option LTP")


if __name__ == '__main__':
    main()
