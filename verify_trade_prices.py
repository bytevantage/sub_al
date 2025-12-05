#!/usr/bin/env python3
"""
Comprehensive trade price verification report
Compares paper trade entry prices with option chain data at trade time
"""

import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# Add project path
sys.path.append('.')

def verify_all_trades():
    """Verify all trades against option chain data"""
    logger.info("🔍 COMPREHENSIVE TRADE VERIFICATION REPORT")
    logger.info("=" * 80)
    
    try:
        from backend.database.database import db as database
        from backend.database.models import Trade, OptionSnapshot
        
        session = database.get_session()
        
        # Get today's trades
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        trades = session.query(Trade).filter(Trade.entry_time >= today).order_by(Trade.entry_time).all()
        
        logger.info(f"📊 Analyzing {len(trades)} trades from {today.strftime('%Y-%m-%d')}")
        
        verification_results = []
        total_trades = 0
        verified_trades = 0
        problematic_trades = 0
        
        for trade in trades:
            total_trades += 1
            
            # Get option snapshots around trade time
            snapshots = session.query(OptionSnapshot).filter(
                OptionSnapshot.symbol == trade.symbol,
                OptionSnapshot.strike_price == trade.strike_price,
                OptionSnapshot.option_type == trade.instrument_type,
                OptionSnapshot.timestamp >= trade.entry_time - timedelta(minutes=2),
                OptionSnapshot.timestamp <= trade.entry_time + timedelta(minutes=2)
            ).order_by(OptionSnapshot.timestamp).all()
            
            if snapshots:
                # Find closest snapshot
                closest_snap = min(snapshots, key=lambda x: abs(x.timestamp - trade.entry_time))
                time_diff = abs((closest_snap.timestamp - trade.entry_time).total_seconds())
                
                # Calculate price difference
                if closest_snap.ltp > 0:
                    price_diff_pct = abs(trade.entry_price - closest_snap.ltp) / closest_snap.ltp * 100
                else:
                    price_diff_pct = 100
                
                # Check if price is reasonable
                is_valid = price_diff_pct < 10  # Within 10%
                
                if is_valid:
                    verified_trades += 1
                else:
                    problematic_trades += 1
                
                verification_results.append({
                    'trade': trade,
                    'snapshot': closest_snap,
                    'time_diff': time_diff,
                    'price_diff_pct': price_diff_pct,
                    'is_valid': is_valid
                })
            else:
                problematic_trades += 1
                verification_results.append({
                    'trade': trade,
                    'snapshot': None,
                    'time_diff': None,
                    'price_diff_pct': None,
                    'is_valid': False
                })
        
        # Print detailed report
        logger.info(f"\n📋 VERIFICATION SUMMARY:")
        logger.info(f"   Total Trades: {total_trades}")
        logger.info(f"   ✅ Verified: {verified_trades} ({verified_trades/total_trades*100:.1f}%)")
        logger.info(f"   ⚠️  Problematic: {problematic_trades} ({problematic_trades/total_trades*100:.1f}%)")
        
        # Show problematic trades
        logger.info(f"\n🚨 PROBLEMATIC TRADES:")
        for result in verification_results:
            if not result['is_valid']:
                trade = result['trade']
                snapshot = result['snapshot']
                
                logger.info(f"\n📊 {trade.symbol} {trade.instrument_type} {trade.strike_price}")
                logger.info(f"   Trade Time: {trade.entry_time.strftime('%H:%M:%S')}")
                logger.info(f"   Trade Price: ₹{trade.entry_price}")
                logger.info(f"   Strategy: {trade.strategy_name}")
                
                if snapshot:
                    logger.info(f"   Option Chain Time: {snapshot.timestamp.strftime('%H:%M:%S')} ({result['time_diff']:.0f}s diff)")
                    logger.info(f"   Option Chain LTP: ₹{snapshot.ltp}")
                    logger.info(f"   Price Difference: {result['price_diff_pct']:.1f}%")
                    logger.info(f"   Bid-Ask: ₹{snapshot.bid} - ₹{snapshot.ask}")
                else:
                    logger.info(f"   ❌ No option chain data found")
        
        # Analysis of the issue
        logger.info(f"\n🤔 ISSUE ANALYSIS:")
        logger.info(f"1. All trades are PAPER trades (entry_mode='PAPER')")
        logger.info(f"2. Paper trading uses option chain prices via _get_option_price_from_chain_dict()")
        logger.info(f"3. Large price discrepancies suggest:")
        logger.info(f"   - Option chain data timing issues")
        logger.info(f"   - Different expiry dates")
        logger.info(f"   - Paper trading using stale/cached data")
        logger.info(f"   - Calculation errors in price fetching")
        
        # Recommendations
        logger.info(f"\n💡 RECOMMENDATIONS:")
        logger.info(f"1. Check option chain data freshness in paper trading")
        logger.info(f"2. Verify expiry date matching")
        logger.info(f"3. Add price validation before trade execution")
        logger.info(f"4. Log option chain data at trade generation time")
        logger.info(f"5. Consider using live prices for paper trading")
        
        session.close()
        
        return verified_trades, problematic_trades
        
    except Exception as e:
        logger.error(f"❌ Error in verification: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0

if __name__ == "__main__":
    verified, problematic = verify_all_trades()
    logger.info(f"\n🎯 VERIFICATION COMPLETE: {verified} verified, {problematic} problematic")
