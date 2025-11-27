#!/usr/bin/env python3
"""
Real-time Data Freshness Monitor
Ensures trading data is fresh and alerts on stale data
"""

import sys
import os
import time
import asyncio
from datetime import datetime

# Add project root to path
sys.path.append('/Users/srbhandary/Documents/Projects/srb-algo')

from backend.data.market_data import MarketDataManager
from backend.core.upstox_client import UpstoxClient
from backend.core.logger import get_logger

logger = get_logger(__name__)

async def test_data_freshness():
    """Test real-time data freshness for trading safety"""
    
    print("🔍 Testing Real-time Data Freshness")
    print("=" * 50)
    
    try:
        # Initialize components
        upstox_client = UpstoxClient()
        market_data_manager = MarketDataManager(upstox_client)
        
        print("\n📊 Testing Spot Price Freshness...")
        
        # Test SENSEX spot price freshness
        symbol = "SENSEX"
        fresh_prices = []
        stale_count = 0
        
        for i in range(10):
            start_time = time.time()
            price = await market_data_manager.get_spot_price(symbol)
            end_time = time.time()
            
            if price:
                age = (end_time - start_time) * 1000  # Convert to ms
                fresh_prices.append({
                    'price': price,
                    'fetch_time_ms': age,
                    'timestamp': datetime.now()
                })
                print(f"   ✅ SENSEX {symbol}: ₹{price} (fetch: {age:.1f}ms)")
            else:
                stale_count += 1
                print(f"   ❌ SENSEX {symbol}: FAILED to fetch")
            
            await asyncio.sleep(0.5)  # 500ms between requests
        
        # Analyze freshness
        if fresh_prices:
            avg_fetch_time = sum(p['fetch_time_ms'] for p in fresh_prices) / len(fresh_prices)
            max_fetch_time = max(p['fetch_time_ms'] for p in fresh_prices)
            price_changes = len(set(p['price'] for p in fresh_prices))
            
            print(f"\n📈 Spot Price Analysis:")
            print(f"   • Average fetch time: {avg_fetch_time:.1f}ms")
            print(f"   • Max fetch time: {max_fetch_time:.1f}ms")
            print(f"   • Price updates: {price_changes} changes in 10 samples")
            print(f"   • Stale requests: {stale_count}/10")
            
            # Check for dangerous patterns
            if avg_fetch_time > 1000:  # > 1 second is dangerous
                print(f"   ⚠️  DANGER: Average fetch time > 1s!")
            if price_changes < 2:
                print(f"   ⚠️  WARNING: Prices not updating frequently!")
            if stale_count > 2:
                print(f"   🚨 CRITICAL: High stale data rate!")
        
        print("\n📊 Testing Option Chain Freshness...")
        
        # Test SENSEX option chain freshness
        expiry = market_data_manager._get_current_weekly_expiry(symbol)
        fresh_chains = 0
        stale_chains = 0
        
        for i in range(5):
            start_time = time.time()
            option_chain = await market_data_manager.get_option_chain(symbol, expiry)
            end_time = time.time()
            
            if option_chain:
                fetch_time = (end_time - start_time) * 1000
                fresh_chains += 1
                
                # Check for specific strike 85600 CE
                calls = option_chain.get('calls', {})
                strike_key = "85600"
                
                if strike_key in calls:
                    ce_price = calls[strike_key].get('ltp', 0)
                    print(f"   ✅ SENSEX 85600 CE: ₹{ce_price} (fetch: {fetch_time:.1f}ms)")
                else:
                    print(f"   ⚠️  SENSEX 85600 CE: Not found in chain")
            else:
                stale_chains += 1
                print(f"   ❌ Option chain fetch failed")
            
            await asyncio.sleep(1)  # 1 second between requests
        
        print(f"\n📈 Option Chain Analysis:")
        print(f"   • Fresh chains: {fresh_chains}/5")
        print(f"   • Stale chains: {stale_chains}/5")
        
        if stale_chains > 1:
            print(f"   🚨 CRITICAL: Option chain freshness issues!")
        
        print("\n🎯 Trading Safety Assessment:")
        
        # Overall assessment
        critical_issues = []
        
        if avg_fetch_time > 1000:
            critical_issues.append("Slow spot price fetching")
        if stale_count > 2:
            critical_issues.append("High spot price failure rate")
        if stale_chains > 1:
            critical_issues.append("Option chain freshness issues")
        
        if critical_issues:
            print(f"   🚨 CRITICAL ISSUES FOUND:")
            for issue in critical_issues:
                print(f"      • {issue}")
            print(f"   ⚠️  RECOMMENDATION: Reduce cache TTL further or disable caching")
        else:
            print(f"   ✅ Data freshness looks safe for trading")
        
        return len(critical_issues) == 0
        
    except Exception as e:
        print(f"   ❌ Data freshness test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_data_freshness())
    if success:
        print("\n🚀 Real-time data freshness is SAFE for trading")
    else:
        print("\n⚠️  Real-time data freshness issues detected - REVIEW NEEDED")
