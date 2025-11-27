#!/usr/bin/env python3
"""Debug OI strategy specifically"""

import sys
sys.path.append('backend')
from datetime import datetime, timedelta
import asyncio
from backend.database.db import session_scope
from backend.database.models import OptionChainSnapshot
from backend.strategies.oi_strategy import OIStrategy

async def debug_oi_strategy():
    print("Starting debug...")
    # Load a market state
    try:
        with session_scope() as session:
            # Get a recent snapshot
            recent_snap = session.query(OptionChainSnapshot).filter(
                OptionChainSnapshot.symbol == 'NIFTY'
            ).order_by(OptionChainSnapshot.timestamp.desc()).first()

            if not recent_snap:
                print("No NIFTY snapshots found")
                return

            print(f"Using snapshot from: {recent_snap.timestamp}")
            print(f"Spot price: {recent_snap.spot_price}")

            # Get all snapshots at this timestamp
            timestamp = recent_snap.timestamp
            snapshots = session.query(OptionChainSnapshot).filter(
                OptionChainSnapshot.symbol == 'NIFTY',
                OptionChainSnapshot.timestamp == timestamp
            ).all()

            print(f"Found {len(snapshots)} strikes at this timestamp")

            # Build market state
            calls = {}
            puts = {}

            for snap in snapshots:
                strike_key = str(snap.strike_price)

                if snap.option_type == 'CALL':
                    calls[strike_key] = {
                        'ltp': snap.ltp,
                        'bid': snap.bid,
                        'ask': snap.ask,
                        'volume': snap.volume,
                        'oi': snap.oi,
                        'oi_change': snap.oi_change,
                        'delta': snap.delta,
                        'gamma': snap.gamma,
                        'theta': snap.theta,
                        'vega': snap.vega,
                        'iv': snap.iv,
                        'expiry_date': snap.expiry.isoformat() if snap.expiry else None
                    }
                elif snap.option_type == 'PUT':
                    puts[strike_key] = {
                        'ltp': snap.ltp,
                        'bid': snap.bid,
                        'ask': snap.ask,
                        'volume': snap.volume,
                        'oi': snap.oi,
                        'oi_change': snap.oi_change,
                        'delta': snap.delta,
                        'gamma': snap.gamma,
                        'theta': snap.theta,
                        'vega': snap.vega,
                        'iv': snap.iv,
                        'expiry_date': snap.expiry.isoformat() if snap.expiry else None
                    }

            # Calculate metrics
            total_call_oi = sum(c.get('oi', 0) for c in calls.values())
            total_put_oi = sum(p.get('oi', 0) for p in puts.values())
            pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 0

            spot_price = snapshots[0].spot_price
            atm_strike = round(spot_price / 100) * 100

            market_data = {
                'NIFTY': {
                    'spot_price': spot_price,
                    'atm_strike': atm_strike,
                    'expiry': snapshots[0].expiry.isoformat() if snapshots[0].expiry else None,
                    'option_chain': {
                        'calls': calls,
                        'puts': puts,
                        'pcr': pcr,
                        'total_call_oi': total_call_oi,
                        'total_put_oi': total_put_oi,
                    },
                    'technical_indicators': {},
                    'timestamp': timestamp.isoformat()
                }
            }

            print(f"Market data built: spot={spot_price}, atm={atm_strike}, PCR={pcr:.2f}")
            print(f"Calls: {len(calls)}, Puts: {len(puts)}")

            # Test OI strategy directly
            oi_strategy = OIStrategy(weight=75)
            print(f"OI Strategy enabled: {oi_strategy.enabled}")
            print(f"OI Strategy can generate: {oi_strategy.can_generate_signal()}")

            print("\nTesting OI strategy...")
            signals = await oi_strategy.analyze(market_data)

            print(f"OI Strategy generated {len(signals)} signals")

            # Debug the analysis
            print("\nDebugging OI analysis...")
            await debug_oi_analysis(oi_strategy, market_data)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

async def debug_oi_analysis(oi_strategy, market_data):
    """Debug OI analysis step by step"""
    try:
        # Simulate the analysis
        if not oi_strategy.can_generate_signal():
            print("Strategy cannot generate signal (cooldown or disabled)")
            return
        
        for symbol, data in market_data.items():
            print(f"\nAnalyzing {symbol}...")
            option_chain = data.get('option_chain')
            if not option_chain:
                print("No option chain")
                continue
            
            atm_strike = data.get('atm_strike')
            puts = option_chain.get('puts', {})
            
            print(f"ATM strike: {atm_strike}")
            print(f"Puts available: {len(puts)}")
            
            # Get strikes to check
            strikes_to_check = [
                atm_strike - 100,
                atm_strike - 50,
                atm_strike,
                atm_strike + 50,
                atm_strike + 100
            ]
            
            print(f"Checking strikes: {strikes_to_check}")
            
            buildup_count = 0
            for strike in strikes_to_check:
                strike_key = str(int(strike))
                if strike_key not in puts:
                    print(f"  Strike {strike}: NOT FOUND")
                    continue
                
                put_data = puts[strike_key]
                oi_change = put_data.get('oi_change', 0)
                oi = put_data.get('oi', 0)
                
                if oi == 0:
                    print(f"  Strike {strike}: OI=0")
                    continue
                
                oi_change_pct = oi_change / oi if oi > 0 else 0
                print(f"  Strike {strike}: OI={oi}, Change={oi_change} ({oi_change_pct:.1f}%)")
                
                if oi_change_pct > oi_strategy.significant_oi_change:
                    buildup_count += 1
                    print(f"    -> BUILDUP detected ({buildup_count}/{oi_strategy.min_strikes_required})")
            
            print(f"Total buildup strikes: {buildup_count}")
            if buildup_count >= oi_strategy.min_strikes_required:
                print("SHOULD GENERATE PUT BUY SIGNAL")
            else:
                print("Not enough buildup strikes")
                
    except Exception as e:
        print(f"Debug error: {e}")
        import traceback
        traceback.print_exc()
