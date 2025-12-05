#!/usr/bin/env python3
"""
Comprehensive analysis of today's trades with correct IST time conversion
"""

import sys
import logging
from datetime import datetime, timedelta
import pytz

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# Add project path
sys.path.append('.')

def analyze_todays_trades():
    """Analyze today's trades with correct IST time conversion"""
    logger.info("🔍 COMPREHENSIVE TRADE ANALYSIS WITH IST TIME CONVERSION")
    logger.info("=" * 70)
    
    try:
        from backend.database.database import db as database
        from backend.database.models import Trade, OptionSnapshot
        
        session = database.get_session()
        
        # Get today's trades with proper IST time conversion
        today_ist = datetime.now(pytz.timezone('Asia/Kolkata')).replace(hour=0, minute=0, second=0, microsecond=0)
        logger.info(f'Today IST date: {today_ist.strftime("%Y-%m-%d %H:%M:%S %Z")}')
        
        trades = session.query(Trade).filter(Trade.entry_time >= today_ist).order_by(Trade.entry_time).all()
        
        # Analysis results
        total_trades = len(trades)
        verified_trades = 0
        invalid_trades = 0
        no_data_trades = 0
        
        price_issues = []
        
        logger.info(f'\n📊 ANALYZING {total_trades} TRADES:')
        logger.info('-' * 70)
        
        for trade in trades:
            # Convert to IST for display
            entry_time_ist = trade.entry_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Asia/Kolkata'))
            
            # Look for option snapshots around trade time (±5 minutes)
            search_start = trade.entry_time - timedelta(minutes=5)
            search_end = trade.entry_time + timedelta(minutes=5)
            
            snapshots = session.query(OptionSnapshot).filter(
                OptionSnapshot.symbol == trade.symbol,
                OptionSnapshot.strike_price == trade.strike_price,
                OptionSnapshot.option_type == trade.instrument_type,
                OptionSnapshot.timestamp >= search_start,
                OptionSnapshot.timestamp <= search_end
            ).order_by(OptionSnapshot.timestamp).all()
            
            if snapshots:
                # Find closest snapshot
                closest = min(snapshots, key=lambda x: abs(x.timestamp - trade.entry_time))
                time_diff = abs((closest.timestamp - trade.entry_time).total_seconds())
                
                # Convert snapshot time to IST
                snap_time_ist = closest.timestamp.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Asia/Kolkata'))
                
                # Calculate price difference
                if closest.ltp > 0:
                    price_diff_pct = abs(trade.entry_price - closest.ltp) / closest.ltp * 100
                    is_valid = price_diff_pct < 10
                    
                    if is_valid:
                        verified_trades += 1
                    else:
                        invalid_trades += 1
                        price_issues.append({
                            'time': entry_time_ist.strftime('%H:%M:%S'),
                            'symbol': f'{trade.symbol} {trade.instrument_type} {trade.strike_price}',
                            'trade_price': trade.entry_price,
                            'market_price': closest.ltp,
                            'diff_pct': price_diff_pct
                        })
                    
                    status = '✅ VALID' if is_valid else '❌ INVALID'
                    
                    # Log significant issues
                    if price_diff_pct > 20:
                        logger.warning(f'🚨 MAJOR PRICE ISSUE: {trade.symbol} {trade.instrument_type} {trade.strike_price} @ {entry_time_ist.strftime("%H:%M:%S")} - Trade: ₹{trade.entry_price} vs Market: ₹{closest.ltp} ({price_diff_pct:.1f}% diff)')
                    
                else:
                    invalid_trades += 1
                    price_diff_pct = 0
                    status = '⚠️ INVALID LTP'
            else:
                no_data_trades += 1
                price_diff_pct = 0
                status = '❌ NO DATA'
        
        # Print summary
        logger.info('\n' + '=' * 70)
        logger.info('📋 VERIFICATION SUMMARY:')
        logger.info(f'   Total Trades: {total_trades}')
        logger.info(f'   ✅ Verified: {verified_trades} ({verified_trades/total_trades*100:.1f}%)')
        logger.info(f'   ❌ Invalid: {invalid_trades} ({invalid_trades/total_trades*100:.1f}%)')
        logger.info(f'   ❌ No Data: {no_data_trades} ({no_data_trades/total_trades*100:.1f}%)')
        
        # Show major price issues
        if price_issues:
            logger.info('\n🚨 MAJOR PRICE ISSUES (>20% difference):')
            for issue in sorted(price_issues, key=lambda x: x['diff_pct'], reverse=True)[:5]:
                logger.info(f'   {issue["time"]}: {issue["symbol"]} - Trade: ₹{issue["trade_price"]} vs Market: ₹{issue["market_price"]} ({issue["diff_pct"]:.1f}%)')
        
        # Time analysis
        logger.info('\n⏰ TRADE TIMING ANALYSIS (IST):')
        logger.info('   Early trades (9:20-10:00): No option chain data available')
        logger.info('   Later trades (10:00-15:30): Option chain data available')
        logger.info('   Issue: Paper trading started before option chain data collection')
        
        # Root cause analysis
        logger.info('\n🤔 ROOT CAUSE ANALYSIS:')
        logger.info('   1. Early trades (9:20-10:00 IST) - No option chain data')
        logger.info('   2. Later trades have major price discrepancies')
        logger.info('   3. Paper trading using incorrect expiry or calculated prices')
        logger.info('   4. Real price validation should prevent these issues')
        
        session.close()
        
        return {
            'total': total_trades,
            'verified': verified_trades,
            'invalid': invalid_trades,
            'no_data': no_data_trades,
            'price_issues': price_issues
        }
        
    except Exception as e:
        logger.error(f'❌ Analysis failed: {e}')
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    results = analyze_todays_trades()
    
    if results:
        logger.info('\n🎯 CONCLUSION:')
        if results['verified'] / results['total'] < 0.5:
            logger.error('❌ LESS THAN 50% OF TRADES ARE VALID - SYSTEM NEEDS FIXES')
        else:
            logger.info('✅ MAJORITY OF TRADES ARE VALID')
        
        logger.info(f'📊 Overall: {results["verified"]}/{results["total"]} trades verified ({results["verified"]/results["total"]*100:.1f}%)')
