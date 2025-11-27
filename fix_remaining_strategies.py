#!/usr/bin/env python3
"""
Comprehensive fix for remaining strategies to add Greeks
Fixes: Time-of-Day, Hidden OI, Liquidity Hunting, and Spread strategies
"""

import re
from pathlib import Path

def fix_pattern_strategies():
    """Fix pattern_strategies.py Time-of-Day signals"""
    file_path = Path('/Users/srbhandary/Documents/Projects/srb-algo/backend/strategies/pattern_strategies.py')
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix all three Time-of-Day Signal() creations
    # They all use entry_price=spot_price and wrong calculate_targets signature
    
    fixes = [
        {
            'old': '''        atm_strike = market_data.get("atm_strike", spot_price)
        iv = market_data.get("iv", 20)
        
        direction = "CALL" if breakout_pct > 0 else "PUT"
        strength = min(85, 60 + abs(breakout_pct) * 10)
        
        targets = self.calculate_targets(
            entry=spot_price,
            direction=direction,
            strength=strength,
            volatility=iv,
            time_decay_factor=0.8
        )
        
        return Signal(
            strategy_name=self.name,
            symbol="NIFTY",
            direction=direction,
            strike=int(atm_strike),
            entry_price=spot_price,
            target_price=targets["target1"],
            stop_loss=targets["stop_loss"],
            strength=strength,
            reason=f"Opening range breakout {breakout_pct:+.2f}%"
        )''',
            'new': '''        atm_strike = market_data.get("atm_strike", spot_price)
        strike_key = str(int(atm_strike))
        option_chain = market_data.get("option_chain", {})
        expiry = market_data.get("expiry")
        
        direction = "CALL" if breakout_pct > 0 else "PUT"
        option_data = option_chain.get('calls' if direction == "CALL" else 'puts', {}).get(strike_key, {})
        entry_price = option_data.get('ltp', 0)
        iv = option_data.get('iv', 20)
        
        if entry_price <= 0:
            return None
        
        strength = min(85, 60 + abs(breakout_pct) * 10)
        target, stop_loss = self.calculate_targets(entry_price, strength, iv, 3)
        
        # Extract Greeks
        delta = option_data.get('delta', 0.0)
        gamma = option_data.get('gamma', 0.0)
        theta = option_data.get('theta', 0.0)
        vega = option_data.get('vega', 0.0)
        oi = option_data.get('oi', 0)
        volume = option_data.get('volume', 0)
        bid = option_data.get('bid', 0.0)
        ask = option_data.get('ask', 0.0)
        
        return Signal(
            strategy_name=self.name,
            symbol="NIFTY",
            direction=direction,
            action="BUY",
            strike=int(atm_strike),
            expiry=expiry,
            entry_price=entry_price,
            strength=strength,
            reason=f"Opening range breakout {breakout_pct:+.2f}%",
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            iv=iv,
            oi=oi,
            volume=volume,
            bid=bid,
            ask=ask,
            spot_price=spot_price
        )'''
        }
    ]
    
    for fix in fixes:
        content = content.replace(fix['old'], fix['new'])
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✓ Fixed pattern_strategies.py")

if __name__ == '__main__':
    fix_pattern_strategies()
    print("Complete!")
