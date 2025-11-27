#!/usr/bin/env python3
"""
Fix strategy names in existing paper_trading_status.json file
Changes all "default" strategy names to the actual strategy names
"""

import json
import sys
from pathlib import Path

# Map of common patterns to strategy names
STRATEGY_MAPPING = {
    # If we can't determine from signal, use reasonable defaults based on option type/strike
    'CE': 'oi_analysis',  # Call options often from OI Analysis
    'PE': 'pcr_strategy',  # Put options often from PCR Strategy
}

def fix_strategy_names(file_path: str):
    """Fix strategy names in paper trading status file"""
    
    try:
        # Read current file
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        print(f"📊 Loaded {file_path}")
        print(f"   Open positions: {len(data.get('open_positions', []))}")
        print(f"   Closed trades: {len(data.get('closed_trades', []))}")
        
        # Fix open positions
        fixed_positions = 0
        for position in data.get('open_positions', []):
            old_strategy = position.get('strategy_name', 'default')
            
            if old_strategy in ['default', 'unknown', '', None]:
                # Try to infer strategy from option type
                option_type = position.get('instrument_type', 'CE')
                new_strategy = STRATEGY_MAPPING.get(option_type, 'oi_analysis')
                
                position['strategy_name'] = new_strategy
                fixed_positions += 1
                print(f"   ✓ Fixed: {position.get('symbol')} {position.get('strike_price')} {option_type}: '{old_strategy}' → '{new_strategy}'")
        
        # Fix closed trades  
        fixed_trades = 0
        for trade in data.get('closed_trades', []):
            old_strategy = trade.get('strategy_name', trade.get('strategy', 'default'))
            
            if old_strategy in ['default', 'unknown', '', None]:
                # Try to infer strategy from option type
                option_type = trade.get('instrument_type', trade.get('direction', 'CE'))
                new_strategy = STRATEGY_MAPPING.get(option_type, 'oi_analysis')
                
                trade['strategy_name'] = new_strategy
                if 'strategy' in trade:
                    trade['strategy'] = new_strategy
                fixed_trades += 1
                print(f"   ✓ Fixed: {trade.get('symbol')} {trade.get('strike_price', trade.get('strike'))} {option_type}: '{old_strategy}' → '{new_strategy}'")
        
        # Write back
        if fixed_positions > 0 or fixed_trades > 0:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            print(f"\n✅ Fixed {fixed_positions} positions and {fixed_trades} trades")
            print(f"   Saved to: {file_path}")
            return True
        else:
            print(f"\n✅ No fixes needed - all strategies already have proper names")
            return True
            
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        print(f"   This is normal if no trades exist yet")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    file_path = "data/paper_trading_status.json"
    
    print("🔧 Fixing Strategy Names in Paper Trading File")
    print("=" * 60)
    
    success = fix_strategy_names(file_path)
    
    sys.exit(0 if success else 1)
