#!/usr/bin/env python3
"""Check option chain data by symbol"""

import sys
sys.path.append('backend')
from datetime import datetime, timedelta
from backend.database.db import session_scope
from backend.database.models import OptionChainSnapshot

# Check what symbols have data
with session_scope() as session:
    # Count by symbol
    from sqlalchemy import func
    symbol_counts = session.query(
        OptionChainSnapshot.symbol,
        func.count(OptionChainSnapshot.id).label('count')
    ).group_by(OptionChainSnapshot.symbol).all()

    print('Option chain data by symbol:')
    for symbol, count in symbol_counts:
        print(f'  {symbol}: {count} snapshots')

    # Check NIFTY data specifically
    nifty_count = session.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == 'NIFTY'
    ).count()

    print(f'\nNIFTY snapshots: {nifty_count}')

    if nifty_count > 0:
        # Show time range for NIFTY
        earliest_nifty = session.query(OptionChainSnapshot).filter(
            OptionChainSnapshot.symbol == 'NIFTY'
        ).order_by(OptionChainSnapshot.timestamp).first()

        latest_nifty = session.query(OptionChainSnapshot).filter(
            OptionChainSnapshot.symbol == 'NIFTY'
        ).order_by(OptionChainSnapshot.timestamp.desc()).first()

        print(f'NIFTY time range: {earliest_nifty.timestamp} to {latest_nifty.timestamp}')
