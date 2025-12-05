#!/usr/bin/env python3
"""
Fix P&L calculation for existing trades that were calculated with wrong direction logic
"""

import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# Add project path
sys.path.append('.')

def fix_trade_pnl():
    """Fix P&L for trades with wrong direction calculation"""
    logger.info("🔧 Fixing P&L calculations for existing trades...")
    
    try:
        from backend.database.database import db as database
        from backend.database.models import Trade
        
        session = database.get_session()
        
        # Get today's trades
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        trades = session.query(Trade).filter(Trade.entry_time >= today).all()
        
        logger.info(f"📊 Found {len(trades)} trades to check")
        
        fixed_count = 0
        
        for trade in trades:
            # Recalculate P&L with correct direction logic
            entry_price = trade.entry_price
            exit_price = trade.exit_price or trade.current_price
            quantity = trade.quantity
            direction = trade.direction if hasattr(trade, 'direction') else 'SELL'  # Most are SELL
            
            # Correct P&L calculation
            if direction == 'BUY':
                correct_pnl = (exit_price - entry_price) * quantity
            else:  # SELL
                correct_pnl = (entry_price - exit_price) * quantity
            
            # Check if P&L needs fixing
            if abs(trade.net_pnl - correct_pnl) > 0.01:  # Small tolerance for rounding
                logger.info(f"🔄 Fixing {trade.symbol} {trade.instrument_type} {trade.strike_price}")
                logger.info(f"   Old P&L: ₹{trade.net_pnl:.2f}")
                logger.info(f"   New P&L: ₹{correct_pnl:.2f}")
                logger.info(f"   Direction: {direction}")
                
                # Update the trade
                trade.net_pnl = correct_pnl
                trade.gross_pnl = correct_pnl  # Update gross P&L too
                
                fixed_count += 1
        
        # Commit changes
        if fixed_count > 0:
            session.commit()
            logger.info(f"✅ Fixed {fixed_count} trades")
        else:
            logger.info("ℹ️ No trades needed fixing")
        
        # Calculate new totals
        total_pnl = sum(trade.net_pnl or 0 for trade in trades)
        winning_trades = sum(1 for trade in trades if (trade.net_pnl or 0) > 0)
        total_trades = len(trades)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        logger.info(f"📈 New totals:")
        logger.info(f"   Total P&L: ₹{total_pnl:.2f}")
        logger.info(f"   Winning trades: {winning_trades}/{total_trades}")
        logger.info(f"   Win rate: {win_rate:.1f}%")
        
        session.close()
        
        return total_pnl, win_rate
        
    except Exception as e:
        logger.error(f"❌ Error fixing trades: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0

if __name__ == "__main__":
    total_pnl, win_rate = fix_trade_pnl()
    
    if total_pnl > 0:
        logger.info(f"🎉 SUCCESS: Today's P&L corrected to +₹{total_pnl:,.2f}")
        logger.info(f"📊 Win rate: {win_rate:.1f}%")
    else:
        logger.info("ℹ️ Fix completed - check results above")
