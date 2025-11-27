#!/usr/bin/env python3
"""Check available strikes"""

import sys
sys.path.append('backend')
from backend.database.db import session_scope
from backend.database.models import OptionChainSnapshot

with session_scope() as session:
    # Get a recent timestamp
    recent_snap = session.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == 'NIFTY'
    ).order_by(OptionChainSnapshot.timestamp.desc()).first()

    if recent_snap:
        timestamp = recent_snap.timestamp
        snapshots = session.query(OptionChainSnapshot).filter(
            OptionChainSnapshot.symbol == 'NIFTY',
            OptionChainSnapshot.timestamp == timestamp
        ).all()

        puts_strikes = sorted([s.strike_price for s in snapshots if s.option_type == 'PUT'])
        calls_strikes = sorted([s.strike_price for s in snapshots if s.option_type == 'CALL'])
        
        print(f'PUT strikes ({len(puts_strikes)}): {puts_strikes[:10]} ...')
        if len(puts_strikes) > 10:
            print(f'  ... {puts_strikes[-10:]}')
        print(f'CALL strikes ({len(calls_strikes)}): {calls_strikes[:10]} ...')
        if len(calls_strikes) > 10:
            print(f'  ... {calls_strikes[-10:]}')
        
        spot = recent_snap.spot_price
        print(f'Spot price: {spot}')
        print(f'ATM should be around: {round(spot/100)*100}')
