"""
Price History Tracker
Tracks prev_close and OHLC data for option chains using Upstox full market quote API
"""

from typing import Dict, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
from backend.core.logger import logger


class PriceHistoryTracker:
    """Tracks option price history for strategy analysis"""
    
    def __init__(self, upstox_client):
        self.upstox_client = upstox_client
        self.price_history = defaultdict(dict)  # {instrument_key: {timestamp: price_data}}
        self.prev_close_cache = {}  # {instrument_key: prev_close_price}
        self.last_fetch_time = {}
        self.fetch_interval = 30  # Fetch full quotes every 30 seconds
        
    async def update_option_prices(self, option_chain: Dict, symbol: str) -> Dict:
        """
        Update option chain with prev_close and OHLC data
        Returns enriched option chain with historical price data
        """
        try:
            # Collect all instrument keys
            instrument_keys = []
            
            for strike_data in option_chain.get('calls', {}).values():
                if 'instrument_key' in strike_data:
                    instrument_keys.append(strike_data['instrument_key'])
                    
            for strike_data in option_chain.get('puts', {}).values():
                if 'instrument_key' in strike_data:
                    instrument_keys.append(strike_data['instrument_key'])
            
            if not instrument_keys:
                return option_chain
            
            # Check if we need to fetch (rate limiting)
            now = datetime.now()
            cache_key = f"{symbol}_options"
            
            if cache_key in self.last_fetch_time:
                time_since_fetch = (now - self.last_fetch_time[cache_key]).total_seconds()
                if time_since_fetch < self.fetch_interval:
                    # Use cached data
                    return self._apply_cached_prices(option_chain)
            
            # Fetch full market quotes (batches of 100 instruments)
            batch_size = 100
            all_quotes = {}
            
            for i in range(0, len(instrument_keys), batch_size):
                batch = instrument_keys[i:i + batch_size]
                
                # Run in thread to avoid blocking
                quotes = await asyncio.to_thread(
                    self.upstox_client.get_full_market_quote,
                    batch
                )
                
                if quotes and 'data' in quotes:
                    all_quotes.update(quotes['data'])
            
            # Update cache and enrich option chain
            self.last_fetch_time[cache_key] = now
            return self._enrich_option_chain(option_chain, all_quotes)
            
        except Exception as e:
            logger.error(f"Error updating option prices: {e}")
            return option_chain
    
    def _enrich_option_chain(self, option_chain: Dict, quotes: Dict) -> Dict:
        """Add prev_close, OHLC to option chain from full market quotes"""
        
        enriched = option_chain.copy()
        
        # Enrich calls
        if 'calls' in enriched:
            for strike, data in enriched['calls'].items():
                instrument_key = data.get('instrument_key')
                if not instrument_key:
                    continue
                
                # Upstox returns keys with colon instead of pipe
                quote_key = instrument_key.replace('|', ':')
                quote = quotes.get(quote_key, {})
                
                ohlc = quote.get('ohlc', {})
                enriched['calls'][strike]['prev_close'] = ohlc.get('close', data.get('ltp', 0))
                enriched['calls'][strike]['open'] = ohlc.get('open', 0)
                enriched['calls'][strike]['high'] = ohlc.get('high', 0)
                enriched['calls'][strike]['low'] = ohlc.get('low', 0)
                
                # Cache for fast access
                self.prev_close_cache[instrument_key] = ohlc.get('close', data.get('ltp', 0))
        
        # Enrich puts
        if 'puts' in enriched:
            for strike, data in enriched['puts'].items():
                instrument_key = data.get('instrument_key')
                if not instrument_key:
                    continue
                
                quote_key = instrument_key.replace('|', ':')
                quote = quotes.get(quote_key, {})
                
                ohlc = quote.get('ohlc', {})
                enriched['puts'][strike]['prev_close'] = ohlc.get('close', data.get('ltp', 0))
                enriched['puts'][strike]['open'] = ohlc.get('open', 0)
                enriched['puts'][strike]['high'] = ohlc.get('high', 0)
                enriched['puts'][strike]['low'] = ohlc.get('low', 0)
                
                self.prev_close_cache[instrument_key] = ohlc.get('close', data.get('ltp', 0))
        
        return enriched
    
    def _apply_cached_prices(self, option_chain: Dict) -> Dict:
        """Apply cached prev_close prices to option chain"""
        enriched = option_chain.copy()
        
        # Apply to calls
        if 'calls' in enriched:
            for strike, data in enriched['calls'].items():
                instrument_key = data.get('instrument_key')
                if instrument_key in self.prev_close_cache:
                    enriched['calls'][strike]['prev_close'] = self.prev_close_cache[instrument_key]
        
        # Apply to puts
        if 'puts' in enriched:
            for strike, data in enriched['puts'].items():
                instrument_key = data.get('instrument_key')
                if instrument_key in self.prev_close_cache:
                    enriched['puts'][strike]['prev_close'] = self.prev_close_cache[instrument_key]
        
        return enriched
    
    def get_prev_close(self, instrument_key: str) -> Optional[float]:
        """Get cached prev_close for an instrument"""
        return self.prev_close_cache.get(instrument_key)
