"""
Redis Cache Manager
Caches market data for performance improvement without changing data sources
Only caches existing spot prices and option chains - no new data
"""

import json
import os
import time
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import redis
from backend.core.logger import get_logger

logger = get_logger(__name__)

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class RedisCacheManager:
    """Redis caching for existing market data only"""
    
    def __init__(self, redis_url: str = None):
        self.redis_client = None
        # Use environment variable or construct from host/port
        if redis_url is None:
            redis_host = os.getenv('REDIS_HOST', 'localhost')
            redis_port = os.getenv('REDIS_PORT', '6379')
            redis_url = f"redis://{redis_host}:{redis_port}/0"
        
        self.redis_url = redis_url
        self._connect()
        
        # Cache TTL settings (BALANCED for trading safety + rate limiting)
        self.SPOT_PRICE_TTL = 5  # 5 seconds for spot prices (12 req/min per symbol - SAFE)
        self.OPTION_CHAIN_TTL = 10  # 10 seconds for option chains (6 req/min per symbol - SAFE)
        self.TECHNICAL_INDICATORS_TTL = 30  # 30 seconds for technical indicators (2 req/min per symbol - SAFE)
        
        logger.info("Redis Cache Manager initialized")
    
    def _connect(self):
        """Connect to Redis with fallback handling"""
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            logger.info("✓ Redis connection established")
        except Exception as e:
            logger.warning(f"Redis not available: {e}. Caching disabled.")
            self.redis_client = None
    
    def is_available(self) -> bool:
        """Check if Redis is available"""
        return self.redis_client is not None
    
    def get_spot_price(self, symbol: str) -> Optional[float]:
        """Get cached spot price for symbol"""
        if not self.is_available():
            return None
        
        try:
            key = f"spot:{symbol}"
            cached_data = self.redis_client.get(key)
            if cached_data:
                data = json.loads(cached_data)
                if time.time() - data['timestamp'] < self.SPOT_PRICE_TTL:
                    logger.debug(f"Cache hit: spot price for {symbol}")
                    return data['price']
                else:
                    # Expired data, remove it
                    self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Error getting cached spot price: {e}")
        
        return None
    
    def set_spot_price(self, symbol: str, price: float):
        """Cache spot price for symbol"""
        if not self.is_available():
            return
        
        try:
            key = f"spot:{symbol}"
            data = {
                'price': price,
                'timestamp': time.time(),
                'symbol': symbol
            }
            self.redis_client.setex(
                key, 
                self.SPOT_PRICE_TTL, 
                json.dumps(data, cls=DateTimeEncoder)
            )
            logger.debug(f"Cached spot price for {symbol}: {price}")
        except Exception as e:
            logger.error(f"Error caching spot price: {e}")
    
    def get_option_chain(self, symbol: str, expiry: str) -> Optional[Dict]:
        """Get cached option chain for symbol/expiry"""
        if not self.is_available():
            return None
        
        try:
            key = f"chain:{symbol}:{expiry}"
            cached_data = self.redis_client.get(key)
            if cached_data:
                data = json.loads(cached_data)
                if time.time() - data['timestamp'] < self.OPTION_CHAIN_TTL:
                    logger.debug(f"Cache hit: option chain for {symbol} {expiry}")
                    return data['chain']
                else:
                    # Expired data, remove it
                    self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Error getting cached option chain: {e}")
        
        return None
    
    def set_option_chain(self, symbol: str, expiry: str, chain: Dict):
        """Cache option chain for symbol/expiry"""
        if not self.is_available():
            return
        
        try:
            key = f"chain:{symbol}:{expiry}"
            data = {
                'chain': chain,
                'timestamp': time.time(),
                'symbol': symbol,
                'expiry': expiry
            }
            self.redis_client.setex(
                key,
                self.OPTION_CHAIN_TTL,
                json.dumps(data, cls=DateTimeEncoder)
            )
            logger.debug(f"Cached option chain for {symbol} {expiry}")
        except Exception as e:
            logger.error(f"Error caching option chain: {e}")
    
    def get_technical_indicators(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """Get cached technical indicators"""
        if not self.is_available():
            return None
        
        try:
            key = f"indicators:{symbol}:{timeframe}"
            cached_data = self.redis_client.get(key)
            if cached_data:
                data = json.loads(cached_data)
                if time.time() - data['timestamp'] < self.TECHNICAL_INDICATORS_TTL:
                    logger.debug(f"Cache hit: indicators for {symbol} {timeframe}")
                    return data['indicators']
                else:
                    # Expired data, remove it
                    self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Error getting cached indicators: {e}")
        
        return None
    
    def set_technical_indicators(self, symbol: str, timeframe: str, indicators: Dict):
        """Cache technical indicators"""
        if not self.is_available():
            return
        
        try:
            key = f"indicators:{symbol}:{timeframe}"
            data = {
                'indicators': indicators,
                'timestamp': time.time(),
                'symbol': symbol,
                'timeframe': timeframe
            }
            self.redis_client.setex(
                key,
                self.TECHNICAL_INDICATORS_TTL,
                json.dumps(data, cls=DateTimeEncoder)
            )
            logger.debug(f"Cached indicators for {symbol} {timeframe}")
        except Exception as e:
            logger.error(f"Error caching indicators: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring"""
        if not self.is_available():
            return {"status": "unavailable"}
        
        try:
            info = self.redis_client.info()
            return {
                "status": "available",
                "used_memory": info.get('used_memory_human', 'N/A'),
                "connected_clients": info.get('connected_clients', 0),
                "keyspace_hits": info.get('keyspace_hits', 0),
                "keyspace_misses": info.get('keyspace_misses', 0),
                "hit_rate": self._calculate_hit_rate(info)
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"status": "error", "error": str(e)}
    
    def _calculate_hit_rate(self, info: Dict) -> float:
        """Calculate cache hit rate"""
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0
    
    def clear_cache(self):
        """Clear all cached data (for debugging/maintenance)"""
        if not self.is_available():
            return
        
        try:
            # Clear only our keys, not entire Redis
            patterns = ["spot:*", "chain:*", "indicators:*"]
            for pattern in patterns:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            logger.info("Cache cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

# Global instance
_cache_manager = None

def get_cache_manager() -> RedisCacheManager:
    """Get global cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = RedisCacheManager()
    return _cache_manager
