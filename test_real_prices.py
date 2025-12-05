#!/usr/bin/env python3
"""
Test script to verify real price fetching is working end-to-end
"""

import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# Add project path
sys.path.append('.')

def test_real_price_system():
    """Test the complete real price system"""
    logger.info("🔍 TESTING REAL PRICE SYSTEM END-TO-END")
    logger.info("=" * 60)
    
    try:
        from backend.database.database import db as database
        from backend.database.models import OptionSnapshot
        
        session = database.get_session()
        
        # Get latest option chain data
        latest_snapshots = {}
        symbols = ['NIFTY', 'SENSEX']
        
        for symbol in symbols:
            latest = session.query(OptionSnapshot).filter(
                OptionSnapshot.symbol == symbol
            ).order_by(OptionSnapshot.timestamp.desc()).limit(5).all()
            
            if latest:
                latest_snapshots[symbol] = latest
                logger.info(f"📊 {symbol}: Found {len(latest)} recent snapshots")
                
                for snap in latest[:3]:
                    age_seconds = (datetime.now() - snap.timestamp).total_seconds()
                    logger.info(f"   {snap.strike_price} {snap.option_type}: ₹{snap.ltp} ({age_seconds:.0f}s old)")
            else:
                logger.warning(f"⚠️ {symbol}: No snapshots found")
        
        # Test market data fetching
        logger.info("\n🔄 TESTING MARKET DATA FETCHING...")
        
        # Test option chain fetching
        for symbol in symbols:
            try:
                from backend.data.market_data import MarketDataManager
                market_data = MarketDataManager()
                
                # Create async function to test
                async def test_option_chain():
                    return await market_data.get_option_chain(symbol, "2025-12-04")
                
                option_chain = await test_option_chain()
                
                if option_chain:
                    # Check if timestamp is present
                    if 'timestamp' in option_chain:
                        logger.info(f"✅ {symbol}: Option chain has timestamp")
                    else:
                        logger.warning(f"⚠️ {symbol}: Option chain missing timestamp")
                    
                    # Check if calls/puts have data
                    calls = option_chain.get('calls', {})
                    puts = option_chain.get('puts', {})
                    
                    if calls:
                        sample_strike = list(calls.keys())[0]
                        sample_call = calls[sample_strike]
                        logger.info(f"   Sample CALL {sample_strike}: ₹{sample_call.get('ltp', 'N/A')}")
                    
                    if puts:
                        sample_strike = list(puts.keys())[0]
                        sample_put = puts[sample_strike]
                        logger.info(f"   Sample PUT {sample_strike}: ₹{sample_put.get('ltp', 'N/A')}")
                else:
                    logger.warning(f"⚠️ {symbol}: No option chain data")
            except Exception as e:
                logger.error(f"❌ {symbol}: Error fetching option chain: {e}")
        
        session.close()
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_real_price_system())
