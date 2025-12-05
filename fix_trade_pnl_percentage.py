#!/usr/bin/env python3
"""
Fix P&L percentage calculation for existing trades
Most trades are SELL positions but database uses BUY formula
"""

import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# Add project path
sys.path.append('.')

def fix_pnl_percentage():
    """Fix P&L percentage for all trades"""
    logger.info("🔧 Fixing P&L percentage calculations...")
    
    try:
        from backend.database.database import db as database
        from backend.database.models import Trade
        
        session = database.get_session()
        
        # Get all trades (or today's trades)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        trades = session.query(Trade).filter(Trade.entry_time >= today).all()
        
        logger.info(f"📊 Found {len(trades)} trades to fix")
        
        fixed_count = 0
        
        for trade in trades:
            entry_price = trade.entry_price
            exit_price = trade.exit_price
            quantity = trade.quantity
            net_pnl = trade.net_pnl
            current_pct = trade.pnl_percentage
            
            # Since most trades are SELL positions (options writing), 
            # we use SELL formula: ((entry - exit) / entry) * 100
            correct_pct = ((entry_price - exit_price) / entry_price) * 100
            
            # Check if percentage needs fixing
            if abs(current_pct - correct_pct) > 0.1:  # Small tolerance for rounding
                logger.info(f"🔄 Fixing {trade.symbol} {trade.instrument_type} {trade.strike_price}")
                logger.info(f"   Entry: ₹{entry_price}, Exit: ₹{exit_price}")
                logger.info(f"   P&L: ₹{net_pnl:.2f}")
                logger.info(f"   Old P&L%: {current_pct:.2f}%")
                logger.info(f"   New P&L%: {correct_pct:.2f}%")
                
                # Update the trade
                trade.pnl_percentage = correct_pct
                fixed_count += 1
        
        # Commit changes
        if fixed_count > 0:
            session.commit()
            logger.info(f"✅ Fixed {fixed_count} P&L percentages")
        else:
            logger.info("ℹ️ No P&L percentages needed fixing")
        
        # Show some examples
        logger.info("📈 Sample corrected trades:")
        for trade in trades[:5]:
            logger.info(f"   {trade.symbol} {trade.instrument_type}: P&L ₹{trade.net_pnl:.2f} ({trade.pnl_percentage:.2f}%)")
        
        session.close()
        
        return fixed_count
        
    except Exception as e:
        logger.error(f"❌ Error fixing P&L percentages: {e}")
        import traceback
        traceback.print_exc()
        return 0

if __name__ == "__main__":
    fixed_count = fix_pnl_percentage()
    logger.info(f"🎉 P&L percentage fix completed: {fixed_count} trades corrected")
