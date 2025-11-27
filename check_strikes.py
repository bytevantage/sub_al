#!/usr/bin/env python3
"""Debug OI strategy strike checking"""

import sys
sys.path.append('backend')
from backend.database.db import session_scope
from backend.database.models import OptionChainSnapshot

# Check specific strikes around ATM
with session_scope() as session:
    # Get a recent timestamp
    recent_snap = session.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == 'NIFTY'
    ).order_by(OptionChainSnapshot.timestamp.desc()).first()

    if not recent_snap:
        print("No snapshots")
        exit(1)

    timestamp = recent_snap.timestamp
    spot_price = recent_snap.spot_price
    atm_strike = round(spot_price / 100) * 100

    print(f"Timestamp: {timestamp}")
    print(f"Spot: {spot_price}, ATM: {atm_strike}")

    # Check strikes that OI strategy looks at
    strikes_to_check = [
        atm_strike - 100,
        atm_strike - 50,
        atm_strike,
        atm_strike + 50,
        atm_strike + 100
    ]

    print(f"Checking strikes: {strikes_to_check}")

    for strike in strikes_to_check:
        # Check CALL
        call_snap = session.query(OptionChainSnapshot).filter(
            OptionChainSnapshot.symbol == 'NIFTY',
            OptionChainSnapshot.timestamp == timestamp,
            OptionChainSnapshot.strike_price == strike,
            OptionChainSnapshot.option_type == 'CALL'
        ).first()

        if call_snap:
            oi_change_pct = (call_snap.oi_change / call_snap.oi * 100) if call_snap.oi > 0 else 0
            print(f"  CALL {strike}: OI={call_snap.oi}, Change={call_snap.oi_change} ({oi_change_pct:.1f}%)")
        else:
            print(f"  CALL {strike}: NOT FOUND")

        # Check PUT
        put_snap = session.query(OptionChainSnapshot).filter(
            OptionChainSnapshot.symbol == 'NIFTY',
            OptionChainSnapshot.timestamp == timestamp,
            OptionChainSnapshot.strike_price == strike,
            OptionChainSnapshot.option_type == 'PUT'
        ).first()

        if put_snap:
            oi_change_pct = (put_snap.oi_change / put_snap.oi * 100) if put_snap.oi > 0 else 0
            print(f"  PUT  {strike}: OI={put_snap.oi}, Change={put_snap.oi_change} ({oi_change_pct:.1f}%)")
        else:
            print(f"  PUT  {strike}: NOT FOUND")
