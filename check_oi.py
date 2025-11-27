#!/usr/bin/env python3
"""Check OI change values"""

import sys
sys.path.append('backend')
from backend.database.db import session_scope
from backend.database.models import OptionChainSnapshot

# Check OI change values
with session_scope() as session:
    # Get a few recent snapshots
    snapshots = session.query(OptionChainSnapshot).filter(
        OptionChainSnapshot.symbol == 'NIFTY'
    ).order_by(OptionChainSnapshot.timestamp.desc()).limit(20).all()

    print('Recent NIFTY OI change values:')
    for snap in snapshots[:10]:  # First 10
        oi_change_pct = (snap.oi_change / snap.oi * 100) if snap.oi > 0 else 0
        print(f'  Strike {snap.strike_price} {snap.option_type}: OI={snap.oi}, OI_Change={snap.oi_change} ({oi_change_pct:.1f}%)')
