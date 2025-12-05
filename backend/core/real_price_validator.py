# Real Price Validation Module
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class RealPriceValidator:
    """
    Validates that option prices are real and fresh
    """
    
    def __init__(self):
        self.last_fetch_times = {}
        self.price_cache = {}
        self.max_cache_age = 30  # 30 seconds max cache age
    
    def validate_option_price(self, symbol: str, strike: float, direction: str, 
                            option_chain_data: Dict, current_time: datetime = None) -> tuple[bool, float, str]:
        """
        Validate option price is real and fresh
        
        Returns:
            (is_valid, price, validation_message)
        """
        if not current_time:
            current_time = datetime.now()
        
        # Get option data from chain
        options_dict = option_chain_data.get('calls' if direction == 'CALL' else 'puts', {})
        strike_key = str(int(strike))
        
        if strike_key not in options_dict:
            return False, 0.0, f"Strike {strike} not found in option chain"
        
        option_data = options_dict[strike_key]
        ltp = option_data.get('ltp', 0)
        bid = option_data.get('bid', 0)
        ask = option_data.get('ask', 0)
        
        # Basic validation
        if ltp <= 0:
            return False, 0.0, f"Invalid LTP: {ltp}"
        
        if bid <= 0 or ask <= 0:
            return False, ltp, f"Missing bid/ask: bid={bid}, ask={ask}"
        
        if bid > ask:
            return False, ltp, f"Bid > Ask: bid={bid}, ask={ask}"
        
        if ltp < bid or ltp > ask:
            # Allow some tolerance for LTP outside bid-ask
            tolerance = 0.05  # 5% tolerance
            if abs(ltp - bid) / bid > tolerance and abs(ltp - ask) / ask > tolerance:
                return False, ltp, f"LTP outside bid-ask: ltp={ltp}, bid={bid}, ask={ask}"
        
        # Check option chain freshness
        chain_timestamp = option_chain_data.get('timestamp')
        if chain_timestamp:
            if isinstance(chain_timestamp, str):
                try:
                    chain_timestamp = datetime.fromisoformat(chain_timestamp.replace('Z', '+00:00'))
                except:
                    chain_timestamp = current_time
        else:
            chain_timestamp = current_time
        
        age_seconds = (current_time - chain_timestamp).total_seconds()
        if age_seconds > self.max_cache_age:
            return False, ltp, f"Option chain too old: {age_seconds:.1f}s"
        
        return True, ltp, f"Valid price: ₹{ltp} (age: {age_seconds:.1f}s)"
    
    def log_price_validation(self, symbol: str, strike: float, direction: str, 
                           is_valid: bool, price: float, message: str):
        """Log price validation result"""
        if is_valid:
            logger.info(f"✅ Price validated: {symbol} {direction} {strike} @ ₹{price} - {message}")
        else:
            logger.error(f"❌ Price invalid: {symbol} {direction} {strike} @ ₹{price} - {message}")
