#!/usr/bin/env python3
"""Check option chain data in database"""

import sys
sys.path.append('backend')
from datetime import datetime, timedelta
from backend.database.db import session_scope
from backend.database.models import OptionChainSnapshot

# Check what option chain data exists
with session_scope() as session:
    # Count total snapshots
    total = session.query(OptionChainSnapshot).count()
    print(f'Total option chain snapshots: {total}')

    # Check date range
    if total > 0:
        earliest = session.query(OptionChainSnapshot).order_by(OptionChainSnapshot.timestamp).first()
        latest = session.query(OptionChainSnapshot).order_by(OptionChainSnapshot.timestamp.desc()).first()
        print(f'Date range: {earliest.timestamp} to {latest.timestamp}')

        # Check today's data
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        today_count = session.query(OptionChainSnapshot).filter(
            OptionChainSnapshot.timestamp >= today_start,
            OptionChainSnapshot.timestamp <= today_end
        ).count()

        print(f"Today's snapshots: {today_count}")

        # Show a few recent ones
        recent = session.query(OptionChainSnapshot).filter(
            OptionChainSnapshot.timestamp >= today_start
        ).order_by(OptionChainSnapshot.timestamp.desc()).limit(5).all()

        print('Recent snapshots:')
        for snap in recent:
            print(f'  {snap.timestamp} | {snap.symbol} | {snap.option_type} | Strike: {snap.strike_price}')
