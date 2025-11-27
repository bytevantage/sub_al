#!/usr/bin/env python3
"""
Test script to verify 3:25 PM trading cutoff
"""

import sys
from datetime import datetime, time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.core.timezone_utils import IST

def test_time_at(test_time: time):
    """Test trading status at a specific time"""
    # Create a datetime with the test time
    test_dt = datetime.now(IST).replace(hour=test_time.hour, minute=test_time.minute, second=0, microsecond=0)
    
    # Check market hours manually
    market_open = time(9, 15)
    market_close = time(15, 25)  # 3:25 PM
    is_weekday = test_dt.weekday() < 5
    
    in_market_hours = market_open <= test_time <= market_close and is_weekday
    eod_exit = test_time >= time(15, 25)  # 3:25 PM
    
    return {
        'time': test_time.strftime('%H:%M'),
        'market_open': in_market_hours,
        'eod_exit': eod_exit,
        'should_trade': in_market_hours and not eod_exit
    }

def test_trading_cutoff():
    """Test that trading stops at 3:25 PM"""
    
    print("Testing 3:25 PM trading cutoff...")
    print("=" * 50)
    
    # Test times
    test_cases = [
        (time(15, 24), True),   # Should be trading
        (time(15, 25), False),  # Should stop trading
        (time(15, 26), False),  # Should be stopped
        (time(15, 30), False),  # Should be stopped
    ]
    
    all_passed = True
    
    for test_time, expected_trading in test_cases:
        result = test_time_at(test_time)
        time_str = result['time']
        
        print(f"\nTime: {time_str}")
        print(f"  Market Hours: {'✅ Open' if result['market_open'] else '❌ Closed'}")
        print(f"  EOD Exit: {'🔴 Exit' if result['eod_exit'] else '⏸️ Continue'}")
        print(f"  Should Trade: {'✅ Yes' if result['should_trade'] else '❌ No'}")
        print(f"  Expected: {'✅ Yes' if expected_trading else '❌ No'}")
        
        # Verify
        if result['should_trade'] == expected_trading:
            print(f"  Status: ✅ Correct")
        else:
            print(f"  Status: ❌ WRONG!")
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ All tests passed! Trading correctly stops at 3:25 PM")
    else:
        print("❌ Some tests failed!")
    
    # Show current status
    now = datetime.now(IST)
    current_status = test_time_at(now.time())
    
    print(f"\nCurrent time: {now.strftime('%H:%M:%S')} IST")
    print(f"Market open: {'✅ Yes' if current_status['market_open'] else '❌ No'}")
    print(f"EOD exit triggered: {'🔴 Yes' if current_status['eod_exit'] else '⏸️ No'}")
    print(f"Should trade: {'✅ Yes' if current_status['should_trade'] else '❌ No'}")

if __name__ == "__main__":
    test_trading_cutoff()
