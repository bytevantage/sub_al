"""
Redis Cache API Endpoints
Monitor cache performance and statistics
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from backend.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/cache", tags=["cache"])

@router.get("/status")
async def get_cache_status():
    """Get Redis cache status and performance metrics"""
    try:
        from backend.cache.redis_cache import get_cache_manager
        cache_manager = get_cache_manager()
        
        if not cache_manager.is_available():
            return {
                "status": "unavailable",
                "message": "Redis server not running - using in-memory cache only",
                "cache_type": "memory_only"
            }
        
        stats = cache_manager.get_cache_stats()
        return {
            "status": "available",
            "message": "Redis cache operational",
            "cache_type": "redis_memory_hybrid",
            **stats
        }
        
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clear")
async def clear_cache():
    """Clear all cached data (for maintenance purposes)"""
    try:
        from backend.cache.redis_cache import get_cache_manager
        cache_manager = get_cache_manager()
        
        if not cache_manager.is_available():
            raise HTTPException(
                status_code=503, 
                detail="Redis not available - cannot clear cache"
            )
        
        cache_manager.clear_cache()
        
        return {
            "status": "success",
            "message": "Cache cleared successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance")
async def get_cache_performance():
    """Get detailed cache performance metrics"""
    try:
        from backend.cache.redis_cache import get_cache_manager
        cache_manager = get_cache_manager()
        
        if not cache_manager.is_available():
            return {
                "status": "unavailable",
                "cache_hit_rate": 0.0,
                "memory_usage": "N/A",
                "recommendation": "Consider starting Redis server for better performance"
            }
        
        stats = cache_manager.get_cache_stats()
        
        # Add performance recommendations
        hit_rate = stats.get('hit_rate', 0)
        recommendation = "Cache performance is good"
        if hit_rate < 50:
            recommendation = "Consider increasing cache TTL for better hit rates"
        elif hit_rate > 90:
            recommendation = "Excellent cache performance"
        
        return {
            "status": "available",
            "cache_hit_rate": hit_rate,
            "memory_usage": stats.get('used_memory', 'N/A'),
            "connected_clients": stats.get('connected_clients', 0),
            "recommendation": recommendation,
            "total_requests": stats.get('keyspace_hits', 0) + stats.get('keyspace_misses', 0),
            "cache_hits": stats.get('keyspace_hits', 0),
            "cache_misses": stats.get('keyspace_misses', 0)
        }
        
    except Exception as e:
        logger.error(f"Error getting cache performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))
