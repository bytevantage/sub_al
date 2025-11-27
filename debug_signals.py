#!/usr/bin/env python3
"""Debug signal generation"""

import sys
sys.path.append('backend')
from datetime import datetime, timedelta
import asyncio
from backend.database.db import session_scope
from backend.database.models import OptionChainSnapshot
from backend.strategies.strategy_engine import StrategyEngine
from backend.ml.model_manager import ModelManager

async def debug_signals():
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

            # Build market state (similar to backtester)
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

            market_state = {
                'NIFTY': {
                    'spot_price': snapshots[0].spot_price,
                    'atm_strike': round(snapshots[0].spot_price / 100) * 100,
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
                },
                'timestamp': timestamp.isoformat(),
                'last_update': timestamp
            }

            print(f"Market state built with {len(calls)} calls, {len(puts)} puts")
            print(f"Spot: {market_state['NIFTY']['spot_price']}, PCR: {pcr:.2f}")

            # Initialize strategy engine
            model_manager = ModelManager()
            await model_manager.load_models()

            strategy_engine = StrategyEngine(model_manager)

            # Generate signals
            print("\nGenerating signals...")
            signals = await strategy_engine.generate_signals(market_state)

            print(f"Generated {len(signals)} signals")

            for i, signal in enumerate(signals[:5]):  # Show first 5
                print(f"Signal {i+1}: {signal.get('strategy_name')} {signal.get('symbol')} {signal.get('direction')} {signal.get('strike')} @ ₹{signal.get('entry_price')}")

            # Score signals
            if signals:
                print("\nScoring signals...")
                scored_signals = await model_manager.score_signals(signals, market_state)
                print(f"Scored {len(scored_signals)} signals")

                for i, signal in enumerate(scored_signals[:3]):  # Show first 3
                    confidence = signal.get('ml_confidence', 0)
                    print(f"Scored {i+1}: {signal.get('strategy_id')} confidence: {confidence:.3f}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(debug_signals())
